# LifeSignal 시리얼·AI 운영 가이드

이 문서는 다음 두 환경을 구분합니다.

```text
MacBook: 학습용 데이터 수집 → 모델 학습
Raspberry Pi: 실시간 센서 수신 → AI 추론 → HTML 대시보드 제공
```

V-PR100과 C4001은 서로 다른 CSV와 모델을 사용합니다. 학습을 위해서는 각
센서에서 `empty`, `human`, `dog` 라벨마다 최소 2개의 독립된 실제 측정
세션이 필요합니다. 어그멘테이션 데이터는 독립 세션으로 계산되지 않습니다.

## 1. MacBook 공통 준비

모든 명령은 프로젝트 디렉터리에서 실행합니다.

```bash
cd /Users/gony0510/LifeSignal
```

연결된 시리얼 포트를 확인합니다.

```bash
./.venv/bin/python -m serial.tools.list_ports -v
```

Arduino IDE 시리얼 모니터 등 같은 포트를 사용하는 프로그램은 먼저 닫습니다.

## 2. MacBook V-PR100 데이터 수집

V-PR100은 중앙 서버와 시리얼 브리지를 먼저 실행한 뒤, 세 번째 터미널에서
데이터를 수집합니다. 브리지는 센서가 보내는 최신 측정값을 최대 0.2초 간격으로
서버에 전달합니다.

### 터미널 1: 서버 실행

```bash
cd /Users/gony0510/LifeSignal
./.venv/bin/python server.py
```

### 터미널 2: V-PR100 브리지 실행

```bash
cd /Users/gony0510/LifeSignal
./.venv/bin/python serial_bridge.py \
  --port /dev/cu.PL2303G-USBtoUART10 \
  --baud 115200 \
  --protocol binary \
  --publish-interval 0.2
```

포트 이름이 달라졌다면 공통 준비 단계의 포트 확인 명령으로 다시 찾습니다.

### 터미널 3: empty 데이터 2세션

측정 공간을 비운 상태에서 서로 분리된 두 번의 측정을 진행합니다.
`--include-inactive`를 사용하면 비감지 상태도 저장합니다.

```bash
./.venv/bin/python AI/collect_data.py \
  --server ws://127.0.0.1:8881 \
  --label empty \
  --session vpr100_empty_01 \
  --duration 60 \
  --output AI/data/vpr100_samples.csv \
  --include-inactive

./.venv/bin/python AI/collect_data.py \
  --server ws://127.0.0.1:8881 \
  --label empty \
  --session vpr100_empty_02 \
  --duration 60 \
  --output AI/data/vpr100_samples.csv \
  --include-inactive
```

### 터미널 3: human 데이터 2세션

```bash
./.venv/bin/python AI/collect_data.py \
  --server ws://127.0.0.1:8881 \
  --label human \
  --session vpr100_human_01 \
  --duration 60 \
  --output AI/data/vpr100_samples.csv

./.venv/bin/python AI/collect_data.py \
  --server ws://127.0.0.1:8881 \
  --label human \
  --session vpr100_human_02 \
  --duration 60 \
  --output AI/data/vpr100_samples.csv
```

### 터미널 3: dog 데이터 2세션

```bash
./.venv/bin/python AI/collect_data.py \
  --server ws://127.0.0.1:8881 \
  --label dog \
  --session vpr100_dog_01 \
  --duration 60 \
  --output AI/data/vpr100_samples.csv

./.venv/bin/python AI/collect_data.py \
  --server ws://127.0.0.1:8881 \
  --label dog \
  --session vpr100_dog_02 \
  --duration 60 \
  --output AI/data/vpr100_samples.csv
```

## 3. MacBook V-PR100 학습

### 선택 사항: 어그멘테이션

어그멘테이션은 필수 단계가 아닙니다. 먼저 `--apply` 없이 생성 예정 행 수를
확인합니다.

```bash
./.venv/bin/python AI/augment_sensor_csv.py \
  --sensor vpr100 \
  --sessions vpr100_empty_01 vpr100_empty_02 \
  --count 700
```

확인 후 실제 CSV에 적용하려면 같은 명령에 `--apply`를 추가합니다.

```bash
./.venv/bin/python AI/augment_sensor_csv.py \
  --sensor vpr100 \
  --sessions vpr100_empty_01 vpr100_empty_02 \
  --count 700 \
  --apply
```

특정 라벨만 과도하게 늘리지 않도록 실제 행 수와 세션 구성을 확인한 뒤
적용합니다.

### SVM 학습

```bash
./.venv/bin/python AI/train_vpr100_svm.py
```

결과:

```text
AI/artifacts/vpr100-svm.joblib
```

### 1D CNN 학습

```bash
./.venv/bin/python AI/train_vpr100_cnn.py
```

결과:

```text
AI/artifacts/vpr100-cnn.keras
AI/artifacts/vpr100-cnn.json
```

## 4. MacBook C4001 데이터 수집

C4001 학습 데이터는 ESP32 USB 시리얼에서 직접 수집하므로 중앙 서버를
실행할 필요가 없습니다. 아래 포트는 예시이므로 실제 연결 포트를 확인합니다.

### human 데이터 2세션

```bash
./.venv/bin/python AI/collect_c4001_serial.py \
  --port /dev/cu.usbmodem1101 \
  --label human \
  --session c4001_human_01 \
  --duration 600

./.venv/bin/python AI/collect_c4001_serial.py \
  --port /dev/cu.usbmodem1101 \
  --label human \
  --session c4001_human_02 \
  --duration 600
```

### empty 데이터 2세션
 
```bash
./.venv/bin/python AI/collect_c4001_serial.py \
  --port /dev/cu.usbmodem1101 \
  --label empty \
  --session c4001_empty_01 \
  --duration 600

./.venv/bin/python AI/collect_c4001_serial.py \
  --port /dev/cu.usbmodem1101 \
  --label empty \
  --session c4001_empty_02 \
  --duration 600
```

### dog 데이터 2세션

```bash
./.venv/bin/python AI/collect_c4001_serial.py \
  --port /dev/cu.usbmodem1101 \
  --label dog \
  --session c4001_dog_01 \
  --duration 600

./.venv/bin/python AI/collect_c4001_serial.py \
  --port /dev/cu.usbmodem1101 \
  --label dog \
  --session c4001_dog_02 \
  --duration 600
```

## 5. MacBook C4001 학습

### 선택 사항: 어그멘테이션

먼저 미리보기로 확인합니다.

```bash
./.venv/bin/python AI/augment_sensor_csv.py \
  --sensor c4001 \
  --sessions c4001_empty_01 c4001_empty_02 \
  --count 700
```

확인 후 적용합니다.

```bash
./.venv/bin/python AI/augment_sensor_csv.py \
  --sensor c4001 \
  --sessions c4001_empty_01 c4001_empty_02 \
  --count 700 \
  --apply
```

### SVM 학습

```bash
./.venv/bin/python AI/train_c4001_svm.py
```

결과:

```text
AI/artifacts/c4001-svm.joblib
```

### 1D CNN 학습

```bash
./.venv/bin/python AI/train_c4001_cnn.py
```

결과:

```text
AI/artifacts/c4001-cnn.keras
AI/artifacts/c4001-cnn.json
```

두 센서의 SVM을 한 번에 학습하려면 다음 명령을 사용할 수도 있습니다.

```bash
./.venv/bin/python AI/train_all.py
```

## 6. Raspberry Pi 최초 환경 준비

Raspberry Pi에는 학습 CSV나 MacBook의 `.venv`를 복사할 필요가 없습니다.
프로젝트 실행 코드와 학습된 모델 파일만 배치합니다.

Pi 사용자 이름이 `pi-user`, IP가 `192.168.0.30`이라고 가정한 최초 코드 복사
예시입니다. 실제 사용자 이름과 IP로 바꿉니다.

```bash
cd /Users/gony0510/LifeSignal
rsync -av \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude 'AI/data/' \
  ./ pi-user@192.168.0.30:~/LifeSignal/
```

Pi에서 최초 한 번 실행합니다.

```bash
cd ~/LifeSignal
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-pi.txt
sudo usermod -aG dialout "$USER"
sudo reboot
```

재부팅 후 V-PR100 USB-RS232 포트를 확인합니다.

```bash
cd ~/LifeSignal
./.venv/bin/python -m serial.tools.list_ports -v
```

Pi에서는 일반적으로 PL2303 USB-RS232 장치가 `/dev/ttyUSB0`처럼 표시됩니다.

## 7. MacBook에서 Raspberry Pi로 SVM 모델 복사

아래 예시의 `pi-user`와 `192.168.0.30`은 실제 Pi 사용자 이름과 IP로
바꿉니다. Pi에 프로젝트 코드가 이미 배치되어 있다는 기준입니다.

```bash
cd /Users/gony0510/LifeSignal
ssh pi-user@192.168.0.30 'mkdir -p ~/LifeSignal/AI/artifacts'

rsync -av AI/artifacts/vpr100-svm.joblib \
  pi-user@192.168.0.30:~/LifeSignal/AI/artifacts/

rsync -av AI/artifacts/c4001-svm.joblib \
  pi-user@192.168.0.30:~/LifeSignal/AI/artifacts/
```

부스 운영에는 설치와 추론이 가벼운 SVM을 우선 권장합니다. 1D CNN을 사용할
경우 `.keras`와 같은 이름의 `.json`을 함께 복사하고 Pi에 TensorFlow 실행
환경을 별도로 준비해야 합니다.

## 8. Raspberry Pi 최종 부스 실행

### 터미널 1: AI·대시보드 서버

```bash
cd ~/LifeSignal
./.venv/bin/python server.py
```

기본 경로에 SVM 모델 두 개가 있다면 서버가 자동으로 발견합니다. 시작 로그에
다음 내용이 표시되는지 확인합니다.

```text
vpr100 AI 모델 로드 완료
c4001 AI 모델 로드 완료
포트 8881에서 센서 및 대시보드 연결 대기 중
```

### 터미널 2: V-PR100 시리얼 브리지

```bash
cd ~/LifeSignal
./.venv/bin/python serial_bridge.py \
  --port /dev/ttyUSB0 \
  --baud 115200 \
  --protocol binary \
  --publish-interval 0.2
```

포트를 생략하면 PL2303 또는 `/dev/ttyUSB*` 장치를 자동으로 찾습니다.

```bash
./.venv/bin/python serial_bridge.py --protocol binary
```

### C4001 ESP32 연결

최종 부스에서 C4001은 Pi의 USB 시리얼 브리지가 아니라 ESP32의 Wi-Fi
WebSocket으로 서버에 접속합니다. BLE 설정 화면에서 다음 값을 입력합니다.

```text
서버 주소: Raspberry Pi의 로컬 IP
서버 포트: 8881
```

### HTML 대시보드

Pi와 같은 네트워크의 브라우저에서 다음 주소를 엽니다.

```text
http://Raspberry-Pi-IP:8881
```

대시보드는 같은 Pi의 WebSocket 서버에 자동으로 연결합니다.

## 9. Raspberry Pi 부팅 자동 실행

서버와 V-PR100 브리지는 서로 다른 systemd 사용자 서비스로 등록합니다.

```bash
cd ~/LifeSignal
mkdir -p ~/.config/systemd/user
cp deploy/systemd/lifesignal-server.service ~/.config/systemd/user/
cp deploy/systemd/lifesignal-vpr100-bridge.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now lifesignal-server.service
systemctl --user enable --now lifesignal-vpr100-bridge.service
sudo loginctl enable-linger "$USER"
```

각 프로세스의 상태와 로그를 따로 확인할 수 있습니다.

```bash
systemctl --user status lifesignal-server.service
systemctl --user status lifesignal-vpr100-bridge.service
journalctl --user -u lifesignal-server.service -f
journalctl --user -u lifesignal-vpr100-bridge.service -f
```

수동 실행으로 시험할 때는 같은 서비스를 먼저 중지해야 포트 충돌이 발생하지
않습니다.

```bash
systemctl --user stop lifesignal-server.service
systemctl --user stop lifesignal-vpr100-bridge.service
```

## 10. 문제 확인

### 모델이 로드되지 않을 때

```bash
ls -lh ~/LifeSignal/AI/artifacts/
```

SVM 파일 이름이 다음과 정확히 일치해야 자동으로 선택됩니다.

```text
vpr100-svm.joblib
c4001-svm.joblib
```

### V-PR100 포트가 보이지 않을 때

```bash
./.venv/bin/python -m serial.tools.list_ports -v
ls -l /dev/ttyUSB0
groups
```

`dialout` 그룹 추가 후에는 로그아웃하거나 재부팅해야 권한이 반영됩니다.

### 대시보드에 접속할 수 없을 때

```bash
hostname -I
ss -ltnp 'sport = :8881'
```

브라우저와 Pi가 같은 로컬 네트워크에 있는지 확인합니다. 포트 `8881`은 인증이
없는 내부 관제망용이므로 인터넷 포트 포워딩으로 직접 공개하지 않습니다.

### SVM과 CNN이 모두 있을 때

서버 자동 탐색은 SVM을 우선 선택합니다. CNN을 사용하려면 모델 경로를 직접
지정합니다.

```bash
./.venv/bin/python server.py \
  --vpr100-model AI/artifacts/vpr100-cnn.keras \
  --c4001-model AI/artifacts/c4001-cnn.keras
```
