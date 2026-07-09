import importlib
import time

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import (
    PlayerStats,
    Room,
    MAX_STREAMER_QUEUE,
    RANDOM_WAIT_CONNECT_GRACE_SECONDS,
    TOTAL_TIME_SECONDS,
    TURN_TIME_SECONDS,
    app,
    apply_ranked_result,
    client_last_seen,
    invalidate_leaderboard_cache,
    leaderboard_payload,
    load_stats_from_db,
    player_stats,
    rooms,
)


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

            ws0.send_json({"type": "emoticon", "emoticon": "lol"})
            emoted_for_p0 = ws0.receive_json()
            emoted_for_p1 = ws1.receive_json()

            assert emoted_for_p0["game"]["currentPlayer"] == started_for_p0["game"]["currentPlayer"]
            assert emoted_for_p0["game"]["phase"] == started_for_p0["game"]["phase"]
            assert emoted_for_p0["log"][0]["type"] == "emoticon"
            assert emoted_for_p0["log"][0]["player"] == 0
            assert emoted_for_p0["log"][0]["emoticon"] == "lol"
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
                    first.send_json({"type": "waiting_emoticon", "emoticon": "lol"})
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


def test_ranked_result_updates_score_wins_losses_and_streak_weight():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()

    room = Room(code="1234", random_match=True, ranked=True)
    room.player_ids = ["winner", "loser"]
    room.game.result = {"winner": 0}

    apply_ranked_result(room)

    assert player_stats["winner"].score == 10
    assert player_stats["winner"].wins == 1
    assert player_stats["winner"].streak == 1
    assert player_stats["loser"].score == 0
    assert player_stats["loser"].losses == 1
    assert player_stats["loser"].streak == -1

    next_room = Room(code="1235", random_match=True, ranked=True)
    next_room.player_ids = ["winner", "loser"]
    next_room.game.result = {"winner": 0}

    apply_ranked_result(next_room)

    assert player_stats["winner"].score == 22
    assert player_stats["winner"].wins == 2
    assert player_stats["winner"].streak == 2
    assert player_stats["loser"].score == 0
    assert player_stats["loser"].losses == 2
    assert player_stats["loser"].streak == -2


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


def test_status_payload_includes_top_twenty_leaderboard():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    client = TestClient(app)

    for index in range(25):
        player_stats[f"player-{index}"] = PlayerStats(
            name=f"Player {index}",
            score=index,
            wins=index % 7,
            losses=25 - index,
        )
    invalidate_leaderboard_cache()

    response = client.get("/api/status?client_id=player-24")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stats"]["score"] == 24
    assert payload["stats"]["rank"] == 1
    assert len(payload["leaderboard"]) == 20
    assert payload["leaderboard"][0]["rank"] == 1
    assert payload["leaderboard"][0]["name"] == "Player 24"
    assert payload["leaderboard"][-1]["score"] == 5
    assert payload["leaderboard"][-1]["rank"] == 20


def test_leaderboard_cache_is_invalidated_after_ranked_result():
    rooms.clear()
    player_stats.clear()
    client_last_seen.clear()
    player_stats["winner"] = PlayerStats(name="Winner")
    player_stats["loser"] = PlayerStats(name="Loser", score=5)
    invalidate_leaderboard_cache()
    assert leaderboard_payload()[0]["clientId"] == "loser"

    room = Room(code="8888", random_match=True, ranked=True)
    room.player_ids = ["winner", "loser"]
    room.game.result = {"winner": 0}
    apply_ranked_result(room)

    updated = leaderboard_payload()
    assert updated[0]["clientId"] == "winner"
    assert updated[0]["score"] == 10


def test_unchanged_player_name_does_not_persist_again(monkeypatch):
    main_module = importlib.import_module("app.main")
    player_stats.clear()
    player_stats["same-name"] = PlayerStats(name="Same", score=10)
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
    client_last_seen.clear()

    player_stats["winner"] = PlayerStats(name="Winner")
    player_stats["loser"] = PlayerStats(name="Loser", score=25)
    room = Room(code="7777", random_match=True, ranked=True)
    room.player_ids = ["winner", "loser"]
    room.game.result = {"winner": 0}

    apply_ranked_result(room)
    player_stats.clear()
    load_stats_from_db()

    assert player_stats["winner"].name == "Winner"
    assert player_stats["winner"].score == 10
    assert player_stats["winner"].wins == 1
    assert player_stats["loser"].score == 15
    assert player_stats["loser"].losses == 1
