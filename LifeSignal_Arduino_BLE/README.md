# LifeSignal ESP32 BLE 개선 펌웨어

`LifeSignal_Arduino_BLE.ino`는 기존 C4001 센서 로직에 iPhone용 BLE 네트워크
설정을 추가한 개선 버전입니다. 기존
`LifeSignal_Arduino/LifeSignal_Arduino.ino`는 수정하지 않았습니다.

## 필요한 Arduino 라이브러리

- ESP32 보드 패키지 by Espressif Systems
- DFRobot C4001
- WebSockets by Markus Sattler

`WiFi`, `Preferences`, ESP32 BLE 라이브러리는 ESP32 보드 패키지에 포함됩니다.

## 업로드

1. Arduino IDE에서 `LifeSignal_Arduino_BLE.ino`를 엽니다.
2. 보드를 `XIAO_ESP32S3`로 선택하고 현재 사용 중인 XIAO 포트를 선택합니다.
3. `Tools > Partition Scheme`에서 `Default with spiffs (3MB APP/1.5MB SPIFFS)`를 선택합니다.
4. C4001 UART 연결이 기존 코드와 동일하게 `D2`(RX), `D3`(TX)인지 확인합니다.
5. 펌웨어를 업로드하고 시리얼 모니터를 `115200` baud로 엽니다.
6. `BLE 프로비저닝 대기: LifeSignal-XXXX` 메시지를 확인합니다.

센서 내부 설정을 공장값으로 일회 복구해야 하는 경우에는
[`C4001_Factory_Reset`](../C4001_Factory_Reset/README.md)의 절차를 먼저 완료한
뒤 이 펌웨어를 다시 업로드합니다.

현재 코드는 XIAO ESP32S3의 `D2`(GPIO3)를 C4001 UART RX로,
`D3`(GPIO4)를 UART TX로 사용합니다. C4001 `TX`는 XIAO `D2`에,
C4001 `RX`는 XIAO `D3`에 교차 연결합니다.

이 펌웨어를 한 번 업로드한 뒤에는 Wi-Fi나 관제 서버 주소가 바뀌어도 Arduino
코드를 다시 수정할 필요가 없습니다. iPhone 앱에서 새 설정을 전송하면 됩니다.

## 저장 및 재연결 동작

- 앱에서 받은 SSID, 비밀번호, 서버 주소, 포트를 `Preferences`에 저장합니다.
- ESP32 재부팅 시 저장된 설정으로 Wi-Fi와 WebSocket 서버에 자동 연결합니다.
- Wi-Fi 연결은 20초 후 시간 초과로 처리하며 앱에서 다시 설정할 수 있습니다.
- WebSocket 연결이 끊기면 5초 간격으로 자동 재연결합니다.
- 앱의 `저장 설정 삭제` 기능으로 ESP32에 저장된 네트워크 정보를 지울 수 있습니다.

## 서버 전송 데이터

개선 펌웨어는 기존 감지 정보에 서버와 대시보드가 사용하는 `type` 및 `sensor`
필드를 포함합니다.

```json
{
  "type": "radar_data",
  "sensor": "C4001",
  "room": 402,
  "status": true,
  "target_energy": 120,
  "location": "거실"
}
```

`target_energy`는 센서에서 가장 최근에 읽은 Energy이며 중앙 서버의 C4001
AI 입력으로 사용됩니다. 이 필드를 추가해도 센서 모드, 거리, 감도,
측정·전송 주기는 변경되지 않습니다.

방 번호와 위치를 변경하려면 개선 펌웨어 상단의 `ROOM_NUMBER`와
`ZONE_LOCATION`을 수정합니다.

### C4001 원시 학습 데이터

서버에는 위의 `radar_data`만 전송합니다. 전체 원시 측정값은
`AI/collect_c4001_serial.py`가 USB 시리얼 수집을 시작했을 때만 별도 형식으로
전달하며 서버에는 보내지 않습니다. 수집 프로그램은 원시 행을 화면에서 숨기고
기존 아두이노 상태 메시지만 표시합니다.

수집되는 값은 C4001 속도 측정 모드에서 제공하는 다음 항목입니다.

- 움직임 여부(타깃 속도로 계산)
- 순간 감지 여부와 1초 단위 최종 감지 상태
- 타깃 수
- 타깃 속도(m/s)
- 타깃 거리(m)
- 타깃 에너지

사람 데이터 수집 예시는 다음과 같습니다. Arduino IDE 시리얼 모니터를 먼저
닫고 실행해야 합니다.

```bash
python3 AI/collect_c4001_serial.py \
  --label human \
  --session c4001_human_01 \
  --duration 60
```

반려동물 수집 시에는 라벨과 세션 이름을 바꾸어 서버를 다시 실행합니다.

```bash
python3 AI/collect_c4001_serial.py \
  --label pet \
  --session c4001_pet_01 \
  --duration 60
```

기본 저장 위치는 `AI/data/c4001_samples.csv`입니다. 포트 자동 탐색이 되지
않으면 `--port /dev/cu.usbserial-...`를 추가합니다. 저장 위치는 `--output`으로
바꿀 수 있습니다. 같은 CSV에 여러 세션을 이어 쓸 수 있지만, 서로 다른 측정
실험에는 반드시 서로 다른 `--session`을 지정해야 합니다.

수집 중 USB 연결이 끊어지면 프로그램은 종료하지 않고 포트를 다시 탐색합니다.
연결이 복구되면 같은 CSV와 세션에 이어서 저장하며, 연결이 끊긴 시간은 지정한
수집 시간에 포함하지 않습니다. 기본 재연결 시도 간격은 2초입니다.

## 보안 참고

현재 프로비저닝은 현장 설치 편의를 우선한 BLE 연결 방식입니다. Wi-Fi 비밀번호를
전송할 때는 ESP32 가까이에서 짧게 작업하고, 불특정 사용자가 접근할 수 있는
장소에 장치를 장기간 프로비저닝 상태로 방치하지 않는 것이 좋습니다. 제품 배포
단계에서는 BLE 페어링, 소유권 인증, 설정용 일회성 코드 추가를 권장합니다.
