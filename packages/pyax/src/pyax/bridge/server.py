"""
PyAx Assistant Bridge Server

WebSocket server that bridges pyax accessibility events to the SwiftUI frontend.
Automatically detects the focused application and streams accessibility events as JSON.

Architecture:
  - Main thread: runs CFRunLoop (required by pyax observers + macOS accessibility)
  - Background thread: runs asyncio event loop with WebSocket server
  - Thread-safe queue bridges events from main thread → asyncio/WebSocket thread
"""

from __future__ import annotations

import asyncio
import json
import signal
import sys
import threading
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

# Thread-safe queue: main thread pushes events, WebSocket thread consumes them
event_queue = Queue()


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


class ObserverManager:
    """
    Manages pyax observers on the main thread (CFRunLoop).
    Uses a CFRunLoopTimer for periodic focus polling.
    Pushes events into the thread-safe queue.
    """

    def __init__(self):
        self.tracker = FocusedAppTracker()
        self._observer = None
        self._main_runloop = None
        self._callback_ref = None  # prevent GC of callback

    def notification_callback(self, observer, element, notification, info):
        """Called by pyax when an accessibility event fires (on main thread)."""
        try:
            role = None
            title = None
            value = None

            if element is not None:
                try:
                    role = element["AXRole"]
                except Exception:
                    pass
                try:
                    title = element["AXTitle"]
                except Exception:
                    pass
                try:
                    value = element["AXValue"]
                    if value is not None and not isinstance(
                        value, (str, int, float, bool)
                    ):
                        value = str(value)
                except Exception:
                    pass

            event = {
                "type": "event",
                "app": self.tracker.current_app_name or "Unknown",
                "notification": str(notification),
                "element": {
                    "role": str(role) if role else None,
                    "title": str(title) if title else None,
                    "value": str(value) if value else None,
                },
                "timestamp": datetime.now().isoformat(),
            }
            event_queue.put_nowait(event)
        except Exception as e:
            print(f"[bridge] Callback error: {e}", flush=True)

    def start_observer_for_pid(self, pid):
        """Create a pyax observer attached to the main thread's CFRunLoop."""
        self.stop_observer()

        try:
            # Keep a strong ref to the callback to prevent garbage collection
            self._callback_ref = self.notification_callback

            # Don't pass cfrunloop — we're already on the main thread,
            # so CFRunLoopGetCurrent() inside create_observer will use
            # the main run loop automatically.
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

    def run(self):
        """Run the CFRunLoop on the main thread with a focus-polling timer."""
        self._main_runloop = CFRunLoopGetCurrent()

        timer = CFRunLoopTimerCreate(
            kCFAllocatorDefault,
            CFAbsoluteTimeGetCurrent() + FOCUS_POLL_INTERVAL,
            FOCUS_POLL_INTERVAL,
            0,
            0,
            self.poll_focus,
            None,
        )
        CFRunLoopAddTimer(self._main_runloop, timer, kCFRunLoopDefaultMode)

        print("[bridge] CFRunLoop running on main thread", flush=True)
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
    """Async WebSocket server that broadcasts events from the queue to clients."""

    def __init__(self):
        self.clients = set()

    async def register(self, websocket):
        self.clients.add(websocket)
        print(f"[bridge] Client connected ({len(self.clients)} total)", flush=True)

    async def unregister(self, websocket):
        self.clients.discard(websocket)
        print(f"[bridge] Client disconnected ({len(self.clients)} total)", flush=True)

    async def broadcast(self, message):
        if not self.clients:
            return
        data = json.dumps(message)
        disconnected = set()
        for client in self.clients:
            try:
                await client.send(data)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
        self.clients -= disconnected

    async def handle_client(self, websocket):
        await self.register(websocket)
        try:
            async for message in websocket:
                try:
                    cmd = json.loads(message)
                    if cmd.get("type") == "ping":
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "pong",
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )
                        )
                except json.JSONDecodeError:
                    pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)

    async def event_pump(self):
        """Pull events from the thread-safe queue and broadcast to WebSocket clients."""
        while True:
            try:
                event = event_queue.get_nowait()
                await self.broadcast(event)
            except Empty:
                await asyncio.sleep(0.05)
            except Exception as e:
                print(f"[bridge] Event pump error: {e}", flush=True)
                await asyncio.sleep(0.1)

    async def serve(self):
        print(f"[bridge] WebSocket listening on ws://{HOST}:{PORT}", flush=True)
        async with websockets.serve(self.handle_client, HOST, PORT):
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


def run():
    """Main entry — starts WebSocket thread, then runs CFRunLoop on main thread."""
    print("[bridge] Starting PyAx Assistant Bridge", flush=True)

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
