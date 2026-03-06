# SPEC: pyax Agent Layer

## 1. Overview

The pyax agent adds an AI-powered layer on top of the existing pyax accessibility bridge. When prompted by the user (via text or voice), the agent inspects the current UI state, reasons about it, and takes actions — clicking buttons, typing text, reading screen content, highlighting elements, and speaking responses.

The agent is **prompt-driven, not proactive**. It does nothing until the user asks.

The primary audience is **disabled users** who need assistance interacting with macOS applications. The agent remembers each user's specific needs, disabilities, input/output preferences, and learned workflows across sessions through a persistent memory system.

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
│  HTTP Server                                                   │
│    POST /chat       → SSE stream (thinking, actions, response) │
│    POST /stop       → cancel current agent loop                │
│    GET  /health     → status check                             │
│                                                                │
│  Agent Loop (Anthropic Messages API + tool_use)                │
│    Bridge tools  → forwarded to pyax bridge via WebSocket      │
│    Swift tools   → emitted as SSE events, Swift renders them   │
│    Python tools  → executed locally (screenshot, memory)       │
│    └── Bridge Client (ws://localhost:8765)                     │
│                                                                │
│  Memory (persistent markdown files on disk)                    │
│    SOUL.md / USER.md / WORKSPACE.md                            │
│    Loaded into system prompt at session start                  │
│    Updated by agent via memory tools                           │
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

- **Anthropic Python SDK** with `tool_use` — standard agentic loop, no wrappers
- **HTTP + SSE** between Swift and agent — POST for requests, SSE for streaming responses
- **AX tree primary, screenshots optional** — default to structured data, use vision when needed
- **macOS native voice** — AVSpeechSynthesizer (output) + SFSpeechRecognizer (input), both in Swift
- **Swift owns all visualization** — highlights, overlays, voice output are rendered by Swift; Python only passes data through SSE events
- **Separate process** — agent runs on port 8766, bridge stays on 8765
- **General purpose** — works with any focused macOS application
- **Persistent memory** — the agent remembers the user across sessions via editable markdown files

---

## 2. Agent Tools

Tools fall into four categories based on where they execute.

### 2.1 Bridge Tools (agent → pyax bridge → macOS)

The agent forwards commands to the pyax bridge over WebSocket. The bridge executes them via the macOS Accessibility API.

| Tool                      | Purpose                                               |
| ------------------------- | ----------------------------------------------------- |
| `get_ui_tree`             | Get hierarchical element tree of focused app          |
| `find_elements`           | Search for elements by role, title, value (wildcards) |
| `get_element`             | Get element details by path (array of child indices)  |
| `get_focused_element`     | Get the element that currently has keyboard focus     |
| `click_element`           | Click (AXPress) a button, link, or other element      |
| `type_text`               | Set text in a text field (focus + set AXValue)        |
| `scroll`                  | Scroll a scrollable area up or down                   |
| `perform_action`          | Any AX action (AXShowMenu, AXConfirm, AXCancel, etc)  |
| `get_element_at_position` | Hit-test: get the element at screen coordinates       |
| `get_app_info`            | Focused app metadata: name, PID, windows, menu bar    |
| `list_windows`            | List all windows with titles, sizes, positions        |

Elements are identified by **paths** (arrays of child indices from root, e.g. `[0, 3, 2]`) or **search criteria** with wildcards (`*text*` contains, `text*` starts with, `*text` ends with).

### 2.2 Swift Tools (agent → SSE event → Swift renders)

The agent emits SSE side-events that Swift consumes. Python never draws or speaks — it only describes _what_ to draw or say. Swift handles all rendering and audio.

| Tool                 | SSE Event          | What Swift Does                            |
| -------------------- | ------------------ | ------------------------------------------ |
| `highlight_elements` | `highlight`        | Draw colored rectangles over UI elements   |
| `clear_highlights`   | `clear_highlights` | Remove all highlight overlays              |
| `speak_text`         | `speak`            | Speak text aloud via system text-to-speech |

**Flow for Swift tools:**

1. Claude calls the tool (e.g. `highlight_elements`)
2. Python returns `{"success": true}` to Claude immediately (so the model knows it worked)
3. Python simultaneously emits an SSE side-event to Swift with the rendering data
4. Swift receives the event and renders it (draws highlights, speaks text, etc.)
5. Highlights auto-clear after a specified duration

### 2.3 Python-Local Tools

These run directly in the agent process without involving the bridge or Swift.

| Tool              | Purpose                                                  |
| ----------------- | -------------------------------------------------------- |
| `take_screenshot` | Capture screen as image for visual analysis by the model |

### 2.4 Memory Tools

The agent can read and update its own persistent memory files on disk. Memory is injected into the system prompt at session start, and these tools allow the agent to update it mid-session as it learns about the user.

| Tool            | Files Affected        | Purpose                                                |
| --------------- | --------------------- | ------------------------------------------------------ |
| `read_memory`   | Any memory file       | Read a specific memory file (SOUL, USER, or WORKSPACE) |
| `update_memory` | USER.md, WORKSPACE.md | Update a specific section within a memory file         |
| `save_workflow` | WORKSPACE.md          | Save a named multi-step workflow the user taught       |

The agent **cannot modify SOUL.md** — it defines who the agent is and is only editable by the developer or user manually. The agent **can** freely update USER.md (as it learns about the user) and WORKSPACE.md (as it discovers app patterns and the user teaches it workflows).

---

## 3. Agent Memory

The agent maintains persistent knowledge across sessions through three markdown files stored on disk. These are **user-specific, gitignored, and local to each installation**.

### 3.1 Memory Files

#### `SOUL.md` — Agent Identity & Values

Defines who the agent is. **Read-only at runtime** — the agent cannot modify this file via tools. Only the developer or user edits it manually.

Contains:

- **Mission**: help disabled users interact with macOS as independently as possible
- **Personality**: patient, calm, never rushing, proactively explains what it sees
- **Values**: user autonomy (assist, don't take over), privacy (never log sensitive content), safety (confirm before destructive actions)
- **Communication principles**: adapt to the user's abilities — concise for motor-impaired voice users, descriptive for low-vision users, confirmatory for users who need step-by-step guidance
- **Accessibility-first behavior**: always announce actions before performing them, highlight elements before clicking, describe visual elements verbally, respect the user's pace

Example default SOUL.md:

```markdown
# Soul

## Mission

Help disabled users interact with macOS applications as independently as possible.
Act as a patient, reliable assistant that makes the computer accessible.

## Personality

- Patient and calm — never rush the user
- Proactive about describing what you see on screen
- Honest when something isn't working or you're unsure
- Encouraging without being patronizing

## Values

- User autonomy: assist and empower, don't take over
- Privacy: never log or remember passwords, financial data, or private messages
- Safety: always confirm before destructive actions (delete, close without saving, etc.)
- Transparency: tell the user what you're about to do before you do it

## Accessibility-First Behavior

- Always highlight elements before interacting with them
- Speak actions aloud when the user relies on voice output
- Describe visual elements (colors, images, layout) when the user has vision impairment
- Keep responses short when the user communicates via voice (less to listen to)
- Keep responses detailed when the user communicates via text and needs screen descriptions
- Respect the user's pace — never auto-advance or timeout on user input
```

#### `USER.md` — User Profile

Stores everything about the specific human this agent is helping. **Updated by the agent** as it learns — when the user mentions a preference, disability, or limitation, the agent saves it here.

Contains:

- **Name / preferred name**
- **Disability profile**: type and severity of vision, motor, cognitive, hearing impairments
- **Input preferences**: primary input method (voice, keyboard, switch, eye-tracking), secondary input, mouse ability, typing considerations
- **Output preferences**: speech rate, preferred speech voice, needs elements spoken aloud, highlight size/color/contrast preferences, preferred response length
- **Interaction style**: prefers confirmations before actions? wants step-by-step narration? prefers autonomous execution?
- **Known limitations**: things the user has said they can't do (e.g., "I can't use right-click", "I can't read small text")
- **Goals & context**: what the user generally uses their computer for

Example USER.md after a few sessions:

```markdown
# User

## Profile

- Name: Alex
- Primary language: English

## Disability

- Vision: low vision, right eye only — needs high-contrast highlights and verbal descriptions
- Motor: limited fine motor control in hands — cannot reliably use trackpad, relies on voice input
- Hearing: normal

## Input Preferences

- Primary input: voice (push-to-talk)
- Can use keyboard: yes, slowly, for short text only
- Can use mouse/trackpad: no

## Output Preferences

- Speech rate: 0.4 (slightly slower than default)
- Always speak actions before performing them: yes
- Highlight color: #FFD700 (yellow, high contrast)
- Response length: concise — user listens to everything spoken aloud

## Interaction Style

- Confirm before any destructive action (close, delete, etc.)
- Don't confirm before simple navigation (clicking links, scrolling)
- Step-by-step narration: yes, for unfamiliar apps; no, for known workflows

## Known Limitations

- Cannot right-click (use AXShowMenu instead)
- Cannot drag and drop
- Cannot read text smaller than 16pt without zoom
```

#### `WORKSPACE.md` — Known Apps, Tools & Workflows

Stores what the agent has learned about the user's computing environment and any workflows the user has taught it. **Updated by the agent** as it discovers app patterns and when the user teaches it named sequences.

Contains:

- **System info**: macOS version, screen resolution, accessibility features already enabled (VoiceOver, Zoom, Sticky Keys, etc.)
- **Frequently used apps**: apps the user works with, with notes on their AX tree structure and any quirks
- **App-specific notes**: workarounds the agent discovered (e.g., "this app's toolbar buttons don't respond to AXPress, use AXShowMenu instead")
- **Saved workflows**: named multi-step sequences the user taught, with the exact steps
- **Failed approaches**: things that didn't work, so the agent doesn't retry them

Example WORKSPACE.md after a few sessions:

```markdown
# Workspace

## System

- macOS: 15.2
- Screen: 2560x1600 (Retina)
- Accessibility features enabled: Zoom, Sticky Keys, Slow Keys

## Frequently Used Apps

### Safari

- Address bar path: usually [0, 0, 1, 3] but can shift with extensions
- Web content is deeply nested — use find_elements with dom_id when possible
- AXPress works on all toolbar buttons

### Mail

- Message list: AXTable in main window
- Compose window is a separate window, not a sheet
- "Reply All" button sometimes hidden in toolbar overflow

### Messages

- Message input: AXTextArea with description "Message"
- Conversation list: AXTable on the left sidebar
- AXPress on conversation items selects them

## Saved Workflows

### "check email"

1. Activate Mail (get_app_info to confirm, or find in running apps)
2. Click "Inbox" in sidebar
3. Find first unread message (AXStaticText with font weight bold, or AXRow with unread indicator)
4. Click it to open
5. Speak the sender and subject line
6. Speak the message body

### "reply to this email"

1. Click "Reply" button in Mail toolbar
2. Wait for compose window to appear
3. Focus the message body text area
4. User dictates the reply via voice
5. After user says "send it", click the Send button

## Known Issues

- Slack: AXPress on message input doesn't focus it; use set_attribute to set AXFocused instead
- Preview: scroll actions are inconsistent; use get_element_at_position + AXIncrement instead
```

### 3.2 Memory Loading

At session start, the agent loads all three memory files and injects them into the system prompt:

1. **SOUL.md** — always loaded first, forms the core of the system prompt
2. **USER.md** — loaded second, so the agent immediately knows who it's talking to and how to communicate
3. **WORKSPACE.md** — loaded third, provides context about available apps, known workflows, and past learnings

If a file doesn't exist yet (first run), the agent creates it from a default template and optionally asks the user introductory questions to populate USER.md.

### 3.3 Memory Update Behavior

The agent updates memory **automatically with notification** — when it learns something worth remembering, it saves it and tells the user:

- **User mentions a disability or preference** → agent updates USER.md and says "I've noted that in your profile"
- **Agent discovers an app quirk or workaround** → agent updates WORKSPACE.md silently (no need to announce technical notes)
- **User teaches a workflow** ("when I say 'check email', do this...") → agent calls `save_workflow` and confirms "I've saved the 'check email' workflow"
- **User corrects the agent** → agent updates the relevant file to avoid repeating the mistake

The agent **never stores**:

- Passwords, credentials, or API keys
- Private message content, financial data, or health records
- Anything the user asks it to forget

### 3.4 First-Run Experience

On the very first session (no USER.md exists), the agent should:

1. Greet the user and explain what it can do
2. Ask a few questions to understand their needs:
   - "What's your name?"
   - "Do you have any vision, hearing, or motor challenges I should know about?"
   - "How do you prefer to interact — voice, keyboard, or a mix?"
   - "What apps do you use most?"
3. Save the answers to USER.md
4. Confirm what it understood: "OK, I'll always speak actions aloud and use high-contrast yellow highlights. Let me know if I should adjust anything."

This is conversational, not a form — the agent adapts the questions based on the user's answers.

---

## 4. HTTP API

### `POST /chat`

Send a message to the agent. Returns a Server-Sent Events stream.

**Request:**

```json
{
  "message": "Click the submit button",
  "conversation_id": "optional-uuid-for-history"
}
```

**SSE event types in the response stream:**

| Event              | Data                                          | Purpose                        |
| ------------------ | --------------------------------------------- | ------------------------------ |
| `thinking`         | `{"status": "analyzing_request"}`             | Agent is processing            |
| `tool_call`        | `{"tool": "find_elements", "input": {...}}`   | Agent is calling a tool        |
| `tool_result`      | `{"tool": "find_elements", "result": {...}}`  | Tool returned a result         |
| `highlight`        | `{"highlights": [...], "duration": 3.0}`      | Swift should draw highlights   |
| `clear_highlights` | `{}`                                          | Swift should clear highlights  |
| `speak`            | `{"text": "...", "rate": 0.5}`                | Swift should speak text aloud  |
| `message`          | `{"content": "I clicked the Submit button."}` | Final text response from agent |
| `done`             | `{}`                                          | Stream is complete             |
| `error`            | `{"message": "..."}`                          | Something went wrong           |

### `POST /stop`

Cancel the agent's current action loop.

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

---

## 5. Agent Behavior

### 5.1 Agentic Loop

Standard Anthropic `tool_use` loop:

1. User sends a message via `POST /chat`
2. Agent builds context (current app state from bridge + memory files)
3. Agent sends message + context + tool definitions to Claude
4. Claude responds with text or tool calls
5. If tool calls: agent executes them, feeds results back to Claude, goto 4
6. If text response: stream it as SSE `message` event, end

Max 20 tool-call rounds per request. 120 second timeout per request.

### 5.2 Context Injection

Before each agent turn, the system prompt is assembled from:

1. **SOUL.md** contents (agent identity and values)
2. **USER.md** contents (who the user is and how to communicate with them)
3. **WORKSPACE.md** contents (known apps, workflows, past learnings)
4. **Live context** from the bridge: current focused app, windows, menu bar, focused element

This means the agent always knows who the user is, what their needs are, and what apps/workflows it has learned — without the user having to repeat themselves each session.

### 5.3 System Prompt Structure

The system prompt is composed of these sections in order:

1. **Role & capabilities** — what the agent is and what tools it has
2. **SOUL.md** — personality, values, accessibility-first behavior rules
3. **USER.md** — the user's profile, disabilities, preferences
4. **WORKSPACE.md** — known apps, workflows, past learnings
5. **Guidelines** — tactical rules for tool usage:
   - Use the AX tree for element discovery — it's fast and structured
   - Use screenshots only when visual context is needed (images, colors, layout)
   - Highlight elements before acting on them so the user sees what you're targeting
   - Announce actions before performing them (if user prefers)
   - Verify actions succeeded by checking UI state afterward
   - When the user invokes a saved workflow by name, execute it without re-asking the steps
6. **Live context** — current app, focused element, windows

---

## 6. Swift Frontend

### 6.1 Chat Interface

The Swift app adds a chat tab alongside the existing event stream. The chat interface provides:

- **Message list**: scrollable conversation with user messages, agent responses, and status indicators (thinking, tool calls)
- **Text input**: text field with send button
- **Voice input**: push-to-talk microphone button
- **Thinking indicator**: visual feedback when the agent is processing

The chat connects to the agent via `POST /chat` and parses the SSE stream to update the UI in real-time.

### 6.2 Highlight Overlay

A transparent, click-through, full-screen overlay window that draws colored rectangles over UI elements. Used by the agent to show the user what it's looking at or about to interact with.

- Renders colored rectangles with optional text labels
- Sits above all other windows (including the floating panel)
- Fully click-through — never intercepts mouse events
- Auto-clears after the duration specified in the SSE event

### 6.3 Voice I/O

**Input** — push-to-talk:

1. User holds microphone button
2. Speech recognition captures text
3. On release, transcript is sent to agent as a regular chat message

**Output** — text-to-speech:

1. Agent calls `speak_text` tool
2. Swift receives SSE `speak` event
3. System text-to-speech engine speaks the text
4. Text is also always displayed in the chat (never voice-only)

Speech rate and voice are adapted to user preferences stored in USER.md.

Required permissions: speech recognition usage description, microphone usage description.

---

## 7. Configuration

Agent configuration includes:

- **API key**: from `ANTHROPIC_API_KEY` env var, never stored in config files
- **Model**: defaults to `claude-sonnet-4-20250514`
- **Max tokens**: 4096 per response
- **Max turns**: 20 tool-call rounds per request
- **Bridge URL**: `ws://localhost:8765`
- **Agent port**: 8766
- **Memory directory**: path to the `memory/` folder containing SOUL.md, USER.md, WORKSPACE.md
- **Auto-context**: whether to attach current app info with each turn (default: on)

---

## 8. Security & Privacy

- **API key**: from environment variable only, never stored in config files
- **No destructive actions without verification**: agent checks action availability before performing, and confirms destructive actions with the user (per SOUL.md values)
- **Rate limiting**: max 20 tool calls per request, 120 second timeout
- **Local only**: agent server binds to `localhost`, not accessible from network
- **Memory privacy**: the agent never stores passwords, credentials, private messages, financial data, or health records in memory files. Memory files are local, gitignored, and user-owned.
- **SOUL.md is read-only**: the agent cannot modify its own identity/values at runtime — only the developer or user can change SOUL.md manually
- **User can delete memory at any time**: clearing USER.md or WORKSPACE.md resets the agent's knowledge. The agent should handle missing files gracefully.

---

## 9. Example Workflows

### User says: "Click the submit button"

1. Agent highlights and finds all buttons matching "submit"
2. Agent highlights the match so the user sees it
3. Agent clicks it
4. Agent verifies the UI changed (button gone or form submitted)
5. Agent speaks "Done, I clicked Submit" and responds in chat

### User says: "Read me this email"

1. Agent gets the UI tree of Mail
2. Agent finds the message body text
3. Agent speaks the sender, subject, and body text aloud
4. Agent responds in chat with a text summary

### User says: "Check email" (saved workflow)

1. Agent recognizes "check email" as a saved workflow in WORKSPACE.md
2. Agent executes the saved steps: activate Mail → click Inbox → find first unread → click it → speak sender and subject → speak body
3. No confirmation needed — user explicitly invoked a known workflow

### User says: "When I say 'send a reply', I want you to click Reply, wait for the compose window, focus the body, and let me dictate"

1. Agent saves this as a workflow named "send a reply" in WORKSPACE.md
2. Agent confirms: "Got it — I've saved the 'send a reply' workflow"
3. Next time the user says "send a reply", the agent executes those steps

### First session — new user

1. Agent sees no USER.md exists
2. Agent greets the user and asks about their needs
3. User (via voice): "I'm Alex, I have low vision and can't use the trackpad"
4. Agent saves to USER.md: name, vision impairment, no trackpad
5. Agent adjusts: starts using high-contrast highlights, speaking all actions, using voice-friendly concise responses
6. Agent confirms: "Thanks Alex. I'll always speak what I'm doing and use bright highlights. Just let me know if I should adjust anything."

---

## 10. Phased Implementation

### Phase 1: Foundation

- [ ] Python agent package scaffold
- [ ] Bridge client (WebSocket client to pyax bridge)
- [ ] Agent core (Anthropic API + tool_use loop)
- [ ] Bridge tools: `get_ui_tree`, `find_elements`, `get_element`, `click_element`, `type_text`
- [ ] HTTP server with SSE streaming
- [ ] Swift: agent SSE client service
- [ ] Swift: chat view + text input
- [ ] Swift: tab picker (Events / Chat)
- [ ] End-to-end: user types → agent inspects → agent acts → agent responds

### Phase 2: Visual & Voice

- [ ] `take_screenshot` tool (multimodal input to Claude)
- [ ] Swift tools: `highlight_elements`, `clear_highlights`, `speak_text`
- [ ] Swift: highlight overlay window
- [ ] Swift: voice service (speech recognition + text-to-speech)
- [ ] Swift: microphone button in chat input
- [ ] Bridge tools: `list_windows`, `get_app_info`, `scroll`, `perform_action`, `get_element_at_position`

### Phase 3: Memory & Personalization

- [ ] Memory file structure: SOUL.md, USER.md, WORKSPACE.md with default templates
- [ ] Memory loading into system prompt at session start
- [ ] Memory tools: `read_memory`, `update_memory`, `save_workflow`
- [ ] First-run experience: introductory questions → populate USER.md
- [ ] Auto-update USER.md when user mentions preferences/disabilities
- [ ] Workflow saving and invocation from WORKSPACE.md
- [ ] App quirk learning: agent notes workarounds in WORKSPACE.md

### Phase 4: Polish

- [ ] Conversation history persistence
- [ ] Auto-highlight before actions
- [ ] Error recovery and retry logic
- [ ] Agent configuration UI in Swift
- [ ] Timeout and rate limit guardrails
