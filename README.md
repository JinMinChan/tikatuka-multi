# TikaTuka Multi

티카투카를 웹에서 1:1로 플레이할 수 있게 만든 멀티플레이 구현체입니다.
프론트엔드는 정적 HTML/CSS/JavaScript로 구성되어 있고, 백엔드는 FastAPI와
WebSocket으로 방, 매칭, 게임 진행, 전적, 토너먼트를 관리합니다.

게임 판정은 서버 권위 방식입니다. 클라이언트는 화면 표시와 사용자 입력 전달을
담당하고, 실제 주사위 생성·배치·승패 판정은 서버의 게임 엔진에서 처리합니다.

봇 클라이언트를 만들려면 [BOT_INTEGRATION.md](BOT_INTEGRATION.md)를 먼저 보세요.
WebSocket snapshot 구조와 행동 프로토콜이 정리되어 있습니다.

## 주요 기능

- 랜덤 매칭
- 숫자 방 코드 기반 1:1 친선전
- 스트리머 모드
  - 방장 1P 고정
  - 대기열/관전
  - 대기자 이모티콘
  - 상대 교체
- 토너먼트 모드
  - 4인, 8인, 16인
  - 단판, 3판 2선승, 5판 3선승
  - 랜덤 배치와 지정 배치
  - 진행 중인 대진표 표시
- 모바일 전용 세로 UI
- 티어/별/마스터 점수 시스템
- 칭호 시스템
- 보드판·이모티콘 커스터마이징
- 서버 관리자용 상태/유저 관리 API
- 봇 연동용 방 조회 API

## 프로젝트 구조

```text
tikatuka-multi/
├── frontend/
│   ├── index.html          # 화면 DOM 구조
│   ├── app.js              # 클라이언트 상태, 렌더링, WebSocket 처리
│   ├── styles.css          # PC/모바일 UI, 애니메이션, 커스터마이징 스타일
│   ├── emoticon/           # 기본 이모티콘과 카탈로그 이미지
│   └── sound_samples/      # 효과음
├── server/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── app/
│       ├── game_engine.py  # 순수 게임 규칙 엔진
│       └── main.py         # FastAPI, WebSocket, 방/매칭/전적 관리
├── tests/
│   ├── test_game_engine.py
│   └── test_server.py
├── scripts/
│   └── tikatuka_admin.py   # 관리자 API 보조 스크립트
├── BOT_INTEGRATION.md      # 봇 클라이언트 연동 가이드
├── AGENTS.md               # 에이전트 작업 규칙
└── README.md
```

## 로컬 실행

### 1. 의존성 설치

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r server/requirements-dev.txt
```

### 2. 백엔드 실행

```bash
PYTHONPATH=server .venv/bin/uvicorn app.main:app \
  --reload --host 127.0.0.1 --port 8000
```

상태 확인:

```bash
curl http://127.0.0.1:8000/health
```

### 3. 프론트엔드 실행

```bash
python3 -m http.server 5174 -d frontend
```

브라우저에서 `http://127.0.0.1:5174/`로 접속합니다.
로컬 정적 서버가 `5173` 또는 `5174` 포트에서 뜨면 프론트엔드는 API 서버를
자동으로 `http://127.0.0.1:8000`으로 잡습니다.

## 테스트

```bash
PYTHONPATH=server .venv/bin/python -m pytest -q
PYTHONPATH=server .venv/bin/python -m compileall -q server
node --check frontend/app.js
git diff --check
```

현재 테스트는 게임 엔진 규칙, 서버 방 수명주기, 랜덤 매칭, 시간패, 재대결,
티어/전적, 관리자 API, 토너먼트 관련 동작을 중심으로 구성되어 있습니다.

## 프론트엔드 개요

### `frontend/index.html`

PC와 모바일 UI의 DOM 골격을 함께 담고 있습니다.
모바일에서는 CSS media query와 `.mobile-game` 영역을 사용해 세로 화면 전용 UI를
표시합니다.

프론트 변경 시 브라우저 캐시를 피하기 위해 `styles.css?v=...`,
`app.js?v=...` 값을 함께 갱신하는 편이 안전합니다.

### `frontend/app.js`

주요 책임:

- 서버 주소 결정
- client id와 닉네임 localStorage 관리
- HTTP API 호출
- WebSocket 연결과 snapshot 수신
- PC/모바일 렌더링
- 주사위, 알까기, 이모티콘, 토너먼트 애니메이션
- 커스터마이징 상태 저장

중요한 상태:

- `state.clientId`: 브라우저별 사용자 식별자
- `state.snapshot`: 서버에서 받은 최신 게임 상태
- `state.ws`: 현재 WebSocket 연결
- `state.boardSkin`: 선택된 보드판 스킨
- `state.emoticonLoadout`: 장착한 6개 이모티콘

모바일 UI는 사용자가 항상 자신의 보드를 아래쪽 초록 진영으로 보도록 렌더링합니다.
이 변환은 화면 표시용일 뿐이며, 서버의 실제 `player 0/1` 의미를 바꾸면 안 됩니다.

### `frontend/styles.css`

PC/모바일 공용 스타일, 반응형 레이아웃, 토너먼트 대진표, 스트리머 대기열,
칭호/티어 배지, 커스터마이징 화면, 이모티콘 연출을 담당합니다.

모바일 게임 화면은 기준 stage를 두고 JavaScript가 CSS 변수로 스케일을 조정합니다.
작은 화면에서는 UI가 잘리지 않는 것을 우선으로 합니다.

## 백엔드 개요

### `server/app/game_engine.py`

티카투카의 핵심 규칙 엔진입니다.

주요 개념:

- `boards[player][field]`: 각 플레이어의 3개 필드
- `held_die`: 현재 배치해야 하는 주사위
- `rolled_dice`: 타짜의 손놀림으로 선택 가능한 주사위
- `current_player`: 현재 턴 플레이어
- `phase`: 현재 행동 단계
- `result`: 게임 종료 결과

주요 액션:

- `place_normal`
- `use_hand_trick`
- `select_die`
- `place_bonus`
- `hold`

핵심 규칙:

- 선공 첫 주사위는 실드입니다.
- 같은 라인의 상대 필드에 같은 눈이 있으면 알까기가 발생할 수 있습니다.
- 실드 주사위는 알까기 대상에서 보호됩니다.
- 보너스 주사위는 실드이며 알까기를 유발하지 않습니다.
- 승패는 필드 승수와 타이브레이크 규칙으로 결정됩니다.

### `server/app/main.py`

FastAPI 앱과 WebSocket 서버입니다.

주요 책임:

- 방 생성과 입장
- 랜덤 매칭
- 스트리머 모드 대기열
- 토너먼트 생성/배치/진행
- WebSocket snapshot 브로드캐스트
- 턴 시간/총 시간 관리
- 전적, 티어, 칭호 저장
- 관리자 API와 봇 연동 API

대표 HTTP API:

```text
GET  /health
POST /api/heartbeat
POST /api/rooms
POST /api/streamer-rooms
POST /api/tournament-rooms
POST /api/random-match
GET  /api/rooms/{code}
GET  /api/admin/random-waiting-rooms
GET  /api/admin/streamer-rooms
```

WebSocket 연결:

```text
/ws/{code}?client_id={clientId}&nickname={nickname}
```

서버가 보내는 기본 메시지는 `snapshot`입니다. 클라이언트는 snapshot을 현재 상태의
진실로 사용해야 합니다.

## 게임 모드

### 랜덤 매칭

대기 중인 랜덤 방을 찾거나 새 랜덤 방을 만듭니다. 게임 중인 랜덤 방은 매칭 대상이
아니며, 게임 종료 후에는 재대결 흐름과 재매칭 흐름을 분리해 관리합니다.

### 친선전

4자리 방 번호로 입장하는 1:1 모드입니다. 같은 상대와 다시하기를 하면 방 안 전적이
누적되고, 상대가 나가거나 교체되면 초기화됩니다.

### 스트리머 모드

방장이 1P로 고정되고, 현재 도전자가 2P가 됩니다. 나머지 참가자는 대기열에서
관전하다가 순서가 오면 자동으로 2P 자리에 들어갑니다. 진행 중에도 정원이 남아
있으면 대기열 입장이 가능합니다.

### 토너먼트 모드

방장이 토너먼트 방을 만들고 참가자를 모은 뒤, 랜덤 배치 또는 지정 배치로 대진표를
완성합니다. 배치가 끝나면 시작할 수 있고, 각 경기 결과에 따라 승자가 다음 라운드로
진출합니다.

## 티어와 칭호

티어는 브론즈부터 마스터까지 구성됩니다. 마스터 전까지는 별 기반으로 진행하고,
마스터부터는 점수제를 사용합니다. 랭킹은 티어, 등급, 별, 마스터 점수를 기준으로
계산합니다.

칭호는 사용자가 보유한 것만 선택할 수 있으며, 닉네임 앞에 표시됩니다. TOP 칭호처럼
상태에 따라 자동으로 바뀌는 칭호와, 관리자 API로 지급하는 칭호를 함께 지원합니다.

## 커스터마이징

메인 화면의 커스터마이징 메뉴에서 보드판 스킨과 장착 이모티콘을 바꿀 수 있습니다.
이모티콘은 기본 6개를 보장하고, 카탈로그에서 원하는 항목을 선택해 슬롯에 넣는
방식입니다.

커스터마이징 값은 브라우저 localStorage에 저장됩니다.

## 데이터 저장

서버는 SQLite를 사용해 유저 전적, 티어, 칭호, 일부 운영 데이터를 저장합니다.
테스트 환경에서는 기본적으로 영속 저장을 끄고, 필요한 테스트에서 별도 DB 경로를
지정합니다.

환경 변수로 조정하는 대표 값:

```text
TIKATUKA_STATS_DB
TIKATUKA_DISABLE_STATS_DB
TIKATUKA_ADMIN_SECRET
TIKATUKA_BOT_SECRET
```

비밀값은 저장소에 커밋하지 않습니다.

## 배포 메모

이 저장소의 README에는 운영 서버 주소, SSH 키 경로, 관리자 비밀값 같은 환경별
정보를 기록하지 않습니다. 배포는 각 운영 환경의 CI/CD, systemd, reverse proxy,
정적 파일 서빙 구성을 사용해 진행합니다.

배포 전에는 최소한 다음을 확인하세요.

```bash
PYTHONPATH=server .venv/bin/python -m pytest -q
PYTHONPATH=server .venv/bin/python -m compileall -q server
node --check frontend/app.js
git diff --check
```

프론트엔드 정적 파일을 교체할 때는 `frontend/index.html`의 캐시 버전도 함께
올리는 것을 권장합니다.

## 작업 시 주의사항

- 서버가 게임 상태의 진실입니다. 클라이언트 표시 로직을 서버 규칙과 섞지 마세요.
- 모바일 UI의 색상 재매핑은 렌더링 전용입니다.
- 진행 중인 게임 연결을 끊으면 패배 처리될 수 있으므로 나가기/항복/재대결 흐름을
  구분해야 합니다.
- 임시 분석 파일, 캡처 이미지, 운영 메모, 비밀값은 커밋하지 마세요.
- 큰 기능을 바꿀 때는 `tests/test_server.py`와 `tests/test_game_engine.py`에
  회귀 테스트를 추가하는 편이 안전합니다.
