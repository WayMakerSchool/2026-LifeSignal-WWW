import CoreBluetooth
import Foundation

struct DiscoveredLifeSignalDevice: Identifiable, Equatable {
    let id: UUID
    var name: String
    var rssi: Int
}

private struct ESPStatus: Decodable {
    let state: String
    let message: String
    let deviceIP: String
    let serverEndpoint: String
}

final class BLEProvisioningManager: NSObject, ObservableObject {
    static let serviceUUID = CBUUID(string: "7b6f0001-6d5f-4c20-9f4b-2e1d7a0c1000")

    private enum Characteristic {
        static let ssid = CBUUID(string: "7b6f0002-6d5f-4c20-9f4b-2e1d7a0c1000")
        static let password = CBUUID(string: "7b6f0003-6d5f-4c20-9f4b-2e1d7a0c1000")
        static let serverHost = CBUUID(string: "7b6f0004-6d5f-4c20-9f4b-2e1d7a0c1000")
        static let serverPort = CBUUID(string: "7b6f0005-6d5f-4c20-9f4b-2e1d7a0c1000")
        static let command = CBUUID(string: "7b6f0006-6d5f-4c20-9f4b-2e1d7a0c1000")
        static let status = CBUUID(string: "7b6f0007-6d5f-4c20-9f4b-2e1d7a0c1000")

        static let all: [CBUUID] = [
            ssid,
            password,
            serverHost,
            serverPort,
            command,
            status
        ]
    }

    private struct PendingWrite {
        let characteristic: CBCharacteristic
        let data: Data
    }

    private final class DeviceSession {
        let peripheral: CBPeripheral
        var name: String
        var characteristics: [CBUUID: CBCharacteristic] = [:]
        var pendingWrites: [PendingWrite] = []
        var isReadyToProvision = false
        var isProvisioning = false
        var state = "connecting"
        var message = "ESP32에 연결 중입니다."
        var deviceIP = ""
        var serverEndpoint = ""

        init(peripheral: CBPeripheral, name: String) {
            self.peripheral = peripheral
            self.name = name
        }
    }

    @Published private(set) var devices: [DiscoveredLifeSignalDevice] = []
    @Published private(set) var connectedDeviceIDs: Set<UUID> = []
    @Published private(set) var deviceListStates: [UUID: String] = [:]
    @Published private(set) var isScanning = false
    @Published private(set) var isShowingDeviceDetail = false
    @Published private(set) var isConnected = false
    @Published private(set) var isReadyToProvision = false
    @Published private(set) var isProvisioning = false
    @Published private(set) var bluetoothSummary = "Bluetooth 확인 중"
    @Published private(set) var connectionSummary = "ESP32를 검색해 주세요"
    @Published private(set) var connectedDeviceName = ""
    @Published private(set) var deviceState = "idle"
    @Published private(set) var deviceMessage = "아직 연결된 장치가 없습니다."
    @Published private(set) var deviceIP = ""
    @Published private(set) var serverEndpoint = ""
    @Published var alertMessage: String?

    var hasConnectedDevices: Bool {
        !connectedDeviceIDs.isEmpty
    }

    private var centralManager: CBCentralManager!
    private var peripheralsByIdentifier: [UUID: CBPeripheral] = [:]
    private var sessionsByIdentifier: [UUID: DeviceSession] = [:]
    private var activeDeviceID: UUID?
    private var scanStopWorkItem: DispatchWorkItem?

    override init() {
        super.init()
        centralManager = CBCentralManager(delegate: self, queue: .main)
    }

    func isDeviceConnected(_ identifier: UUID) -> Bool {
        connectedDeviceIDs.contains(identifier)
    }

    func deviceListStatus(for identifier: UUID) -> String? {
        guard let state = deviceListStates[identifier] else { return nil }
        switch state {
        case "ready":
            return "설정 완료"
        case "wifi_failed":
            return "Wi‑Fi 실패"
        case "server_disconnected":
            return "서버 재연결"
        case "connecting":
            return "연결 중"
        default:
            return connectedDeviceIDs.contains(identifier) ? "연결됨" : nil
        }
    }

    func startScan() {
        guard centralManager.state == .poweredOn else {
            alertMessage = "iPhone의 Bluetooth를 켠 뒤 다시 시도해 주세요."
            return
        }

        scanStopWorkItem?.cancel()
        isScanning = true
        connectionSummary = connectedDeviceIDs.isEmpty
            ? "LifeSignal 장치를 찾는 중"
            : "\(connectedDeviceIDs.count)대 연결 유지 중 · 다른 장치를 찾는 중"

        centralManager.scanForPeripherals(
            withServices: [Self.serviceUUID],
            options: [CBCentralManagerScanOptionAllowDuplicatesKey: true]
        )

        let workItem = DispatchWorkItem { [weak self] in
            self?.stopScan()
        }
        scanStopWorkItem = workItem
        DispatchQueue.main.asyncAfter(deadline: .now() + 12, execute: workItem)
    }

    func stopScan() {
        guard isScanning else { return }
        centralManager.stopScan()
        isScanning = false
        updateDeviceListSummary()
    }

    func connect(to device: DiscoveredLifeSignalDevice) {
        guard let peripheral = peripheralsByIdentifier[device.id] else {
            alertMessage = "선택한 장치 정보를 찾을 수 없습니다. 다시 검색해 주세요."
            return
        }

        stopScan()
        activeDeviceID = device.id
        isShowingDeviceDetail = true

        if let session = sessionsByIdentifier[device.id],
           session.peripheral.state == .connected {
            syncActivePresentation()
            requestStatus()
            return
        }

        let session = DeviceSession(peripheral: peripheral, name: device.name)
        sessionsByIdentifier[device.id] = session
        deviceListStates[device.id] = "connecting"
        syncActivePresentation()
        centralManager.connect(peripheral, options: nil)
    }

    func showDeviceList() {
        activeDeviceID = nil
        isShowingDeviceDetail = false
        clearActivePresentation()
        updateDeviceListSummary()
    }

    func disconnect() {
        guard
            let identifier = activeDeviceID,
            let session = sessionsByIdentifier[identifier]
        else { return }

        centralManager.cancelPeripheralConnection(session.peripheral)
    }

    func provision(
        ssid: String,
        password: String,
        serverHost: String,
        serverPort: String
    ) {
        guard
            let identifier = activeDeviceID,
            let session = sessionsByIdentifier[identifier],
            session.peripheral.state == .connected,
            session.isReadyToProvision
        else {
            alertMessage = "먼저 ESP32에 연결해 주세요."
            return
        }

        let trimmedSSID = ssid.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedHost = serverHost.trimmingCharacters(in: .whitespacesAndNewlines)

        guard !trimmedSSID.isEmpty, trimmedSSID.utf8.count <= 32 else {
            alertMessage = "Wi‑Fi 이름은 1~32바이트로 입력해 주세요."
            return
        }
        guard password.utf8.count <= 63 else {
            alertMessage = "Wi‑Fi 비밀번호는 최대 63바이트까지 입력할 수 있습니다."
            return
        }
        guard isValidServerHost(trimmedHost) else {
            alertMessage = "서버 주소에는 IP 또는 호스트 이름만 입력해 주세요. 예: 192.168.0.10"
            return
        }
        guard let port = UInt16(serverPort), port > 0 else {
            alertMessage = "서버 포트는 1~65535 범위로 입력해 주세요."
            return
        }

        let values: [(CBUUID, String)] = [
            (Characteristic.ssid, trimmedSSID),
            (Characteristic.password, password),
            (Characteristic.serverHost, trimmedHost),
            (Characteristic.serverPort, String(port)),
            (Characteristic.command, "connect")
        ]

        do {
            session.pendingWrites = try values.map { uuid, value in
                guard let characteristic = session.characteristics[uuid] else {
                    throw ProvisioningError.missingCharacteristic
                }
                guard let data = value.data(using: .utf8) else {
                    throw ProvisioningError.invalidEncoding
                }
                guard data.count <= session.peripheral.maximumWriteValueLength(for: .withResponse) else {
                    throw ProvisioningError.valueTooLong
                }
                return PendingWrite(characteristic: characteristic, data: data)
            }
        } catch {
            alertMessage = "설정 데이터를 준비하지 못했습니다. ESP32를 다시 연결해 주세요."
            return
        }

        session.isProvisioning = true
        session.state = "sending"
        session.message = "Wi‑Fi와 서버 설정을 ESP32로 전송 중입니다."
        deviceListStates[identifier] = session.state
        syncActivePresentation()
        writeNextValue(for: identifier)
    }

    func clearStoredConfiguration() {
        guard
            let identifier = activeDeviceID,
            let session = sessionsByIdentifier[identifier],
            let command = session.characteristics[Characteristic.command],
            let data = "clear".data(using: .utf8)
        else {
            alertMessage = "먼저 ESP32에 연결해 주세요."
            return
        }

        session.peripheral.writeValue(data, for: command, type: .withResponse)
        session.message = "ESP32에 저장된 설정 삭제를 요청했습니다."
        syncActivePresentation()
    }

    func requestStatus() {
        guard
            let identifier = activeDeviceID,
            let session = sessionsByIdentifier[identifier],
            let status = session.characteristics[Characteristic.status]
        else { return }

        session.peripheral.readValue(for: status)
    }

    private func writeNextValue(for identifier: UUID) {
        guard let session = sessionsByIdentifier[identifier] else { return }
        guard !session.pendingWrites.isEmpty else {
            session.message = "설정 전송 완료. ESP32의 Wi‑Fi 연결을 기다리는 중입니다."
            if activeDeviceID == identifier {
                syncActivePresentation()
            }
            return
        }

        let next = session.pendingWrites.removeFirst()
        session.peripheral.writeValue(next.data, for: next.characteristic, type: .withResponse)
    }

    private func isValidServerHost(_ host: String) -> Bool {
        guard !host.isEmpty, host.utf8.count <= 64 else { return false }
        let invalidCharacters = CharacterSet.whitespacesAndNewlines
            .union(CharacterSet(charactersIn: "/:"))
        return host.rangeOfCharacter(from: invalidCharacters) == nil
    }

    private func clearActivePresentation() {
        isConnected = false
        isReadyToProvision = false
        isProvisioning = false
        connectedDeviceName = ""
        deviceState = "idle"
        deviceMessage = "ESP32를 선택해 설정을 확인하세요."
        deviceIP = ""
        serverEndpoint = ""
    }

    private func syncActivePresentation() {
        guard
            let identifier = activeDeviceID,
            let session = sessionsByIdentifier[identifier]
        else {
            clearActivePresentation()
            return
        }

        isShowingDeviceDetail = true
        isConnected = session.peripheral.state == .connected
        isReadyToProvision = session.isReadyToProvision
        isProvisioning = session.isProvisioning
        connectedDeviceName = session.name
        deviceState = session.state
        deviceMessage = session.message
        deviceIP = session.deviceIP
        serverEndpoint = session.serverEndpoint

        if session.state == "ready" {
            connectionSummary = "설정 완료"
        } else if session.isReadyToProvision {
            connectionSummary = "\(session.name) 연결됨"
        } else {
            connectionSummary = "\(session.name)에 연결 중"
        }
    }

    private func updateDeviceListSummary() {
        if devices.isEmpty {
            connectionSummary = "장치를 찾지 못했습니다. ESP32 전원을 확인해 주세요."
        } else if connectedDeviceIDs.isEmpty {
            connectionSummary = "연결할 ESP32를 선택해 주세요."
        } else {
            connectionSummary = "\(connectedDeviceIDs.count)대 BLE 연결 유지 중 · 다른 ESP32를 선택하세요."
        }
    }

    private func apply(status: ESPStatus, to identifier: UUID) {
        guard let session = sessionsByIdentifier[identifier] else { return }

        session.state = status.state
        session.deviceIP = status.deviceIP
        session.serverEndpoint = status.serverEndpoint
        session.message = localizedMessage(for: status)

        switch status.state {
        case "ready":
            session.isProvisioning = false
        case "wifi_failed", "missing_config":
            session.isProvisioning = false
        case "config_cleared":
            session.isProvisioning = false
            session.deviceIP = ""
            session.serverEndpoint = ""
        default:
            break
        }

        deviceListStates[identifier] = status.state
        if activeDeviceID == identifier {
            syncActivePresentation()
        }
    }

    private func localizedMessage(for status: ESPStatus) -> String {
        switch status.state {
        case "ble_ready":
            return "ESP32가 새 설정을 받을 준비가 되었습니다."
        case "config_saved":
            return "설정을 저장했습니다."
        case "wifi_connecting":
            return "ESP32가 Wi‑Fi에 연결 중입니다."
        case "wifi_connected":
            return "Wi‑Fi 연결 성공. ESP32 IP를 확인했습니다."
        case "server_connecting":
            return "ESP32가 관제 서버에 연결 중입니다."
        case "ready":
            return "Wi‑Fi와 관제 서버 연결이 모두 완료되었습니다."
        case "wifi_failed":
            return "Wi‑Fi 연결 시간이 초과되었습니다. 정보를 확인해 다시 시도해 주세요."
        case "missing_config":
            return "Wi‑Fi 이름과 서버 주소를 입력해 주세요."
        case "server_disconnected":
            return "관제 서버 연결이 끊겼습니다. ESP32가 자동으로 재시도합니다."
        case "config_cleared":
            return "ESP32에 저장된 네트워크 설정을 삭제했습니다."
        default:
            return status.message
        }
    }

    private enum ProvisioningError: Error {
        case missingCharacteristic
        case invalidEncoding
        case valueTooLong
    }
}

extension BLEProvisioningManager: CBCentralManagerDelegate {
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        switch central.state {
        case .poweredOn:
            bluetoothSummary = "Bluetooth 사용 가능"
        case .poweredOff:
            bluetoothSummary = "Bluetooth 꺼짐"
            stopScan()
            sessionsByIdentifier.removeAll()
            connectedDeviceIDs.removeAll()
            deviceListStates.removeAll()
            activeDeviceID = nil
            isShowingDeviceDetail = false
            clearActivePresentation()
            updateDeviceListSummary()
        case .unauthorized:
            bluetoothSummary = "Bluetooth 권한 필요"
            alertMessage = "설정 앱에서 LifeSignal의 Bluetooth 권한을 허용해 주세요."
        case .unsupported:
            bluetoothSummary = "Bluetooth LE 미지원"
        case .resetting:
            bluetoothSummary = "Bluetooth 재설정 중"
        case .unknown:
            bluetoothSummary = "Bluetooth 상태 확인 중"
        @unknown default:
            bluetoothSummary = "Bluetooth 상태 알 수 없음"
        }
    }

    func centralManager(
        _ central: CBCentralManager,
        didDiscover peripheral: CBPeripheral,
        advertisementData: [String: Any],
        rssi RSSI: NSNumber
    ) {
        let advertisedName = advertisementData[CBAdvertisementDataLocalNameKey] as? String
        let name = advertisedName ?? peripheral.name ?? "LifeSignal ESP32"
        let identifier = peripheral.identifier
        peripheralsByIdentifier[identifier] = peripheral

        if let session = sessionsByIdentifier[identifier] {
            session.name = name
        }

        if let index = devices.firstIndex(where: { $0.id == identifier }) {
            devices[index].rssi = RSSI.intValue
            devices[index].name = name
        } else {
            devices.append(
                DiscoveredLifeSignalDevice(
                    id: identifier,
                    name: name,
                    rssi: RSSI.intValue
                )
            )
            devices.sort { $0.rssi > $1.rssi }
        }
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        let identifier = peripheral.identifier
        let fallbackName = devices.first(where: { $0.id == identifier })?.name
            ?? peripheral.name
            ?? "LifeSignal ESP32"
        let session = sessionsByIdentifier[identifier]
            ?? DeviceSession(peripheral: peripheral, name: fallbackName)

        sessionsByIdentifier[identifier] = session
        connectedDeviceIDs.insert(identifier)
        deviceListStates[identifier] = "connected"
        peripheral.delegate = self
        session.state = "connected"
        session.message = "BLE 서비스 정보를 확인하고 있습니다."

        if activeDeviceID == identifier {
            syncActivePresentation()
        }
        peripheral.discoverServices([Self.serviceUUID])
    }

    func centralManager(
        _ central: CBCentralManager,
        didFailToConnect peripheral: CBPeripheral,
        error: Error?
    ) {
        let identifier = peripheral.identifier
        sessionsByIdentifier.removeValue(forKey: identifier)
        connectedDeviceIDs.remove(identifier)
        deviceListStates.removeValue(forKey: identifier)

        if activeDeviceID == identifier {
            activeDeviceID = nil
            isShowingDeviceDetail = false
            clearActivePresentation()
            updateDeviceListSummary()
        }
        alertMessage = error?.localizedDescription ?? "ESP32에 연결하지 못했습니다."
    }

    func centralManager(
        _ central: CBCentralManager,
        didDisconnectPeripheral peripheral: CBPeripheral,
        error: Error?
    ) {
        let identifier = peripheral.identifier
        let deviceName = sessionsByIdentifier[identifier]?.name ?? peripheral.name ?? "ESP32"
        sessionsByIdentifier.removeValue(forKey: identifier)
        connectedDeviceIDs.remove(identifier)
        deviceListStates.removeValue(forKey: identifier)

        if activeDeviceID == identifier {
            activeDeviceID = nil
            isShowingDeviceDetail = false
            clearActivePresentation()
            updateDeviceListSummary()
        }

        if let error {
            alertMessage = "\(deviceName) BLE 연결이 끊겼습니다: \(error.localizedDescription)"
        }
    }
}

extension BLEProvisioningManager: CBPeripheralDelegate {
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        if let error {
            alertMessage = "BLE 서비스를 확인하지 못했습니다: \(error.localizedDescription)"
            return
        }

        guard let service = peripheral.services?.first(where: { $0.uuid == Self.serviceUUID }) else {
            alertMessage = "이 장치에서 LifeSignal 설정 서비스를 찾지 못했습니다."
            return
        }

        peripheral.discoverCharacteristics(Characteristic.all, for: service)
    }

    func peripheral(
        _ peripheral: CBPeripheral,
        didDiscoverCharacteristicsFor service: CBService,
        error: Error?
    ) {
        let identifier = peripheral.identifier
        guard let session = sessionsByIdentifier[identifier] else { return }

        if let error {
            alertMessage = "BLE 설정 항목을 확인하지 못했습니다: \(error.localizedDescription)"
            return
        }

        service.characteristics?.forEach {
            session.characteristics[$0.uuid] = $0
        }

        let hasEveryCharacteristic = Characteristic.all.allSatisfy {
            session.characteristics[$0] != nil
        }
        guard hasEveryCharacteristic else {
            alertMessage = "ESP32 펌웨어의 BLE 통신 규격이 앱과 일치하지 않습니다."
            return
        }

        if let status = session.characteristics[Characteristic.status] {
            peripheral.setNotifyValue(true, for: status)
            peripheral.readValue(for: status)
        }

        session.isReadyToProvision = true
        session.state = "ble_ready"
        session.message = "Wi‑Fi와 관제 서버 정보를 입력해 주세요."
        deviceListStates[identifier] = session.state

        if activeDeviceID == identifier {
            syncActivePresentation()
        }
    }

    func peripheral(
        _ peripheral: CBPeripheral,
        didWriteValueFor characteristic: CBCharacteristic,
        error: Error?
    ) {
        let identifier = peripheral.identifier
        guard let session = sessionsByIdentifier[identifier] else { return }

        if let error {
            session.pendingWrites.removeAll()
            session.isProvisioning = false
            if activeDeviceID == identifier {
                syncActivePresentation()
            }
            alertMessage = "ESP32로 설정을 전송하지 못했습니다: \(error.localizedDescription)"
            return
        }

        if session.isProvisioning {
            writeNextValue(for: identifier)
        }
    }

    func peripheral(
        _ peripheral: CBPeripheral,
        didUpdateValueFor characteristic: CBCharacteristic,
        error: Error?
    ) {
        if let error {
            alertMessage = "ESP32 상태를 읽지 못했습니다: \(error.localizedDescription)"
            return
        }
        guard
            characteristic.uuid == Characteristic.status,
            let data = characteristic.value
        else { return }

        do {
            let status = try JSONDecoder().decode(ESPStatus.self, from: data)
            apply(status: status, to: peripheral.identifier)
        } catch {
            alertMessage = "ESP32가 보낸 상태 데이터를 해석하지 못했습니다."
        }
    }
}
