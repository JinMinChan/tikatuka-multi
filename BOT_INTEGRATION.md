# TikaTuka Bot Integration Guide

이 문서는 티카투카 봇을 만드는 개발자나 AI 에이전트가 현재 멀티플레이 서버에
플레이어 클라이언트로 연결하는 데 필요한 구조와 프로토콜을 정리한다.

봇 개발 환경은 운영 Oracle 서버와 분리한다. 예제의 기본 주소는 항상
`http://127.0.0.1:8000`이며, 운영 주소를 코드에 하드코딩하지 않는다.

## 1. 봇이 알아야 할 파일

- `server/app/game_engine.py`
  - 순수 게임 규칙에 가장 가까운 코드다.
  - `GameEngine.snapshot()`이 관측 상태를 만든다.
  - `GameEngine.apply_action(player, payload)`가 행동을 검증하고 적용한다.
  - 점수와 최종 승패는 `score_field()`와 `evaluate_result()`에서 판정한다.
- `server/app/main.py`
  - 방, 플레이어 자리, WebSocket, 타이머, 재대결과 연결 종료를 관리한다.
  - 네트워크 봇은 이 서버가 보내는 snapshot만 현재 상태의 진실로 사용해야 한다.
- `tests/test_game_engine.py`
  - 알까기, 실드, 보너스, 더블·트리플 점수와 타이브레이크 예시가 있다.
- `tests/test_server.py`
  - 실제 HTTP/WebSocket 방 수명주기와 타이머 동작 예시가 있다.
- `frontend/app.js`
  - 사람용 클라이언트 구현 참고 자료다. 봇 판단 로직을 여기에 넣을 필요는 없다.

## 2. 권장 사람 대 봇 실행 흐름

백엔드를 로컬에서 실행한다.

```bash
PYTHONPATH=server .venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000
```

사람이 브라우저 UI도 사용할 경우 별도 터미널에서 프론트엔드를 실행한다.

```bash
python3 -m http.server 5174 -d frontend
```

권장 대전 흐름은 다음과 같다.

1. 사람이 `http://127.0.0.1:5174/`에서 일반 방을 만든다.
2. 표시된 숫자 4자리 방 번호를 봇 프로세스에 전달한다.
3. 봇이 WebSocket으로 접속하면 자동으로 빈 플레이어 자리를 받는다.
4. 두 플레이어가 연결되면 일반 방은 자동으로 게임을 시작한다.

반대로 봇이 먼저 방을 만들 수도 있다.

```http
POST http://127.0.0.1:8000/api/rooms
```

응답:

```json
{"code": "1234"}
```

그 뒤 봇이 먼저 WebSocket에 연결하고, 사람은 UI에서 `1234`를 입력해 입장한다.

## 3. WebSocket 연결

```text
ws://127.0.0.1:8000/ws/{code}?client_id={clientId}&nickname={nickname}
```

- `client_id`
  - 필수이며 최대 80자다.
  - 한 봇 인스턴스가 재접속할 때는 같은 값을 유지하는 편이 좋다.
- `nickname`
  - 공백 정리 후 최대 16자만 사용한다.
- 일반 방은 최대 2명이며 먼저 연결한 클라이언트부터 빈 자리를 받는다.
- 연결 종료는 진행 중인 게임에서 기권패가 될 수 있다.

서버가 보내는 메시지는 세 종류다.

- `snapshot`: 현재 전체 상태
- `error`: 잘못된 행동 또는 현재 상태에서 허용되지 않는 요청
- `room_closed`: 방이 종료됐거나 내보내기 된 상태

## 4. snapshot 구조

축약 예시:

```json
{
  "type": "snapshot",
  "room": {
    "code": "1234",
    "started": true,
    "players": [
      {"index": 0, "name": "Human", "occupied": true, "connected": true},
      {"index": 1, "name": "Bot", "occupied": true, "connected": true}
    ],
    "randomMatch": false,
    "streamerMode": false,
    "friendlyScore": [0, 0],
    "turnClocks": [15.0, 15.0],
    "totalClocks": [60.0, 60.0],
    "clockPlayer": 1
  },
  "you": {
    "clientId": "my-bot-id",
    "player": 1,
    "spectator": false,
    "queuePosition": null
  },
  "game": {
    "boards": [[[], [], []], [[], [], []]],
    "currentPlayer": 1,
    "phase": "place_normal",
    "handTrickUsed": [false, false],
    "holding": [false, false],
    "rolledDice": [],
    "heldDie": {"id": 1, "value": 4, "shield": true, "owner": 1},
    "scores": [[0, 0, 0], [0, 0, 0]],
    "result": null
  },
  "log": []
}
```

판단할 때 특히 중요한 값:

- `you.player`: 봇의 실제 서버 player index. `0` 또는 `1`이다.
- `room.started`: `false`면 게임 행동을 보내지 않는다.
- `game.currentPlayer`: 현재 행동할 player index다.
- `game.phase`: 지금 허용되는 행동 종류다.
- `game.boards[player][field]`: 각 플레이어의 3개 필드. 필드당 최대 주사위 3개다.
- `game.heldDie`, `game.rolledDice`: 현재 배치 또는 선택할 주사위다.
- `game.result`: 값이 생기면 게임이 끝난 것이다.

모바일 UI는 사람에게 자기 진영을 항상 초록색으로 보이게 변환하지만, 봇은 색상을
기준으로 판단하면 안 된다. 항상 `you.player`와 서버 player index를 사용한다.

## 5. 행동 프로토콜

모든 게임 행동은 다음 외형을 사용한다.

```json
{"type": "action", "action": "행동 이름"}
```

| phase | 행동 | 추가 값 | 조건 |
|---|---|---|---|
| `place_normal` | `place_normal` | `field: 0..2` | 자기 필드의 빈 자리에 현재 `heldDie` 배치 |
| `place_normal` | `use_hand_trick` | 없음 | 게임당 한 번, 현재 주사위와 다른 눈 하나를 추가로 굴림 |
| `select_die` | `select_die` | `index` | `rolledDice` 중 사용할 주사위 선택 |
| `place_normal`, `select_die` | `hold` | 없음 | 현재 주사위를 버리고 이후 자신의 모든 턴을 포기 |
| `place_bonus` | `place_bonus` | `targetPlayer`, `field` | 어느 플레이어 필드든 빈 자리에 보너스 실드 배치 |

메시지 예시:

```json
{"type": "action", "action": "place_normal", "field": 2}
{"type": "action", "action": "use_hand_trick"}
{"type": "action", "action": "select_die", "index": 0}
{"type": "action", "action": "hold"}
{"type": "action", "action": "place_bonus", "targetPlayer": 1, "field": 0}
```

주사위 굴리기 행동은 따로 없다. 서버가 게임 시작과 새 턴 시작 시 자동으로
주사위를 굴리고 다음 snapshot에 `heldDie`를 넣는다.

게임 종료 후 같은 상대와 재대결하려면 양쪽 모두 다음 메시지를 보낸다.

```json
{"type": "restart"}
```

방송인 모드에서는 1P 방송인만 다음 메시지를 보내면 현재 도전자와 게임이
시작된다. 2P 도전자는 준비 메시지를 보낼 필요가 없으며 서버도 이를 거부한다.

```json
{"type": "ready"}
```

## 6. 최소 봇 루프

개발 의존성을 설치하면 `websockets`를 사용할 수 있다.

```bash
.venv/bin/python -m pip install -r server/requirements-dev.txt
```

아래 예시는 가장 높은 눈을 선택하고, 자기 필드 중 첫 빈 필드에 배치하는 단순
클라이언트 골격이다. 전략 봇은 `choose_action()`만 교체하면 된다.

```python
import asyncio
import json
import os
import urllib.parse

from websockets.asyncio.client import connect


WS_BASE = os.getenv("TIKATUKA_WS_URL", "ws://127.0.0.1:8000")


def choose_action(snapshot):
    room = snapshot["room"]
    game = snapshot["game"]
    me = snapshot["you"]["player"]
    if (
        me not in (0, 1)
        or not room["started"]
        or game["result"] is not None
        or game["currentPlayer"] != me
    ):
        return None

    phase = game["phase"]
    if phase == "select_die":
        dice = game["rolledDice"]
        index = max(range(len(dice)), key=lambda idx: dice[idx]["value"])
        return {"type": "action", "action": "select_die", "index": index}

    if phase == "place_normal":
        legal_fields = [
            field for field in range(3) if len(game["boards"][me][field]) < 3
        ]
        if legal_fields:
            return {
                "type": "action",
                "action": "place_normal",
                "field": legal_fields[0],
            }

    if phase == "place_bonus":
        legal_targets = [
            (player, field)
            for player in range(2)
            for field in range(3)
            if len(game["boards"][player][field]) < 3
        ]
        if legal_targets:
            player, field = legal_targets[0]
            return {
                "type": "action",
                "action": "place_bonus",
                "targetPlayer": player,
                "field": field,
            }
    return None


async def play(room_code):
    client_id = "local-example-bot"
    nickname = "ExampleBot"
    query = urllib.parse.urlencode(
        {"client_id": client_id, "nickname": nickname}
    )
    uri = f"{WS_BASE}/ws/{room_code}?{query}"
    last_decision_state = None

    async with connect(uri) as websocket:
        async for raw_message in websocket:
            message = json.loads(raw_message)
            if message["type"] == "error":
                print("server error:", message["message"])
                continue
            if message["type"] == "room_closed":
                print("room closed:", message["message"])
                return
            if message["type"] != "snapshot":
                continue

            game = message["game"]
            decision_state = json.dumps(
                {
                    "player": message["you"]["player"],
                    "currentPlayer": game["currentPlayer"],
                    "phase": game["phase"],
                    "boards": game["boards"],
                    "heldDie": game["heldDie"],
                    "rolledDice": game["rolledDice"],
                    "result": game["result"],
                },
                sort_keys=True,
            )
            if decision_state == last_decision_state:
                continue

            action = choose_action(message)
            if action is not None:
                last_decision_state = decision_state
                await websocket.send(json.dumps(action))


if __name__ == "__main__":
    import sys

    asyncio.run(play(sys.argv[1]))
```

같은 snapshot에 같은 행동을 중복 전송하지 않도록 상태 fingerprint나
`action_pending` 플래그를 반드시 둔다. 서버에서 `error`가 오면 현재 snapshot을
다시 확인하고 무작정 같은 행동을 반복하지 않는다.

## 7. 핵심 게임 규칙

- 보드에는 플레이어마다 3개 필드가 있고 각 필드에는 주사위가 최대 3개 들어간다.
- 같은 눈 2개는 기본 합에 눈 값 1개분을 더하고, 3개는 눈 값 2개분을 더한다.
- 내 일반 주사위를 놓은 라인의 상대 필드에 같은 눈의 일반 주사위가 있으면
  알까기로 해당 일반 주사위를 제거한다.
- 상대의 같은 눈 실드는 제거되지 않는다.
- 알까기가 발생하면 방금 놓은 주사위도 사라지고 보너스 실드 주사위를 받는다.
- 보너스 실드는 어느 플레이어의 빈 필드에도 둘 수 있고 추가 알까기를 만들지 않는다.
- 선공 플레이어의 첫 주사위는 실드다.
- 최종 승패는 3개 필드의 승리 개수로 우선 판정한다.
- 정확히 `1승·1무·1패`이면 각자 이긴 필드의 점수 차가 큰 쪽이 이긴다.
- 점수 차도 같으면 무승부다.

권위 판정은 항상 서버가 한다. 봇 내부 시뮬레이터가 다른 결과를 내더라도 실제
대전에서는 서버 snapshot과 `game.result`를 따라야 한다.

## 8. 타이머와 운영상 주의

- 새 턴마다 턴 시간 15초가 주어진다.
- 턴 시간 소진 후부터 개인 총 시간 60초가 차감된다.
- 총 시간이 0이면 시간패다.
- 네트워크 봇은 snapshot을 받은 즉시 비동기 추론을 시작하고 제한 시간 전에
  행동을 보내야 한다.
- 긴 모델 추론은 별도 worker에서 수행하고 WebSocket 수신 루프를 막지 않는다.
- 운영 Oracle 서버와 봇 실험 서버의 URL, 통계 DB와 client ID namespace를 분리한다.
- 랜덤 매칭에 봇을 넣기 전에는 일반 방에서 규칙 준수와 시간 제한을 충분히 검증한다.

## 9. 봇 개발 검증

기존 회귀 테스트:

```bash
PYTHONPATH=server .venv/bin/python -m compileall -q server
PYTHONPATH=server .venv/bin/python -m pytest -q
```

전략을 게임 엔진에서 빠르게 검증할 때는 `tests/test_game_engine.py`처럼
`GameEngine`을 직접 생성할 수 있다. 다만 실전 네트워크 대전에서는 방 시작,
선공 추첨, 타이머와 연결 종료가 `Room`에 있으므로 WebSocket 통합 테스트도 함께
작성해야 한다.
