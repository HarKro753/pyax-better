import SwiftUI

struct StatusBarView: View {
    let onClear: () -> Void

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "accessibility")
                .font(.system(size: 14))
                .foregroundStyle(.secondary)

            Text("PyAx Assistant")
                .font(.system(.caption, weight: .semibold))
                .foregroundStyle(.primary)

            Spacer()

            Button(action: onClear) {
                Image(systemName: "trash")
                    .font(.system(size: 10, weight: .medium))
                    .frame(width: 22, height: 22)
            }
            .buttonStyle(.plain)
            .foregroundStyle(.secondary)
            .background(.white.opacity(0.08))
            .clipShape(.rect(cornerRadius: 5))
            .help("Clear chat")
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
    }
}
