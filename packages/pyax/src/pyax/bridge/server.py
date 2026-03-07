"""
PyAx Assistant Bridge Server

WebSocket server that bridges pyax accessibility to the SwiftUI frontend and AI agents.

Provides two modes of interaction:
  1. **Event streaming** (passive) — observes AX events and pushes them to clients
  2. **Command protocol** (active) — clients request UI snapshots, element queries,
     and perform actions (click, type, etc.)

Architecture:
  - Main thread: runs CFRunLoop (required by pyax observers + macOS accessibility)
    - Also processes incoming commands from the command_queue
  - Background thread: runs asyncio event loop with WebSocket server
  - Thread-safe queues bridge between threads:
    - event_queue: main thread → WebSocket (events + command results)
    - command_queue: WebSocket → main thread (commands to execute)
"""

from __future__ import annotations

import asyncio
import json
import signal
import socket
import sys
import threading
import traceback
import uuid
from datetime import datetime
from queue import Queue, Empty

import websockets
import pyax

from Quartz import (
    CFRunLoopGetCurrent,
    CFRunLoopRun,
    CFRunLoopStop,
    CFRunLoopTimerCreate,
    CFRunLoopAddTimer,
    kCFRunLoopDefaultMode,
    CFAbsoluteTimeGetCurrent,
    kCFAllocatorDefault,
)

# --- Configuration ---
HOST = "localhost"
PORT = 8765
FOCUS_POLL_INTERVAL = 0.5
COMMAND_POLL_INTERVAL = 0.05  # Check for commands every 50ms

# Thread-safe queues
event_queue = Queue()  # main thread → WebSocket thread (events + responses)
command_queue = Queue()  # WebSocket thread → main thread (commands to execute)


# =============================================================================
# Accessibility element serialization
# =============================================================================


def _safe_str(val):
    """Safely convert a value to string, handling None and complex types."""
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    try:
        return str(val)
    except Exception:
        return "<unreadable>"


def _serialize_element(element, depth=0, max_depth=10, include_actions=False):
    """
    Serialize an AXUIElement to a JSON-friendly dict.
    Recursively includes children up to max_depth.
    """
    if element is None:
        return None

    node = {}

    # Core attributes every agent needs
    for attr in [
        "AXRole",
        "AXRoleDescription",
        "AXTitle",
        "AXDescription",
        "AXValue",
        "AXIdentifier",
        "AXDOMIdentifier",
        "AXEnabled",
        "AXFocused",
        "AXSelected",
    ]:
        try:
            val = element[attr]
            if val is not None:
                node[attr] = _safe_str(val)
        except Exception:
            pass

    # Position and size (for coordinate-based interaction)
    try:
        frame = element["AXFrame"]
        if frame is not None:
            try:
                node["AXFrame"] = frame.to_dict()
            except Exception:
                node["AXFrame"] = _safe_str(frame)
    except Exception:
        pass

    try:
        pos = element["AXPosition"]
        if pos is not None:
            try:
                node["AXPosition"] = pos.to_dict()
            except Exception:
                pass
    except Exception:
        pass

    try:
        size = element["AXSize"]
        if size is not None:
            try:
                node["AXSize"] = size.to_dict()
            except Exception:
                pass
    except Exception:
        pass

    # Available actions (so the agent knows what it can do)
    if include_actions:
        try:
            actions = element.actions
            if actions:
                node["actions"] = actions
        except Exception:
            pass

    # Settable attributes (so the agent knows what it can change)
    if include_actions:
        settable = []
        for attr in ["AXValue", "AXFocused", "AXSelected"]:
            try:
                if element.is_attribute_settable(attr):
                    settable.append(attr)
            except Exception:
                pass
        if settable:
            node["settable"] = settable

    # Children (recursive)
    if depth < max_depth:
        try:
            children = element["AXChildren"]
            if children:
                child_list = []
                for child in children:
                    serialized = _serialize_element(
                        child, depth + 1, max_depth, include_actions
                    )
                    if serialized:
                        child_list.append(serialized)
                if child_list:
                    node["children"] = child_list
        except Exception:
            pass

    return node


def _find_element_by_path(root, path):
    """
    Navigate to a child element by index path.
    path is a list of child indices, e.g. [0, 2, 1] means:
    root -> children[0] -> children[2] -> children[1]
    """
    current = root
    for idx in path:
        try:
            children = current["AXChildren"]
            if children is None or idx >= len(children):
                return None
            current = children[idx]
        except Exception:
            return None
    return current


def _find_element_by_criteria(root, criteria, max_results=10):
    """
    Find elements matching criteria (role, title, value, identifier).
    Returns a list of (element, path) tuples.
    """
    results = []

    def _match(element, c):
        for key, val in c.items():
            attr_map = {
                "role": "AXRole",
                "title": "AXTitle",
                "value": "AXValue",
                "identifier": "AXIdentifier",
                "description": "AXDescription",
                "dom_id": "AXDOMIdentifier",
            }
            ax_attr = attr_map.get(key)
            if ax_attr is None:
                continue
            try:
                elem_val = element[ax_attr]
                if elem_val is None:
                    return False
                elem_str = str(elem_val)
                if val.startswith("*") and val.endswith("*"):
                    # Contains match
                    if val[1:-1].lower() not in elem_str.lower():
                        return False
                elif val.startswith("*"):
                    # Ends-with match
                    if not elem_str.lower().endswith(val[1:].lower()):
                        return False
                elif val.endswith("*"):
                    # Starts-with match
                    if not elem_str.lower().startswith(val[:-1].lower()):
                        return False
                else:
                    # Exact match (case-insensitive)
                    if elem_str.lower() != val.lower():
                        return False
            except Exception:
                return False
        return True

    def _search(element, path):
        if len(results) >= max_results:
            return
        if _match(element, criteria):
            results.append((element, list(path)))
        try:
            children = element["AXChildren"]
            if children:
                for i, child in enumerate(children):
                    _search(child, path + [i])
        except Exception:
            pass

    _search(root, [])
    return results


# =============================================================================
# Focused app tracker
# =============================================================================


class FocusedAppTracker:
    """Tracks the currently focused macOS application."""

    def __init__(self):
        self._current_app_name = None
        self._current_pid = None

    def get_focused_app(self):
        """Return (app_name, pid) of the currently focused application."""
        try:
            from AppKit import NSWorkspace

            active_app = NSWorkspace.sharedWorkspace().frontmostApplication()
            if active_app is None:
                return None, None
            name = active_app.localizedName()
            pid = active_app.processIdentifier()
            return name, pid
        except Exception:
            return None, None

    @property
    def current_app_name(self):
        return self._current_app_name

    @property
    def current_pid(self):
        return self._current_pid

    def update(self):
        """Check for focused app change. Returns True if changed."""
        name, pid = self.get_focused_app()
        # Ignore our own app and only switch when PID actually changes
        if pid != self._current_pid and name != "PyAxAssistant":
            self._current_app_name = name
            self._current_pid = pid
            return True
        return False


# =============================================================================
# Observer + Command manager (main thread)
# =============================================================================


class ObserverManager:
    """
    Manages pyax observers and processes commands on the main thread (CFRunLoop).
    Uses CFRunLoopTimers for periodic focus polling and command processing.
    Pushes events/responses into the thread-safe event_queue.
    """

    def __init__(self):
        self.tracker = FocusedAppTracker()
        self._observer = None
        self._main_runloop = None
        self._callback_ref = None  # prevent GC of callback
        self._app_element = None  # pyax AXUIElement for the focused app

    def notification_callback(self, observer, element, notification, info):
        """Called by pyax when an accessibility event fires (on main thread).
        Serializes the full element tree (depth 1) with attributes and actions,
        like `pyax observe` does."""
        try:
            element_data = (
                _serialize_element(element, depth=0, max_depth=1, include_actions=True)
                if element is not None
                else None
            )

            event = {
                "type": "event",
                "app": self.tracker.current_app_name or "Unknown",
                "notification": str(notification),
                "element": element_data,
                "timestamp": datetime.now().isoformat(),
            }
            event_queue.put_nowait(event)
        except Exception as e:
            print(f"[bridge] Callback error: {e}", flush=True)

    def start_observer_for_pid(self, pid):
        """Create a pyax observer attached to the main thread's CFRunLoop."""
        self.stop_observer()

        try:
            # Get the app element for command handling
            self._app_element = pyax.get_application_from_pid(pid)

            # Keep a strong ref to the callback to prevent garbage collection
            self._callback_ref = self.notification_callback

            observer = pyax.create_observer(pid, self._callback_ref)
            if observer is None:
                print(f"[bridge] Failed to create observer for PID {pid}", flush=True)
                return

            # Register for all known accessibility events
            events_added = 0
            for event_name in pyax.EVENTS:
                try:
                    observer.add_notifications(event_name)
                    events_added += 1
                except Exception as e:
                    print(f"[bridge] Could not add {event_name}: {e}", flush=True)

            self._observer = observer
            print(
                f"[bridge] Observer started for PID {pid} ({events_added} events registered)",
                flush=True,
            )
        except Exception as e:
            print(f"[bridge] Error starting observer: {e}", flush=True)

    def stop_observer(self):
        """Stop the current observer."""
        if self._observer is not None:
            print("[bridge] Stopping previous observer", flush=True)
        self._observer = None
        self._callback_ref = None
        self._app_element = None

    # ----- Command handlers (run on main thread) -----

    def _handle_command(self, cmd):
        """
        Process a command dict and return a response dict.
        All accessibility API calls happen here on the main thread.
        """
        cmd_type = cmd.get("command")
        request_id = cmd.get("id", str(uuid.uuid4()))

        try:
            if cmd_type == "get_tree":
                return self._cmd_get_tree(cmd, request_id)
            elif cmd_type == "find_elements":
                return self._cmd_find_elements(cmd, request_id)
            elif cmd_type == "get_element":
                return self._cmd_get_element(cmd, request_id)
            elif cmd_type == "perform_action":
                return self._cmd_perform_action(cmd, request_id)
            elif cmd_type == "set_attribute":
                return self._cmd_set_attribute(cmd, request_id)
            elif cmd_type == "get_element_at_position":
                return self._cmd_get_element_at_position(cmd, request_id)
            elif cmd_type == "get_focused_element":
                return self._cmd_get_focused_element(cmd, request_id)
            elif cmd_type == "get_app_info":
                return self._cmd_get_app_info(cmd, request_id)
            elif cmd_type == "list_all_windows":
                return self._cmd_list_all_windows(cmd, request_id)
            else:
                return {
                    "type": "response",
                    "id": request_id,
                    "error": f"Unknown command: {cmd_type}",
                }
        except Exception as e:
            print(f"[bridge] Command error ({cmd_type}): {e}", flush=True)
            traceback.print_exc()
            return {
                "type": "response",
                "id": request_id,
                "error": str(e),
            }

    def _cmd_get_tree(self, cmd, request_id):
        """
        Get the full UI tree of the focused app.
        Options:
          - depth: max depth (default 5)
          - include_actions: include available actions on each node (default true)
        """
        if self._app_element is None:
            return {"type": "response", "id": request_id, "error": "No app focused"}

        depth = cmd.get("depth", 5)
        include_actions = cmd.get("include_actions", True)

        tree = _serialize_element(
            self._app_element,
            depth=0,
            max_depth=depth,
            include_actions=include_actions,
        )

        return {
            "type": "response",
            "id": request_id,
            "command": "get_tree",
            "app": self.tracker.current_app_name,
            "pid": self.tracker.current_pid,
            "tree": tree,
            "timestamp": datetime.now().isoformat(),
        }

    def _cmd_find_elements(self, cmd, request_id):
        """
        Find elements matching search criteria in the focused app's UI tree.
        Criteria can include: role, title, value, identifier, description, dom_id
        Values support wildcards: "Save*", "*button*", "*Cancel"
        """
        if self._app_element is None:
            return {"type": "response", "id": request_id, "error": "No app focused"}

        criteria = cmd.get("criteria", {})
        max_results = cmd.get("max_results", 10)
        include_actions = cmd.get("include_actions", True)

        if not criteria:
            return {
                "type": "response",
                "id": request_id,
                "error": "No criteria provided",
            }

        matches = _find_element_by_criteria(
            self._app_element, criteria, max_results=max_results
        )

        results = []
        for element, path in matches:
            node = _serialize_element(
                element, depth=0, max_depth=0, include_actions=include_actions
            )
            node["_path"] = path
            results.append(node)

        return {
            "type": "response",
            "id": request_id,
            "command": "find_elements",
            "app": self.tracker.current_app_name,
            "results": results,
            "count": len(results),
            "timestamp": datetime.now().isoformat(),
        }

    def _cmd_get_element(self, cmd, request_id):
        """
        Get detailed info about an element by its path (child index path from root).
        Options:
          - path: list of child indices, e.g. [0, 2, 1]
          - depth: how deep to recurse children of this element (default 1)
          - include_actions: include available actions (default true)
        """
        if self._app_element is None:
            return {"type": "response", "id": request_id, "error": "No app focused"}

        path = cmd.get("path", [])
        depth = cmd.get("depth", 1)
        include_actions = cmd.get("include_actions", True)

        element = _find_element_by_path(self._app_element, path)
        if element is None:
            return {
                "type": "response",
                "id": request_id,
                "error": f"No element at path {path}",
            }

        node = _serialize_element(
            element, depth=0, max_depth=depth, include_actions=include_actions
        )

        return {
            "type": "response",
            "id": request_id,
            "command": "get_element",
            "path": path,
            "element": node,
            "timestamp": datetime.now().isoformat(),
        }

    def _cmd_perform_action(self, cmd, request_id):
        """
        Perform an action on an element.
        Requires:
          - path: child index path to the element, OR
          - criteria: search criteria to find the element
          - action: action name (e.g. "AXPress", "AXShowMenu", "AXConfirm")
        """
        if self._app_element is None:
            return {"type": "response", "id": request_id, "error": "No app focused"}

        action = cmd.get("action")
        if not action:
            return {
                "type": "response",
                "id": request_id,
                "error": "No action specified",
            }

        element = self._resolve_element(cmd)
        if element is None:
            return {
                "type": "response",
                "id": request_id,
                "error": "Could not find target element",
            }

        # Verify the action is available
        try:
            available = element.actions
            if action not in available:
                return {
                    "type": "response",
                    "id": request_id,
                    "error": f"Action '{action}' not available. Available: {available}",
                }
        except Exception:
            pass  # Proceed anyway; some elements don't list actions properly

        result = element.perform_action(action)
        print(f"[bridge] Performed {action} on {element}", flush=True)

        return {
            "type": "response",
            "id": request_id,
            "command": "perform_action",
            "action": action,
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }

    def _cmd_set_attribute(self, cmd, request_id):
        """
        Set an attribute value on an element (e.g. type into a text field).
        Requires:
          - path or criteria: to locate the element
          - attribute: attribute name (e.g. "AXValue", "AXFocused")
          - value: the new value
        """
        if self._app_element is None:
            return {"type": "response", "id": request_id, "error": "No app focused"}

        attribute = cmd.get("attribute")
        value = cmd.get("value")
        if not attribute:
            return {
                "type": "response",
                "id": request_id,
                "error": "No attribute specified",
            }

        element = self._resolve_element(cmd)
        if element is None:
            return {
                "type": "response",
                "id": request_id,
                "error": "Could not find target element",
            }

        # Check if settable
        try:
            if not element.is_attribute_settable(attribute):
                return {
                    "type": "response",
                    "id": request_id,
                    "error": f"Attribute '{attribute}' is not settable on this element",
                }
        except Exception:
            pass  # Try anyway

        element[attribute] = value
        print(f"[bridge] Set {attribute}={repr(value)} on {element}", flush=True)

        return {
            "type": "response",
            "id": request_id,
            "command": "set_attribute",
            "attribute": attribute,
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }

    def _cmd_get_element_at_position(self, cmd, request_id):
        """
        Get the element at a specific screen position (x, y).
        """
        if self._app_element is None:
            return {"type": "response", "id": request_id, "error": "No app focused"}

        x = cmd.get("x")
        y = cmd.get("y")
        if x is None or y is None:
            return {
                "type": "response",
                "id": request_id,
                "error": "x and y are required",
            }

        element = pyax.get_element_at_position(self._app_element, float(x), float(y))
        if element is None:
            return {
                "type": "response",
                "id": request_id,
                "error": f"No element at ({x}, {y})",
            }

        node = _serialize_element(element, depth=0, max_depth=0, include_actions=True)

        return {
            "type": "response",
            "id": request_id,
            "command": "get_element_at_position",
            "x": x,
            "y": y,
            "element": node,
            "timestamp": datetime.now().isoformat(),
        }

    def _cmd_get_focused_element(self, cmd, request_id):
        """Get the currently focused UI element."""
        if self._app_element is None:
            return {"type": "response", "id": request_id, "error": "No app focused"}

        try:
            focused = self._app_element["AXFocusedUIElement"]
            if focused is None:
                return {
                    "type": "response",
                    "id": request_id,
                    "error": "No focused element",
                }

            depth = cmd.get("depth", 0)
            node = _serialize_element(
                focused, depth=0, max_depth=depth, include_actions=True
            )

            return {
                "type": "response",
                "id": request_id,
                "command": "get_focused_element",
                "element": node,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"type": "response", "id": request_id, "error": str(e)}

    def _cmd_get_app_info(self, cmd, request_id):
        """Get info about the focused app (windows, menu bar, etc.)."""
        if self._app_element is None:
            return {"type": "response", "id": request_id, "error": "No app focused"}

        info = {
            "app": self.tracker.current_app_name,
            "pid": self.tracker.current_pid,
        }

        # Get windows
        try:
            windows = self._app_element["AXWindows"]
            if windows:
                info["windows"] = []
                for win in windows:
                    w = {}
                    for attr in [
                        "AXTitle",
                        "AXRole",
                        "AXFrame",
                        "AXMain",
                        "AXMinimized",
                    ]:
                        try:
                            val = win[attr]
                            if val is not None:
                                if attr == "AXFrame":
                                    try:
                                        w[attr] = val.to_dict()
                                    except Exception:
                                        w[attr] = _safe_str(val)
                                else:
                                    w[attr] = _safe_str(val)
                        except Exception:
                            pass
                    info["windows"].append(w)
        except Exception:
            pass

        # Get menu bar items (top-level)
        try:
            menu_bar = self._app_element["AXMenuBar"]
            if menu_bar:
                menus = menu_bar["AXChildren"]
                if menus:
                    info["menu_bar"] = [
                        _safe_str(m["AXTitle"]) for m in menus if m["AXTitle"]
                    ]
        except Exception:
            pass

        return {
            "type": "response",
            "id": request_id,
            "command": "get_app_info",
            **info,
            "timestamp": datetime.now().isoformat(),
        }

    def _cmd_list_all_windows(self, cmd, request_id):
        """List windows from ALL running applications, not just the focused one."""
        try:
            from AppKit import NSWorkspace

            running_apps = NSWorkspace.sharedWorkspace().runningApplications()

            all_windows = []
            for app in running_apps:
                app_name = app.localizedName()
                pid = app.processIdentifier()
                if not app_name or pid <= 0:
                    continue

                try:
                    app_element = pyax.get_application_from_pid(pid)
                    if app_element is None:
                        continue
                    windows = app_element["AXWindows"]
                    if not windows:
                        continue
                    for win in windows:
                        w = {"app": app_name, "pid": pid}
                        for attr in [
                            "AXTitle",
                            "AXRole",
                            "AXFrame",
                            "AXMain",
                            "AXMinimized",
                        ]:
                            try:
                                val = win[attr]
                                if val is not None:
                                    if attr == "AXFrame":
                                        try:
                                            w[attr] = val.to_dict()
                                        except Exception:
                                            w[attr] = _safe_str(val)
                                    else:
                                        w[attr] = _safe_str(val)
                            except Exception:
                                pass
                        # Only include windows that have a title or are main
                        if w.get("AXTitle") or w.get("AXMain"):
                            all_windows.append(w)
                except Exception:
                    # Skip apps we can't access (no AX permissions, etc.)
                    continue

            return {
                "type": "response",
                "id": request_id,
                "command": "list_all_windows",
                "windows": all_windows,
                "count": len(all_windows),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "type": "response",
                "id": request_id,
                "error": str(e),
            }

    def _resolve_element(self, cmd):
        """Resolve a target element from a command — by path or by criteria."""
        if "path" in cmd:
            return _find_element_by_path(self._app_element, cmd["path"])
        elif "criteria" in cmd:
            matches = _find_element_by_criteria(
                self._app_element, cmd["criteria"], max_results=1
            )
            if matches:
                return matches[0][0]
        return None

    # ----- CFRunLoop callbacks -----

    def poll_focus(self, timer, info):
        """CFRunLoop timer callback — checks for focused app changes."""
        changed = self.tracker.update()
        if changed and self.tracker.current_pid is not None:
            app_name = self.tracker.current_app_name
            pid = self.tracker.current_pid
            print(f"[bridge] Focus changed: {app_name} (PID {pid})", flush=True)

            event_queue.put_nowait(
                {
                    "type": "app_changed",
                    "app": app_name,
                    "pid": pid,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            self.start_observer_for_pid(pid)

    def process_commands(self, timer, info):
        """CFRunLoop timer callback — processes pending commands from WebSocket thread."""
        # Process up to 10 commands per tick to avoid blocking the run loop
        for _ in range(10):
            try:
                cmd = command_queue.get_nowait()
                response = self._handle_command(cmd)
                event_queue.put_nowait(response)
            except Empty:
                break
            except Exception as e:
                print(f"[bridge] Command processing error: {e}", flush=True)

    def run(self):
        """Run the CFRunLoop on the main thread with timers for focus polling and command processing."""
        self._main_runloop = CFRunLoopGetCurrent()

        # Timer for focus polling (every 0.5s)
        focus_timer = CFRunLoopTimerCreate(
            kCFAllocatorDefault,
            CFAbsoluteTimeGetCurrent() + FOCUS_POLL_INTERVAL,
            FOCUS_POLL_INTERVAL,
            0,
            0,
            self.poll_focus,
            None,
        )
        CFRunLoopAddTimer(self._main_runloop, focus_timer, kCFRunLoopDefaultMode)

        # Timer for command processing (every 50ms)
        cmd_timer = CFRunLoopTimerCreate(
            kCFAllocatorDefault,
            CFAbsoluteTimeGetCurrent() + COMMAND_POLL_INTERVAL,
            COMMAND_POLL_INTERVAL,
            0,
            0,
            self.process_commands,
            None,
        )
        CFRunLoopAddTimer(self._main_runloop, cmd_timer, kCFRunLoopDefaultMode)

        print(
            "[bridge] CFRunLoop running on main thread (events + commands)", flush=True
        )
        CFRunLoopRun()

    def stop(self):
        """Stop the CFRunLoop."""
        self.stop_observer()
        if self._main_runloop:
            CFRunLoopStop(self._main_runloop)


# =============================================================================
# WebSocket server — runs in a background thread with its own asyncio loop
# =============================================================================


class WebSocketServer:
    """Async WebSocket server that broadcasts events and handles commands."""

    def __init__(self):
        self.clients = set()
        # Map request IDs to specific client websockets for targeted responses
        self._pending_requests = {}  # type: dict[str, websocket]

    async def register(self, websocket):
        self.clients.add(websocket)
        print(f"[bridge] Client connected ({len(self.clients)} total)", flush=True)

    async def unregister(self, websocket):
        self.clients.discard(websocket)
        # Clean up any pending requests for this client
        to_remove = [k for k, v in self._pending_requests.items() if v is websocket]
        for k in to_remove:
            del self._pending_requests[k]
        print(f"[bridge] Client disconnected ({len(self.clients)} total)", flush=True)

    async def broadcast(self, message):
        """Broadcast an event to all connected clients."""
        if not self.clients:
            return
        data = json.dumps(message, default=str)
        disconnected = set()
        for client in self.clients:
            try:
                await client.send(data)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
        self.clients -= disconnected

    async def send_to_client(self, websocket, message):
        """Send a response to a specific client."""
        try:
            data = json.dumps(message, default=str)
            await websocket.send(data)
        except websockets.exceptions.ConnectionClosed:
            pass

    async def handle_client(self, websocket):
        await self.register(websocket)
        try:
            async for message in websocket:
                try:
                    cmd = json.loads(message)
                    msg_type = cmd.get("type")

                    if msg_type == "ping":
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "pong",
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )
                        )
                    elif msg_type == "command":
                        # Forward command to main thread for execution
                        request_id = cmd.get("id", str(uuid.uuid4()))
                        cmd["id"] = request_id
                        self._pending_requests[request_id] = websocket
                        command_queue.put_nowait(cmd)
                        print(
                            f"[bridge] Command queued: {cmd.get('command')} (id={request_id})",
                            flush=True,
                        )
                    else:
                        print(
                            f"[bridge] Unknown message type from client: {msg_type}",
                            flush=True,
                        )

                except json.JSONDecodeError:
                    pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)

    async def event_pump(self):
        """Pull events/responses from the thread-safe queue and dispatch them."""
        while True:
            try:
                message = event_queue.get_nowait()

                if message.get("type") == "response":
                    # Targeted response — send to the requesting client
                    request_id = message.get("id")
                    client = self._pending_requests.pop(request_id, None)
                    if client:
                        await self.send_to_client(client, message)
                    else:
                        # Fallback: broadcast if we lost track of the client
                        await self.broadcast(message)
                else:
                    # Event — broadcast to all clients
                    await self.broadcast(message)
            except Empty:
                await asyncio.sleep(0.05)
            except Exception as e:
                print(f"[bridge] Event pump error: {e}", flush=True)
                await asyncio.sleep(0.1)

    async def serve(self):
        print(f"[bridge] WebSocket listening on ws://{HOST}:{PORT}", flush=True)
        # SO_REUSEADDR allows immediate rebind after restart (avoids TIME_WAIT)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass  # SO_REUSEPORT not available on all platforms
        sock.bind((HOST, PORT))
        sock.listen()
        sock.setblocking(False)
        async with websockets.serve(self.handle_client, sock=sock):
            await self.event_pump()


def _run_websocket_thread():
    """Entry point for the WebSocket background thread."""
    server = WebSocketServer()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(server.serve())
    except Exception as e:
        print(f"[bridge] WebSocket thread error: {e}", flush=True)
    finally:
        loop.close()


# =============================================================================
# Entry points
# =============================================================================


def _set_background_only():
    """
    Mark this process as a background-only agent so it doesn't appear
    in the Dock, app switcher, or steal focus from the observed app.
    Must be called before CFRunLoopRun.
    """
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyProhibited

        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyProhibited)
        print("[bridge] Set activation policy to background-only", flush=True)
    except Exception as e:
        print(f"[bridge] Warning: Could not set background policy: {e}", flush=True)


def run():
    """Main entry — starts WebSocket thread, then runs CFRunLoop on main thread."""
    # Prevent this process from appearing as a GUI app (Dock, app switcher)
    _set_background_only()

    print("[bridge] Starting PyAx Assistant Bridge", flush=True)
    print(
        "[bridge] Commands: get_tree, find_elements, get_element, perform_action,",
        flush=True,
    )
    print(
        "[bridge]           set_attribute, get_element_at_position, get_focused_element, get_app_info",
        flush=True,
    )

    # Start WebSocket server in a daemon thread
    ws_thread = threading.Thread(target=_run_websocket_thread, daemon=True)
    ws_thread.start()

    # Prepare the observer manager (runs on main thread)
    mgr = ObserverManager()

    def shutdown(signum, frame):
        print("\n[bridge] Shutting down...", flush=True)
        mgr.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Block main thread on CFRunLoop (required for accessibility observers)
    mgr.run()
    print("[bridge] Bridge stopped", flush=True)


async def main():
    """Async wrapper for compatibility with bridge __init__.py."""
    run()


if __name__ == "__main__":
    run()
