# TikaTuka Multi

티카투카 2인 멀티플레이 웹 구현체입니다.
프론트엔드는 정적 HTML/CSS/JS이고, 백엔드는 FastAPI + WebSocket으로 동작합니다. 게임 판정은 서버 권위 방식이며, 클라이언트는 화면 표시와 입력 전달만 담당합니다.

현재 배포 주소:

```text
http://tikatuka.duckdns.org/
```

이 문서는 이 레포를 처음 보는 개발자나 다른 AI 에이전트가 바로 작업할 수 있도록, 폴더 구조/실행 명령/배포 절차/주의사항을 상세히 설명합니다.

티카투카 봇을 별도 환경에서 만들거나 사람과 대전시키려면
[`BOT_INTEGRATION.md`](BOT_INTEGRATION.md)의 snapshot·행동 프로토콜과 최소
WebSocket 클라이언트 예시를 먼저 확인하세요.

---

## 1. 전체 구조 요약

```text
tikatuka-multi/
├── AGENTS.md
├── BOT_INTEGRATION.md
├── README.md
├── frontend/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   ├── emoticon/
│   │   ├── gogo.png
│   │   ├── lol.png
│   │   ├── sad.png
│   │   ├── stop.png
│   │   ├── what.png
│   │   └── whatwhat.png
│   └── sound_samples/
│       ├── roll.m4a
│       ├── place.m4a
│       └── egg.m4a
├── emoticon/
│   └── 원본 이모티콘 이미지
├── server/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── app/
│       ├── __init__.py
│       ├── game_engine.py
│       └── main.py
└── tests/
    ├── test_game_engine.py
    └── test_server.py
```

핵심 책임:

- `frontend/index.html`: DOM 골격. PC/모바일 공용 요소와 모바일 전용 보드가 함께 있다.
- `frontend/styles.css`: PC판, 모바일판, 애니메이션, 이모티콘, 랭킹 배지, 사운드 UI 스타일.
- `frontend/app.js`: 클라이언트 상태, WebSocket 연결, 렌더링, 효과음, 주사위/알까기/이모티콘 FX.
- `server/app/game_engine.py`: 티카투카 게임 규칙 엔진. 주사위 생성, 배치, 알까기, 점수, 승패 판정.
- `server/app/main.py`: FastAPI 앱. 방 생성, 랜덤 매칭, WebSocket, 랭킹/전적, 타이머, 이모티콘 이벤트.
- `tests/`: 게임 규칙과 서버 동작 회귀 테스트.

---

## 2. 중요한 작업 원칙

1. 서버 반영은 사용자가 명시적으로 `서버 반영`이라고 말했을 때만 한다.
   - 평소에는 로컬 파일 수정과 테스트까지만 한다.
   - 배포는 Oracle 인스턴스의 실제 서비스에 영향을 준다.

2. 프론트 변경 시 `frontend/index.html`의 캐시 버전을 올린다.
   - 예:

     ```html
     <link rel="stylesheet" href="./styles.css?v=20260626-9" />
     <script src="./app.js?v=20260626-9"></script>
     ```

   - 모바일 브라우저 캐시가 강하게 남는 경우가 있어, `app.js`/`styles.css` 변경 시 버전을 올리는 편이 안전하다.

3. 게임 로직은 서버가 진실이다.
   - 클라이언트에서 색상이나 위치를 바꿔 보여도 서버의 `player 0/1`, `currentPlayer`, `phase`는 그대로 유지해야 한다.
   - 특히 모바일은 “내 화면에서는 항상 내가 초록, 상대가 빨강”으로 보이지만, 서버 논리상 내가 1번 플레이어일 수 있다.

4. 모바일과 PC를 구분해서 생각한다.
   - PC판은 좌/우 보드 구조.
   - 모바일판은 세로 화면 최적화 구조이며, “내 보드가 아래, 상대 보드가 위”로 보인다.
   - 모바일 렌더링은 표시용 변환이 많으므로 서버 로직과 섞으면 버그가 난다.

5. 이모티콘은 게임 액션이 아니다.
   - 턴을 소비하지 않는다.
   - 타이머/승패/게임 상태에 영향을 주지 않는다.
   - 서버 로그 이벤트로만 양쪽에 전달된다.

6. 수정 후 최소 검증:

   ```bash
   cd /home/moon/workspace/minchan/tikatuka-multi
   PYTHONPATH=server .venv/bin/python -m compileall -q server
   PYTHONPATH=server .venv/bin/python -m pytest -q
   git diff --check
   ```

---

## 3. 로컬 개발 환경

### 3-1. Python 가상환경

이 레포에는 `.venv`가 있다. 없거나 새로 만들 때:

```bash
cd /home/moon/workspace/minchan/tikatuka-multi
python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r server/requirements-dev.txt
```

### 3-2. 백엔드 실행

```bash
cd /home/moon/workspace/minchan/tikatuka-multi
PYTHONPATH=server .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

정상 확인:

```bash
curl http://127.0.0.1:8000/health
```

예상 응답:

```json
{"ok": true, "service": "tikatuka", "rooms": 0}
```

### 3-3. 프론트엔드 실행

다른 터미널에서:

```bash
cd /home/moon/workspace/minchan/tikatuka-multi
python3 -m http.server 5174 -d frontend
```

브라우저:

```text
http://127.0.0.1:5174/
```

로컬 정적 서버가 `5173` 또는 `5174` 포트에서 떠 있으면 `frontend/app.js`가 API 서버를 자동으로 `http://127.0.0.1:8000`으로 잡는다.

### 3-4. 모바일 화면 데모

백엔드 없이 모바일 레이아웃만 빠르게 볼 때:

```text
http://127.0.0.1:5174/?demo=mobile
```

헤드리스 Chrome으로 캡처 예시:

```bash
google-chrome --headless --no-sandbox --disable-gpu \
  --window-size=430,900 \
  --screenshot=/tmp/tikatuka-mobile.png \
  'http://127.0.0.1:5174/?demo=mobile'
```

---

## 4. 테스트

전체 테스트:

```bash
cd /home/moon/workspace/minchan/tikatuka-multi
PYTHONPATH=server .venv/bin/python -m pytest -q
```

서버 문법/임포트 확인:

```bash
PYTHONPATH=server .venv/bin/python -m compileall -q server
```

패치 공백 확인:

```bash
git diff --check
```

현재 주요 테스트 범위:

- 방 생성
- 두 플레이어 입장 후 게임 시작
- 선공 결정 및 첫 실드 주사위
- 랜덤 매칭
- 랜덤 매칭 방 재사용
- 상대가 나간 방 정리
- 다시하기 투표
- 랭킹/전적 저장
- 시간 초과/나가기 패배 처리
- 이모티콘 이벤트 브로드캐스트
- 게임 엔진의 알까기, 실드, 홀드, 점수 판정

---

## 5. 프론트엔드 상세

### 5-1. `frontend/index.html`

역할:

- PC 상단 플레이어 카드
- 로비/랭킹/내 점수
- 방 패널
- PC 보드
- 모바일 전용 보드
- 사운드 패널

주의:

- 모바일 전용 DOM은 `.mobile-game` 안에 있다.
- PC 보드는 `.board-wrap` 안에 있다.
- 모바일에서는 CSS media query로 PC 보드를 숨기고 `.mobile-game`을 보여준다.
- 캐시 무효화를 위해 `styles.css?v=...`, `app.js?v=...` 버전을 관리한다.

### 5-2. `frontend/app.js`

주요 상태:

- `state.clientId`: 브라우저 localStorage에 저장되는 사용자 식별자.
- `state.ws`: WebSocket 연결.
- `state.snapshot`: 서버에서 받은 최신 방/게임 상태.
- `state.leaveReserved`: 게임 중 나가기 예약 여부. 예약 중에는 WebSocket을 닫지 않는다.
- `state.emoticonPickerPlayer`: 현재 열린 이모티콘 선택창의 플레이어.
- `fx.seenEvents`: 이미 처리한 서버 로그 이벤트 추적.

서버 주소 결정:

- `window.TIKATUKA_SERVER_URL`이 있으면 그것을 사용.
- `file://`이면 `http://tikatuka.duckdns.org`.
- localhost `5173/5174`이면 `http://127.0.0.1:8000`.
- 그 외에는 현재 origin 사용.

중요한 함수:

- `connectRoom(code, options)`: WebSocket 연결.
- `randomMatch()`: 랜덤 매칭 API 호출 후 방 연결.
- `render()`: 전체 렌더링 진입점.
- `renderBoard(game)`: PC 보드.
- `renderMobile(room, game, you)`: 모바일 보드.
- `renderTrays(game)`: PC 트레이.
- `renderMobileTray(room, game, you, me)`: 모바일 트레이. 상대 턴에는 상대 주사위도 표시한다.
- `renderClocks(room, game)`: PC의 턴 시간/총 시간 UI를 갱신한다.
- `renderMobileClocks(room, game, me, opponent)`: 모바일의 턴 시간/총 시간 UI를 갱신한다.
- `clockValues(player)`: 마지막 서버 snapshot 이후의 경과 시간을 반영해 화면용 두 시계를 계산한다.
- `sendAction(action, payload)`: 게임 액션 전송.
- `sendEmoticon(emoticon)`: 이모티콘 이벤트 전송.
- `requestLeave()`: 나가기 버튼 처리. 게임 중이면 예약만 하고, 게임 종료 후 자동으로 로비로 나간다.
- `processFx(snapshot)`: 서버 로그 이벤트를 보고 연출 실행.
- `showEmoticon(player, emoticon)`: PC/모바일 이모티콘 표시.

모바일 표시 원칙:

- 서버 논리상 `player 0`은 초록, `player 1`은 빨강이지만, 모바일 UI에서는 “나=초록, 상대=빨강”으로 재매핑한다.
- 그래서 `renderDie(..., { ownerOverride })`가 있다.
- 이 로직을 서버 게임 상태에 반영하면 안 된다. 오직 렌더링용이다.

애니메이션 중복 방지:

- 서버는 최근 이벤트 로그를 내려준다.
- 입장 직후 오래된 이벤트까지 모두 재생하면 주사위/알까기 연출이 폭주한다.
- 그래서 `primeExistingFxEvents()`가 첫 snapshot에서 과거 이벤트를 `seenEvents`에 미리 넣는다.
- 모바일에서는 0.5초 시계 갱신 루프가 `renderMobile()` 전체를 계속 호출하면 주사위 DOM이 재생성되어 CSS 애니메이션이 반복 재생될 수 있다.
- 그래서 `Date.now() < fx.animatingUntil`인 동안에는 모바일 전체 리렌더 대신 `renderMobileClocks()`만 호출한다.

나가기 예약:

- 게임 중 `나가기`를 누르면 즉시 WebSocket을 닫지 않고 버튼을 `나가기 예약중`으로 바꾼다.
- 이후 `game.result`가 생기면 클라이언트가 로비로 이동한다.
- 이 동작은 탈주 패배가 아니다. 브라우저/탭을 닫거나 연결이 끊기는 경우에는 기존처럼 서버가 탈주 패배를 처리한다.
- 따라서 `requestLeave()`를 우회해서 게임 중 `returnToLobby()`를 직접 호출하면 안 된다.

시간 UI:

- 각 플레이어마다 위쪽 `턴 시간`, 아래쪽 `총 시간`을 표시한다.
- 현재 턴의 첫 15초에는 `턴 시간`만 활성 강조한다.
- 턴 시간이 0초가 된 뒤에는 `총 시간`만 활성 강조한다.
- PC는 보드 아래 좌우에 각각 두 줄로 표시하고, 모바일은 하단 나가기 버튼 좌우에 각각 두 줄로 표시한다.
- 화면의 0.5초 갱신은 표시를 부드럽게 하기 위한 것이며 승패 판정의 진실은 서버다.

### 5-3. `frontend/styles.css`

주요 영역:

- 기본 레이아웃/테이블 배경
- 로비/랭킹
- PC 플레이어 카드/트레이/보드
- 모바일 카드/보드/트레이/시간
- 주사위 UI
- 실드/알까기/던지기/배치 애니메이션
- 이모티콘 팝업/이모티콘 띠용 애니메이션
- 반응형 media query

이모티콘 관련 클래스:

- `.emoticon-control`
- `.emoticon-picker`
- `.emoticon-choice`
- `.pc-emoticon-picker`: PC판에서는 트레이 옆에 세로 한 줄로 표시한다.
- `.mobile-emoticon-picker`: 모바일판에서는 컨트롤 독 위에 뜨며, 컨트롤 독 `overflow`에 잘리지 않아야 한다.
- `.pc-emoticon-burst`
- `.mobile-card-emoticon`
- `@keyframes emoticonBoing`
- `@keyframes mobileEmoticonBoing`

랭킹 배지:

- `.rank-badge`

모바일 폭:

- 기준 stage는 `390 x 844`.
- JS가 `--mobile-stage-scale`, `--mobile-stage-width` CSS 변수를 설정한다.
- 작은 화면에서는 잘리지 않는 것이 최우선이고, 넓은 화면에서는 가능한 만큼 가로를 더 쓴다.

---

## 6. 백엔드 상세

### 6-1. `server/app/game_engine.py`

서버 권위 게임 엔진이다. 클라이언트가 보낸 액션은 이 엔진을 통과해야만 게임 상태가 바뀐다.

주요 개념:

- `boards[player][field]`: 각 플레이어의 3개 필드.
- `held_die`: 현재 배치해야 하는 주사위.
- `rolled_dice`: 타짜의 손놀림으로 2개 중 선택해야 할 때 사용.
- `current_player`: 현재 턴 플레이어.
- `phase`:
  - `place_normal`
  - `select_die`
  - `place_bonus`
  - `game_over`
- `hand_trick_used`: 타짜의 손놀림 사용 여부.
- `holding`: 홀드 여부.

액션:

- `use_hand_trick`
- `select_die`
- `hold`
- `place_normal`
- `place_bonus`

중요한 규칙:

- 선공 첫 주사위는 실드.
- 알까기 대상은 동일 라인의 상대 필드.
- 상대 동일 숫자 중 실드가 아닌 주사위가 있을 때만 알까기 발생.
- 보너스 주사위는 실드이며 알까기를 유발하지 않는다.
- 홀드하면 이후 자신의 턴은 스킵된다.
- 최종 승패는 먼저 필드 승수로 판정한다.
- 정확히 `1승·1무·1패`이면 각 플레이어가 이긴 라인의 **점수 자체가 아니라 점수 차**를 비교한다.
  - 예: A는 `17:12`로 이겨 승리 점수 차가 5점, B는 `15:8`로 이겨 승리 점수 차가 7점이면 B 승리.
  - 승리 점수 차도 같으면 최종 무승부다.
- `evaluate_result()` 결과의 `tiebreakScores`는 각자의 승리 라인 점수, `tiebreakMargins`는 실제 승패 판정에 사용하는 승리 점수 차다.

### 6-2. `server/app/main.py`

FastAPI 앱과 WebSocket 서버다.

HTTP API:

- `GET /health`
  - 서버 상태 확인.
- `POST /api/heartbeat`
  - 접속자 수/내 전적/랭킹 갱신.
- `GET /api/status`
  - 상태 조회.
- `POST /api/rooms`
  - 4자리 방 생성.
- `POST /api/streamer-rooms`
  - 방송인 1P 고정 방과 1~10명 대기열 생성.
- `POST /api/random-match`
  - 랜덤 매칭.
- `GET /api/rooms/{code}`
  - 방 존재 여부 확인.

WebSocket:

```text
/ws/{code}?client_id={clientId}&nickname={nickname}
```

클라이언트 → 서버 메시지:

```json
{"type": "action", "action": "place_normal", "field": 0}
{"type": "action", "action": "place_bonus", "targetPlayer": 1, "field": 2}
{"type": "action", "action": "use_hand_trick"}
{"type": "action", "action": "select_die", "index": 0}
{"type": "action", "action": "hold"}
{"type": "restart"}
{"type": "ready"}
{"type": "kick_opponent"}
{"type": "timeout_check"}
{"type": "emoticon", "emoticon": "lol"}
{"type": "waiting_emoticon", "emoticon": "lol"}
```

서버 → 클라이언트:

- 기본은 `snapshot`.
- 방 종료 시 `room_closed`.
- 문제 발생 시 `error`.

`snapshot`에는 다음이 포함된다.

- `room`: 방 정보, 플레이어 정보, 랭킹/전적, 타이머, 다시하기 투표 수, 방송인 대기열.
- `you`: 현재 접속자의 player index와 방송인 모드 대기 순서.
- `game`: 게임 엔진 상태.
- `log`: 최근 이벤트 로그.

### 6-3. 턴 시간과 총 시간

시간 규칙은 `server/app/main.py`의 `Room`이 서버 권위로 관리한다.

- `TURN_TIME_SECONDS = 15`
- `TOTAL_TIME_SECONDS = 60`
- 자기 턴이 시작될 때마다 해당 플레이어의 턴 시간이 15초로 초기화된다.
- 15초가 남아 있는 동안에는 총 시간이 줄지 않는다.
- 턴 시간이 0초가 된 뒤부터 해당 플레이어의 총 시간에서 초과분을 차감한다.
- 총 시간이 0초가 되면 `force_loss(player, "timeout")`로 시간패 처리한다.
- 타짜의 손놀림과 주사위 선택처럼 같은 턴 안에서 이어지는 행동은 턴 시간을 초기화하지 않는다.
- 일반 배치 완료, 보너스 배치 완료, 홀드처럼 다음 턴이 시작되는 경우에만 초기화한다.
- 상대가 홀드하거나 필드가 가득 차서 같은 플레이어가 연속으로 행동하더라도 새 턴이면 15초를 다시 준다.

관련 `Room` 필드:

- `turn_clocks`: 각 플레이어의 현재 턴 시간.
- `clocks`: 각 플레이어의 남은 총 시간. 이전 클라이언트와의 호환을 위해 이름을 유지한다.
- `clock_player`: 현재 시간이 흐르는 플레이어.
- `clock_started_at`: 마지막 서버 확정 시각.

snapshot의 `room` 타이머 필드:

```json
{
  "turnClocks": [15.0, 8.2],
  "totalClocks": [60.0, 54.7],
  "clocks": [60.0, 54.7],
  "clockPlayer": 1,
  "clockUpdatedAt": 1782500000.0,
  "turnTimeSeconds": 15,
  "totalTimeSeconds": 60
}
```

`clocks`는 `totalClocks`와 같은 값인 하위 호환 필드다. 새 코드는 의미가 분명한 `turnClocks`와 `totalClocks`를 우선 사용한다.

시간 처리 흐름:

1. 게임 시작 또는 새 턴 시작 시 `arm_clock(reset_turn=True)`를 호출한다.
2. 클라이언트 행동을 적용하기 전에 `charge_clock()`가 서버 경과 시간을 확정한다.
3. 경과 시간은 먼저 `turn_clocks`에서 빼고 남은 초과분만 `clocks`에서 뺀다.
4. 행동 결과 이벤트에 `die_rolled`가 있으면 새 턴으로 보고 턴 시간을 15초로 재설정한다.
5. 브라우저는 총 시간이 0으로 보이면 `{"type": "timeout_check"}`를 전송한다.
6. 상대 클라이언트도 같은 snapshot을 기준으로 검사하므로 현재 플레이어가 버튼을 누르지 않아도 시간패를 요청할 수 있다.

타이머를 수정할 때는 적어도 다음 회귀 테스트를 유지해야 한다.

- 15초 이내에는 총 시간이 줄지 않는다.
- 15초 초과분만 총 시간에서 줄어든다.
- 새 턴에는 15초가 복구된다.
- 같은 플레이어의 연속 턴에도 15초가 복구된다.
- 총 시간 0초에는 `timeout_loss`와 `game_finished`가 한 번씩 발생한다.

랜덤 매칭 주의:

- 랜덤 방은 게임 중에는 매칭 풀에 잡히면 안 된다.
- 게임이 끝나거나 상대가 나간 뒤 남은 플레이어가 있으면 다시 대기방으로 돌아간다.
- 이때 이전 게임 로그는 지워야 한다. 지우지 않으면 새 입장자가 과거 주사위/알까기 애니메이션을 한꺼번에 본다.

일반 방과 방송인 모드:

- 일반 방의 방장은 게임 종료 후 상대를 내보내고 같은 방 번호를 유지할 수 있다.
- 게스트가 나가면 닉네임, 보드, 타이머, 다시하기 상태를 비우고 새 게스트를 받는다.
- 일반 방의 현재 상대 전적은 같은 상대와 재대결할 때만 누적하고, 게스트가 나가면 `0 : 0`으로 초기화한다.
- 방송인 모드는 생성자의 `clientId`를 1P로 예약하고 현재 도전자만 2P가 된다.
- 추가 참가자는 최대 10명까지 FIFO 대기열에서 관전하며 게임 중에도 입장할 수 있다.
- 방송인만 준비 버튼을 누르면 현재 도전자와 게임이 시작되며, 도전자에게는 준비 버튼을 표시하지 않는다.
- 방송인 방의 현재 상대 전적도 재대결에는 누적하고, 도전자가 교체되면 `0 : 0`으로 초기화한다.
- 도전자가 나가거나 방장이 내보내면 대기열 첫 사람이 2P로 승격되고 라운드 상태를 초기화한다.
- 대기자는 게임 액션을 보낼 수 없고 `waiting_emoticon`만 사용할 수 있다.
- PC 방송인 화면의 대기자 목록은 게임판 오른쪽 전용 영역, 대기자 이모티콘은 시계 아래 전용 영역에 표시한다.
- 모바일 방송인 화면은 대기자 수를 작은 `👥 숫자` 버튼으로 표시하고, 버튼을 누른 동안에만 전체 대기자 목록을 연다.

랭킹/전적:

- 랜덤 매칭 결과만 랭킹에 반영한다.
- 승리: 기본 `+10`, 연승 가중치 추가.
- 패배: 기본 `-10`, 연패 가중치 추가. 최저 점수는 `0`.
- Top20 안에 들면 서버가 `rank` 값을 stats에 포함한다.

전적 저장:

- SQLite 사용.
- 로컬 기본 경로:

  ```text
  /home/moon/workspace/minchan/tikatuka-data/tikatuka_stats.sqlite3
  ```

- Oracle 배포 기본 경로는 코드 위치 기준으로 보통:

  ```text
  /home/ubuntu/apps/tikatuka-data/tikatuka_stats.sqlite3
  ```

- 테스트에서는 기본적으로 DB 저장을 꺼두고, 필요한 테스트에서 `TIKATUKA_STATS_DB`를 별도로 지정한다.

---

## 7. 이모티콘 시스템

원본:

```text
emoticon/
```

프론트에서 실제로 서빙하는 정규화본:

```text
frontend/emoticon/
```

현재 이모티콘:

- `gogo`
- `lol`
- `sad`
- `stop`
- `what`
- `whatwhat`

서버 허용 목록:

```python
ALLOWED_EMOTICONS = {"gogo", "lol", "sad", "stop", "what", "whatwhat"}
```

추가 절차:

1. 원본 이미지를 `emoticon/`에 추가.
2. `frontend/emoticon/`에 100x100 PNG로 정규화해서 추가.
3. `frontend/app.js`의 `EMOTICONS` 배열에 추가.
4. `server/app/main.py`의 `ALLOWED_EMOTICONS`에 추가.
5. 필요하면 테스트 추가.

UX 규칙:

- PC판 이모티콘 선택창은 트레이 옆에 세로 한 줄로 배치한다.
- 모바일판 이모티콘 선택창은 컨트롤 독 위쪽에 뜬다. 모바일 화면 제약상 다른 UI 일부를 가려도 괜찮지만, 선택창 자체가 잘리면 안 된다.
- 이모티콘을 하나 보내도 선택창은 닫히지 않는다.
- 선택창은 `이모티콘` 버튼을 다시 눌러 닫는다.
- 이모티콘 이미지는 클릭/터치/드래그 대상이 아니어야 한다. 게임 조작을 방해하면 안 된다.

이미지 정규화 예시:

```bash
cd /home/moon/workspace/minchan/tikatuka-multi
python3 - <<'PY'
from pathlib import Path
from PIL import Image

source = Path("emoticon")
target = Path("frontend/emoticon")
target.mkdir(parents=True, exist_ok=True)

for path in sorted(source.glob("*.png")):
    image = Image.open(path).convert("RGBA")
    if image.size != (100, 100):
        image = image.resize((100, 100), Image.Resampling.LANCZOS)
    image.save(target / path.name)
    print(path.name, image.size)
PY
```

---

## 8. 사운드

사운드 파일:

```text
frontend/sound_samples/
├── roll.m4a
├── place.m4a
└── egg.m4a
```

현재 사용:

- `roll`: 주사위 굴림.
- `place`: 주사위 배치.
- `egg`: 알까기.

브라우저 정책상 사용자 입력 전에는 오디오 재생이 막힐 수 있다.
`app.js`는 첫 클릭/터치 때 오디오 unlock을 시도한다.

---

## 9. 배포 구조

현재 Oracle Always Free 인스턴스:

```text
Public IPv4: 161.33.14.219
Domain:      tikatuka.duckdns.org
SSH key:     /home/moon/workspace/minchan/tikatuka/ssh-key-2026-06-25.key
```

원격 경로:

```text
/var/www/tikatuka-multi          # Caddy가 서빙하는 정적 프론트
/home/ubuntu/apps/tikatuka-multi/server       # FastAPI 서버 코드
```

Caddy 구조:

```caddy
:80 {
    root * /var/www/tikatuka-multi

    handle /api/* {
        reverse_proxy 127.0.0.1:8000
    }

    handle /ws/* {
        reverse_proxy 127.0.0.1:8000
    }

    handle /health {
        reverse_proxy 127.0.0.1:8000
    }

    file_server
}
```

FastAPI는 systemd 서비스로 실행된다. 서비스명은 현재 관례상:

```text
tikatuka
```

---

## 10. 서버 반영 절차

반드시 로컬 검증 후 진행한다.

```bash
cd /home/moon/workspace/minchan/tikatuka-multi

PYTHONPATH=server .venv/bin/python -m compileall -q server
PYTHONPATH=server .venv/bin/python -m pytest -q
git diff --check
```

프론트 배포:

`/var/www/tikatuka-multi`는 Caddy가 소유하고 있어 `ubuntu` 사용자가 직접 덮어쓸 수 없다.
따라서 먼저 `/tmp`로 올린 뒤 원격에서 `sudo rsync`로 반영한다.

```bash
rsync -az --delete \
  -e "ssh -i /home/moon/workspace/minchan/tikatuka/ssh-key-2026-06-25.key" \
  frontend/ ubuntu@161.33.14.219:/tmp/tikatuka-multi-frontend/

ssh -i /home/moon/workspace/minchan/tikatuka/ssh-key-2026-06-25.key ubuntu@161.33.14.219 \
  "sudo rsync -az --delete /tmp/tikatuka-multi-frontend/ /var/www/tikatuka-multi/ && sudo chown -R caddy:caddy /var/www/tikatuka-multi"
```

백엔드 배포:

```bash
rsync -az --delete --exclude ".venv/" --exclude "__pycache__/" \
  -e "ssh -i /home/moon/workspace/minchan/tikatuka/ssh-key-2026-06-25.key" \
  server/ ubuntu@161.33.14.219:/home/ubuntu/apps/tikatuka-multi/server/
```

README도 원격 작업 디렉터리에 남기고 싶다면:

```bash
scp -i /home/moon/workspace/minchan/tikatuka/ssh-key-2026-06-25.key \
  README.md ubuntu@161.33.14.219:/home/ubuntu/apps/tikatuka-multi/README.md
```

서버 재시작:

```bash
ssh -i /home/moon/workspace/minchan/tikatuka/ssh-key-2026-06-25.key ubuntu@161.33.14.219 \
  "cd /home/ubuntu/apps/tikatuka-multi/server && .venv/bin/python -m pip install -r requirements.txt && sudo systemctl restart tikatuka && sudo systemctl status tikatuka --no-pager"
```

배포 후 확인:

```bash
curl -I http://tikatuka.duckdns.org/
curl http://tikatuka.duckdns.org/health
```

로그 확인:

```bash
ssh -i /home/moon/workspace/minchan/tikatuka/ssh-key-2026-06-25.key ubuntu@161.33.14.219 \
  "sudo journalctl -u tikatuka -n 120 --no-pager"
```

---

## 11. 흔한 문제와 해결

### 11-1. 모바일에서 예전 애니메이션이 한꺼번에 재생됨

원인 후보:

- 서버 랜덤방 재사용 시 이전 `room.log`가 남아 있음.
- 클라이언트가 첫 snapshot의 과거 로그를 새 이벤트로 처리함.
- 모바일 시계 갱신 루프가 애니메이션 중 `renderMobile()` 전체를 다시 호출해 DOM을 재생성함.

확인 지점:

- `server/app/main.py`의 `prepare_random_room_for_waiting()`에서 `room.log.clear()`가 있는지.
- `frontend/app.js`의 `primeExistingFxEvents()`가 첫 snapshot에서 과거 이벤트를 seen 처리하는지.
- `frontend/app.js` 하단 interval에서 `Date.now() < fx.animatingUntil`일 때 `renderMobileClocks()`만 호출하는지.

### 11-2. 모바일에서 내가 빨강으로 보임

원인:

- 서버 player index를 그대로 모바일 색상에 사용함.

확인 지점:

- 모바일 렌더링에서는 `mobileVisualOwner()`와 `ownerOverride`를 사용해야 한다.
- 서버의 실제 player index는 절대 바꾸면 안 된다.

### 11-3. 랜덤 매칭에서 상대가 나간 방에 들어감

확인 지점:

- `random_waiting_player_alive()`
- `is_joinable_random_room()`
- `cleanup_rooms()`

### 11-4. WebSocket 연결 실패

확인:

```bash
curl http://tikatuka.duckdns.org/health
sudo systemctl status tikatuka --no-pager
sudo journalctl -u tikatuka -n 120 --no-pager
sudo systemctl status caddy --no-pager
```

브라우저 콘솔에서 `ws://.../ws/{code}` 연결이 막히는지 확인한다.

### 11-5. 프론트 변경했는데 브라우저에 반영 안 됨

확인:

- `frontend/index.html`의 `?v=...`가 올라갔는지.
- Caddy 정적 파일 경로 `/var/www/tikatuka-multi`에 새 파일이 들어갔는지.
- 모바일 브라우저 캐시 삭제 또는 강제 새로고침.

### 11-6. 랭킹/전적이 서버 재시작 후 사라짐

확인:

- SQLite 파일이 생성되는지.
- systemd 서비스 유저가 DB 디렉터리에 쓸 권한이 있는지.
- 원격 기본 경로가 `/home/ubuntu/apps/tikatuka-data/tikatuka_stats.sqlite3`인지.

---

## 12. Git 작업 시 참고

현재 이 레포는 사용자가 직접 실험 중인 작업물이 많을 수 있다.
다른 에이전트가 작업할 때는 다음을 지킨다.

- `git reset --hard`, `git checkout --` 같은 파괴적 명령 금지.
- 사용자가 요청하지 않은 서버 반영 금지.
- 변경 전 `git status --short`로 현재 수정 상태 확인.
- 테스트를 돌리고 결과를 보고.
- 배포가 필요한 경우 어떤 파일을 서버에 반영했는지 명확히 보고.

---

## 13. 빠른 작업 체크리스트

작업 시작:

```bash
cd /home/moon/workspace/minchan/tikatuka-multi
git status --short
```

로컬 서버:

```bash
PYTHONPATH=server .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
python3 -m http.server 5174 -d frontend
```

테스트:

```bash
PYTHONPATH=server .venv/bin/python -m pytest -q
PYTHONPATH=server .venv/bin/python -m compileall -q server
git diff --check
```

배포:

```bash
rsync -az --delete -e "ssh -i /home/moon/workspace/minchan/tikatuka/ssh-key-2026-06-25.key" frontend/ ubuntu@161.33.14.219:/tmp/tikatuka-multi-frontend/
ssh -i /home/moon/workspace/minchan/tikatuka/ssh-key-2026-06-25.key ubuntu@161.33.14.219 "sudo rsync -az --delete /tmp/tikatuka-multi-frontend/ /var/www/tikatuka-multi/ && sudo chown -R caddy:caddy /var/www/tikatuka-multi"
rsync -az --delete --exclude ".venv/" --exclude "__pycache__/" -e "ssh -i /home/moon/workspace/minchan/tikatuka/ssh-key-2026-06-25.key" server/ ubuntu@161.33.14.219:/home/ubuntu/apps/tikatuka-multi/server/
ssh -i /home/moon/workspace/minchan/tikatuka/ssh-key-2026-06-25.key ubuntu@161.33.14.219 "cd /home/ubuntu/apps/tikatuka-multi/server && .venv/bin/python -m pip install -r requirements.txt && sudo systemctl restart tikatuka && sudo systemctl status tikatuka --no-pager"
```
