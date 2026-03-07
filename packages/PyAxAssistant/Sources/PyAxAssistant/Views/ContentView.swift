import SwiftUI

struct ContentView: View {
    @Environment(ChatState.self) private var chatState

    var body: some View {
        VStack(spacing: 0) {
            StatusBarView(
                onClear: { chatState.clearConversation() }
            )

            Divider()
                .opacity(0.3)

            ChatView()
        }
        .frame(minWidth: 340, minHeight: 300)
    }
}
