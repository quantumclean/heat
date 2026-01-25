import Foundation

@MainActor
final class HeatService: ObservableObject {
    @Published var statewideIntensity: Double = 0
    @Published var latestClusters: [ClusterSummary] = []
    
    // Set to your CDN base, e.g. https://dxxxx.cloudfront.net/exports/
    var baseUrl: String = "https://example-cloudfront/exports/"
    
    struct ClusterSummary: Decodable {
        let id: Int
        let zip: String
        let summary: String
        let strength: Double
    }
    
    struct Tier0: Decodable {
        let intensity_pct: Double?
        let clusters: [ClusterSummary]?
    }
    
    func loadTier0() async {
        guard let url = URL(string: baseUrl + "tier0_public.json") else { return }
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let decoded = try JSONDecoder().decode(Tier0.self, from: data)
            statewideIntensity = decoded.intensity_pct ?? 0
            latestClusters = decoded.clusters ?? []
        } catch {
            statewideIntensity = 0
            latestClusters = []
        }
    }
}