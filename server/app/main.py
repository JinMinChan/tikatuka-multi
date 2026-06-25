from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .game_engine import GameEngine, PLAYER_NAMES


ROOM_TTL_SECONDS = 60 * 60 * 6
RANDOM_WAIT_TTL_SECONDS = 60 * 5
ONLINE_WINDOW_SECONDS = 45
MAX_LOG_ITEMS = 80


@dataclass
class PlayerStats:
    score: int = 0
    wins: int = 0
    losses: int = 0
    streak: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "score": self.score,
            "wins": self.wins,
            "losses": self.losses,
            "streak": self.streak,
        }


@dataclass
class Room:
    code: str
    random_match: bool = False
    ranked: bool = False
    ranked_recorded: bool = False
    game: GameEngine = field(default_factory=GameEngine)
    player_ids: list[str | None] = field(default_factory=lambda: [None, None])
    player_names: list[str] = field(default_factory=lambda: PLAYER_NAMES.copy())
    connected: list[bool] = field(default_factory=lambda: [False, False])
    sockets: dict[str, WebSocket] = field(default_factory=dict)
    started: bool = False
    rolloff: dict[str, Any] | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    log: list[dict[str, Any]] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def touch(self) -> None:
        self.updated_at = time.time()

    def add_events(self, events: list[dict[str, Any]]) -> None:
        now = time.time()
        for event in events:
            self.log.insert(0, {"ts": now, **event})
        self.log = self.log[:MAX_LOG_ITEMS]
        if events:
            self.touch()

    def slot_for(self, client_id: str) -> int | None:
        for idx, known_id in enumerate(self.player_ids):
            if known_id == client_id:
                return idx
        for idx, known_id in enumerate(self.player_ids):
            if known_id is None:
                self.player_ids[idx] = client_id
                return idx
        return None

    def existing_slot_for(self, client_id: str) -> int | None:
        for idx, known_id in enumerate(self.player_ids):
            if known_id == client_id:
                return idx
        return None

    def public_players(self) -> list[dict[str, Any]]:
        return [
            {
                "index": idx,
                "name": self.player_names[idx],
                "occupied": self.player_ids[idx] is not None,
                "connected": self.connected[idx],
                "stats": stats_for(self.player_ids[idx]).to_dict()
                if self.player_ids[idx]
                else None,
            }
            for idx in range(2)
        ]

    def snapshot(self, client_id: str | None = None) -> dict[str, Any]:
        slot = self.slot_for(client_id) if client_id else None
        return {
            "type": "snapshot",
            "room": {
                "code": self.code,
                "started": self.started,
                "players": self.public_players(),
                "rolloff": self.rolloff,
                "randomMatch": self.random_match,
                "ranked": self.ranked,
                "createdAt": self.created_at,
                "updatedAt": self.updated_at,
            },
            "you": {
                "clientId": client_id,
                "player": slot,
                "spectator": slot is None,
                "stats": stats_for(client_id).to_dict() if client_id else None,
            },
            "game": self.game.snapshot(),
            "log": self.log,
        }

    def start_game_events(self, include_reset: bool = False) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if include_reset:
            events.extend(self.game.reset())

        rolls = [self.game.roll_value(), self.game.roll_value()]
        rerolls = 0
        while rolls[0] == rolls[1]:
            rerolls += 1
            rolls = [self.game.roll_value(), self.game.roll_value()]

        winner = 0 if rolls[0] > rolls[1] else 1
        self.game.set_first_player(winner)
        self.rolloff = {
            "rolls": rolls,
            "winner": winner,
            "rerolls": rerolls,
            "ts": time.time(),
        }
        events.append(
            {
                "type": "first_player_rolloff",
                "rolls": rolls,
                "winner": winner,
                "rerolls": rerolls,
            }
        )
        events.extend(self.game.ensure_turn_ready())
        return events


app = FastAPI(title="TikaTuka Multiplayer", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

rooms: dict[str, Room] = {}
player_stats: dict[str, PlayerStats] = {}
client_last_seen: dict[str, float] = {}


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "tikatuka", "rooms": len(rooms)}


@app.post("/api/heartbeat")
async def heartbeat(payload: dict[str, Any]) -> dict[str, Any]:
    client_id = clean_client_id(str(payload.get("clientId", "")))
    if client_id:
        touch_client(client_id)
    return status_payload(client_id or None)


@app.get("/api/status")
async def get_status(client_id: str | None = None) -> dict[str, Any]:
    cleaned = clean_client_id(client_id or "")
    if cleaned:
        touch_client(cleaned)
    return status_payload(cleaned or None)


@app.post("/api/rooms")
async def create_room() -> dict[str, str]:
    cleanup_rooms()
    for _ in range(200):
        code = f"{secrets.randbelow(10_000):04d}"
        if code not in rooms:
            rooms[code] = Room(code=code)
            return {"code": code}
    raise HTTPException(status_code=503, detail="방 번호를 만들 수 없습니다.")


@app.post("/api/random-match")
async def random_match(payload: dict[str, Any]) -> dict[str, Any]:
    cleanup_rooms()
    client_id = clean_client_id(str(payload.get("clientId", "")))
    if not client_id:
        raise HTTPException(status_code=400, detail="clientId가 필요합니다.")
    nickname = clean_nickname(str(payload.get("nickname", "")), PLAYER_NAMES[0])
    touch_client(client_id)

    for room in sorted(rooms.values(), key=lambda item: item.created_at):
        if (
            room.random_match
            and not room.started
            and room.player_ids[0] == client_id
            and room.player_ids[1] is None
        ):
            room.player_names[0] = clean_nickname(nickname, PLAYER_NAMES[0])
            room.touch()
            return {"code": room.code, "matched": False, "player": 0}

    for room in sorted(rooms.values(), key=lambda item: item.created_at):
        if (
            room.random_match
            and not room.started
            and room.player_ids[0] is not None
            and room.player_ids[0] != client_id
            and room.player_ids[1] is None
        ):
            room.player_ids[1] = client_id
            room.player_names[1] = clean_nickname(nickname, PLAYER_NAMES[1])
            room.touch()
            return {"code": room.code, "matched": True, "player": 1}

    for _ in range(200):
        code = f"{secrets.randbelow(10_000):04d}"
        if code not in rooms:
            room = Room(code=code, random_match=True, ranked=True)
            room.player_ids[0] = client_id
            room.player_names[0] = clean_nickname(nickname, PLAYER_NAMES[0])
            rooms[code] = room
            return {"code": code, "matched": False, "player": 0}
    raise HTTPException(status_code=503, detail="랜덤 매칭 방을 만들 수 없습니다.")


@app.get("/api/rooms/{code}")
async def get_room(code: str) -> dict[str, Any]:
    room = get_room_or_404(code)
    return {
        "code": room.code,
        "started": room.started,
        "players": room.public_players(),
    }


@app.websocket("/ws/{code}")
async def websocket_room(websocket: WebSocket, code: str) -> None:
    client_id = websocket.query_params.get("client_id", "").strip()
    nickname = websocket.query_params.get("nickname", "")
    if not client_id:
        await websocket.close(code=1008, reason="client_id is required")
        return
    client_id = clean_client_id(client_id)
    if not client_id:
        await websocket.close(code=1008, reason="client_id is required")
        return
    room = rooms.get(code)
    if room is None:
        await websocket.close(code=1008, reason="room not found")
        return

    await websocket.accept()
    async with room.lock:
        touch_client(client_id)
        slot = room.slot_for(client_id)
        if slot is not None:
            room.player_names[slot] = clean_nickname(nickname, PLAYER_NAMES[slot])
            room.connected[slot] = True
        room.sockets[client_id] = websocket
        if not room.started and all(room.player_ids) and all(room.connected):
            room.started = True
            room.add_events([{"type": "room_started"}])
            room.add_events(room.start_game_events())
        else:
            room.touch()
        await broadcast(room)

    try:
        while True:
            payload = await websocket.receive_json()
            await handle_message(room, client_id, payload)
    except WebSocketDisconnect:
        pass
    finally:
        async with room.lock:
            slot = room.existing_slot_for(client_id)
            if room.sockets.get(client_id) is websocket:
                room.sockets.pop(client_id, None)
            if slot == 0 and rooms.get(room.code) is room:
                await destroy_room(room, "방장이 나가 방이 종료되었습니다.")
                return
            if slot is not None:
                room.connected[slot] = False
            room.touch()
            await broadcast(room)


async def handle_message(room: Room, client_id: str, payload: dict[str, Any]) -> None:
    async with room.lock:
        slot = room.slot_for(client_id)
        if slot is None:
            await send_error(room, client_id, "방이 가득 차서 관전자로 접속했습니다.")
            return
        if not room.started:
            await send_error(room, client_id, "상대가 입장할 때까지 기다려주세요.")
            return

        msg_type = str(payload.get("type", "action"))
        if msg_type == "restart":
            if slot != 0:
                await send_error(room, client_id, "방장만 다시 시작할 수 있습니다.")
                return
            if room.ranked:
                await send_error(room, client_id, "랜덤 매칭은 다시하기를 사용할 수 없습니다.")
                return
            events = room.game.reset()
            room.started = all(room.player_ids)
            if room.started:
                events.extend(room.start_game_events())
            room.add_events(events)
            await broadcast(room)
            return

        if msg_type != "action":
            await send_error(room, client_id, "알 수 없는 메시지입니다.")
            return

        try:
            events = room.game.apply_action(slot, payload)
        except ValueError as exc:
            await send_error(room, client_id, str(exc))
            return
        room.add_events(events)
        apply_ranked_result(room)
        await broadcast(room)


async def broadcast(room: Room) -> None:
    stale: list[str] = []
    for client_id, socket in room.sockets.items():
        try:
            await socket.send_json(room.snapshot(client_id))
        except RuntimeError:
            stale.append(client_id)
    for client_id in stale:
        room.sockets.pop(client_id, None)


async def send_error(room: Room, client_id: str, message: str) -> None:
    socket = room.sockets.get(client_id)
    if socket:
        await socket.send_json({"type": "error", "message": message})


async def destroy_room(room: Room, message: str) -> None:
    rooms.pop(room.code, None)
    sockets = list(room.sockets.values())
    room.sockets.clear()
    room.started = False
    for socket in sockets:
        try:
            await socket.send_json({"type": "room_closed", "message": message})
        except RuntimeError:
            pass
        try:
            await socket.close(code=1000, reason=message)
        except RuntimeError:
            pass


def get_room_or_404(code: str) -> Room:
    room = rooms.get(code)
    if room is None:
        raise HTTPException(status_code=404, detail="방을 찾을 수 없습니다.")
    return room


def cleanup_rooms() -> None:
    now = time.time()
    expired = [
        code
        for code, room in rooms.items()
        if not room.sockets
        and (
            now - room.updated_at > ROOM_TTL_SECONDS
            or (
                room.random_match
                and not room.started
                and now - room.updated_at > RANDOM_WAIT_TTL_SECONDS
            )
        )
    ]
    for code in expired:
        rooms.pop(code, None)

    stale_clients = [
        client_id
        for client_id, seen_at in client_last_seen.items()
        if now - seen_at > ONLINE_WINDOW_SECONDS * 4
    ]
    for client_id in stale_clients:
        client_last_seen.pop(client_id, None)


def clean_nickname(value: str, fallback: str) -> str:
    nickname = " ".join(value.strip().split())
    if not nickname:
        return fallback
    return nickname[:16]


def clean_client_id(value: str) -> str:
    return value.strip()[:80]


def stats_for(client_id: str | None) -> PlayerStats:
    if not client_id:
        return PlayerStats()
    if client_id not in player_stats:
        player_stats[client_id] = PlayerStats()
    return player_stats[client_id]


def touch_client(client_id: str) -> None:
    if client_id:
        client_last_seen[client_id] = time.time()


def online_user_count() -> int:
    now = time.time()
    active = {
        client_id
        for client_id, seen_at in client_last_seen.items()
        if now - seen_at <= ONLINE_WINDOW_SECONDS
    }
    for room in rooms.values():
        active.update(room.sockets.keys())
    return len(active)


def status_payload(client_id: str | None = None) -> dict[str, Any]:
    cleanup_rooms()
    return {
        "onlineUsers": online_user_count(),
        "stats": stats_for(client_id).to_dict() if client_id else PlayerStats().to_dict(),
    }


def apply_ranked_result(room: Room) -> None:
    if not room.ranked or room.ranked_recorded or not room.game.result:
        return
    winner = room.game.result.get("winner")
    if winner not in (0, 1):
        room.ranked_recorded = True
        return
    loser = 1 - winner
    winner_id = room.player_ids[winner]
    loser_id = room.player_ids[loser]
    if not winner_id or not loser_id:
        return

    winner_stats = stats_for(winner_id)
    loser_stats = stats_for(loser_id)

    win_bonus = max(0, winner_stats.streak) * 2
    loss_penalty = max(0, -loser_stats.streak) * 2

    winner_stats.score += 10 + win_bonus
    winner_stats.wins += 1
    winner_stats.streak = winner_stats.streak + 1 if winner_stats.streak > 0 else 1

    loser_stats.score = max(0, loser_stats.score - (10 + loss_penalty))
    loser_stats.losses += 1
    loser_stats.streak = loser_stats.streak - 1 if loser_stats.streak < 0 else -1

    room.ranked_recorded = True
