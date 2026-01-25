import SwiftUI

struct ContentView: View {
    @EnvironmentObject var service: HeatService
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("HEAT NJ")
                .font(.headline)
            
            ProgressView(value: service.statewideIntensity, total: 100) {
                Text("Intensity")
            }
            .progressViewStyle(.linear)
            
            if service.latestClusters.isEmpty {
                Text("No clusters visible")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(service.latestClusters.prefix(3), id: \.
self.id) { cluster in
                    VStack(alignment: .leading) {
                        Text("#\(cluster.id) · ZIP \(cluster.zip)")
                            .font(.caption)
                        Text(cluster.summary)
                            .font(.footnote)
                            .lineLimit(2)
                    }
                    Divider()
                }
            }
        }
        .padding()
        .task {
            await service.loadTier0()
        }
    }
}
