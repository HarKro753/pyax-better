You are a senior developer working on pyax — a macOS Accessibility API toolkit.
The project is a monorepo with a Python library, an AI agent, and a Swift macOS companion app.

For Swift and SwiftUI coding rules, load the `swift-rules` skill.

## Project Context

pyax wraps Apple's low-level AXUIElement C API (via pyobjc) into a Pythonic interface.
It provides a CLI tool for inspecting UI trees and observing accessibility events,
plus a WebSocket bridge server that enables the Swift companion app (and AI agents)
to programmatically query and interact with any macOS application's UI.

The AI agent (pyax-agent) sits on top of the bridge and uses the Claude Agent SDK
to provide natural-language accessibility assistance to disabled users.

The Swift companion app (PyAxAssistant) is a floating overlay panel that connects
to the agent, displays event streams, and exposes a chat interface.

## Repository Structure

```
pyax-better/
├── AGENTS.md
├── SPEC.md                        — Full architecture specification
├── LICENSE
├── README.md
├── .gitignore
├── .opencode/
│   └── skills/
│       ├── swift-rules/           — Swift & SwiftUI coding standards
│       ├── swiftui-expert-skill/  — SwiftUI advanced patterns
│       └── xcode-build/           — xcodebuild & simctl commands
└── packages/
    ├── pyax/                      — Python accessibility library
    ├── pyax-agent/                — AI-powered accessibility agent
    └── PyAxAssistant/             — Swift macOS companion app
```

## packages/pyax — Python Accessibility Library

Python client library for the macOS Accessibility API.
Uses a mixin/monkey-patching pattern to inject Pythonic methods onto native AXUIElement objects at import time.

```
pyax/
├── pyproject.toml                 — Hatch config, deps (pyobjc, typer), optional extras [highlight], [bridge]
└── src/
    └── pyax/
        ├── __init__.py            — Public API facade: get_applications, create_observer, start/stop, EVENTS
        ├── __main__.py            — Typer CLI entry point (tree, observe, inspect commands)
        ├── _cli.py                — CLI command implementations (tree dump, observe, inspect)
        ├── _constants.py          — ~110 macOS AX event name strings
        ├── _highlighter.py        — PyQt6 transparent overlay for visual element highlighting
        ├── _mixin.py              — Runtime monkey-patching of Cocoa/AX classes with Python methods
        ├── _observer.py           — AX event observer: CFRunLoop integration, start/stop, callbacks
        ├── _uielement.py          — Core AXUIElement wrapper: attributes, actions, tree traversal, search
        ├── utils.py               — Interactive mouse-based element picker with highlight
        └── bridge/
            ├── __init__.py        — Re-exports server.run as main
            ├── __main__.py        — Allows `python3 -m pyax.bridge`
            └── server.py          — WebSocket bridge: CFRunLoop on main thread, asyncio on background thread
```

### Bridge Architecture

Two-thread design required because macOS AX APIs need CFRunLoop on the main thread:

- **Main thread**: CFRunLoop with timers polling for app changes (500ms) and draining command queue (50ms). All accessibility API calls happen here.
- **Background thread**: asyncio WebSocket server. Incoming commands go to command_queue, outgoing events/responses pulled from event_queue.

### Bridge Command Protocol

8 commands over WebSocket: `get_tree`, `find_elements`, `get_element`, `perform_action`, `set_attribute`, `get_element_at_position`, `get_focused_element`, `get_app_info`.

Request format: `{"type": "command", "id": "<uuid>", "command": "get_tree", ...}`
Response format: `{"type": "response", "id": "<uuid>", "command": "get_tree", ...}`

## packages/pyax-agent — AI Accessibility Agent

AI-powered accessibility agent built on the Claude Agent SDK (`claude-agent-sdk>=0.1.48`).
Connects to the pyax bridge via WebSocket and exposes an HTTP+SSE API for the Swift frontend.

### Agent Architecture

```
Swift App ──POST /chat──▶ pyax-agent HTTP server (Starlette)
                              │
                              ▼
                    claude-agent-sdk query()
                              │
                              ▼
                    Claude Code CLI subprocess
                              │
                              ▼
                    In-process MCP server (pyax-tools)
                              │
                              ▼
                    Tool handlers call BridgeClient
                              │
                              ▼
                    pyax bridge (ws://localhost:8765)
                              │
                              ▼
                    macOS Accessibility APIs
```

Key design decisions:

- **Claude Agent SDK** wraps the Claude Code CLI — no `ANTHROPIC_API_KEY` needed, uses `~/.claude` auth
- **In-process MCP server** via `create_sdk_mcp_server()` — zero-overhead tool calls, no subprocess IPC
- **Tool factory pattern with closures** — each tool file exports `create_<name>(bridge)` returning an `@tool`-decorated `SdkMcpTool`
- **SSE streaming** — the HTTP server streams thinking/tool_call/tool_result/message/done events to Swift
- **Permission mode `bypassPermissions`** — our tools are safe accessibility read/write operations

```
pyax-agent/
├── pyproject.toml                        — Deps: claude-agent-sdk, starlette, uvicorn, websockets, httpx
├── conftest.py                           — Root pytest config
└── src/
    └── pyax_agent/
        ├── __init__.py                   — Version string
        ├── __main__.py                   — Uvicorn entry point
        ├── config.py                     — AgentConfig dataclass (model, max_turns, bridge_url, permission_mode)
        ├── bridge_client.py              — Async WebSocket client to pyax bridge (ws://localhost:8765)
        ├── agent.py                      — AgentLoop: wraps claude-agent-sdk query(), maps SDK messages to SSE events
        ├── server.py                     — Starlette HTTP server (POST /chat, POST /stop, GET /health)
        ├── models/
        │   ├── api.py                    — ChatRequest, ChatMessage, ErrorResponse dataclasses
        │   └── sse.py                    — 9 SSE event types + sse_serialize()
        └── tools/
            ├── __init__.py               — Exports TOOL_NAMES, create_all_tools, create_mcp_server
            ├── registry.py               — create_all_tools(bridge), create_mcp_server(bridge), TOOL_NAMES
            ├── get_ui_tree.py            — @tool: get accessibility tree of focused app
            ├── find_elements.py          — @tool: search elements by role/title/value with wildcards
            ├── get_element.py            — @tool: get element details by path
            ├── click_element.py          — @tool: AXPress on element by path or criteria
            ├── type_text.py              — @tool: focus element + set AXValue
            └── get_focused_element.py    — @tool: get element with keyboard focus
```

### Tool Pattern

All tools use the `claude_agent_sdk.tool` decorator with the factory/closure pattern:

```python
from claude_agent_sdk import tool

def create_get_ui_tree(bridge: BridgeClient):
    @tool("get_ui_tree", "Get the UI element tree...", {"depth": int})
    async def get_ui_tree(args: dict) -> dict:
        response = await bridge.send_command("get_tree", depth=args.get("depth", 5))
        return {"content": [{"type": "text", "text": json.dumps(...)}]}
    return get_ui_tree
```

Tools are bundled into an in-process MCP server in `registry.py`:

```python
from claude_agent_sdk import create_sdk_mcp_server

def create_mcp_server(bridge):
    tools = create_all_tools(bridge)
    return create_sdk_mcp_server(name="pyax-tools", version="0.1.0", tools=tools)
```

### Agent Loop

`AgentLoop` in `agent.py` wraps the SDK's `query()` function:

1. Builds `ClaudeAgentOptions` with system prompt, model, MCP server, allowed tools
2. Calls `query(prompt=message, options=options)` which yields SDK message types
3. Maps `AssistantMessage` → `ToolCallEvent`/`MessageEvent`, `ResultMessage` → `MessageEvent`, etc.
4. Strips `mcp__pyax-tools__` prefix from tool names for clean SSE output

The `query_fn` parameter is injectable for testing (avoids spawning Claude Code CLI in tests).

### SSE Events (Swift Frontend Protocol)

9 event types streamed via `text/event-stream`:

- `thinking` — agent is processing (status: analyzing_request, reasoning, system)
- `tool_call` — agent is calling a tool (tool name + input args)
- `tool_result` — tool returned a result (tool name + result data)
- `message` — text response from agent
- `done` — stream complete
- `error` — something went wrong
- `highlight` — Swift should draw UI highlights (future)
- `speak` — Swift should speak text aloud (future)
- `clear_highlights` — Swift should remove highlights (future)

### HTTP Endpoints

- `POST /chat` — `{"message": "...", "conversation_id": "..."}` → SSE stream
- `POST /stop` — Cancel current agent loop → `{"stopped": true}`
- `GET /health` — `{"status": "ok", "bridge_connected": bool, "model": "...", "uptime_seconds": float}`

### Test Infrastructure

124 tests in `tests/` (run with `.venv/bin/python -m pytest tests/ -v --tb=short`):

- `test_config.py` — 13 tests: defaults, validation, env vars, permission mode
- `test_bridge_client.py` — 10 tests: connection, commands, receive loop, ping
- `test_models.py` — 42 tests: API models, all 9 SSE event types, serialization
- `test_tools.py` — 30 tests: registry, MCP server, all 6 tools via FakeBridge + handler()
- `test_agent.py` — 19 tests: init, options, all message types, error/cancel, helpers
- `test_server.py` — 10 tests: health, stop, chat SSE streaming, validation

Tests use a `FakeBridge` that captures commands and returns canned responses.
Agent tests inject a `fake_query` async generator instead of calling the real SDK.

## packages/PyAxAssistant — Swift macOS Companion App

macOS floating overlay (NSPanel) that connects to the Python bridge via WebSocket.
Displays accessibility event streams and exposes the bridge command interface.

```
PyAxAssistant/
├── Package.swift                          — Swift 6.0, macOS 15+, executable + test targets
├── Sources/PyAxAssistant/
│   ├── PyAxAssistantApp.swift             — App entry point, @Environment injection in AppDelegate
│   ├── Models/
│   │   ├── AppState.swift                 — @Observable state manager, owns all app state
│   │   ├── BridgeConfiguration.swift      — Centralized config (ports, timeouts, limits)
│   │   ├── BridgeError.swift              — Typed error enum
│   │   ├── BridgeMessage.swift            — Typed enum for parsed WebSocket messages
│   │   ├── BridgeResponse.swift           — Sendable response wrapper
│   │   ├── BridgeStatus.swift             — Process lifecycle status enum
│   │   ├── ConnectionStatus.swift         — WebSocket connection status enum
│   │   └── RawMessage.swift               — Identifiable JSON message model
│   ├── Services/
│   │   ├── BridgeMessageParser.swift      — Stateless JSON parsing struct
│   │   ├── PortManager.swift              — Orphan process cleanup utility
│   │   ├── PythonBridgeService.swift      — Python process lifecycle + path resolution
│   │   ├── WebSocketConnection.swift      — Connection lifecycle, reconnection, keep-alive
│   │   └── WebSocketService.swift         — Command/response orchestrator, convenience API
│   └── Views/
│       ├── ContentView.swift              — Main composition, consumes @Environment
│       ├── EventStreamView.swift          — Scrollable message list + empty state
│       ├── FloatingPanel.swift            — NSPanel subclass + controller
│       └── StatusBarView.swift            — Status bar with connection indicator + controls
└── Tests/PyAxAssistantTests/
    ├── AppStateTests.swift
    ├── BridgeConfigurationTests.swift
    ├── BridgeMessageParserTests.swift
    ├── BridgeResponseTests.swift
    └── BridgeStatusTests.swift
```

### How the Three Packages Connect

```
┌─────────────────┐    POST /chat (SSE)    ┌──────────────┐    WebSocket     ┌─────────────┐
│  PyAxAssistant  │ ◀───────────────────▶  │  pyax-agent  │ ◀─────────────▶ │  pyax bridge │
│  (Swift app)    │    port 8766           │  (AI agent)  │   port 8765     │  (Python)    │
└─────────────────┘                        └──────────────┘                 └─────────────┘
                                                  │                               │
                                                  ▼                               ▼
                                           Claude Code CLI              macOS Accessibility APIs
                                           (claude-agent-sdk)           (AXUIElement via pyobjc)
```

1. `PyAxAssistant` spawns `python3 -m pyax.bridge` as a child process (`PythonBridgeService`)
2. After a 2-second startup delay, it connects via WebSocket to `ws://localhost:8765` (`WebSocketService`)
3. The bridge streams accessibility events as JSON; PyAxAssistant displays them in `EventStreamView`
4. User chat messages go to `pyax-agent` via `POST /chat` on port 8766
5. The agent uses Claude Agent SDK to reason about the UI and call tools (get_ui_tree, click_element, etc.)
6. Tool calls go through BridgeClient → pyax bridge → macOS AX APIs
7. Agent responses stream back as SSE events (thinking, tool_call, tool_result, message, done)
