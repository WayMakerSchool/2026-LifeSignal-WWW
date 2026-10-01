# LifeSignal 사람/빈 공간/개 AI

센서 측정값을 시간 순서대로 모아 SVM 또는 1D CNN으로 사람, 빈 공간,
개를 구분합니다. 모델은 서버에서 한 번만 로드되며, 센서별 최근 데이터는 계속
누적하되 AI 결과는 5초에 한 번 갱신됩니다.

## 데이터 형식

수집 파일은 한 행이 센서 측정 한 번인 long-format CSV입니다. 두 센서의
값과 특성이 다르므로 하나의 CSV나 하나의 모델로 합치지 않습니다.

| 센서 | 학습 신호 | 기본 데이터 파일 |
|---|---|---|
| V-PR100 | `presence_score`, `status` | `AI/data/vpr100_samples.csv` |
| C4001 | `target_energy`, `status` | `AI/data/c4001_samples.csv` |

두 파일 모두 `session_id`, `label`을 포함해야 하며 라벨은 `human`,
`empty`, `dog` 중 하나입니다. V-PR100은 `sensor`, C4001은 `sensor_id`도
필요합니다. 방과 위치 정보는 CSV에 보존하지만 AI 입력 채널로 사용하지
않습니다.

## 1. 데이터 수집

### C4001 USB 원시 데이터

C4001은 서버를 거치지 않고 ESP32 USB 시리얼에서 CSV로 직접 수집합니다.
Arduino IDE 시리얼 모니터를 닫은 뒤 실행하세요.

```bash
python3 AI/collect_c4001_serial.py \
  --port /dev/cu.usbmodem1101 \
  --label human \
  --session c4001_human_01 \
  --duration 600
```

빈 공간과 개는 각각 다른 세션으로 수집합니다.

```bash
python3 AI/collect_c4001_serial.py \
  --port /dev/cu.usbmodem1101 \
  --label empty \
  --session c4001_empty_01 \
  --duration 600

python3 AI/collect_c4001_serial.py \
  --port /dev/cu.usbmodem1101 \
  --label dog \
  --session c4001_dog_01 \
  --duration 600
```

C4001 CSV에는 다음 열만 저장합니다.
```csv
session_id,label,timestamp,sample_millis,sensor_id,room,location,status,target_energy
```

`session_id`는 `--session`으로 입력한 `empty_01`, `human_01`, `dog_01` 등의
세션 이름으로 기록되고, `sensor_id`는 `c4001`로 기록됩니다. 방 번호, 위치,
감지 상태와 Energy를 함께 보존하며, 신뢰하지 않는 속도·거리·타깃 수와 별도
움직임 값은 저장하지 않습니다.

### V-PR100 서버 데이터

중앙 서버와 시리얼 브리지를 실행한 뒤 별도 터미널에서 수집합니다.

```bash
python3 AI/collect_data.py \
  --server ws://127.0.0.1:8881 \
  --label human \
  --session human_walk_01 \
  --duration 60
```

개 세션:

```bash
python3 AI/collect_data.py \
  --server ws://127.0.0.1:8881 \
  --label dog \
  --session dog_walk_01 \
  --duration 60
```

V-PR100의 기본 출력 파일은 `AI/data/vpr100_samples.csv`입니다. 각 세션
이름은 중복되지 않게 지정합니다. 기본적으로 `status=true`인 감지 데이터만
저장합니다. `empty` 세션은 비감지 데이터가 필요하므로
`--include-inactive` 옵션을 추가하세요.

## 2. CSV에 어그멘테이션 데이터 추가

학습을 실행하지 않아도 원할 때 독립 도구로 센서 CSV에 증강 데이터를
추가할 수 있습니다. 먼저 `--apply` 없이 추가될 데이터 수를 확인합니다.

```bash
python3 AI/augment_sensor_csv.py \
  --sensor c4001 \
  --sessions empty_01 empty_02 \
  --count 700
```

내용을 확인한 뒤 같은 명령에 `--apply`를 추가하면 실제 파일에 저장됩니다.

```bash
python3 AI/augment_sensor_csv.py \
  --sensor c4001 \
  --sessions empty_01 empty_02 \
  --count 700 \
  --apply
```

V-PR100은 센서 종류만 바꿉니다.

```bash
python3 AI/augment_sensor_csv.py \
  --sensor vpr100 \
  --sessions empty_01 empty_02 \
  --count 700 \
  --apply
```

C4001은 `target_energy`, V-PR100은 `presence_score`만 변형하며 `status`,
`motion`, 라벨, 방과 위치 정보는 그대로 보존합니다. 기본 변형 정도는
`--jitter 0.03`, `--scale 0.05`이고 필요하면 직접 조절할 수 있습니다.
`--count 700`은 선택한 원본 세션 전체를 기준으로 증강 행을 정확히 700개
추가한다는 뜻입니다. 여러 세션을 선택하면 원본 행 수 비율로 나누되 전체
생성 행 수는 항상 지정한 값과 일치합니다.

적용 전 원본은 CSV와 같은 폴더의 `backups` 디렉터리에 자동으로
백업됩니다. 증강 행에는 `source_session_id`, `is_augmented`,
`augmentation_id`가 기록됩니다. 이미 증강한 세션을 다시 증강하는 것은
같은 `empty_01__aug` 형식의 증강 세션에 시간순으로 이어서 추가합니다.
데이터 세션 이름에는 날짜나 실행 번호를 넣지 않으며, 실행 번호는
`c4001_samples_backup_001.csv` 같은 백업 파일에만 사용합니다.

증강 세션은 별도 `session_id`를 갖지만 학습·검증 분리에서는
`source_session_id`를 기준으로 원본과 같은 그룹에 배치됩니다. 따라서
증강 데이터가 독립 검증 세션으로 잘못 계산되지 않습니다.

## 2.5 시연용 수집 프리셋

라벨과 세션 이름을 직접 입력하는 대신, 시연 배치에 맞춘 프리셋을 사용할 수
있습니다. 프리셋의 `human_danger`와 `human_normal`은 시나리오 설명일 뿐이며,
CSV 학습 라벨은 둘 다 `human`으로 저장됩니다.

사용 가능한 목록:

```bash
./.venv/bin/python AI/collect_session.py --list
```

V-PR100은 서버와 시리얼 브리지를 먼저 실행한 뒤 프리셋을 실행합니다.

```bash
./.venv/bin/python AI/collect_session.py \
  --preset vpr100_human_danger_01
```

이 프리셋은 401호 거실A에서 위험 사람 인형의 `human` 데이터를 수집합니다.
호흡 모션을 준 뒤 호흡 모션을 멈추는 순서로 측정합니다. 개 인형은 다음처럼
별도 세션으로 수집합니다.

위험 사람 프리셋은 호흡을 멈춘 구간도 보존하기 위해 `status=False` 행을
포함해서 저장합니다.

```bash
./.venv/bin/python AI/collect_session.py \
  --preset vpr100_dog_01
```

C4001은 해당 ESP32의 USB 시리얼 포트를 지정합니다. room/location은 센서에
업로드된 펌웨어의 설정에서 들어오므로, 업로드 전에 실제 설치 위치와 맞춰야
합니다.

현재 시연 배치 기준으로 C4001 개 프리셋은 402호 방B, C4001 보통 사람
프리셋은 402호 거실B를 예상 위치로 표시합니다.

```bash
./.venv/bin/python AI/collect_session.py \
  --preset c4001_human_normal_01 \
  --port /dev/cu.usbmodem1101
```

각 라벨은 `01`, `02` 두 개의 독립 세션을 수집해야 학습·검증 분리가 됩니다.
대상 없이 측정하는 `empty` 프리셋은 비감지 상태를 포함합니다.

실제 연결 전에 프리셋, 라벨, 저장 경로만 확인하려면 다음을 사용합니다.

```bash
./.venv/bin/python AI/collect_session.py \
  --preset vpr100_human_danger_01 \
  --dry-run
```

수집이 완료되면 행 수와 완료 시각이 `AI/data/collection_manifest.json`에
기록됩니다. 이 파일은 학습 CSV와 분리되어 있으므로 모델 학습 입력에는
영향을 주지 않습니다.

## 3. SVM 학습

V-PR100과 C4001은 반드시 각 센서 전용 명령으로 학습합니다.

V-PR100 SVM:

```bash
python3 AI/train_vpr100_svm.py
```

C4001 SVM:

```bash
python3 AI/train_c4001_svm.py
```

두 센서 데이터가 모두 준비됐다면 한 번에 학습할 수 있습니다.

```bash
python3 AI/train_all.py
```

이 명령은 두 CSV의 라벨과 독립 세션 수를 먼저 검사한 다음 기본 SVM 모델 두
개를 `AI/artifacts`에 생성합니다. MacBook에서 학습한 모델을 Raspberry Pi의
같은 경로에 복사한 뒤 Pi에서 `python3 server.py`를 실행하면 서버가 두 모델을
자동으로 발견합니다. V-PR100 수신은 별도 터미널의
`python3 serial_bridge.py --protocol binary`가 담당합니다.

어그멘테이션은 기본적으로 사용하지 않습니다. 필요할 때만 다음처럼 변형
사본 수를 지정합니다.

```bash
python3 AI/train_c4001_svm.py \
  --augment-copies 2 \
  --augment-jitter 0.03 \
  --augment-scale 0.05
```

`--augment-copies 0`이 기본값이며 이때 원본 데이터만 사용합니다. 변형은
세션 기준 학습·검증 분리가 끝난 뒤 학습 윈도우에만 적용됩니다. `status`,
`motion` 같은 불리언 채널은 그대로 두고 `target_energy`, `presence_score`
등의 숫자 채널만 변형합니다.

SVM은 각 윈도우에서 평균, 표준편차, 분위수, 변화량, 기울기 등의 특징을
추출하고 `StandardScaler + RBF SVM`을 학습합니다. 모델과 스케일러는
하나의 `joblib` 파일에 함께 저장됩니다. 기본 결과는 각각
`AI/artifacts/vpr100-svm.joblib`, `AI/artifacts/c4001-svm.joblib`입니다.

V-PR100과 C4001 모두 0.2초 주기 기준 25개 샘플(약 5초)을 하나의 학습
윈도우로 사용합니다. 두 센서 모두 5개 샘플 간격으로 다음 학습 윈도우를
만듭니다.

## 4. 1D CNN 학습

V-PR100 1D CNN:

```bash
python3 AI/train_vpr100_cnn.py
```

C4001 1D CNN:

```bash
python3 AI/train_c4001_cnn.py
```

1D CNN도 SVM과 동일한 `--augment-copies`, `--augment-jitter`,
`--augment-scale` 옵션을 지원합니다.

Keras 모델과 함께 같은 이름의 JSON 메타데이터가 생성됩니다.

```text
AI/artifacts/vpr100-cnn.keras
AI/artifacts/vpr100-cnn.json
AI/artifacts/c4001-cnn.keras
AI/artifacts/c4001-cnn.json
```

메타데이터에는 채널 순서, 정규화 값, 윈도우 크기와 라벨 기준이 들어
있습니다. `sensor_type`도 기록되므로 어느 센서의 모델인지 구분할 수
있습니다. Keras 파일과 같은 이름의 JSON 파일을 항상 같이 보관해야 합니다.

네 전용 명령은 학습 전에 필요한 열, 세 라벨, 세션 구성을 검사합니다.
각 라벨은 학습/검증 분리를 위해 최소 2세션이 필요합니다. 예를 들어 현재
C4001 CSV에 `empty`만 있다면 학습하지 않고 부족한 `human`, `dog` 데이터를
안내합니다.

## 5. AI 서버 실행

V-PR100 SVM 모델을 사용할 때:

```bash
python3 server.py \
  --ai-model AI/artifacts/vpr100-svm.joblib \
  --ai-update-interval 5
```

V-PR100 1D CNN 모델을 사용할 때:

```bash
python3 server.py \
  --ai-model AI/artifacts/vpr100-cnn.keras \
  --ai-update-interval 5
```

C4001 모델은 위 경로를 각각 `AI/artifacts/c4001-svm.joblib` 또는
`AI/artifacts/c4001-cnn.keras`로 바꿔 실행할 수 있습니다.

두 센서 모델을 동시에 사용하려면 다음처럼 실행합니다.

```bash
python3 server.py \
  --vpr100-model AI/artifacts/vpr100-svm.joblib \
  --c4001-model AI/artifacts/c4001-svm.joblib \
  --ai-update-interval 5
```

기본 출력 경로에 모델이 있다면 모델 옵션을 생략해도 자동으로 두 모델을
찾습니다.

```bash
python3 server.py
```

서버는 `sensor` 이름에 따라 V-PR100과 C4001 모델을 자동 선택하고, 모델의
`sensor_type` 메타데이터가 모델 슬롯과 일치하는지 확인합니다. 기존 단일
모델용 `--ai-model`도 호환성을 위해 유지합니다.

모델을 지정하지 않아도 서버와 기존 대시보드는 동작하며, AI 상태만
`모델 없음`으로 표시됩니다.

모델이 로드된 경우에는 센서의 `status=True/False`와 관계없이 최근 데이터를
윈도우에 누적합니다. 따라서 `empty`도 AI 모델이 직접 판정할 수 있습니다.
모델이 없는 상태에서 명시적인 `status=False`가 들어오면 기존처럼
`no_target`으로 처리합니다.

## 6. 구조 우선순위

AI 판정 뒤 서버는 다음 `rescue_priority` 객체를 센서 메시지에 추가합니다.

| AI 판정 | level | rank | 표시 |
|---|---:|---:|---|
| empty | `none` | 0 | 구조 대상 없음 |
| dog/pet | `low` | 1 | 낮음 · 반려동물 |
| human | `normal` | 2 | 보통 · 사람 |
| human + 위험 판정 | `danger` | 3 | 위험 · 사람 |

```json
{
  "rescue_priority": {
    "level": "normal",
    "rank": 2,
    "label_ko": "보통 · 사람",
    "target_type": "human",
    "reason_codes": ["human_detected", "human_default_priority"],
    "updated_at": "2026-08-14T00:00:00+00:00"
  }
}
```

현재 사람 판정의 기본값은 `normal`입니다. 향후 움직임 기반 위험 모델이
`human_risk`를 제공하면 위험 점수 0.7 이상인 사람만 `danger`로 올립니다.
반려동물은 위험 입력이 있어도 항상 `low`입니다.

## 7. 실제 센서 연결

USB 텍스트 로그와 공식 Presence Serial 바이너리 패킷은 자동으로
판별합니다.

```bash
python3 serial_bridge.py --protocol auto
```

필요하면 입력 방식을 명시할 수도 있습니다.

```bash
python3 serial_bridge.py --protocol text
python3 serial_bridge.py --protocol binary
```

## 8. 거리값이 없는 Serial 펌웨어

V-PR100 공식 Presence Serial 패킷에서 거리값을 제공하지 않는 현재 구성은
전용 학습 명령이 자동으로 점수와 감지 상태만 사용합니다.

```bash
python3 AI/train_vpr100_svm.py
python3 AI/train_vpr100_cnn.py
```

거리와 움직임은 V-PR100 AI 입력에 포함하지 않습니다. 서버는 모델
메타데이터에 저장된 채널 순서를 자동으로 사용합니다. 공통 알고리즘 파일인
`AI/svm.py`, `AI/1d-cnn.py`는 내부 구현과 고급 실험용으로 유지하지만 실제
센서 학습에는 위 전용 명령을 사용합니다.
