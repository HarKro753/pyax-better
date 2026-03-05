---
name: swift-rules
description: Enforce Swift and SwiftUI coding standards, architecture patterns, and naming conventions for this project. Use when writing, reviewing, or refactoring Swift code to ensure consistency with established project rules.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

# Swift & SwiftUI Project Rules

Coding standards and architecture patterns for all Swift code in this project.

## When to Use This Skill

Use this skill when:
- Writing new Swift files or types
- Reviewing existing Swift code for compliance
- Refactoring code to match project conventions
- Creating new SwiftUI views or @Observable managers
- Adding new packages or modules

## Architecture

### Package Separation

All packages live under `packages/`. Each package has a single responsibility:

| Package | Responsibility |
|---------|---------------|
| Env | @Observable state managers |
| Graphql | GraphQL client, queries, mutations, fragments |
| Theme | Theme protocol, color tokens, typography, spacing, dark/light mode |
| Models | Domain entities, Codable conformances, validation logic |
| PyAxAssistant | macOS floating overlay for accessibility event streaming |

### Environment Pattern

```swift
// At App entry point — inject managers
ContentView()
    .environment(appState)
    .environment(webSocket)
    .environment(pythonBridge)

// In child views — consume, never instantiate
struct ContentView: View {
    @Environment(AppState.self) private var appState
}
```

Rules:
- Inject `@Observable` managers at the App entry point using `.environment()`
- Consume in views with `@Environment(ManagerType.self)`
- Use `@State` for view-local state only
- Combine with system environment values like `@Environment(\.dismiss)`
- Propagate managers through view hierarchy, never instantiate in child views

### Observable Classes

All `@Observable` classes must follow this pattern:

```swift
@Observable
@MainActor
final class AppState {
    // Private fields with underscore prefix
    private var _connectionStatus: ConnectionStatus = .disconnected
    private var _messages: [RawMessage] = []

    // Read access through computed properties
    var connectionStatus: ConnectionStatus { _connectionStatus }
    var messages: [RawMessage] { _messages }

    // Write access through setter methods with validation
    func updateConnectionStatus(_ status: ConnectionStatus) {
        _connectionStatus = status
    }

    func appendMessage(_ json: String) {
        guard !_isPaused else { return }
        _messages.append(RawMessage(id: UUID(), json: json))
    }
}
```

Rules:
- All fields must be private with underscore prefix
- Expose read access through computed properties
- Expose write access through setter methods with validation
- Use `@Observable` macro for observation
- Mark classes as `final` unless inheritance is required

## Coding Rules

### General
- Prefer explicit `if/else` blocks over ternary operators for complex logic
- Separate concerns: one type, one responsibility
- Handle business logic in Services, state in Observable managers
- Don't reinvent patterns, use the established architecture
- Don't write inline comments unless intent is not clear by the code (95% of code is self-explaining)
- Write strongly typed code, avoid `Any` and `AnyObject` where possible
- Use dependency injection via Environment or initializer injection
- Prefer `async/await` for asynchronous operations
- Prefer `let` over `var`, embrace immutability
- Write pure functions when possible
- Provide meaningful error messages for users and developers
- Use `Result` type or typed throws for error handling
- Prefer higher-order functions (`map`, `filter`, `reduce`) when it improves readability

### Types
- Use structs for Models and Views
- Use classes for Observable state
- All class fields must be private; expose through computed properties or methods
- Use `private(set)` only when external read access is required
- Validate inputs in setter methods before updating private state

### SwiftUI Best Practices
- Extract reusable components into separate View structs
- Use `@ViewBuilder` for conditional view composition
- Prefer `@Binding` over closures for two-way data flow
- Use `@State` only for view-local state
- Use `@Environment` for shared state across view hierarchy
- Avoid force unwrapping, use `if let` or `guard let`
- Use `.task` modifier for async work on view appearance
- Cancel tasks appropriately using `.task(id:)` or manual cancellation
- Prefer `LazyVStack`/`LazyHStack` for large collections
- Use `@MainActor` for UI-related operations
- Support Dynamic Type and accessibility

## Naming Conventions

| Kind | Convention | Example |
|------|-----------|---------|
| Types (struct, class, enum, protocol) | PascalCase | `BridgeConfiguration` |
| Properties, methods, variables | camelCase | `connectionStatus` |
| Private properties | Underscore prefix | `_connectionStatus` |
| Protocols | Suffix with -able, -ible, or -Protocol | `PythonPathResolving` |
| Observable classes | Suffix with Manager or Store | `AppState` (exception: core state) |
| Action methods | Verb phrases | `appendMessage()`, `togglePause()` |

## Security

- Store sensitive data in Keychain, never UserDefaults
- Use App Transport Security, avoid arbitrary loads
- Implement certificate pinning for sensitive endpoints
- Never hardcode API keys or secrets in source code
- Use proper data protection for files
- Validate and sanitize all user inputs
- Use HTTPS only for all network requests
- Implement proper token refresh and expiration handling
- Never log sensitive information

## PyAxAssistant Package Reference

Current structure for the accessibility overlay package:

```
Sources/PyAxAssistant/
├── PyAxAssistantApp.swift          — App entry point, @Environment injection in AppDelegate
├── Models/
│   ├── AppState.swift              — @Observable state manager, owns all app state
│   ├── BridgeConfiguration.swift   — Centralized config (ports, timeouts, limits)
│   ├── BridgeError.swift           — Typed error enum
│   ├── BridgeMessage.swift         — Typed enum for parsed WebSocket messages
│   ├── BridgeResponse.swift        — Sendable response wrapper
│   ├── BridgeStatus.swift          — Process lifecycle status enum
│   ├── ConnectionStatus.swift      — WebSocket connection status enum
│   └── RawMessage.swift            — Identifiable JSON message model
├── Services/
│   ├── BridgeMessageParser.swift   — Stateless JSON parsing struct
│   ├── PortManager.swift           — Orphan process cleanup utility
│   ├── PythonBridgeService.swift   — Python process lifecycle + path resolution
│   ├── WebSocketConnection.swift   — Connection lifecycle, reconnection, keep-alive
│   └── WebSocketService.swift      — Command/response orchestrator, convenience API
└── Views/
    ├── ContentView.swift           — Main composition, consumes @Environment
    ├── EventStreamView.swift       — Scrollable message list + empty state
    ├── FloatingPanel.swift         — NSPanel subclass + controller
    └── StatusBarView.swift         — Status bar with connection indicator + controls
Tests/PyAxAssistantTests/
├── AppStateTests.swift
├── BridgeConfigurationTests.swift
├── BridgeMessageParserTests.swift
├── BridgeResponseTests.swift
└── BridgeStatusTests.swift
```

## Checklist for New Code

Before submitting any Swift code, verify:

1. All class fields are private with `_` prefix
2. Read access via computed properties, write access via methods
3. `@Observable` classes are `@MainActor final`
4. Views consume shared state via `@Environment`, not `@State`
5. No inline comments unless truly necessary
6. No `Any`/`AnyObject` unless unavoidable
7. `let` preferred over `var`
8. Tests written for testable logic
9. No hardcoded configuration values — use `BridgeConfiguration` or equivalent
10. Naming follows project conventions
