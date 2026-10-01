import SwiftUI

@main
struct LifeSignalApp: App {
    @StateObject private var provisioningManager = BLEProvisioningManager()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(provisioningManager)
        }
    }
}
