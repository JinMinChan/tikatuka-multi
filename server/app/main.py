from __future__ import annotations

import asyncio
import os
import secrets
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .game_engine import GameEngine, PLAYER_NAMES


ROOM_TTL_SECONDS = 60 * 60 * 6
RANDOM_WAIT_TTL_SECONDS = 60 * 5
RANDOM_WAIT_CONNECT_GRACE_SECONDS = 20
MAX_STREAMER_QUEUE = 10
ONLINE_WINDOW_SECONDS = 45
MAX_LOG_ITEMS = 80
TURN_TIME_SECONDS = 15
TOTAL_TIME_SECONDS = 60
WAITING_PLAYER_NAME = "상대 대기중..."
ALLOWED_EMOTICONS = {"gogo", "lol", "sad", "stop", "what", "whatwhat"}
DEFAULT_STATS_DB_PATH = (
    Path(__file__).resolve().parents[3] / "tikatuka-data" / "tikatuka_stats.sqlite3"
)


@dataclass
class PlayerStats:
    name: str = "플레이어"
    score: int = 0
    wins: int = 0
    losses: int = 0
    streak: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "wins": self.wins,
            "losses": self.losses,
            "streak": self.streak,
        }


@dataclass
class Room:
    code: str
    random_match: bool = False
    streamer_mode: bool = False
    queue_limit: int = 0
    ranked: bool = False
    ranked_recorded: bool = False
    friendly_wins: list[int] = field(default_factory=lambda: [0, 0])
    friendly_result_recorded: bool = False
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
    rematch_votes: set[str] = field(default_factory=set)
    ready_players: set[str] = field(default_factory=set)
    waiting_ids: list[str] = field(default_factory=list)
    waiting_names: dict[str, str] = field(default_factory=dict)
    clocks: list[float] = field(default_factory=lambda: [TOTAL_TIME_SECONDS, TOTAL_TIME_SECONDS])
    turn_clocks: list[float] = field(
        default_factory=lambda: [TURN_TIME_SECONDS, TURN_TIME_SECONDS]
    )
    clock_player: int | None = None
    clock_started_at: float | None = None
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
                "name": self.player_names[idx]
                if self.player_ids[idx] is not None
                else WAITING_PLAYER_NAME,
                "occupied": self.player_ids[idx] is not None,
                "connected": self.connected[idx],
                "ready": bool(
                    self.player_ids[idx] and self.player_ids[idx] in self.ready_players
                ),
                "stats": stats_payload(self.player_ids[idx]) if self.player_ids[idx] else None,
            }
            for idx in range(2)
        ]

    def occupied_player_ids(self) -> list[str]:
        return [client_id for client_id in self.player_ids if client_id]

    def waiting_payload(self) -> list[dict[str, Any]]:
        return [
            {
                "position": position,
                "name": self.waiting_names.get(client_id, "대기자"),
            }
            for position, client_id in enumerate(self.waiting_ids, start=1)
        ]

    def assign_streamer_client(self, client_id: str, nickname: str) -> str | None:
        slot = self.existing_slot_for(client_id)
        if slot is not None:
            self.player_names[slot] = clean_nickname(nickname, PLAYER_NAMES[slot])
            return "player"
        if client_id in self.waiting_ids:
            self.waiting_names[client_id] = clean_nickname(nickname, "대기자")
            return "waiting"
        if self.player_ids[0] is None:
            self.player_ids[0] = client_id
            self.player_names[0] = clean_nickname(nickname, PLAYER_NAMES[0])
            return "player"
        if self.player_ids[1] is None:
            self.player_ids[1] = client_id
            self.player_names[1] = clean_nickname(nickname, PLAYER_NAMES[1])
            return "player"
        if len(self.waiting_ids) >= self.queue_limit:
            return None
        self.waiting_ids.append(client_id)
        self.waiting_names[client_id] = clean_nickname(nickname, "대기자")
        return "waiting"

    def reset_clocks(self) -> None:
        self.clocks = [TOTAL_TIME_SECONDS, TOTAL_TIME_SECONDS]
        self.turn_clocks = [TURN_TIME_SECONDS, TURN_TIME_SECONDS]
        self.clock_player = None
        self.clock_started_at = None

    @staticmethod
    def consume_clock_elapsed(
        player: int,
        elapsed: float,
        turn_clocks: list[float],
        total_clocks: list[float],
    ) -> None:
        elapsed = max(0.0, elapsed)
        turn_spent = min(turn_clocks[player], elapsed)
        turn_clocks[player] = max(0.0, turn_clocks[player] - turn_spent)
        overtime = elapsed - turn_spent
        if overtime > 0:
            total_clocks[player] = max(0.0, total_clocks[player] - overtime)

    def clock_snapshot(self, now: float | None = None) -> tuple[list[float], list[float]]:
        now = now or time.time()
        turn_clocks = self.turn_clocks.copy()
        total_clocks = self.clocks.copy()
        if (
            self.started
            and self.game.result is None
            and self.clock_player in (0, 1)
            and self.clock_started_at is not None
        ):
            elapsed = max(0.0, now - self.clock_started_at)
            self.consume_clock_elapsed(
                self.clock_player,
                elapsed,
                turn_clocks,
                total_clocks,
            )
        return (
            [round(value, 3) for value in turn_clocks],
            [round(value, 3) for value in total_clocks],
        )

    def arm_clock(self, reset_turn: bool = False) -> None:
        if self.started and self.game.result is None and self.game.phase != "game_over":
            player_changed = self.clock_player != self.game.current_player
            if player_changed or reset_turn:
                self.turn_clocks[self.game.current_player] = TURN_TIME_SECONDS
            if player_changed or reset_turn or self.clock_started_at is None:
                self.clock_player = self.game.current_player
                self.clock_started_at = time.time()
            return
        self.clock_player = None
        self.clock_started_at = None

    def charge_clock(self) -> list[dict[str, Any]]:
        if (
            not self.started
            or self.game.result is not None
            or self.clock_player not in (0, 1)
            or self.clock_started_at is None
        ):
            self.arm_clock()
            return []

        now = time.time()
        player = self.clock_player
        elapsed = max(0.0, now - self.clock_started_at)
        self.consume_clock_elapsed(
            player,
            elapsed,
            self.turn_clocks,
            self.clocks,
        )
        self.clock_started_at = now
        if self.clocks[player] > 0:
            return []
        return self.force_loss(player, "timeout")

    def force_loss(self, loser: int, reason: str) -> list[dict[str, Any]]:
        winner = 1 - loser
        self.game.result = self.game.evaluate_result()
        self.game.result["winner"] = winner
        self.game.result["forced"] = reason
        self.game.phase = "game_over"
        self.game.held_die = None
        self.game.rolled_dice = []
        self.clock_player = None
        self.clock_started_at = None
        event_type = "timeout_loss" if reason == "timeout" else "forfeit_loss"
        return [
            {"type": event_type, "loser": loser, "winner": winner},
            {"type": "game_finished", "result": self.game.result},
        ]

    def snapshot(self, client_id: str | None = None) -> dict[str, Any]:
        slot = self.existing_slot_for(client_id) if client_id else None
        queue_position = (
            self.waiting_ids.index(client_id) + 1
            if client_id and client_id in self.waiting_ids
            else None
        )
        now = time.time()
        turn_clocks, total_clocks = self.clock_snapshot(now)
        return {
            "type": "snapshot",
            "room": {
                "code": self.code,
                "started": self.started,
                "players": self.public_players(),
                "rolloff": self.rolloff,
                "randomMatch": self.random_match,
                "streamerMode": self.streamer_mode,
                "queueLimit": self.queue_limit,
                "waitingPlayers": self.waiting_payload(),
                "ranked": self.ranked,
                "friendlyScore": self.friendly_wins,
                "createdAt": self.created_at,
                "updatedAt": self.updated_at,
                "clocks": total_clocks,
                "turnClocks": turn_clocks,
                "totalClocks": total_clocks,
                "clockPlayer": self.clock_player,
                "clockUpdatedAt": now,
                "turnTimeSeconds": TURN_TIME_SECONDS,
                "totalTimeSeconds": TOTAL_TIME_SECONDS,
                "rematchVotes": len(self.rematch_votes),
                "rematchNeeded": len(self.occupied_player_ids()),
            },
            "you": {
                "clientId": client_id,
                "player": slot,
                "spectator": slot is None,
                "queuePosition": queue_position,
                "stats": stats_payload(client_id) if client_id else None,
            },
            "game": self.game.snapshot(),
            "log": self.log,
        }

    def start_game_events(self, include_reset: bool = False) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if include_reset:
            events.extend(self.game.reset())

        self.ranked_recorded = False
        self.friendly_result_recorded = False
        self.rematch_votes.clear()
        self.ready_players.clear()
        self.reset_clocks()
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
        self.arm_clock(reset_turn=True)
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
leaderboard_cache: list[dict[str, Any]] | None = None
leaderboard_rank_cache: dict[str, int] = {}


def invalidate_leaderboard_cache() -> None:
    global leaderboard_cache, leaderboard_rank_cache
    leaderboard_cache = None
    leaderboard_rank_cache = {}


def stats_db_path() -> Path:
    return Path(os.getenv("TIKATUKA_STATS_DB", str(DEFAULT_STATS_DB_PATH)))


def stats_db_enabled() -> bool:
    if os.getenv("TIKATUKA_DISABLE_STATS_DB") == "1":
        return False
    return "pytest" not in sys.modules or bool(os.getenv("TIKATUKA_STATS_DB"))


def init_stats_db() -> None:
    if not stats_db_enabled():
        return
    path = stats_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS player_stats (
                client_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                score INTEGER NOT NULL,
                wins INTEGER NOT NULL,
                losses INTEGER NOT NULL,
                streak INTEGER NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )


def load_stats_from_db() -> None:
    if not stats_db_enabled():
        return
    init_stats_db()
    with sqlite3.connect(stats_db_path()) as connection:
        rows = connection.execute(
            "SELECT client_id, name, score, wins, losses, streak FROM player_stats"
        ).fetchall()
    for client_id, name, score, wins, losses, streak in rows:
        player_stats[str(client_id)] = PlayerStats(
            name=str(name),
            score=int(score),
            wins=int(wins),
            losses=int(losses),
            streak=int(streak),
        )
    invalidate_leaderboard_cache()


def persist_stats(client_id: str | None) -> None:
    if not client_id or not stats_db_enabled() or client_id not in player_stats:
        return
    init_stats_db()
    stats = player_stats[client_id]
    with sqlite3.connect(stats_db_path()) as connection:
        connection.execute(
            """
            INSERT INTO player_stats (client_id, name, score, wins, losses, streak, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(client_id) DO UPDATE SET
                name = excluded.name,
                score = excluded.score,
                wins = excluded.wins,
                losses = excluded.losses,
                streak = excluded.streak,
                updated_at = excluded.updated_at
            """,
            (
                client_id,
                stats.name,
                stats.score,
                stats.wins,
                stats.losses,
                stats.streak,
                time.time(),
            ),
        )


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "tikatuka", "rooms": len(rooms)}


@app.post("/api/heartbeat")
async def heartbeat(payload: dict[str, Any]) -> dict[str, Any]:
    client_id = clean_client_id(str(payload.get("clientId", "")))
    if client_id:
        touch_client(client_id)
        remember_player_name(client_id, str(payload.get("nickname", "")))
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


@app.post("/api/streamer-rooms")
async def create_streamer_room(payload: dict[str, Any]) -> dict[str, Any]:
    cleanup_rooms()
    client_id = clean_client_id(str(payload.get("clientId", "")))
    if not client_id:
        raise HTTPException(status_code=400, detail="clientId가 필요합니다.")
    nickname = clean_nickname(str(payload.get("nickname", "")), PLAYER_NAMES[0])
    try:
        queue_limit = int(payload.get("queueLimit", 1))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="대기 인원은 1~10명이어야 합니다.")
    if not 1 <= queue_limit <= MAX_STREAMER_QUEUE:
        raise HTTPException(status_code=400, detail="대기 인원은 1~10명이어야 합니다.")

    for _ in range(200):
        code = f"{secrets.randbelow(10_000):04d}"
        if code not in rooms:
            room = Room(
                code=code,
                streamer_mode=True,
                queue_limit=queue_limit,
            )
            room.player_ids[0] = client_id
            room.player_names[0] = nickname
            rooms[code] = room
            touch_client(client_id)
            remember_player_name(client_id, nickname)
            return {"code": code, "queueLimit": queue_limit}
    raise HTTPException(status_code=503, detail="방 번호를 만들 수 없습니다.")


@app.post("/api/random-match")
async def random_match(payload: dict[str, Any]) -> dict[str, Any]:
    cleanup_rooms()
    client_id = clean_client_id(str(payload.get("clientId", "")))
    if not client_id:
        raise HTTPException(status_code=400, detail="clientId가 필요합니다.")
    nickname = clean_nickname(str(payload.get("nickname", "")), PLAYER_NAMES[0])
    touch_client(client_id)
    remember_player_name(client_id, nickname)

    for room in sorted(rooms.values(), key=lambda item: item.created_at):
        if (
            room.random_match
            and not room.started
            and room.player_ids[0] == client_id
            and room.player_ids[1] is None
            and random_waiting_player_alive(room)
        ):
            room.player_names[0] = clean_nickname(nickname, PLAYER_NAMES[0])
            room.touch()
            return {"code": room.code, "matched": False, "player": 0}

    for room in sorted(rooms.values(), key=lambda item: item.created_at):
        if is_joinable_random_room(room, client_id):
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
        "streamerMode": room.streamer_mode,
        "queueLimit": room.queue_limit,
        "waitingCount": len(room.waiting_ids),
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
        if room.streamer_mode:
            role = room.assign_streamer_client(client_id, nickname)
            if role is None:
                await websocket.send_json(
                    {
                        "type": "room_closed",
                        "message": "방송인 모드 대기열 정원이 가득 찼습니다.",
                    }
                )
                await websocket.close(code=1008, reason="streamer queue full")
                return
            slot = room.existing_slot_for(client_id)
        else:
            slot = room.slot_for(client_id)
            if slot is None:
                await websocket.send_json(
                    {"type": "room_closed", "message": "방이 가득 찼습니다."}
                )
                await websocket.close(code=1008, reason="room full")
                return

        if slot is not None:
            room.player_names[slot] = clean_nickname(nickname, PLAYER_NAMES[slot])
            room.connected[slot] = True
            display_name = room.player_names[slot]
        else:
            display_name = room.waiting_names[client_id]
        remember_player_name(client_id, display_name)
        room.sockets[client_id] = websocket
        if (
            not room.streamer_mode
            and not room.started
            and all(room.player_ids)
            and all(room.connected)
        ):
            room.started = True
            room.add_events([{"type": "room_started"}])
            room.add_events(room.start_game_events())
        else:
            room.touch()
        await broadcast(room)
        if (
            room.random_match
            and room.started
            and room.game.result is None
            and not all(room.connected)
        ):
            live_slots = connected_random_slots(room)
            if len(live_slots) == 1:
                prepare_random_room_for_waiting(room, live_slots[0])
            elif not live_slots:
                rooms.pop(room.code, None)
            await broadcast(room)

    try:
        while True:
            payload = await websocket.receive_json()
            await handle_message(room, client_id, payload)
    except WebSocketDisconnect:
        pass
    finally:
        async with room.lock:
            current_socket = room.sockets.get(client_id)
            if current_socket is not None and current_socket is not websocket:
                return
            slot = room.existing_slot_for(client_id)
            is_waiting = client_id in room.waiting_ids
            if current_socket is websocket:
                room.sockets.pop(client_id, None)

            if room.streamer_mode:
                if slot == 0 and rooms.get(room.code) is room:
                    await destroy_room(room, "방송인이 나가 방이 종료되었습니다.")
                    return
                if slot == 1:
                    advance_streamer_queue(room)
                    await broadcast(room)
                    return
                if is_waiting:
                    room.waiting_ids.remove(client_id)
                    room.waiting_names.pop(client_id, None)
                    room.ready_players.discard(client_id)
                    room.touch()
                    await broadcast(room)
                    return

            if slot is not None and room.started and room.game.result is None:
                room.add_events(room.force_loss(slot, "leave"))
                apply_ranked_result(room)
                if room.random_match:
                    prepare_random_room_for_waiting(room, 1 - slot)
                    await broadcast(room)
                    return
                if slot == 0 and rooms.get(room.code) is room:
                    await destroy_room(room, "방장이 나가 방이 종료되었습니다.")
                    return

            if room.random_match and slot is not None:
                room.connected[slot] = False
                other_slot = 1 - slot
                if room.player_ids[other_slot]:
                    prepare_random_room_for_waiting(room, other_slot)
                    await broadcast(room)
                    return
                rooms.pop(room.code, None)
                return

            if slot == 0 and rooms.get(room.code) is room:
                await destroy_room(room, "방장이 나가 방이 종료되었습니다.")
                return
            if slot == 1:
                reset_manual_room_for_guest(room)
                await broadcast(room)


async def handle_message(room: Room, client_id: str, payload: dict[str, Any]) -> None:
    async with room.lock:
        slot = room.existing_slot_for(client_id)
        msg_type = str(payload.get("type", "action"))

        if msg_type == "waiting_emoticon":
            if not room.streamer_mode or client_id not in room.waiting_ids:
                await send_error(room, client_id, "대기자만 사용할 수 있습니다.")
                return
            emoticon = clean_emoticon_id(str(payload.get("emoticon", "")))
            if not emoticon:
                await send_error(room, client_id, "알 수 없는 이모티콘입니다.")
                return
            room.add_events(
                [
                    {
                        "type": "waiting_emoticon",
                        "name": room.waiting_names.get(client_id, "대기자"),
                        "emoticon": emoticon,
                    }
                ]
            )
            await broadcast(room)
            return

        if slot is None:
            await send_error(room, client_id, "현재 대기 순서라 게임을 조작할 수 없습니다.")
            return

        if msg_type == "ready":
            if not room.streamer_mode:
                await send_error(room, client_id, "방송인 모드에서만 준비할 수 있습니다.")
                return
            if room.started or room.game.result:
                await send_error(room, client_id, "지금은 준비할 수 없습니다.")
                return
            if not all(room.player_ids) or not all(room.connected):
                await send_error(room, client_id, "상대가 입장할 때까지 기다려주세요.")
                return
            room.ready_players.add(client_id)
            needed_players = set(room.occupied_player_ids())
            if len(needed_players) == 2 and needed_players.issubset(room.ready_players):
                room.started = True
                room.add_events([{"type": "room_started"}])
                room.add_events(room.start_game_events())
            else:
                room.touch()
            await broadcast(room)
            return

        if msg_type == "kick_opponent":
            if room.random_match or slot != 0:
                await send_error(room, client_id, "방장만 상대를 내보낼 수 있습니다.")
                return
            if not room.game.result:
                await send_error(room, client_id, "게임 종료 후 내보낼 수 있습니다.")
                return
            if not room.player_ids[1]:
                await send_error(room, client_id, "내보낼 상대가 없습니다.")
                return
            await evict_room_opponent(room)
            return

        if msg_type == "timeout_check":
            events = room.charge_clock()
            if events:
                room.add_events(events)
                room.ready_players.clear()
                apply_ranked_result(room)
                await broadcast(room)
                timeout_event = next(
                    (event for event in events if event.get("type") == "timeout_loss"),
                    None,
                )
                if room.random_match and timeout_event:
                    await evict_random_timeout_loser(room, int(timeout_event["loser"]))
            return

        if not room.started:
            await send_error(room, client_id, "상대가 입장할 때까지 기다려주세요.")
            return

        if msg_type == "emoticon":
            emoticon = clean_emoticon_id(str(payload.get("emoticon", "")))
            if not emoticon:
                await send_error(room, client_id, "알 수 없는 이모티콘입니다.")
                return
            room.add_events([{"type": "emoticon", "player": slot, "emoticon": emoticon}])
            await broadcast(room)
            return

        if msg_type == "restart":
            if not room.game.result:
                await send_error(room, client_id, "게임 종료 후 다시 시작할 수 있습니다.")
                return
            room.rematch_votes.add(client_id)
            needed_votes = set(room.occupied_player_ids())
            if len(needed_votes) < 2:
                await send_error(room, client_id, "상대가 입장해야 다시 시작할 수 있습니다.")
                return
            if needed_votes.issubset(room.rematch_votes):
                events = room.start_game_events(include_reset=True)
                room.started = all(room.player_ids)
                room.add_events(events)
            else:
                room.touch()
            await broadcast(room)
            return

        clock_events = room.charge_clock()
        if clock_events:
            room.add_events(clock_events)
            room.ready_players.clear()
            apply_ranked_result(room)
            await broadcast(room)
            return

        if room.game.result:
            await send_error(room, client_id, "이미 종료된 게임입니다.")
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
        next_turn_started = any(event.get("type") == "die_rolled" for event in events)
        room.arm_clock(reset_turn=next_turn_started)
        if room.game.result:
            room.ready_players.clear()
        apply_ranked_result(room)
        await broadcast(room)


async def broadcast(room: Room) -> None:
    stale: dict[str, WebSocket] = {}
    for client_id, socket in room.sockets.items():
        try:
            await socket.send_json(room.snapshot(client_id))
        except (RuntimeError, WebSocketDisconnect):
            stale[client_id] = socket
    for client_id, socket in stale.items():
        if room.sockets.get(client_id) is not socket:
            continue
        room.sockets.pop(client_id, None)
        slot = room.existing_slot_for(client_id)
        if slot is not None:
            room.connected[slot] = False


async def send_error(room: Room, client_id: str, message: str) -> None:
    socket = room.sockets.get(client_id)
    if socket:
        await socket.send_json({"type": "error", "message": message})


def reset_room_round(room: Room) -> None:
    room.started = False
    room.rolloff = None
    room.ranked_recorded = False
    room.rematch_votes.clear()
    room.ready_players.clear()
    room.reset_clocks()
    room.game.reset()
    room.log.clear()


def reset_manual_room_for_guest(room: Room) -> None:
    guest_id = room.player_ids[1]
    if guest_id:
        room.ready_players.discard(guest_id)
        room.rematch_votes.discard(guest_id)
    room.player_ids[1] = None
    room.player_names[1] = WAITING_PLAYER_NAME
    room.connected[1] = False
    room.friendly_wins = [0, 0]
    room.friendly_result_recorded = False
    reset_room_round(room)
    room.add_events([{"type": "waiting_for_player"}])


def advance_streamer_queue(room: Room) -> None:
    current_id = room.player_ids[1]
    if current_id:
        room.ready_players.discard(current_id)
        room.rematch_votes.discard(current_id)

    room.player_ids[1] = None
    room.player_names[1] = WAITING_PLAYER_NAME
    room.connected[1] = False
    promoted_name: str | None = None
    if room.waiting_ids:
        promoted_id = room.waiting_ids.pop(0)
        promoted_name = room.waiting_names.pop(promoted_id, "대기자")
        room.player_ids[1] = promoted_id
        room.player_names[1] = promoted_name
        room.connected[1] = promoted_id in room.sockets

    reset_room_round(room)
    room.add_events(
        [
            {
                "type": "streamer_challenger_changed",
                "name": promoted_name,
            }
        ]
    )


async def evict_room_opponent(room: Room) -> None:
    opponent_id = room.player_ids[1]
    if not opponent_id:
        return
    opponent_socket = room.sockets.pop(opponent_id, None)
    room.connected[1] = False
    if room.streamer_mode:
        advance_streamer_queue(room)
    else:
        reset_manual_room_for_guest(room)

    if opponent_socket:
        try:
            await opponent_socket.send_json(
                {
                    "type": "room_closed",
                    "message": "방장이 상대 플레이어를 내보냈습니다.",
                }
            )
        except (RuntimeError, WebSocketDisconnect):
            pass
        try:
            await opponent_socket.close(code=1000, reason="kicked by host")
        except RuntimeError:
            pass
    await broadcast(room)


async def evict_random_timeout_loser(room: Room, loser: int) -> None:
    winner = 1 - loser
    loser_id = room.player_ids[loser]
    if not loser_id or not room.player_ids[winner]:
        return

    loser_socket = room.sockets.pop(loser_id, None)
    room.connected[loser] = False
    prepare_random_room_for_waiting(room, winner)

    if loser_socket:
        try:
            await loser_socket.send_json(
                {
                    "type": "room_closed",
                    "message": "시간 초과로 패배하여 랜덤 매칭 방에서 나갔습니다.",
                }
            )
        except RuntimeError:
            pass
        try:
            await loser_socket.close(code=1000, reason="timeout loss")
        except RuntimeError:
            pass

    await broadcast(room)


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
    for room in list(rooms.values()):
        recover_stalled_random_room(room, now)

    expired = [
        code
        for code, room in rooms.items()
        if not room.sockets
        and (
            now - room.updated_at > ROOM_TTL_SECONDS
            or (
                room.random_match
                and not room.started
                and (
                    now - room.updated_at > RANDOM_WAIT_TTL_SECONDS
                    or (
                        now - room.updated_at > RANDOM_WAIT_CONNECT_GRACE_SECONDS
                        and not random_waiting_player_alive(room, now)
                    )
                )
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


def connected_random_slots(room: Room) -> list[int]:
    return [
        slot
        for slot, client_id in enumerate(room.player_ids)
        if client_id and room.connected[slot] and client_id in room.sockets
    ]


def recover_stalled_random_room(room: Room, now: float) -> None:
    if (
        not room.random_match
        or room.started
        or not all(room.player_ids)
        or now - room.updated_at <= RANDOM_WAIT_CONNECT_GRACE_SECONDS
    ):
        return

    live_slots = connected_random_slots(room)
    if len(live_slots) == 1:
        prepare_random_room_for_waiting(room, live_slots[0])
    elif not live_slots:
        rooms.pop(room.code, None)


def prepare_random_room_for_waiting(room: Room, keep_slot: int) -> None:
    keep_id = room.player_ids[keep_slot]
    if not keep_id:
        rooms.pop(room.code, None)
        return

    keep_name = room.player_names[keep_slot]
    keep_connected = room.connected[keep_slot]
    room.player_ids = [keep_id, None]
    room.player_names = [keep_name, WAITING_PLAYER_NAME]
    room.connected = [keep_connected, False]
    room.started = False
    room.rolloff = None
    room.ranked_recorded = False
    room.rematch_votes.clear()
    room.ready_players.clear()
    room.reset_clocks()
    room.game.reset()
    room.log.clear()
    room.add_events([{"type": "waiting_for_random", "player": 0}])


def random_waiting_player_alive(room: Room, now: float | None = None) -> bool:
    if not room.random_match or room.started or room.player_ids[0] is None or room.player_ids[1] is not None:
        return False
    now = now or time.time()
    waiting_id = room.player_ids[0]
    return (
        room.connected[0]
        or waiting_id in room.sockets
        or now - room.updated_at <= RANDOM_WAIT_CONNECT_GRACE_SECONDS
    )


def is_joinable_random_room(room: Room, client_id: str) -> bool:
    return (
        room.random_match
        and not room.started
        and room.player_ids[0] is not None
        and room.player_ids[0] != client_id
        and room.player_ids[1] is None
        and random_waiting_player_alive(room)
    )


def clean_nickname(value: str, fallback: str) -> str:
    nickname = " ".join(value.strip().split())
    if not nickname:
        return fallback
    return nickname[:16]


def clean_emoticon_id(value: str) -> str | None:
    emoticon = "".join(char for char in value.strip().lower() if char.isalnum())
    return emoticon if emoticon in ALLOWED_EMOTICONS else None


def clean_client_id(value: str) -> str:
    return value.strip()[:80]


def stats_for(client_id: str | None) -> PlayerStats:
    if not client_id:
        return PlayerStats()
    if client_id not in player_stats:
        player_stats[client_id] = PlayerStats()
    return player_stats[client_id]


def remember_player_name(client_id: str, nickname: str) -> None:
    clean_name = clean_nickname(nickname, "")
    stats = stats_for(client_id)
    if not clean_name or stats.name == clean_name:
        return
    stats.name = clean_name
    invalidate_leaderboard_cache()
    persist_stats(client_id)


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
        "stats": stats_payload(client_id) if client_id else PlayerStats().to_dict(),
        "leaderboard": leaderboard_payload(),
    }


def leaderboard_payload() -> list[dict[str, Any]]:
    global leaderboard_cache, leaderboard_rank_cache
    if leaderboard_cache is not None:
        return leaderboard_cache

    ranked_players = [
        {
            "clientId": client_id,
            **stats.to_dict(),
        }
        for client_id, stats in player_stats.items()
        if stats.score > 0 or stats.wins > 0 or stats.losses > 0
    ]
    ranked_players.sort(
        key=lambda item: (
            -item["score"],
            -item["wins"],
            item["losses"],
            item["name"],
            item["clientId"],
        )
    )
    leaderboard_cache = [
        {
            **entry,
            "rank": index + 1,
        }
        for index, entry in enumerate(ranked_players[:20])
    ]
    leaderboard_rank_cache = {
        str(entry["clientId"]): int(entry["rank"])
        for entry in leaderboard_cache
    }
    return leaderboard_cache


def leaderboard_rank(client_id: str | None) -> int | None:
    if not client_id:
        return None
    leaderboard_payload()
    return leaderboard_rank_cache.get(client_id)


def stats_payload(client_id: str | None) -> dict[str, Any]:
    stats = stats_for(client_id).to_dict()
    rank = leaderboard_rank(client_id)
    if rank is not None:
        stats["rank"] = rank
    return stats


def apply_ranked_result(room: Room) -> None:
    if (
        not room.random_match
        and not room.streamer_mode
        and not room.friendly_result_recorded
        and room.game.result
    ):
        winner = room.game.result.get("winner")
        if winner in (0, 1):
            room.friendly_wins[winner] += 1
        room.friendly_result_recorded = True

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
    invalidate_leaderboard_cache()
    persist_stats(winner_id)
    persist_stats(loser_id)


load_stats_from_db()
