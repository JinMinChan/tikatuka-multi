from fastapi.testclient import TestClient

from app.main import Room, app, apply_ranked_result, client_last_seen, player_stats, rooms


class FixedRng:
    def __init__(self, values):
        self.values = list(values)

    def randint(self, low, high):
        assert low == 1
        assert high == 6
        if not self.values:
            raise AssertionError("fixed rng exhausted")
        return self.values.pop(0)


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
