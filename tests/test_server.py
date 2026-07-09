import importlib
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import (
    PlayerStats,
    Room,
    TournamentState,
    MAX_STREAMER_QUEUE,
    RANDOM_RECENT_REMATCH_BLOCK_SECONDS,
    RANDOM_WAIT_CONNECT_GRACE_SECONDS,
    TOTAL_TIME_SECONDS,
    TURN_TIME_SECONDS,
    app,
    apply_ranked_result,
    client_last_seen,
    finalize_tournament_game,
    invalidate_leaderboard_cache,
    leaderboard_payload,
    last_random_opponents,
    load_stats_from_db,
    player_title_inventory,
    player_stats,
    player_titles,
    rooms,
    seed_tournament_manual,
    start_tournament_next_game,
    tournament_payload,
)


@pytest.fixture(autouse=True)
def clear_random_opponent_history():
    main_module = importlib.import_module("app.main")
    main_module.maintenance_drain_enabled = False
    last_random_opponents.clear()
    yield
    main_module.maintenance_drain_enabled = False
    last_random_opponents.clear()


class FixedRng:
    def __init__(self, values):
        self.values = list(values)

    def randint(self, low, high):
        assert low == 1
        assert high == 6
        if not self.values:
            raise AssertionError("fixed rng exhausted")
        return self.values.pop(0)


class DeadSocket:
    async def send_json(self, payload):
        raise WebSocketDisconnect(code=1006)


def receive_snapshot(ws, predicate=lambda payload: True, attempts=20):
    for _ in range(attempts):
        payload = ws.receive_json()
        if payload.get("type") == "snapshot" and predicate(payload):
            return payload
    raise AssertionError("expected snapshot was not received")


def receive_message_type(ws, message_type, attempts=20):
    for _ in range(attempts):
        payload = ws.receive_json()
        if payload.get("type") == message_type:
            return payload
    raise AssertionError(f"expected {message_type} was not received")


def test_turn_clock_is_spent_before_total_clock(monkeypatch):
    main_module = importlib.import_module("app.main")
    now = [100.0]
    monkeypatch.setattr(main_module.time, "time", lambda: now[0])

    room = Room(code="1010")
    room.started = True
    room.game.phase = "place_normal"
    room.reset_clocks()
    room.arm_clock(reset_turn=True)

    now[0] = 112.0
    turn_clocks, total_clocks = room.clock_snapshot()
    assert turn_clocks == [3.0, TURN_TIME_SECONDS]
    assert total_clocks == [TOTAL_TIME_SECONDS, TOTAL_TIME_SECONDS]

    now[0] = 120.0
    assert room.charge_clock() == []
    assert room.turn_clocks == [0.0, TURN_TIME_SECONDS]
    assert room.clocks == [55.0, TOTAL_TIME_SECONDS]


def test_new_turn_resets_fifteen_seconds_even_for_same_player(monkeypatch):
    main_module = importlib.import_module("app.main")
    now = [200.0]
    monkeypatch.setattr(main_module.time, "time", lambda: now[0])

    room = Room(code="2020")
    room.started = True
    room.game.phase = "place_normal"
    room.reset_clocks()
    room.arm_clock(reset_turn=True)

    now[0] = 210.0
    assert room.charge_clock() == []
    assert room.turn_clocks[0] == 5.0

    # 상대가 홀드한 경우처럼 current_player가 같아도 새 턴이면 재충전해야 한다.
    room.game.current_player = 0
    room.arm_clock(reset_turn=True)
    assert room.turn_clocks[0] == TURN_TIME_SECONDS
    assert room.clock_started_at == 210.0


def test_total_clock_expiry_forces_timeout_loss(monkeypatch):
    main_module = importlib.import_module("app.main")
    now = [300.0]
    monkeypatch.setattr(main_module.time, "time", lambda: now[0])

    room = Room(code="3030")
    room.started = True
    room.game.phase = "place_normal"
    room.reset_clocks()
    room.arm_clock(reset_turn=True)

    now[0] += TURN_TIME_SECONDS + TOTAL_TIME_SECONDS
    events = room.charge_clock()

    assert room.turn_clocks[0] == 0.0
    assert room.clocks[0] == 0.0
    assert room.game.result["winner"] == 1
    assert room.game.result["forced"] == "timeout"
    assert [event["type"] for event in events] == ["timeout_loss", "game_finished"]


def test_random_timeout_loser_leaves_and_winner_can_match_again(monkeypatch):
    main_module = importlib.import_module("app.main")
    now = [400.0]
    monkeypatch.setattr(main_module.time, "time", lambda: now[0])
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)

    waiting = client.post(
        "/api/random-match",
        json={"clientId": "random-a", "nickname": "Alpha"},
    ).json()
    client.post(
        "/api/random-match",
        json={"clientId": "random-b", "nickname": "Beta"},
    )
    room = rooms[waiting["code"]]
    room.game.rng = FixedRng([6, 1, 4])

    with client.websocket_connect(f"/ws/{room.code}?client_id=random-a&nickname=Alpha") as ws0:
        ws0.receive_json()
        with client.websocket_connect(
            f"/ws/{room.code}?client_id=random-b&nickname=Beta"
        ) as ws1:
            ws0.receive_json()
            ws1.receive_json()
            now[0] += TURN_TIME_SECONDS + TOTAL_TIME_SECONDS

            ws1.send_json({"type": "timeout_check"})
            timeout_for_loser = ws0.receive_json()
            timeout_for_winner = ws1.receive_json()
            loser_notice = ws0.receive_json()
            waiting_snapshot = ws1.receive_json()

            assert timeout_for_loser["game"]["result"]["forced"] == "timeout"
            assert timeout_for_winner["game"]["result"]["winner"] == 1
            assert loser_notice["type"] == "room_closed"
            assert waiting_snapshot["room"]["started"] is False
            assert room.player_ids == ["random-b", None]
            assert "random-a" not in room.sockets

            matched = client.post(
                "/api/random-match",
                json={"clientId": "random-c", "nickname": "Gamma"},
            ).json()

            assert matched["matched"] is True
            assert matched["code"] == room.code
            assert room.player_ids == ["random-b", "random-c"]


def test_create_room_returns_unique_four_digit_code():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)

    response = client.post("/api/rooms")

    assert response.status_code == 200
    code = response.json()["code"]
    assert len(code) == 4
    assert code.isdigit()
    assert code in rooms


def test_two_players_joining_room_starts_game_and_accepts_action():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)
    code = client.post("/api/rooms").json()["code"]
    rooms[code].game.rng = FixedRng([2, 5, 4, 3])

    with client.websocket_connect(f"/ws/{code}?client_id=p0&nickname=Maker") as ws0:
        first_snapshot = ws0.receive_json()
        assert first_snapshot["room"]["started"] is False
        assert first_snapshot["you"]["player"] == 0
        assert first_snapshot["room"]["players"][0]["name"] == "Maker"

        with client.websocket_connect(f"/ws/{code}?client_id=p1&nickname=Joiner") as ws1:
            started_for_p0 = ws0.receive_json()
            started_for_p1 = ws1.receive_json()

            assert started_for_p0["room"]["started"] is True
            assert started_for_p1["room"]["started"] is True
            assert started_for_p0["room"]["players"][0]["name"] == "Maker"
            assert started_for_p0["room"]["players"][1]["name"] == "Joiner"
            assert started_for_p0["room"]["rolloff"]["rolls"] == [2, 5]
            assert started_for_p0["room"]["rolloff"]["winner"] == 1
            assert started_for_p1["you"]["player"] == 1
            assert started_for_p0["game"]["currentPlayer"] == 1
            assert started_for_p0["game"]["phase"] == "place_normal"
            assert started_for_p0["game"]["heldDie"]["shield"] is True
            assert started_for_p0["game"]["heldDie"]["owner"] == 1

            ws1.send_json({"type": "action", "action": "place_normal", "field": 0})
            after_action = ws0.receive_json()

            assert after_action["game"]["boards"][1][0]


def test_rolloff_winner_zero_gets_current_turn_and_tray_die():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)
    code = client.post("/api/rooms").json()["code"]
    rooms[code].game.rng = FixedRng([6, 1, 3])

    with client.websocket_connect(f"/ws/{code}?client_id=p0&nickname=Maker") as ws0:
        ws0.receive_json()
        with client.websocket_connect(f"/ws/{code}?client_id=p1&nickname=Joiner") as ws1:
            started_for_p0 = ws0.receive_json()
            ws1.receive_json()

            assert started_for_p0["room"]["rolloff"]["winner"] == 0
            assert started_for_p0["game"]["currentPlayer"] == 0
            assert started_for_p0["game"]["heldDie"]["owner"] == 0
            assert started_for_p0["game"]["heldDie"]["shield"] is True


def test_emoticon_event_broadcasts_without_consuming_turn():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)
    code = client.post("/api/rooms").json()["code"]
    rooms[code].game.rng = FixedRng([6, 1, 3])

    with client.websocket_connect(f"/ws/{code}?client_id=p0&nickname=Maker") as ws0:
        ws0.receive_json()
        with client.websocket_connect(f"/ws/{code}?client_id=p1&nickname=Joiner") as ws1:
            started_for_p0 = ws0.receive_json()
            ws1.receive_json()

            ws0.send_json({"type": "emoticon", "emoticon": "mokoko_001"})
            emoted_for_p0 = ws0.receive_json()
            emoted_for_p1 = ws1.receive_json()

            assert emoted_for_p0["game"]["currentPlayer"] == started_for_p0["game"]["currentPlayer"]
            assert emoted_for_p0["game"]["phase"] == started_for_p0["game"]["phase"]
            assert emoted_for_p0["log"][0]["type"] == "emoticon"
            assert emoted_for_p0["log"][0]["player"] == 0
            assert emoted_for_p0["log"][0]["emoticon"] == "mokoko_001"
            assert emoted_for_p1["log"][0]["type"] == "emoticon"


def test_host_disconnect_destroys_room_number():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)
    code = client.post("/api/rooms").json()["code"]

    with client.websocket_connect(f"/ws/{code}?client_id=host&nickname=Host") as ws0:
        ws0.receive_json()
        assert code in rooms

    assert code not in rooms
    assert client.get(f"/api/rooms/{code}").status_code == 404


def test_host_disconnect_notifies_guest_and_destroys_room():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)
    code = client.post("/api/rooms").json()["code"]
    rooms[code].game.rng = FixedRng([6, 1, 4])

    with client.websocket_connect(f"/ws/{code}?client_id=host&nickname=Host") as host:
        host.receive_json()
        with client.websocket_connect(f"/ws/{code}?client_id=guest&nickname=Guest") as guest:
            host.receive_json()
            guest.receive_json()

            host.close()
            closed = guest.receive_json()

            assert closed["type"] == "room_closed"
            assert "방장" in closed["message"]
            assert code not in rooms


def test_manual_guest_leave_resets_room_and_allows_replacement():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)
    code = client.post("/api/rooms").json()["code"]
    rooms[code].game.rng = FixedRng([6, 1, 4, 5, 2, 3])

    with client.websocket_connect(f"/ws/{code}?client_id=host&nickname=Host") as host:
        host.receive_json()
        with client.websocket_connect(f"/ws/{code}?client_id=guest&nickname=Guest") as guest:
            receive_snapshot(host, lambda payload: payload["room"]["started"])
            receive_snapshot(guest, lambda payload: payload["room"]["started"])
            rooms[code].game.boards[1][0].append(rooms[code].game.make_die(value=6, owner=1))
            rooms[code].rematch_votes.add("host")
            rooms[code].friendly_wins = [2, 1]
            guest.close()
            waiting = receive_snapshot(
                host,
                lambda payload: not payload["room"]["players"][1]["occupied"],
            )

        assert waiting["room"]["started"] is False
        assert waiting["room"]["players"][1]["name"] == "상대 대기중..."
        assert waiting["room"]["rematchVotes"] == 0
        assert waiting["room"]["friendlyScore"] == [0, 0]
        assert waiting["game"]["result"] is None
        assert waiting["game"]["boards"] == [[[], [], []], [[], [], []]]

        with client.websocket_connect(
            f"/ws/{code}?client_id=replacement&nickname=Replacement"
        ) as replacement:
            restarted = receive_snapshot(host, lambda payload: payload["room"]["started"])
            replacement_started = receive_snapshot(
                replacement,
                lambda payload: payload["room"]["started"],
            )
            assert restarted["room"]["players"][1]["name"] == "Replacement"
            assert replacement_started["you"]["player"] == 1


def test_host_can_kick_guest_after_game_and_keep_manual_room():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)
    code = client.post("/api/rooms").json()["code"]
    rooms[code].game.rng = FixedRng([6, 1, 4])

    with client.websocket_connect(f"/ws/{code}?client_id=host&nickname=Host") as host:
        host.receive_json()
        with client.websocket_connect(f"/ws/{code}?client_id=guest&nickname=Guest") as guest:
            receive_snapshot(host, lambda payload: payload["room"]["started"])
            receive_snapshot(guest, lambda payload: payload["room"]["started"])
            rooms[code].game.result = {"winner": 0}
            rooms[code].game.phase = "game_over"

            guest.send_json({"type": "kick_opponent"})
            denied = guest.receive_json()
            assert denied["type"] == "error"

            host.send_json({"type": "kick_opponent"})
            guest_notice = guest.receive_json()
            waiting = receive_snapshot(
                host,
                lambda payload: not payload["room"]["players"][1]["occupied"],
            )

            assert guest_notice["type"] == "room_closed"
            assert waiting["room"]["started"] is False
            assert waiting["game"]["result"] is None
            assert code in rooms
            assert rooms[code].player_ids == ["host", None]


def test_random_match_pairs_two_clients_without_room_number_entry():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)

    waiting = client.post(
        "/api/random-match",
        json={"clientId": "random-a", "nickname": "Alpha"},
    ).json()
    matched = client.post(
        "/api/random-match",
        json={"clientId": "random-b", "nickname": "Beta"},
    ).json()

    assert waiting["matched"] is False
    assert matched["matched"] is True
    assert matched["code"] == waiting["code"]

    room = rooms[waiting["code"]]
    assert room.random_match is True
    assert room.ranked is True
    assert room.player_ids == ["random-a", "random-b"]

    room.game.rng = FixedRng([5, 2, 4])
    with client.websocket_connect(f"/ws/{room.code}?client_id=random-a&nickname=Alpha") as ws0:
        first = ws0.receive_json()
        assert first["you"]["player"] == 0
        assert first["room"]["started"] is False
        with client.websocket_connect(f"/ws/{room.code}?client_id=random-b&nickname=Beta") as ws1:
            started_for_p0 = ws0.receive_json()
            started_for_p1 = ws1.receive_json()

            assert started_for_p0["room"]["started"] is True
            assert started_for_p1["you"]["player"] == 1
            assert started_for_p0["room"]["ranked"] is True
            assert started_for_p0["room"]["players"][0]["name"] == "Alpha"
            assert started_for_p0["room"]["players"][1]["name"] == "Beta"


def test_streamer_room_waiters_watch_running_game_and_queue_is_limited():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)
    created = client.post(
        "/api/streamer-rooms",
        json={"queueLimit": 2, "clientId": "host", "nickname": "Streamer"},
    ).json()
    room = rooms[created["code"]]
    assert room.player_ids[0] == "host"
    room.game.rng = FixedRng([6, 1, 4])

    with client.websocket_connect(
        f"/ws/{room.code}?client_id=host&nickname=Streamer"
    ) as host:
        host_snapshot = host.receive_json()
        assert host_snapshot["you"]["player"] == 0
        with client.websocket_connect(
            f"/ws/{room.code}?client_id=challenger&nickname=Challenger"
        ) as challenger:
            receive_snapshot(host, lambda payload: payload["room"]["players"][1]["occupied"])
            challenger_snapshot = challenger.receive_json()
            assert challenger_snapshot["room"]["started"] is False

            challenger.send_json({"type": "ready"})
            denied = challenger.receive_json()
            assert denied["type"] == "error"
            assert "방송인만" in denied["message"]
            assert room.started is False

            host.send_json({"type": "ready"})
            receive_snapshot(host, lambda payload: payload["room"]["started"])
            receive_snapshot(challenger, lambda payload: payload["room"]["started"])

            with client.websocket_connect(
                f"/ws/{room.code}?client_id=wait-1&nickname=Waiter1"
            ) as waiter1:
                waiter_snapshot = receive_snapshot(
                    waiter1,
                    lambda payload: payload["you"]["queuePosition"] == 1,
                )
                assert waiter_snapshot["you"]["spectator"] is True
                assert waiter_snapshot["room"]["started"] is True
                assert waiter_snapshot["room"]["waitingPlayers"][0]["name"] == "Waiter1"

                waiter1.send_json(
                    {"type": "action", "action": "place_normal", "field": 0}
                )
                error = waiter1.receive_json()
                assert error["type"] == "error"

                with client.websocket_connect(
                    f"/ws/{room.code}?client_id=wait-2&nickname=Waiter2"
                ) as waiter2:
                    receive_snapshot(
                        waiter2,
                        lambda payload: payload["you"]["queuePosition"] == 2,
                    )
                    with client.websocket_connect(
                        f"/ws/{room.code}?client_id=overflow&nickname=Overflow"
                    ) as overflow:
                        rejected = overflow.receive_json()
                        assert rejected["type"] == "room_closed"
                        assert "정원" in rejected["message"]


def test_streamer_kick_promotes_first_waiter_and_resets_ready_state():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)
    code = client.post(
        "/api/streamer-rooms",
        json={"queueLimit": 3, "clientId": "host", "nickname": "Streamer"},
    ).json()["code"]
    room = rooms[code]

    with client.websocket_connect(f"/ws/{code}?client_id=host&nickname=Streamer") as host:
        host.receive_json()
        with client.websocket_connect(
            f"/ws/{code}?client_id=challenger&nickname=Challenger"
        ) as challenger:
            receive_snapshot(host, lambda payload: payload["room"]["players"][1]["occupied"])
            challenger.receive_json()
            with client.websocket_connect(
                f"/ws/{code}?client_id=waiter&nickname=Next"
            ) as waiter:
                receive_snapshot(waiter, lambda payload: payload["you"]["queuePosition"] == 1)
                room.ready_players.update({"host", "challenger"})
                room.rematch_votes.update({"host", "challenger"})
                room.friendly_wins = [2, 1]
                room.started = True
                room.game.result = {"winner": 0}
                room.game.phase = "game_over"

                host.send_json({"type": "kick_opponent"})
                challenger_notice = receive_message_type(challenger, "room_closed")
                promoted = receive_snapshot(
                    waiter,
                    lambda payload: payload["you"]["player"] == 1,
                )
                host_after = receive_snapshot(
                    host,
                    lambda payload: payload["room"]["players"][1]["name"] == "Next",
                )

                assert challenger_notice["type"] == "room_closed"
                assert promoted["you"]["spectator"] is False
                assert promoted["room"]["started"] is False
                assert promoted["game"]["result"] is None
                assert host_after["room"]["waitingPlayers"] == []
                assert host_after["room"]["rematchVotes"] == 0
                assert host_after["room"]["friendlyScore"] == [0, 0]
                assert room.ready_players == set()


def test_streamer_waiter_emoticon_and_leave_update_queue_order():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)
    code = client.post(
        "/api/streamer-rooms",
        json={"queueLimit": 3, "clientId": "host", "nickname": "Streamer"},
    ).json()["code"]

    with client.websocket_connect(f"/ws/{code}?client_id=host&nickname=Streamer") as host:
        host.receive_json()
        with client.websocket_connect(
            f"/ws/{code}?client_id=challenger&nickname=Challenger"
        ) as challenger:
            receive_snapshot(host, lambda payload: payload["room"]["players"][1]["occupied"])
            challenger.receive_json()
            with client.websocket_connect(
                f"/ws/{code}?client_id=wait-1&nickname=First"
            ) as first:
                receive_snapshot(first, lambda payload: payload["you"]["queuePosition"] == 1)
                with client.websocket_connect(
                    f"/ws/{code}?client_id=wait-2&nickname=Second"
                ) as second:
                    receive_snapshot(second, lambda payload: payload["you"]["queuePosition"] == 2)
                    first.send_json({"type": "waiting_emoticon", "emoticon": "yoz_001"})
                    emoted = receive_snapshot(
                        host,
                        lambda payload: payload["log"]
                        and payload["log"][0]["type"] == "waiting_emoticon",
                    )
                    assert emoted["log"][0]["name"] == "First"
                    first.close()
                    updated = receive_snapshot(
                        host,
                        lambda payload: [
                            waiter["name"] for waiter in payload["room"]["waitingPlayers"]
                        ]
                        == ["Second"],
                    )
                    assert updated["room"]["waitingPlayers"][0]["position"] == 1


def test_streamer_room_accepts_ten_waiters_in_fifo_order():
    room = Room(
        code="5555",
        streamer_mode=True,
        queue_limit=MAX_STREAMER_QUEUE,
    )
    assert room.assign_streamer_client("host", "Host") == "player"
    assert room.assign_streamer_client("challenger", "Challenger") == "player"
    for index in range(MAX_STREAMER_QUEUE):
        assert room.assign_streamer_client(f"wait-{index}", f"Wait {index}") == "waiting"

    assert room.assign_streamer_client("overflow", "Overflow") is None
    assert room.waiting_ids == [f"wait-{index}" for index in range(MAX_STREAMER_QUEUE)]


def test_admin_streamer_rooms_reports_host_challenger_and_waiters(monkeypatch):
    monkeypatch.setenv("TIKATUKA_ADMIN_SECRET", "secret")
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    room = Room(code="5555", streamer_mode=True, queue_limit=3)
    room.player_ids = ["host", "challenger"]
    room.player_names = ["방장", "도전자"]
    room.connected = [True, True]
    room.waiting_ids = ["waiter"]
    room.waiting_names = {"waiter": "대기자"}
    room.started = True
    room.game.phase = "place_normal"
    rooms[room.code] = room
    client = TestClient(app)

    response = client.get(
        "/api/admin/streamer-rooms",
        headers={"x-admin-secret": "secret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["rooms"][0]["code"] == "5555"
    assert payload["rooms"][0]["host"]["name"] == "방장"
    assert payload["rooms"][0]["challenger"]["name"] == "도전자"
    assert payload["rooms"][0]["waitingPlayers"][0]["name"] == "대기자"


def test_admin_random_waiting_rooms_reports_connected_waiters(monkeypatch):
    monkeypatch.setenv("TIKATUKA_ADMIN_SECRET", "secret")
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)

    waiting = client.post(
        "/api/random-match",
        json={"clientId": "human-waiter", "nickname": "Human"},
    ).json()
    room = rooms[waiting["code"]]

    with client.websocket_connect(
        f"/ws/{room.code}?client_id=human-waiter&nickname=Human"
    ) as ws:
        ws.receive_json()
        room.random_wait_started_at = time.time() - RANDOM_RECENT_REMATCH_BLOCK_SECONDS - 1
        fresh_room = Room(code="9999", random_match=True, ranked=True)
        fresh_room.player_ids[0] = "fresh"
        fresh_room.player_names[0] = "Fresh"
        fresh_room.connected[0] = True
        fresh_room.random_wait_started_at = time.time()
        rooms[fresh_room.code] = fresh_room

        response = client.get(
            "/api/admin/random-waiting-rooms?minWaitSeconds=10",
            headers={"x-admin-secret": "secret"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] == 1
        assert payload["rooms"][0]["code"] == room.code
        assert payload["rooms"][0]["waitingSeconds"] >= 10
        assert payload["rooms"][0]["player"]["clientId"] == "human-waiter"
        assert payload["rooms"][0]["join"]["wsPath"] == f"/ws/{room.code}"


def test_bot_secret_can_only_read_random_waiting_rooms(monkeypatch):
    monkeypatch.delenv("TIKATUKA_ADMIN_SECRET", raising=False)
    monkeypatch.setenv("TIKATUKA_BOT_SECRET", "bot-secret")
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)

    waiting = client.post(
        "/api/random-match",
        json={"clientId": "human-waiter", "nickname": "Human"},
    ).json()
    room = rooms[waiting["code"]]

    with client.websocket_connect(
        f"/ws/{room.code}?client_id=human-waiter&nickname=Human"
    ) as ws:
        ws.receive_json()
        room.random_wait_started_at = time.time() - RANDOM_RECENT_REMATCH_BLOCK_SECONDS - 1

        allowed = client.get(
            "/api/admin/random-waiting-rooms?minWaitSeconds=10",
            headers={"x-bot-secret": "bot-secret"},
        )
        blocked = client.get(
            "/api/admin/rooms/summary",
            headers={"x-bot-secret": "bot-secret"},
        )

        assert allowed.status_code == 200
        assert allowed.json()["rooms"][0]["code"] == room.code
        assert blocked.status_code == 503


def test_server_drain_prevents_disconnect_loss(monkeypatch):
    monkeypatch.setenv("TIKATUKA_ADMIN_SECRET", "secret")
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)

    waiting = client.post(
        "/api/random-match",
        json={"clientId": "random-a", "nickname": "Alpha"},
    ).json()
    client.post(
        "/api/random-match",
        json={"clientId": "random-b", "nickname": "Beta"},
    )
    room = rooms[waiting["code"]]
    room.game.rng = FixedRng([5, 2, 4])

    with client.websocket_connect(f"/ws/{room.code}?client_id=random-a&nickname=Alpha") as ws0:
        ws0.receive_json()
        with client.websocket_connect(f"/ws/{room.code}?client_id=random-b&nickname=Beta") as ws1:
            ws0.receive_json()
            ws1.receive_json()

            state = client.post(
                "/api/admin/server/drain",
                headers={"x-admin-secret": "secret"},
            )
            ws1.close()
            drained_snapshot = receive_snapshot(
                ws0,
                lambda payload: payload["room"]["players"][1]["connected"] is False,
            )

            assert state.status_code == 200
            assert state.json()["drain"] is True
            assert drained_snapshot["room"]["started"] is True
            assert player_stats.get("random-a", PlayerStats()).wins == 0
            assert player_stats.get("random-b", PlayerStats()).losses == 0
            assert room.game.result is None

    resumed = client.post(
        "/api/admin/server/resume",
        headers={"x-admin-secret": "secret"},
    )
    assert resumed.status_code == 200
    assert resumed.json()["drain"] is False


def test_random_game_leave_counts_loss_and_room_reenters_match_pool():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)

    waiting = client.post(
        "/api/random-match",
        json={"clientId": "random-a", "nickname": "Alpha"},
    ).json()
    client.post(
        "/api/random-match",
        json={"clientId": "random-b", "nickname": "Beta"},
    )
    room = rooms[waiting["code"]]
    room.game.rng = FixedRng([5, 2, 4])

    with client.websocket_connect(f"/ws/{room.code}?client_id=random-a&nickname=Alpha") as ws0:
        ws0.receive_json()
        with client.websocket_connect(f"/ws/{room.code}?client_id=random-b&nickname=Beta") as ws1:
            ws0.receive_json()
            ws1.receive_json()
            ws1.close()
            waiting_snapshot = ws0.receive_json()

            assert waiting_snapshot["room"]["started"] is False
            assert waiting_snapshot["room"]["players"][0]["name"] == "Alpha"
            assert waiting_snapshot["room"]["players"][1]["occupied"] is False
            assert waiting_snapshot["room"]["players"][1]["name"] == "상대 대기중..."
            assert all(
                event["type"] not in {"first_player_rolloff", "die_rolled", "egg_flick"}
                for event in waiting_snapshot["log"]
            )

            assert player_stats["random-a"].wins == 1
            assert player_stats["random-b"].losses == 1
            assert room.player_ids == ["random-a", None]

            matched = client.post(
                "/api/random-match",
                json={"clientId": "random-c", "nickname": "Gamma"},
            ).json()

            assert matched["matched"] is True
            assert matched["code"] == room.code
            assert room.player_ids == ["random-a", "random-c"]


def test_random_match_blocks_same_ip_pairing():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)

    first = client.post(
        "/api/random-match",
        headers={"x-forwarded-for": "203.0.113.10"},
        json={"clientId": "same-ip-a", "nickname": "Alpha"},
    ).json()
    second = client.post(
        "/api/random-match",
        headers={"x-forwarded-for": "203.0.113.10"},
        json={"clientId": "same-ip-b", "nickname": "Beta"},
    ).json()

    assert first["matched"] is False
    assert second["matched"] is False
    assert second["code"] != first["code"]
    assert rooms[first["code"]].player_ids == ["same-ip-a", None]
    assert rooms[second["code"]].player_ids == ["same-ip-b", None]


def test_random_match_blocks_previous_opponent_until_both_play_someone_else():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    last_random_opponents["alpha"] = "beta"
    last_random_opponents["beta"] = "alpha"
    client = TestClient(app)

    first = client.post(
        "/api/random-match",
        headers={"x-forwarded-for": "203.0.113.11"},
        json={"clientId": "alpha", "nickname": "Alpha"},
    ).json()
    blocked = client.post(
        "/api/random-match",
        headers={"x-forwarded-for": "203.0.113.12"},
        json={"clientId": "beta", "nickname": "Beta"},
    ).json()

    assert blocked["matched"] is False
    assert blocked["code"] != first["code"]
    assert rooms[first["code"]].player_ids == ["alpha", None]


def test_random_match_allows_previous_opponent_after_waiting_10_seconds():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    last_random_opponents["alpha"] = "beta"
    last_random_opponents["beta"] = "alpha"
    client = TestClient(app)

    first = client.post(
        "/api/random-match",
        headers={"x-forwarded-for": "203.0.113.11"},
        json={"clientId": "alpha", "nickname": "Alpha"},
    ).json()
    room = rooms[first["code"]]
    room.random_wait_started_at = time.time() - RANDOM_RECENT_REMATCH_BLOCK_SECONDS - 1
    rematch = client.post(
        "/api/random-match",
        headers={"x-forwarded-for": "203.0.113.12"},
        json={"clientId": "beta", "nickname": "Beta"},
    ).json()

    assert rematch["matched"] is True
    assert rematch["code"] == first["code"]
    assert room.player_ids == ["alpha", "beta"]


def test_ranked_random_result_remembers_previous_opponents():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    room = Room(code="9090", random_match=True, ranked=True)
    room.player_ids = ["winner", "loser"]
    room.game.result = {"winner": 0}

    apply_ranked_result(room)

    assert last_random_opponents == {"winner": "loser", "loser": "winner"}


def test_random_match_does_not_join_abandoned_waiting_room():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)

    abandoned = Room(code="1111", random_match=True, ranked=True)
    abandoned.player_ids[0] = "gone"
    abandoned.connected[0] = False
    abandoned.updated_at = time.time() - RANDOM_WAIT_CONNECT_GRACE_SECONDS - 1
    rooms[abandoned.code] = abandoned

    response = client.post(
        "/api/random-match",
        json={"clientId": "fresh", "nickname": "Fresh"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched"] is False
    assert payload["code"] != "1111"
    assert "1111" not in rooms


def test_random_match_replaces_reserved_player_who_never_connects():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)

    waiting = client.post(
        "/api/random-match",
        json={"clientId": "waiting", "nickname": "Waiting"},
    ).json()
    room = rooms[waiting["code"]]

    with client.websocket_connect(
        f"/ws/{room.code}?client_id=waiting&nickname=Waiting"
    ) as waiting_ws:
        waiting_ws.receive_json()
        reserved = client.post(
            "/api/random-match",
            json={"clientId": "no-show", "nickname": "No Show"},
        ).json()
        assert reserved["matched"] is True
        assert reserved["code"] == room.code

        room.updated_at = time.time() - RANDOM_WAIT_CONNECT_GRACE_SECONDS - 1
        replacement = client.post(
            "/api/random-match",
            json={"clientId": "replacement", "nickname": "Replacement"},
        ).json()

        assert replacement["matched"] is True
        assert replacement["code"] == room.code
        assert room.player_ids == ["waiting", "replacement"]


def test_random_match_keeps_connected_joiner_when_creator_never_connects():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)

    creator = client.post(
        "/api/random-match",
        json={"clientId": "creator-no-show", "nickname": "Creator"},
    ).json()
    joiner = client.post(
        "/api/random-match",
        json={"clientId": "joiner", "nickname": "Joiner"},
    ).json()
    room = rooms[creator["code"]]

    with client.websocket_connect(
        f"/ws/{room.code}?client_id=joiner&nickname=Joiner"
    ) as joiner_ws:
        joiner_ws.receive_json()
        room.updated_at = time.time() - RANDOM_WAIT_CONNECT_GRACE_SECONDS - 1
        replacement = client.post(
            "/api/random-match",
            json={"clientId": "replacement", "nickname": "Replacement"},
        ).json()

        assert joiner["matched"] is True
        assert replacement["matched"] is True
        assert replacement["code"] == room.code
        assert room.player_ids == ["joiner", "replacement"]


def test_stale_waiting_socket_does_not_abort_new_random_connection():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)

    room = Room(code="2222", random_match=True, ranked=True)
    room.player_ids[0] = "stale"
    room.connected[0] = True
    room.sockets["stale"] = DeadSocket()
    rooms[room.code] = room

    with client.websocket_connect(
        f"/ws/{room.code}?client_id=fresh&nickname=Fresh"
    ) as fresh_ws:
        started_snapshot = fresh_ws.receive_json()
        waiting_snapshot = fresh_ws.receive_json()

        assert started_snapshot["room"]["started"] is True
        assert waiting_snapshot["room"]["started"] is False
        assert room.player_ids == ["fresh", None]
        assert "stale" not in room.sockets


def test_restart_requires_both_players_to_vote():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)
    code = client.post("/api/rooms").json()["code"]
    rooms[code].game.rng = FixedRng([6, 1, 4, 5, 2, 3])

    with client.websocket_connect(f"/ws/{code}?client_id=p0&nickname=Maker") as ws0:
        ws0.receive_json()
        with client.websocket_connect(f"/ws/{code}?client_id=p1&nickname=Joiner") as ws1:
            ws0.receive_json()
            ws1.receive_json()
            rooms[code].game.result = {"winner": 0}
            rooms[code].game.phase = "game_over"

            ws0.send_json({"type": "restart"})
            voted_for_p0 = ws0.receive_json()
            voted_for_p1 = ws1.receive_json()

            assert voted_for_p0["room"]["rematchVotes"] == 1
            assert voted_for_p1["game"]["result"] == {"winner": 0}

            ws1.send_json({"type": "restart"})
            restarted_for_p0 = ws0.receive_json()
            restarted_for_p1 = ws1.receive_json()

            assert restarted_for_p0["room"]["rematchVotes"] == 0
            assert restarted_for_p0["game"]["result"] is None
            assert restarted_for_p1["room"]["started"] is True


def test_ranked_result_updates_tier_wins_losses_and_streak_bonus():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()

    room = Room(code="1234", random_match=True, ranked=True)
    room.player_ids = ["winner", "loser"]
    room.game.result = {"winner": 0}

    apply_ranked_result(room)

    assert player_stats["winner"].wins == 1
    assert player_stats["winner"].streak == 1
    assert player_stats["winner"].tier == "bronze"
    assert player_stats["winner"].tier_grade == 5
    assert player_stats["winner"].tier_stars == 1
    assert player_stats["loser"].losses == 1
    assert player_stats["loser"].streak == -1
    assert player_stats["loser"].tier_stars == 0

    next_room = Room(code="1235", random_match=True, ranked=True)
    next_room.player_ids = ["winner", "loser"]
    next_room.game.result = {"winner": 0}

    apply_ranked_result(next_room)

    assert player_stats["winner"].wins == 2
    assert player_stats["winner"].streak == 2
    assert player_stats["winner"].tier_grade == 5
    assert player_stats["winner"].tier_stars == 2
    assert player_stats["loser"].losses == 2
    assert player_stats["loser"].streak == -2

    third_room = Room(code="1236", random_match=True, ranked=True)
    third_room.player_ids = ["winner", "loser"]
    third_room.game.result = {"winner": 0}

    apply_ranked_result(third_room)

    assert player_stats["winner"].wins == 3
    assert player_stats["winner"].streak == 3
    assert player_stats["winner"].tier_grade == 4
    assert player_stats["winner"].tier_stars == 1


def test_manual_room_result_does_not_update_ranked_stats():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()

    room = Room(code="9999", ranked=False)
    room.player_ids = ["a", "b"]
    room.game.result = {"winner": 0}

    apply_ranked_result(room)

    assert player_stats == {}


def test_manual_room_score_accumulates_once_across_rematches():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()

    room = Room(code="7777")
    room.player_ids = ["host", "guest"]
    room.game.result = {"winner": 0}

    apply_ranked_result(room)
    apply_ranked_result(room)

    assert room.friendly_wins == [1, 0]
    assert room.snapshot("host")["room"]["friendlyScore"] == [1, 0]

    room.game.rng = FixedRng([6, 1, 4])
    room.start_game_events(include_reset=True)
    assert room.friendly_wins == [1, 0]
    assert room.friendly_result_recorded is False

    room.game.result = {"winner": 1}
    apply_ranked_result(room)

    assert room.friendly_wins == [1, 1]


def test_streamer_room_records_current_challenger_score_once():
    room = Room(code="8888", streamer_mode=True, queue_limit=3)
    room.player_ids = ["host", "challenger"]
    room.game.result = {"winner": 0}

    apply_ranked_result(room)
    apply_ranked_result(room)

    assert room.friendly_wins == [1, 0]

    room.game.rng = FixedRng([6, 1, 4])
    room.start_game_events(include_reset=True)
    room.game.result = {"winner": 1}
    apply_ranked_result(room)

    assert room.friendly_wins == [1, 1]


def make_tournament_room(size=4, target_wins=1, host_participates=True):
    tournament = TournamentState(
        host_id="host",
        host_name="Host",
        host_participates=host_participates,
        size=size,
        target_wins=target_wins,
        slots=[None for _ in range(size)],
    )
    room = Room(code="4444", tournament_mode=True, tournament=tournament)
    for client_id, nickname in [
        ("host", "Host"),
        ("p1", "One"),
        ("p2", "Two"),
        ("p3", "Three"),
    ][:size]:
        room.assign_tournament_client(client_id, nickname)
    return room


def test_tournament_seeded_room_exposes_start_after_placement():
    room = make_tournament_room()

    before = tournament_payload(room)
    assert before["readyToSeed"] is True
    assert before["seeded"] is False
    assert before["canStart"] is False

    seed_tournament_manual(room, ["host", "p1", "p2", "p3"])
    after = tournament_payload(room)

    assert after["seeded"] is True
    assert after["canStart"] is True
    assert after["rounds"][0][0]["players"][0]["name"] == "Host"


def test_tournament_room_endpoint_creates_configured_room():
    rooms.clear()
    client = TestClient(app)

    response = client.post(
        "/api/tournament-rooms",
        json={
            "clientId": "host",
            "nickname": "Host",
            "size": 8,
            "targetWins": 2,
            "hostParticipates": False,
        },
    )

    assert response.status_code == 200
    code = response.json()["code"]
    room = rooms[code]
    assert room.tournament_mode is True
    assert room.tournament.size == 8
    assert room.tournament.target_wins == 2
    assert room.tournament.host_participates is False
    assert room.tournament.participant_ids == []


def test_tournament_start_assigns_current_match_players():
    room = make_tournament_room()
    seed_tournament_manual(room, ["host", "p1", "p2", "p3"])

    start_tournament_next_game(room)

    assert room.started is True
    assert room.player_ids == ["host", "p1"]
    assert room.player_names == ["Host", "One"]
    payload = tournament_payload(room)
    assert payload["activeMatch"]["matchId"] == "r0m0"
    assert payload["canStart"] is False


def test_tournament_match_winner_advances_and_next_start_becomes_available():
    room = make_tournament_room()
    seed_tournament_manual(room, ["host", "p1", "p2", "p3"])
    start_tournament_next_game(room)

    room.game.result = {"winner": 0}
    finalize_tournament_game(room)

    payload = tournament_payload(room)
    assert payload["rounds"][0][0]["completed"] is True
    assert payload["rounds"][1][0]["players"][0]["clientId"] == "host"
    assert payload["canStart"] is True


def test_tournament_best_of_three_needs_two_set_wins():
    room = make_tournament_room(target_wins=2)
    seed_tournament_manual(room, ["host", "p1", "p2", "p3"])
    start_tournament_next_game(room)

    room.game.result = {"winner": 0}
    finalize_tournament_game(room)

    payload = tournament_payload(room)
    assert payload["rounds"][0][0]["scores"] == [1, 0]
    assert payload["rounds"][0][0]["completed"] is False
    assert payload["status"] == "between_sets"
    assert payload["canStart"] is True


def test_status_payload_includes_top_twenty_leaderboard():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)

    for index in range(25):
        player_stats[f"player-{index}"] = PlayerStats(
            name=f"Player {index}",
            tier="master",
            master_points=index,
            wins=index % 7,
            losses=25 - index,
        )
    invalidate_leaderboard_cache()

    response = client.get("/api/status?client_id=player-24")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stats"]["tier"]["points"] == 24
    assert payload["stats"]["rank"] == 1
    assert len(payload["leaderboard"]) == 20
    assert payload["leaderboard"][0]["rank"] == 1
    assert payload["leaderboard"][0]["name"] == "Player 24"
    assert payload["leaderboard"][-1]["tier"]["points"] == 5
    assert payload["leaderboard"][-1]["rank"] == 20


def test_leaderboard_cache_is_invalidated_after_ranked_result():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    player_stats["winner"] = PlayerStats(name="Winner")
    player_stats["loser"] = PlayerStats(name="Loser", tier_stars=1)
    invalidate_leaderboard_cache()
    assert leaderboard_payload()[0]["clientId"] == "loser"

    room = Room(code="8888", random_match=True, ranked=True)
    room.player_ids = ["winner", "loser"]
    room.game.result = {"winner": 0}
    apply_ranked_result(room)

    updated = leaderboard_payload()
    assert updated[0]["clientId"] == "winner"
    assert updated[0]["tier"]["stars"] == 1


def test_unchanged_player_name_does_not_persist_again(monkeypatch):
    main_module = importlib.import_module("app.main")
    player_stats.clear()
    player_stats["same-name"] = PlayerStats(name="Same", tier_stars=1)
    invalidate_leaderboard_cache()
    assert leaderboard_payload()[0]["name"] == "Same"
    persisted = []
    monkeypatch.setattr(main_module, "persist_stats", persisted.append)

    main_module.remember_player_name("same-name", "Same")
    main_module.remember_player_name("same-name", "Changed")

    assert persisted == ["same-name"]
    assert player_stats["same-name"].name == "Changed"
    assert leaderboard_payload()[0]["name"] == "Changed"


def test_ranked_stats_persist_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("TIKATUKA_STATS_DB", str(tmp_path / "stats.sqlite3"))
    rooms.clear()
    player_stats.clear()
    player_titles.clear()
    player_title_inventory.clear()
    client_last_seen.clear()

    player_stats["winner"] = PlayerStats(name="Winner")
    player_stats["loser"] = PlayerStats(name="Loser")
    room = Room(code="7777", random_match=True, ranked=True)
    room.player_ids = ["winner", "loser"]
    room.game.result = {"winner": 0}

    apply_ranked_result(room)
    player_stats.clear()
    load_stats_from_db()

    assert player_stats["winner"].name == "Winner"
    assert player_stats["winner"].wins == 1
    assert player_stats["winner"].tier == "bronze"
    assert player_stats["winner"].tier_grade == 5
    assert player_stats["winner"].tier_stars == 1
    assert player_stats["loser"].losses == 1


def test_title_admin_api_requires_secret(monkeypatch):
    monkeypatch.delenv("TIKATUKA_ADMIN_SECRET", raising=False)
    rooms.clear()
    player_stats.clear()
    player_titles.clear()
    player_title_inventory.clear()
    client_last_seen.clear()
    client = TestClient(app)

    response = client.post(
        "/api/admin/titles/grant",
        json={"clientId": "dev", "label": "개발자"},
    )

    assert response.status_code == 503
    assert player_titles == {}


def test_title_grant_revoke_and_player_search(monkeypatch):
    monkeypatch.setenv("TIKATUKA_ADMIN_SECRET", "secret")
    rooms.clear()
    player_stats.clear()
    player_titles.clear()
    player_title_inventory.clear()
    client_last_seen.clear()
    player_stats["dev-1"] = PlayerStats(name="개발자", score=12, wins=2)
    player_stats["other"] = PlayerStats(name="다른사람", score=5)
    client_last_seen["dev-1"] = time.time()
    client = TestClient(app)

    grant = client.post(
        "/api/admin/titles/grant",
        headers={"x-admin-secret": "secret"},
        json={
            "clientId": "dev-1",
            "label": "듀얼리스트",
            "color": "duelist",
            "icon": "duelist",
            "effect": "crystal",
        },
    )
    found = client.get(
        "/api/admin/players?nickname=개발자",
        headers={"x-admin-secret": "secret"},
    )

    assert grant.status_code == 200
    assert grant.json()["title"] == {
        "id": "duelist",
        "label": "듀얼리스트",
        "color": "duelist",
        "icon": "duelist",
        "iconText": "",
        "effect": "crystal",
    }
    assert found.status_code == 200
    assert found.json()["players"][0]["clientId"] == "dev-1"
    assert found.json()["players"][0]["title"]["label"] == "듀얼리스트"
    assert "title" not in leaderboard_payload()[0]
    assert player_title_inventory["dev-1"]["duelist"].label == "듀얼리스트"

    revoked = client.post(
        "/api/admin/titles/revoke",
        headers={"Authorization": "Bearer secret"},
        json={"clientId": "dev-1"},
    )

    assert revoked.status_code == 200
    assert revoked.json()["removed"] is True
    assert "dev-1" not in player_titles
    assert "dev-1" not in player_title_inventory


def test_title_grant_broadcasts_to_connected_room(monkeypatch):
    monkeypatch.setenv("TIKATUKA_ADMIN_SECRET", "secret")
    rooms.clear()
    player_stats.clear()
    player_titles.clear()
    player_title_inventory.clear()
    client_last_seen.clear()
    client = TestClient(app)
    code = client.post("/api/rooms").json()["code"]

    with client.websocket_connect(f"/ws/{code}?client_id=dev&nickname=개발자") as ws:
        first = receive_snapshot(ws)
        assert "title" not in first["room"]["players"][0]["stats"]

        response = client.post(
            "/api/admin/titles/grant",
            headers={"x-admin-secret": "secret"},
            json={
                "clientId": "dev",
                "label": "실시간칭호",
                "color": "neon",
                "icon": "duck",
                "effect": "glow",
            },
        )
        updated = receive_snapshot(
            ws,
            lambda payload: payload["room"]["players"][0]["stats"]
            .get("title", {})
            .get("label")
            == "실시간칭호",
        )

        assert response.status_code == 200
        assert updated["you"]["stats"]["title"]["iconText"] == "🦆"


def test_player_can_equip_one_owned_title(monkeypatch):
    monkeypatch.setenv("TIKATUKA_ADMIN_SECRET", "secret")
    rooms.clear()
    player_stats.clear()
    player_titles.clear()
    player_title_inventory.clear()
    client_last_seen.clear()
    player_stats["dev"] = PlayerStats(name="개발자")
    client = TestClient(app)

    first = client.post(
        "/api/admin/titles/grant",
        headers={"x-admin-secret": "secret"},
        json={
            "clientId": "dev",
            "titleId": "duelist",
            "label": "듀얼리스트",
            "color": "duelist",
            "icon": "duelist",
            "effect": "crystal",
        },
    )
    second = client.post(
        "/api/admin/titles/grant",
        headers={"x-admin-secret": "secret"},
        json={
            "clientId": "dev",
            "titleId": "ranker",
            "label": "랭커",
            "color": "gold",
            "icon": "crown",
            "effect": "shine",
        },
    )
    equipped = client.post(
        "/api/titles/equip",
        json={"clientId": "dev", "titleId": "duelist"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert equipped.status_code == 200
    stats = equipped.json()["stats"]
    assert stats["title"]["id"] == "duelist"
    assert [title["id"] for title in stats["titles"]] == ["duelist", "ranker"]
    assert [title["equipped"] for title in stats["titles"]] == [True, False]

    unequipped = client.post("/api/titles/unequip", json={"clientId": "dev"})

    assert unequipped.status_code == 200
    unequipped_stats = unequipped.json()["stats"]
    assert "title" not in unequipped_stats
    assert [title["id"] for title in unequipped_stats["titles"]] == [
        "duelist",
        "ranker",
    ]
    assert [title["equipped"] for title in unequipped_stats["titles"]] == [
        False,
        False,
    ]
    assert "dev" not in player_titles


def test_rank_title_reflects_live_leaderboard_and_stays_out_of_leaderboard():
    rooms.clear()
    player_stats.clear()
    player_titles.clear()
    player_title_inventory.clear()
    client_last_seen.clear()
    player_stats["top"] = PlayerStats(name="Top", tier="gold", tier_grade=2, tier_stars=1, wins=4)
    player_stats["second"] = PlayerStats(
        name="Second",
        tier="gold",
        tier_grade=3,
        tier_stars=2,
        wins=2,
    )
    invalidate_leaderboard_cache()
    client = TestClient(app)

    first = client.get("/api/status?client_id=top").json()
    equipped = client.post(
        "/api/titles/equip",
        json={"clientId": "top", "titleId": "rank-top"},
    ).json()

    assert next(title for title in first["stats"]["titles"] if title["id"] == "rank-top")[
        "label"
    ] == "TOP 1"
    assert all("title" not in entry for entry in first["leaderboard"])
    assert equipped["stats"]["title"]["label"] == "TOP 1"

    player_stats["second"].tier = "platinum"
    player_stats["second"].tier_grade = 5
    player_stats["second"].tier_stars = 0
    invalidate_leaderboard_cache()
    changed = client.get("/api/status?client_id=top").json()

    assert changed["stats"]["title"]["label"] == "TOP 2"
    assert next(
        title for title in changed["stats"]["titles"] if title["id"] == "rank-top"
    )["label"] == "TOP 2"

    for index in range(21):
        player_stats[f"ranker-{index}"] = PlayerStats(
            name=f"Ranker {index}",
            tier="master",
            master_points=100 + index,
            wins=index,
        )
    invalidate_leaderboard_cache()
    dropped = client.get("/api/status?client_id=top").json()

    assert "title" not in dropped["stats"]
    assert all(title["id"] != "rank-top" for title in dropped["stats"]["titles"])


def test_duelist_title_is_owned_after_first_ten_random_match_streak():
    rooms.clear()
    player_stats.clear()
    player_titles.clear()
    player_title_inventory.clear()
    client_last_seen.clear()
    player_stats["winner"] = PlayerStats(name="Winner", streak=9, wins=9, score=100)
    player_stats["loser"] = PlayerStats(name="Loser", score=30)
    room = Room(code="7777", random_match=True, ranked=True)
    room.player_ids = ["winner", "loser"]
    room.game.result = {"winner": 0}

    apply_ranked_result(room)

    assert player_stats["winner"].streak == 10
    assert player_title_inventory["winner"]["duelist"].label == "듀얼리스트"


def test_developer_nickname_does_not_auto_create_title():
    rooms.clear()
    player_stats.clear()
    player_titles.clear()
    player_title_inventory.clear()
    client_last_seen.clear()
    player_stats["dev"] = PlayerStats(name="개발자")
    client = TestClient(app)

    payload = client.get("/api/status?client_id=dev").json()

    assert payload["stats"]["titles"] == []


def test_titles_persist_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("TIKATUKA_STATS_DB", str(tmp_path / "stats.sqlite3"))
    monkeypatch.setenv("TIKATUKA_ADMIN_SECRET", "secret")
    rooms.clear()
    player_stats.clear()
    player_titles.clear()
    player_title_inventory.clear()
    client_last_seen.clear()
    player_stats["dev"] = PlayerStats(name="개발자", score=1)
    client = TestClient(app)

    response = client.post(
        "/api/admin/titles/grant",
        headers={"x-admin-secret": "secret"},
        json={
            "clientId": "dev",
            "label": "영구칭호",
            "color": "rainbow",
            "icon": "crown",
            "effect": "rainbow",
        },
    )
    assert response.status_code == 200

    player_stats.clear()
    player_titles.clear()
    player_title_inventory.clear()
    load_stats_from_db()

    assert player_titles["dev"].label == "영구칭호"
    assert player_titles["dev"].color == "rainbow"
    assert player_titles["dev"].icon == "crown"
    assert player_titles["dev"].effect == "rainbow"
    assert player_title_inventory["dev"]["영구칭호"].label == "영구칭호"
