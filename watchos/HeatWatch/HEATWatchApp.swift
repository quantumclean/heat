import SwiftUI

@main
struct HEATWatchApp: App {
    @StateObject private var service = HeatService()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(service)
        }
    }
}
