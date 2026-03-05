# SPEC: pyax Agent Layer

## 1. Overview

The pyax agent adds an AI-powered layer on top of the existing pyax accessibility bridge. When prompted by the user (via text or voice), the agent inspects the current UI state, reasons about it, and takes actions — clicking buttons, typing text, reading screen content, highlighting elements, and speaking responses.

The agent is **prompt-driven, not proactive**. It does nothing until the user asks.

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  PyAxAssistant (Swift)                                         │
│                                                                │
│  EventStreamView ──── ws://localhost:8765 ──── pyax bridge     │
│  (existing raw event stream, unchanged)                        │
│                                                                │
│  ChatView ──── POST http://localhost:8766/chat ──┐             │
│  (user ↔ agent conversation)                SSE stream         │
│                                                  │             │
│  VoiceService (SFSpeech + AVSpeech)              │             │
│  HighlightOverlayWindow (NSWindow rects)         │             │
└──────────────────────────────────────────────────┼─────────────┘
                                                   │
┌──────────────────────────────────────────────────▼─────────────┐
│  pyax-agent (Python, port 8766)                                │
│                                                                │
│  HTTP Server (aiohttp)                                         │
│    POST /chat       → SSE stream (thinking, actions, response) │
│    POST /stop       → cancel current agent loop                │
│    GET  /health     → status check                             │
│                                                                │
│  Agent Loop (Anthropic Messages API + tool_use)                │
│    Bridge tools  → forwarded to pyax bridge via WebSocket      │
│    Swift tools   → emitted as SSE events, Swift renders them   │
│    Python tools  → executed locally (screenshot, clipboard)    │
│    └── Bridge Client (ws://localhost:8765)                     │
└────────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼──────────────────────────────────────┐
│  pyax bridge (Python, port 8765)  — existing, unchanged        │
│  WebSocket server + CFRunLoop + AX observer                    │
└────────────────────────────────────────────────────────────────┘
                          │
                    macOS Applications
```

### Key design decisions

- **Raw Anthropic Python SDK** with `tool_use` — no Claude Agent SDK, no CLI subprocess
- **HTTP + SSE** between Swift and agent — no WebSocket needed for request/response
- **AX tree primary, screenshots optional** — default to structured data, use vision when needed
- **macOS native voice** — `AVSpeechSynthesizer` (output) + `SFSpeechRecognizer` (input), both in Swift
- **Swift owns all visualization** — highlights, overlays, voice output are rendered by Swift; Python only passes data through SSE events
- **Separate process** — agent runs on port 8766, bridge stays on 8765
- **General purpose** — works with any focused macOS application

## 2. Tool Execution Model

Tools fall into three categories based on where they execute:

### Bridge Tools (Python → pyax bridge → macOS)

The agent forwards commands to the pyax bridge over WebSocket. The bridge executes them on the main thread via CFRunLoop and the macOS Accessibility API.

| Tool                      | Bridge Command                             | Purpose                         |
| ------------------------- | ------------------------------------------ | ------------------------------- |
| `get_ui_tree`             | `get_tree`                                 | Get hierarchical element tree   |
| `find_elements`           | `find_elements`                            | Search for elements by criteria |
| `get_element`             | `get_element`                              | Get element details by path     |
| `get_focused_element`     | `get_focused_element`                      | Get keyboard-focused element    |
| `click_element`           | `perform_action` (AXPress)                 | Click a button/link             |
| `type_text`               | `set_attribute` (AXValue)                  | Type into text fields           |
| `scroll`                  | `perform_action` (AXIncrement/AXDecrement) | Scroll areas                    |
| `perform_action`          | `perform_action`                           | Any AX action                   |
| `get_element_at_position` | `get_element_at_position`                  | Hit-test at coordinates         |
| `get_app_info`            | `get_app_info`                             | App metadata, windows, menus    |
| `list_windows`            | `get_app_info` (windows subset)            | List app windows                |

### Swift Tools (Python → SSE event → Swift renders)

The agent emits SSE side-events that Swift consumes. Python never draws or speaks — it only describes _what_ to draw or say. Swift handles all rendering and audio.

| Tool                 | SSE Event                 | Swift Handler                                |
| -------------------- | ------------------------- | -------------------------------------------- |
| `highlight_elements` | `event: highlight`        | `HighlightOverlayWindow` draws colored rects |
| `clear_highlights`   | `event: clear_highlights` | `HighlightOverlayWindow` clears all rects    |
| `speak_text`         | `event: speak`            | `VoiceService` → `AVSpeechSynthesizer`       |

**Flow for Swift tools:**

```
Claude calls tool: highlight_elements({highlights: [{frame: {x:100,y:200,w:80,h:30}, ...}]})
  │
  ├─► Python returns tool result to Claude: {"success": true}
  │   (so Claude knows the highlight was shown)
  │
  └─► Python yields SSE side-event to Swift:
        event: highlight
        data: {"highlights": [...], "duration": 3.0}
            │
            └─► Swift AgentService parses event
                  → AppState.updateHighlights(...)
                  → HighlightOverlayWindow renders colored rectangles
                  → After duration seconds: auto-clears
```

### Python Tools (executed locally in the agent process)

These run directly in the Python agent process without involving the bridge or Swift.

| Tool              | Implementation      | Purpose                                   |
| ----------------- | ------------------- | ----------------------------------------- |
| `take_screenshot` | `screencapture` CLI | Capture screen as base64 image for Claude |

## 3. Package Structure

```
packages/pyax-agent/
├── pyproject.toml
└── src/
    └── pyax_agent/
        ├── __init__.py
        ├── __main__.py            — python3 -m pyax_agent
        ├── agent.py               — Core agentic loop
        ├── config.py              — AgentConfig dataclass
        ├── bridge_client.py       — WebSocket client to pyax bridge
        ├── server.py              — HTTP server with SSE streaming
        └── tools/
            ├── __init__.py        — Tool registry + decorator
            ├── bridge.py          — All bridge tools (get_ui_tree, find_elements, click, type, etc.)
            ├── swift.py           — All Swift tools (highlight, clear_highlights, speak)
            └── local.py           — All Python-local tools (take_screenshot)
```

## 4. HTTP API

The agent exposes a simple HTTP API. No WebSocket — just POST for requests, SSE for streaming responses.

### `POST /chat`

Send a message to the agent. Returns a Server-Sent Events stream.

**Request:**

```json
{
  "message": "Click the submit button",
  "conversation_id": "optional-uuid-for-history"
}
```

**Response:** `text/event-stream`

```
event: thinking
data: {"status": "analyzing_request"}

event: tool_call
data: {"tool": "find_elements", "input": {"role": "AXButton", "title": "*submit*"}}

event: tool_result
data: {"tool": "find_elements", "result": {"count": 1, "elements": [{"AXRole": "AXButton", "AXTitle": "Submit", "_path": [0, 3, 2]}]}}

event: highlight
data: {"highlights": [{"frame": {"x": 100, "y": 200, "w": 80, "h": 30}, "color": "#1982C4", "label": "Submit"}], "duration": 3.0}

event: tool_call
data: {"tool": "click_element", "input": {"path": [0, 3, 2]}}

event: tool_result
data: {"tool": "click_element", "result": {"success": true}}

event: speak
data: {"text": "Done! I clicked the Submit button."}

event: message
data: {"content": "I found the Submit button and clicked it successfully."}

event: done
data: {}
```

### `POST /stop`

Cancel the agent's current action loop.

**Request:** empty body
**Response:** `{"stopped": true}`

### `GET /health`

**Response:**

```json
{
  "status": "ok",
  "bridge_connected": true,
  "model": "claude-sonnet-4-20250514",
  "uptime_seconds": 120
}
```

## 5. Agent Core

### 5.1 Agentic Loop

Standard Anthropic `tool_use` loop. The agent sends messages to Claude with tool definitions, Claude decides which tools to call, the agent executes them and feeds results back.

```python
class Agent:
    def __init__(self, config: AgentConfig):
        self.client = anthropic.Anthropic(api_key=config.api_key)
        self.bridge = BridgeClient(config.bridge_url)
        self.tools = ToolRegistry()
        self.conversations: dict[str, list] = {}

    async def run(self, message: str, conversation_id: str) -> AsyncIterator[dict]:
        """Process user message. Yields SSE events."""
        messages = self.conversations.get(conversation_id, [])
        messages.append({"role": "user", "content": message})

        context = await self._build_context()

        while True:
            yield {"event": "thinking", "data": {"status": "calling_model"}}

            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=self._system_prompt(context),
                tools=self.tools.to_anthropic_format(),
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                text = self._extract_text(response)
                yield {"event": "message", "data": {"content": text}}
                yield {"event": "done", "data": {}}
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        yield {"event": "tool_call", "data": {"tool": block.name, "input": block.input}}

                        result, side_events = await self.tools.execute(block.name, block.input)
                        yield {"event": "tool_result", "data": {"tool": block.name, "result": result}}

                        # Yield SSE side-events for Swift tools (highlight, speak)
                        for side_event in side_events:
                            yield side_event

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": self._format_tool_result(result),
                        })
                messages.append({"role": "user", "content": tool_results})

        self.conversations[conversation_id] = messages
```

### 5.2 System Prompt

```
You are a macOS accessibility agent. You observe and interact with applications
through the macOS Accessibility API.

You have tools to:
- Inspect UI trees and find elements (get_ui_tree, find_elements, get_focused_element)
- Perform actions: click buttons, type text, scroll (click_element, type_text, scroll)
- Take screenshots for visual understanding (take_screenshot)
- Show the user what you see by highlighting elements on screen (highlight_elements)
- Speak responses aloud (speak_text)
- Get app and window information (get_app_info, list_windows)

Guidelines:
1. Start by understanding the current app context (provided automatically)
2. Use the AX tree for element discovery — it's fast and structured
3. Use screenshots only when visual context is needed (images, colors, layout)
4. Highlight elements before acting on them so the user sees what you're targeting
5. Verify actions succeeded by checking UI state afterward
6. Be concise in responses

The current app context is provided with each request. Elements are identified by
paths (arrays of child indices from root) or search criteria with wildcards.
```

### 5.3 Context Building

Before each agent turn, automatically build context about the current state:

```python
async def _build_context(self) -> str:
    app_info = await self.bridge.send_command("get_app_info")
    focused = await self.bridge.send_command("get_focused_element", {"depth": 1})
    return f"""Current app: {app_info.get('app', 'Unknown')} (PID {app_info.get('pid', '?')})
Windows: {json.dumps(app_info.get('windows', []))}
Menu bar: {app_info.get('menu_bar', [])}
Focused element: {json.dumps(focused.get('element', {}))}"""
```

## 6. Tool Definitions

### 6.1 Bridge Tools

#### `get_ui_tree`

```json
{
  "name": "get_ui_tree",
  "description": "Get the accessibility UI tree of the focused application. Returns hierarchical elements with roles, titles, values, positions, and available actions.",
  "input_schema": {
    "type": "object",
    "properties": {
      "depth": {
        "type": "integer",
        "description": "Max depth to traverse. 2-3 for overview, 5+ for detail.",
        "default": 3
      }
    }
  }
}
```

#### `find_elements`

```json
{
  "name": "find_elements",
  "description": "Search for UI elements matching criteria. Supports wildcards: *text* (contains), text* (starts with), *text (ends with). Returns elements with paths for actions.",
  "input_schema": {
    "type": "object",
    "properties": {
      "role": {
        "type": "string",
        "description": "AX role: AXButton, AXTextField, AXLink, AXStaticText, etc."
      },
      "title": {
        "type": "string",
        "description": "Element title with optional wildcards"
      },
      "value": { "type": "string", "description": "Element value" },
      "description": {
        "type": "string",
        "description": "Accessibility description"
      },
      "dom_id": {
        "type": "string",
        "description": "HTML DOM id (web content)"
      },
      "max_results": { "type": "integer", "default": 10 }
    }
  }
}
```

#### `get_element`

```json
{
  "name": "get_element",
  "description": "Get detailed info about a specific element by its path (array of child indices).",
  "input_schema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "array",
        "items": { "type": "integer" },
        "description": "Element path"
      },
      "depth": { "type": "integer", "default": 1 }
    },
    "required": ["path"]
  }
}
```

#### `get_focused_element`

```json
{
  "name": "get_focused_element",
  "description": "Get the element that currently has keyboard focus.",
  "input_schema": {
    "type": "object",
    "properties": {
      "depth": { "type": "integer", "default": 2 }
    }
  }
}
```

#### `click_element`

```json
{
  "name": "click_element",
  "description": "Click (AXPress) a UI element. Identify by path or search criteria.",
  "input_schema": {
    "type": "object",
    "properties": {
      "path": { "type": "array", "items": { "type": "integer" } },
      "criteria": {
        "type": "object",
        "properties": {
          "role": { "type": "string" },
          "title": { "type": "string" },
          "description": { "type": "string" }
        }
      }
    }
  }
}
```

#### `type_text`

```json
{
  "name": "type_text",
  "description": "Set text in a text field. Focuses the element then sets AXValue.",
  "input_schema": {
    "type": "object",
    "properties": {
      "text": { "type": "string" },
      "path": { "type": "array", "items": { "type": "integer" } },
      "criteria": { "type": "object" },
      "append": { "type": "boolean", "default": false }
    },
    "required": ["text"]
  }
}
```

#### `scroll`

```json
{
  "name": "scroll",
  "description": "Scroll a scrollable area using AXIncrement/AXDecrement.",
  "input_schema": {
    "type": "object",
    "properties": {
      "path": { "type": "array", "items": { "type": "integer" } },
      "direction": { "type": "string", "enum": ["up", "down"] },
      "amount": { "type": "integer", "default": 3 }
    },
    "required": ["direction"]
  }
}
```

#### `perform_action`

```json
{
  "name": "perform_action",
  "description": "Perform any AX action on an element. For AXPress use click_element instead. This handles AXShowMenu, AXConfirm, AXCancel, AXRaise, AXZoomWindow, etc.",
  "input_schema": {
    "type": "object",
    "properties": {
      "action": { "type": "string" },
      "path": { "type": "array", "items": { "type": "integer" } },
      "criteria": { "type": "object" }
    },
    "required": ["action"]
  }
}
```

#### `get_element_at_position`

```json
{
  "name": "get_element_at_position",
  "description": "Hit-test: get the UI element at specific screen coordinates.",
  "input_schema": {
    "type": "object",
    "properties": {
      "x": { "type": "number" },
      "y": { "type": "number" }
    },
    "required": ["x", "y"]
  }
}
```

#### `get_app_info`

```json
{
  "name": "get_app_info",
  "description": "Get metadata about the focused app: name, PID, windows, menu bar items.",
  "input_schema": { "type": "object", "properties": {} }
}
```

#### `list_windows`

```json
{
  "name": "list_windows",
  "description": "List all windows of the focused application with titles, sizes, and positions.",
  "input_schema": { "type": "object", "properties": {} }
}
```

### 6.2 Swift Tools

These tools produce SSE side-events. Python returns `{"success": true}` to Claude and emits the event for Swift to handle. **All rendering and audio happens in Swift.**

#### `highlight_elements`

```json
{
  "name": "highlight_elements",
  "description": "Draw colored rectangles over UI elements on screen. Use to show the user what you're looking at or about to interact with. Rendered by the Swift frontend.",
  "input_schema": {
    "type": "object",
    "properties": {
      "highlights": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "frame": {
              "type": "object",
              "properties": {
                "x": { "type": "number" },
                "y": { "type": "number" },
                "w": { "type": "number" },
                "h": { "type": "number" }
              },
              "required": ["x", "y", "w", "h"]
            },
            "color": { "type": "string", "default": "#1982C4" },
            "label": { "type": "string" }
          },
          "required": ["frame"]
        }
      },
      "duration": { "type": "number", "default": 3.0 }
    },
    "required": ["highlights"]
  }
}
```

SSE side-event emitted:

```
event: highlight
data: {"highlights": [...], "duration": 3.0}
```

#### `clear_highlights`

```json
{
  "name": "clear_highlights",
  "description": "Remove all highlight overlays from the screen.",
  "input_schema": { "type": "object", "properties": {} }
}
```

SSE side-event emitted:

```
event: clear_highlights
data: {}
```

#### `speak_text`

```json
{
  "name": "speak_text",
  "description": "Speak text aloud via the macOS text-to-speech engine. Rendered by the Swift frontend.",
  "input_schema": {
    "type": "object",
    "properties": {
      "text": { "type": "string" },
      "rate": {
        "type": "number",
        "default": 0.5,
        "description": "Speech rate 0.0-1.0"
      }
    },
    "required": ["text"]
  }
}
```

SSE side-event emitted:

```
event: speak
data: {"text": "...", "rate": 0.5}
```

### 6.3 Python-Local Tools

#### `take_screenshot`

```json
{
  "name": "take_screenshot",
  "description": "Capture a screenshot. Returns image for visual analysis. Use when you need to see colors, images, layout, or content the AX tree cannot convey.",
  "input_schema": {
    "type": "object",
    "properties": {
      "region": {
        "type": "object",
        "properties": {
          "x": { "type": "number" },
          "y": { "type": "number" },
          "width": { "type": "number" },
          "height": { "type": "number" }
        }
      },
      "window_only": { "type": "boolean", "default": true }
    }
  }
}
```

Implementation uses `screencapture` CLI. Returns base64-encoded image as a multimodal content block in the tool result sent to Claude.

## 7. Swift Frontend Changes

### 7.1 New Models

**`ChatMessage`** — a single message in the conversation:

```swift
struct ChatMessage: Identifiable {
    let id: UUID
    let role: ChatRole        // .user, .agent, .status
    let content: String
    let timestamp: Date
    let metadata: ChatMetadata?
}

enum ChatRole { case user, agent, status }

struct ChatMetadata {
    let toolName: String?
    let isThinking: Bool
}
```

**`AgentEvent`** — parsed SSE event from the agent:

```swift
enum AgentEvent {
    case thinking(status: String)
    case toolCall(tool: String, input: [String: Any])
    case toolResult(tool: String, result: [String: Any])
    case highlight(highlights: [HighlightRect], duration: Double)
    case clearHighlights
    case speak(text: String, rate: Float)
    case message(content: String)
    case done
    case error(message: String)
}

struct HighlightRect {
    let frame: CGRect
    let color: String
    let label: String?
}
```

### 7.2 New Services

**`AgentService`** — HTTP + SSE client for the agent:

```swift
@Observable @MainActor
final class AgentService {
    func sendChat(_ message: String, conversationId: String) -> AsyncStream<AgentEvent>
    func stop() async
    func checkHealth() async -> Bool
}
```

Uses `URLSession` byte streaming to parse SSE (`event:` / `data:` lines).

**`VoiceService`** — speech I/O (all rendering in Swift):

```swift
@Observable @MainActor
final class VoiceService {
    var isListening: Bool
    var currentTranscript: String

    func startListening()             // SFSpeechRecognizer
    func stopListening() -> String    // returns transcript
    func speak(_ text: String, rate: Float)  // AVSpeechSynthesizer
    func stopSpeaking()
}
```

### 7.3 New Views

**`ChatView`** — conversation interface (tab alongside EventStreamView):

```
┌─────────────────────────────────┐
│  StatusBarView                  │
├─────────────────────────────────┤
│  [Events] [Chat]  ← segmented  │
├─────────────────────────────────┤
│                                 │
│  Agent: What would you like     │
│  me to do?                      │
│                                 │
│  You: Click the submit button   │
│                                 │
│  Agent: 🔍 Looking...          │
│  Agent: ✅ Clicked "Submit"    │
│                                 │
├─────────────────────────────────┤
│  [🎤]  [Type a message...]  [→] │
└─────────────────────────────────┘
```

**`HighlightOverlayWindow`** — transparent NSWindow that draws highlights:

- Separate `NSWindow` (not part of the floating panel)
- Level: `.screenSaver` (above everything, including the floating panel)
- `ignoresMouseEvents = true` — fully click-through
- `backgroundColor = .clear`, non-opaque
- Covers full screen bounds
- Draws colored `NSBezierPath` rectangles with optional text labels
- Auto-clears after the duration specified in the SSE event
- Managed by AppState: when `activeHighlights` changes, the window redraws

### 7.4 AppState Extensions

```swift
private var _chatMessages: [ChatMessage] = []
private var _isAgentThinking = false
private var _activeTab: AppTab = .events
private var _agentConnected = false
private var _activeHighlights: [HighlightRect] = []
private var _isVoiceInputActive = false

enum AppTab { case events, chat }
```

### 7.5 ContentView Changes

Add a segmented picker between Events and Chat:

```swift
Picker("", selection: /* activeTab */) {
    Text("Events").tag(AppTab.events)
    Text("Chat").tag(AppTab.chat)
}
.pickerStyle(.segmented)
```

### 7.6 AppDelegate Changes

Inject new services:

```swift
let agentService = AgentService(configuration: configuration)
let voiceService = VoiceService()

ContentView()
    .environment(appState)
    .environment(webSocket)
    .environment(pythonBridge)
    .environment(agentService)
    .environment(voiceService)
```

### 7.7 BridgeConfiguration Extension

```swift
var agentPort: UInt16 { 8766 }
var agentBaseURL: URL { URL(string: "http://\(host):\(agentPort)")! }
var agentChatURL: URL { agentBaseURL.appendingPathComponent("chat") }
var agentStopURL: URL { agentBaseURL.appendingPathComponent("stop") }
var agentHealthURL: URL { agentBaseURL.appendingPathComponent("health") }
```

## 8. Voice I/O

### Input (Swift → Agent)

Push-to-talk model:

1. User holds microphone button in `ChatInputView`
2. `VoiceService.startListening()` → `SFSpeechRecognizer` starts
3. On release → transcript sent to agent via `POST /chat`
4. Agent treats it identically to text

Permissions: `NSSpeechRecognitionUsageDescription`, `NSMicrophoneUsageDescription` in Info.plist.

### Output (Agent → Swift)

1. Agent calls `speak_text` tool → Python returns success to Claude
2. Python emits SSE `speak` event to Swift
3. Swift `VoiceService.speak()` → `AVSpeechSynthesizer`
4. Text also displayed in ChatView (never voice-only)

## 9. Configuration

### Python (`AgentConfig`)

```python
@dataclass
class AgentConfig:
    api_key: str                            # ANTHROPIC_API_KEY env var
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    max_turns: int = 20                     # max tool-use rounds per request

    bridge_url: str = "ws://localhost:8765"
    agent_port: int = 8766

    auto_context: bool = True               # attach app info each turn
    auto_highlight: bool = True             # highlight before clicking
```

### Swift (`BridgeConfiguration`)

Extended with `agentPort`, `agentBaseURL`, `agentChatURL`, etc.

## 10. Security

- **API key**: from `ANTHROPIC_API_KEY` env var, never stored in config files
- **No destructive actions without verification**: agent checks action availability before performing
- **Rate limiting**: max 20 tool calls per request, 120 second timeout per request
- **Local only**: agent server binds to `localhost`, not accessible from network

## 11. Phased Implementation

### Phase 1: Foundation

- [ ] Python package scaffold (`packages/pyax-agent/`)
- [ ] Bridge client (WebSocket client to pyax bridge)
- [ ] Agent core (Anthropic API + tool_use loop)
- [ ] Bridge tools: `get_ui_tree`, `find_elements`, `get_element`, `click_element`, `type_text`
- [ ] HTTP server with SSE streaming
- [ ] Swift: `AgentService` (HTTP + SSE client)
- [ ] Swift: `ChatView` + `ChatInputView`
- [ ] Swift: Tab picker (Events / Chat)
- [ ] End-to-end: user types → agent inspects → agent acts → agent responds

### Phase 2: Visual & Voice

- [ ] Python-local tool: `take_screenshot` (multimodal input to Claude)
- [ ] Swift tools: `highlight_elements`, `clear_highlights`, `speak_text`
- [ ] Swift: `HighlightOverlayWindow` (renders highlights from SSE events)
- [ ] Swift: `VoiceService` (SFSpeech + AVSpeech)
- [ ] Swift: Microphone button in ChatInputView
- [ ] Bridge tools: `list_windows`, `get_app_info`, `scroll`, `perform_action`, `get_element_at_position`

### Phase 3: Polish

- [ ] Conversation history persistence
- [ ] Auto-highlight before actions
- [ ] Error recovery and retry logic
- [ ] Agent configuration UI in Swift
- [ ] Timeout and rate limit guardrails
