import SwiftUI

struct ErrorBannerView: View {
    let error: AppErrorState
    let onDismiss: () -> Void
    @State private var showingDetails = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(.yellow)

                VStack(alignment: .leading, spacing: 6) {
                    Text(error.title)
                        .font(.headline)

                    Text(error.message)
                        .font(.callout)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                Spacer()

                Button("Dismiss", action: onDismiss)
                    .buttonStyle(.borderless)
            }

            if let details = error.details, !details.isEmpty {
                DisclosureGroup(showingDetails ? "Hide details" : "Show details", isExpanded: $showingDetails) {
                    ScrollView {
                        Text(details)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .font(.system(.caption, design: .monospaced))
                            .textSelection(.enabled)
                    }
                    .frame(maxHeight: 180)
                    .padding(.top, 6)
                }
                .font(.callout)
            }
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(.thinMaterial)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .strokeBorder(.quaternary)
        )
        .shadow(color: .black.opacity(0.08), radius: 12, y: 6)
    }
}
