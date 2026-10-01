import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var manager: BLEProvisioningManager

    @State private var ssid = ""
    @State private var password = ""
    @State private var serverHost = ""
    @State private var serverPort = "8881"
    @State private var passwordVisible = false
    @State private var showingClearConfirmation = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 18) {
                    hero
                    bluetoothCard

                    if manager.isConnected {
                        configurationCard
                        statusCard
                    }
                }
                .padding(20)
            }
            .background(Color(uiColor: .systemGroupedBackground))
            .navigationTitle("LifeSignal")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if manager.isShowingDeviceDetail {
                    ToolbarItem(placement: .topBarLeading) {
                        Button {
                            manager.showDeviceList()
                        } label: {
                            Label("홈", systemImage: "house.fill")
                        }
                    }

                    ToolbarItem(placement: .topBarTrailing) {
                        Button("연결 해제") {
                            manager.disconnect()
                        }
                        .disabled(!manager.isConnected)
                    }
                }
            }
        }
        .tint(.red)
        .alert(
            "확인 필요",
            isPresented: Binding(
                get: { manager.alertMessage != nil },
                set: { if !$0 { manager.alertMessage = nil } }
            )
        ) {
            Button("확인", role: .cancel) {
                manager.alertMessage = nil
            }
        } message: {
            Text(manager.alertMessage ?? "")
        }
        .confirmationDialog(
            "ESP32의 저장된 설정을 삭제할까요?",
            isPresented: $showingClearConfirmation,
            titleVisibility: .visible
        ) {
            Button("설정 삭제", role: .destructive) {
                manager.clearStoredConfiguration()
            }
            Button("취소", role: .cancel) {}
        } message: {
            Text("삭제 후에는 Wi‑Fi와 서버 정보를 다시 전송해야 합니다.")
        }
    }

    private var hero: some View {
        ZStack(alignment: .bottomLeading) {
            LinearGradient(
                colors: [Color(red: 0.60, green: 0.02, blue: 0.08), .red],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )

            Circle()
                .fill(.white.opacity(0.10))
                .frame(width: 180, height: 180)
                .offset(x: 220, y: -60)

            VStack(alignment: .leading, spacing: 10) {
                Image(systemName: "wave.3.right.circle.fill")
                    .font(.system(size: 40))
                    .symbolRenderingMode(.hierarchical)

                Text("현장 센서를\n빠르게 연결하세요")
                    .font(.system(size: 29, weight: .bold, design: .rounded))

                Text("Bluetooth로 ESP32에 Wi‑Fi와 관제 서버 정보를 간편하게 전달합니다.")
                    .font(.subheadline)
                    .foregroundStyle(.white.opacity(0.85))
                    .fixedSize(horizontal: false, vertical: true)
            }
            .foregroundStyle(.white)
            .padding(24)
        }
        .frame(height: 230)
        .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
        .shadow(color: .red.opacity(0.18), radius: 18, y: 8)
    }

    private var bluetoothCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Label("ESP32 연결", systemImage: "antenna.radiowaves.left.and.right")
                    .font(.headline)

                Spacer()

                StatusPill(
                    title: manager.bluetoothSummary,
                    color: manager.hasConnectedDevices ? .green : .blue
                )
            }

            Text(manager.connectionSummary)
                .font(.subheadline)
                .foregroundStyle(.secondary)

            if !manager.isShowingDeviceDetail {
                if manager.devices.isEmpty {
                    ContentUnavailableView {
                        Label("검색된 장치 없음", systemImage: "dot.radiowaves.left.and.right")
                    } description: {
                        Text("ESP32에 개선 펌웨어를 업로드하고 전원을 켜 주세요.")
                    }
                    .frame(minHeight: 125)
                } else {
                    VStack(spacing: 10) {
                        ForEach(manager.devices) { device in
                            Button {
                                manager.connect(to: device)
                            } label: {
                                HStack(spacing: 14) {
                                    Image(systemName: "memorychip.fill")
                                        .font(.title2)
                                        .foregroundStyle(.red)
                                        .frame(width: 40, height: 40)
                                        .background(.red.opacity(0.10), in: Circle())

                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(device.name)
                                            .font(.body.weight(.semibold))
                                            .foregroundStyle(.primary)
                                        Text(signalDescription(for: device.rssi))
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }

                                    Spacer()

                                    if let state = manager.deviceListStatus(for: device.id) {
                                        StatusPill(
                                            title: state,
                                            color: manager.isDeviceConnected(device.id) ? .green : .orange
                                        )
                                    } else {
                                        Image(systemName: "chevron.right")
                                            .foregroundStyle(.tertiary)
                                    }
                                }
                                .padding(12)
                                .background(
                                    Color(uiColor: .secondarySystemGroupedBackground),
                                    in: RoundedRectangle(cornerRadius: 16)
                                )
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }

                Button {
                    manager.isScanning ? manager.stopScan() : manager.startScan()
                } label: {
                    HStack {
                        if manager.isScanning {
                            ProgressView()
                                .tint(.white)
                        } else {
                            Image(systemName: "arrow.clockwise")
                        }
                        Text(manager.isScanning ? "검색 중지" : "ESP32 검색")
                            .fontWeight(.semibold)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 13)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
            } else {
                HStack(spacing: 12) {
                    Image(
                        systemName: manager.isConnected
                            ? "checkmark.circle.fill"
                            : "arrow.trianglehead.2.clockwise.rotate.90.circle.fill"
                    )
                        .font(.title2)
                        .foregroundStyle(manager.isConnected ? .green : .orange)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(manager.connectedDeviceName)
                            .font(.body.weight(.semibold))
                        Text(manager.isConnected ? "Bluetooth LE 연결됨" : "Bluetooth LE 연결 중")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .cardStyle()
    }

    private var configurationCard: some View {
        VStack(alignment: .leading, spacing: 18) {
            Label("네트워크 설정", systemImage: "wifi")
                .font(.headline)

            VStack(spacing: 14) {
                LabeledContent("Wi‑Fi 이름") {
                    TextField("SSID", text: $ssid)
                        .multilineTextAlignment(.trailing)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }

                Divider()

                LabeledContent("Wi‑Fi 비밀번호") {
                    HStack(spacing: 8) {
                        Group {
                            if passwordVisible {
                                TextField("비밀번호", text: $password)
                            } else {
                                SecureField("비밀번호", text: $password)
                            }
                        }
                        .multilineTextAlignment(.trailing)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()

                        Button {
                            passwordVisible.toggle()
                        } label: {
                            Image(systemName: passwordVisible ? "eye.slash" : "eye")
                        }
                        .buttonStyle(.plain)
                        .foregroundStyle(.secondary)
                    }
                }

                Divider()

                LabeledContent("관제 서버 IP") {
                    TextField("192.168.0.10", text: $serverHost)
                        .multilineTextAlignment(.trailing)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.numbersAndPunctuation)
                }

                Divider()

                LabeledContent("서버 포트") {
                    TextField("8881", text: $serverPort)
                        .multilineTextAlignment(.trailing)
                        .keyboardType(.numberPad)
                }
            }

            Text("iPhone과 ESP32, 관제 서버가 같은 Wi‑Fi 네트워크에 있어야 합니다.")
                .font(.caption)
                .foregroundStyle(.secondary)

            Button {
                manager.provision(
                    ssid: ssid,
                    password: password,
                    serverHost: serverHost,
                    serverPort: serverPort
                )
            } label: {
                HStack {
                    if manager.isProvisioning {
                        ProgressView()
                            .tint(.white)
                    } else {
                        Image(systemName: "paperplane.fill")
                    }
                    Text(manager.isProvisioning ? "연결 진행 중" : "ESP32에 설정 전송")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 13)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!manager.isReadyToProvision || manager.isProvisioning)
        }
        .cardStyle()
    }

    private var statusCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Label("연결 상태", systemImage: statusIcon)
                    .font(.headline)
                Spacer()
                StatusPill(title: statusTitle, color: statusColor)
            }

            Text(manager.deviceMessage)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            if !manager.deviceIP.isEmpty {
                Divider()
                statusRow(title: "ESP32 IP", value: manager.deviceIP, icon: "network")
            }

            if !manager.serverEndpoint.isEmpty {
                statusRow(
                    title: "관제 서버",
                    value: manager.serverEndpoint,
                    icon: "server.rack"
                )
            }

            HStack {
                Button("상태 새로고침") {
                    manager.requestStatus()
                }
                .buttonStyle(.bordered)

                Spacer()

                Button("저장 설정 삭제", role: .destructive) {
                    showingClearConfirmation = true
                }
                .font(.subheadline)
            }
        }
        .cardStyle()
    }

    private func statusRow(title: String, value: String, icon: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .foregroundStyle(.red)
                .frame(width: 24)
            Text(title)
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
                .font(.system(.body, design: .monospaced).weight(.semibold))
                .textSelection(.enabled)
        }
    }

    private var statusTitle: String {
        switch manager.deviceState {
        case "ready": "연결 완료"
        case "wifi_failed": "연결 실패"
        case "server_disconnected": "서버 재연결"
        case "wifi_connecting", "server_connecting", "sending": "연결 중"
        default: "설정 대기"
        }
    }

    private var statusColor: Color {
        switch manager.deviceState {
        case "ready": .green
        case "wifi_failed": .red
        case "server_disconnected": .orange
        default: .blue
        }
    }

    private var statusIcon: String {
        switch manager.deviceState {
        case "ready": "checkmark.shield.fill"
        case "wifi_failed": "exclamationmark.triangle.fill"
        default: "wave.3.right"
        }
    }

    private func signalDescription(for rssi: Int) -> String {
        switch rssi {
        case -55...0: "신호 매우 강함 · \(rssi) dBm"
        case -70 ..< -55: "신호 양호 · \(rssi) dBm"
        default: "신호 약함 · \(rssi) dBm"
        }
    }
}

private struct StatusPill: View {
    let title: String
    let color: Color

    var body: some View {
        Text(title)
            .font(.caption.weight(.semibold))
            .foregroundStyle(color)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(color.opacity(0.11), in: Capsule())
    }
}

private extension View {
    func cardStyle() -> some View {
        self
            .padding(18)
            .background(
                Color(uiColor: .systemBackground),
                in: RoundedRectangle(cornerRadius: 22, style: .continuous)
            )
            .overlay {
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .stroke(Color.primary.opacity(0.05))
            }
    }
}

#Preview {
    ContentView()
        .environmentObject(BLEProvisioningManager())
}
