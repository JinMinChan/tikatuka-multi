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
MAX_LOG_ITEMS = 80


@dataclass
class Room:
    code: str
    game: GameEngine = field(default_factory=GameEngine)
    player_ids: list[str | None] = field(default_factory=lambda: [None, None])
    connected: list[bool] = field(default_factory=lambda: [False, False])
    sockets: dict[str, WebSocket] = field(default_factory=dict)
    started: bool = False
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

    def public_players(self) -> list[dict[str, Any]]:
        return [
            {
                "index": idx,
                "name": PLAYER_NAMES[idx],
                "occupied": self.player_ids[idx] is not None,
                "connected": self.connected[idx],
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
                "createdAt": self.created_at,
                "updatedAt": self.updated_at,
            },
            "you": {
                "clientId": client_id,
                "player": slot,
                "spectator": slot is None,
            },
            "game": self.game.snapshot(),
            "log": self.log,
        }


app = FastAPI(title="TikaTuka Multiplayer", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

rooms: dict[str, Room] = {}


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "tikatuka", "rooms": len(rooms)}


@app.post("/api/rooms")
async def create_room() -> dict[str, str]:
    cleanup_rooms()
    for _ in range(200):
        code = f"{secrets.randbelow(10_000):04d}"
        if code not in rooms:
            rooms[code] = Room(code=code)
            return {"code": code}
    raise HTTPException(status_code=503, detail="방 번호를 만들 수 없습니다.")


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
    if not client_id:
        await websocket.close(code=1008, reason="client_id is required")
        return
    room = rooms.get(code)
    if room is None:
        await websocket.close(code=1008, reason="room not found")
        return

    await websocket.accept()
    async with room.lock:
        slot = room.slot_for(client_id)
        if slot is not None:
            room.connected[slot] = True
        room.sockets[client_id] = websocket
        if not room.started and all(room.player_ids):
            room.started = True
            room.add_events([{"type": "room_started"}])
            room.add_events(room.game.ensure_turn_ready())
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
            slot = room.slot_for(client_id)
            if room.sockets.get(client_id) is websocket:
                room.sockets.pop(client_id, None)
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
            events = room.game.reset()
            room.started = all(room.player_ids)
            if room.started:
                events.extend(room.game.ensure_turn_ready())
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
        if not room.sockets and now - room.updated_at > ROOM_TTL_SECONDS
    ]
    for code in expired:
        rooms.pop(code, None)

