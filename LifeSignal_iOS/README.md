# LifeSignal iPhone 프로비저닝 앱

ESP32에 Bluetooth Low Energy로 Wi-Fi 및 관제 WebSocket 서버 정보를 전달하는
SwiftUI 앱입니다. 설정이 완료되면 앱에서 ESP32의 로컬 IP와 서버 연결 상태를
확인할 수 있습니다.

## 준비 사항

- iOS 17 이상이 설치된 iPhone
- 전체 Xcode가 설치된 Mac
- `LifeSignal_Arduino_BLE/LifeSignal_Arduino_BLE.ino`가 업로드된 ESP32
- iPhone, ESP32, 관제 서버 Mac이 접속할 수 있는 같은 Wi-Fi 네트워크

Bluetooth LE 검색은 iOS 시뮬레이터에서 실제 ESP32를 대상으로 시험할 수 없으므로
실제 iPhone을 사용해야 합니다.

## iPhone에서 실행

1. Xcode에서 `LifeSignal.xcodeproj`를 엽니다.
2. 프로젝트의 `LifeSignal` 타깃에서 `Signing & Capabilities`를 선택합니다.
3. 본인의 Apple Developer `Team`을 선택합니다.
4. 상단 실행 대상을 연결된 iPhone으로 변경합니다.
5. Run 버튼을 누릅니다.
6. iPhone에 Bluetooth 권한 창이 나타나면 허용합니다.

무료 Apple ID로 설치한 개발용 앱은 서명 유효 기간에 따라 다시 빌드해야 할 수
있습니다.

## 사용 순서

1. ESP32 전원을 켭니다.
2. 앱에서 `ESP32 검색`을 누릅니다.
3. `LifeSignal-XXXX` 형식의 장치를 선택합니다.
4. 현장 Wi-Fi SSID와 비밀번호를 입력합니다.
5. 관제 서버를 실행하는 Mac의 로컬 IP와 포트 `8881`을 입력합니다.
6. `ESP32에 설정 전송`을 누릅니다.
7. 상태가 `연결 완료`로 바뀌고 ESP32 IP가 표시되는지 확인합니다.

서버 주소에는 `ws://`를 붙이지 않습니다. 예를 들어 서버 URL이
`ws://192.168.0.10:8881/`이면 앱에는 IP `192.168.0.10`과 포트 `8881`을
각각 입력합니다.

## 관제 서버 실행

프로젝트 루트에서 다음 명령으로 기존 WebSocket 서버를 실행합니다.

```sh
source .venv/bin/activate
python server.py
```

Mac의 Wi-Fi IP는 일반적인 macOS Wi-Fi 인터페이스에서 다음 명령으로 확인할 수
있습니다.

```sh
ipconfig getifaddr en0
```

그 IP를 앱의 `관제 서버 IP`에 입력합니다. ESP32 IP는 장치 식별 및 진단용이며,
WebSocket 서버 주소로 입력하는 값은 Mac의 IP입니다.

## BLE 통신 규격

서비스 UUID:

`7b6f0001-6d5f-4c20-9f4b-2e1d7a0c1000`

앱은 SSID, 비밀번호, 서버 호스트, 포트를 각각의 쓰기 Characteristic으로 전송한
후 `connect` 명령을 보냅니다. ESP32는 상태 Characteristic을 통해 다음 단계를
JSON으로 알립니다.

- BLE 설정 대기
- 설정 저장
- Wi-Fi 연결 중/성공/실패
- 관제 서버 연결 중
- 전체 연결 완료

Wi-Fi 비밀번호는 앱 파일이나 `UserDefaults`에 저장하지 않습니다. ESP32는 재부팅
후 자동 연결을 위해 자체 비휘발성 저장소(`Preferences`)에 설정을 보관합니다.

## 문제 해결

- 장치가 검색되지 않으면 ESP32 시리얼 모니터에 `BLE 프로비저닝 대기`가
  출력되는지 확인합니다.
- Wi-Fi 연결 실패 시 2.4 GHz 네트워크인지 확인합니다. 대부분의 ESP32는 5 GHz
  전용 네트워크에 접속할 수 없습니다.
- Wi-Fi는 연결되지만 서버 연결이 끝나지 않으면 Mac 방화벽과 포트 `8881`, 앱에
  입력한 Mac IP를 확인합니다.
- 공유기의 클라이언트 격리 기능이 켜져 있으면 같은 Wi-Fi에서도 ESP32와 Mac이
  통신하지 못할 수 있습니다.
