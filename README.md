# 🚀 LifeSignal

> 레이더 센서와 AI로 화재 현장의 구조 대상을 감지하고, 위치, 상태, 그리고 구조우선순위를 실시간 관제 화면에 전달하는 인명 구조 지원 시스템입니다.

<!-- 대표 이미지나 시연 GIF가 있다면 여기에 넣어주세요. -->

<br>

## 📖 프로젝트 소개

- **기간**: 2026년 ~ 진행 중
- **프로젝트**: LifeSignal
- **소개**: 화재 현장에서는 연기와 장애물 때문에 건물 안에 남아 있는 사람과 반려동물의 위치를 파악하기 어렵습니다. LifeSignal은 레이더 센서로 수집한 신호를 분석해 구조 대상을 구분하고, 감지 위치와 상태 및 구조 우선순위를 관제 화면에 표시하여 소방 구조대원의 판단을 돕는 프로젝트입니다. 현재는 모형과 시연 환경을 활용한 프로토타입을 개발하고 있습니다.

<br>

## ✨ 주요 기능

| 기능 | 설명 |
| :-- | :-- |
| 레이더 신호 수집 | V-PR100 센서의 감지 데이터를 수집하고 중앙 서버로 전달합니다. |
| AI 대상 분류 | V-PR100 데이터를 SVM 모델로 분석해 빈 공간·사람·개를 구분합니다. |
| 구조 우선순위 표시 | 시연 환경에서 대상 분류와 움직임 중단 시간을 기준으로 위험 사람·보통 사람·반려동물을 구분해 표시합니다. |
| 실시간 관제 대시보드 | 호수와 공간별 감지 위치, 센서 상태, AI 분류 결과 및 구조 우선순위를 표시합니다. |
| 카메라 영상 연동 | Raspberry Pi 카메라 영상을 관제 화면에서 확인합니다. |
| 현장 네트워크 설정 | iPhone 앱에서 BLE로 ESP32의 Wi-Fi와 관제 서버 연결 정보를 설정합니다. |

<br>

## 🛠 기술 스택

- **언어**: Python, C++(Arduino), Swift, HTML, CSS, JavaScript
- **프레임워크 / 라이브러리**: scikit-learn, TensorFlow, pandas, NumPy, aiohttp, WebSocket, PySerial, SwiftUI
- **도구**: GitHub, Arduino IDE, Xcode, Raspberry Pi 5, V-PR100, C4001, XIAO ESP32-S3

<br>

## 👥 팀원

| <img src="https://github.com/Gony0510.png" width="100"> | <img src="https://github.com/danny4737.png" width="100"> |
| :--: | :--: | :--: |
| [고니](https://github.com/Gony0510) | [데니](https://github.com/danny4737) |
| 센서 연동·AI·앱·대시보드 화면 개발 | 센서 연동·하드웨어·문서 작성 |

<br>

## ▶️ 실행 방법

```bash
# LifeSignal 소스를 내려받아 실행합니다.

# 1. 저장소 받기
git clone https://github.com/WayMakerSchool/2026-LifeSignal-WWW.git
cd 2026-LifeSignal-WWW

# 2. Python 실행 환경 준비
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-pi.txt

# 3. 중앙 관제 서버 실행
python3 server.py

# 4. V-PR100이 연결된 장치의 별도 터미널에서 실행
source .venv/bin/activate
python3 serial_bridge.py --protocol binary

# 5. 브라우저에서 관제 화면 접속
# http://서버IP:8881
```

<br>

## 📁 폴더 구조

<!-- 정리된 LifeSignal 개발 소스의 주요 폴더 구조입니다. -->

```text
.
├── AI/                            # 데이터 수집·전처리·학습·추론
│   └── artifacts/
│       └── vpr100-svm.joblib       # 서버 실행용 최종 SVM 모델
├── LifeSignal_Arduino_BLE/         # C4001·ESP32 펌웨어
├── LifeSignal_Arduino_BLE_LivingB/  # 거실B 센서용 펌웨어
├── LifeSignal_iOS/                 # iPhone BLE 설정 앱
├── deploy/                        # Raspberry Pi 서비스 설정
├── tests/                         # 서버·센서·AI 검증 코드
├── LifeSignal.html                # 웹 관제 대시보드
├── DFRobot_C4001.h                # 구조체 정렬을 수정한 센서 헤더
├── server.py                      # 중앙 관제 서버
├── serial_bridge.py               # V-PR100 시리얼 데이터 전달
├── camera_server.py               # Raspberry Pi 카메라 서버
├── requirements-pi.txt            # 운영용 Python 패키지
├── requirements-ai.txt            # AI 학습용 Python 패키지
├── SERIAL_GUIDE.md                # 시리얼·AI 운영 가이드
├── .gitignore                     # 로컬 데이터·환경·생성 파일 제외
└── README.md
```

<br>

## 🤝 협업 규칙

- **브랜치**
  - `develop`: 개발용 기본 브랜치. 모든 작업은 여기서 시작해요.
  - `feat/기능이름`, `fix/버그이름`: `develop`에서 만들어서 작업하고, PR로 `develop`에 합쳐요.
  - `main`: 발표나 배포할 때만 `develop`을 합쳐요.
- **커밋 메시지**: `feat: 센서 데이터 수집 기능 추가`, `fix: 서버 재연결 오류 수정`, `docs: README 수정`
