from fastapi.testclient import TestClient

from app.main import app, rooms


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
    client = TestClient(app)

    response = client.post("/api/rooms")

    assert response.status_code == 200
    code = response.json()["code"]
    assert len(code) == 4
    assert code.isdigit()
    assert code in rooms


def test_two_players_joining_room_starts_game_and_accepts_action():
    rooms.clear()
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
