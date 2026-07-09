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

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .game_engine import GameEngine, PLAYER_NAMES


ROOM_TTL_SECONDS = 60 * 60 * 6
RANDOM_WAIT_TTL_SECONDS = 60 * 5
RANDOM_WAIT_CONNECT_GRACE_SECONDS = 20
RANDOM_RECENT_REMATCH_BLOCK_SECONDS = 10
MAX_STREAMER_QUEUE = 10
TOURNAMENT_SIZES = {4, 8, 16}
TOURNAMENT_TARGET_WINS = {1, 2, 3}
ONLINE_WINDOW_SECONDS = 45
MAX_LOG_ITEMS = 80
TURN_TIME_SECONDS = 15
TOTAL_TIME_SECONDS = 60
WAITING_PLAYER_NAME = "상대 대기중..."
DEFAULT_EMOTICONS = {"gogo", "lol", "sad", "stop", "what", "whatwhat"}
ALLOWED_EMOTICONS = (
    DEFAULT_EMOTICONS
    | {f"mokoko_{index:03d}" for index in range(1, 119)}
    | {f"yoz_{index:03d}" for index in range(1, 17)}
)
TITLE_LABEL_MAX_LENGTH = 18
TITLE_COLOR_PALETTE: dict[str, dict[str, str]] = {
    "gold": {"name": "금색", "tone": "warm"},
    "silver": {"name": "은색", "tone": "cool"},
    "bronze": {"name": "동색", "tone": "warm"},
    "crimson": {"name": "진홍", "tone": "danger"},
    "rose": {"name": "장미", "tone": "cute"},
    "violet": {"name": "보라", "tone": "magic"},
    "indigo": {"name": "남보라", "tone": "magic"},
    "sky": {"name": "하늘", "tone": "cool"},
    "cyan": {"name": "청록", "tone": "cool"},
    "emerald": {"name": "에메랄드", "tone": "fresh"},
    "lime": {"name": "라임", "tone": "fresh"},
    "amber": {"name": "호박", "tone": "warm"},
    "black": {"name": "흑색", "tone": "dark"},
    "white": {"name": "백색", "tone": "light"},
    "rainbow": {"name": "무지개", "tone": "special"},
    "neon": {"name": "네온", "tone": "special"},
    "duelist": {"name": "듀얼리스트 블루", "tone": "special"},
    "mirang": {"name": "미랑 민트", "tone": "special"},
}
TITLE_ICON_PALETTE: dict[str, dict[str, str]] = {
    "none": {"name": "없음", "symbol": ""},
    "crown": {"name": "왕관", "symbol": "👑"},
    "star": {"name": "별", "symbol": "⭐"},
    "spark": {"name": "반짝", "symbol": "✨"},
    "fire": {"name": "불꽃", "symbol": "🔥"},
    "lightning": {"name": "번개", "symbol": "⚡"},
    "shield": {"name": "방패", "symbol": "🛡️"},
    "dice": {"name": "주사위", "symbol": "🎲"},
    "duck": {"name": "오리", "symbol": "🦆"},
    "chick": {"name": "병아리", "symbol": "🐣"},
    "robot": {"name": "로봇", "symbol": "🤖"},
    "gem": {"name": "보석", "symbol": "💎"},
    "moon": {"name": "달", "symbol": "🌙"},
    "comet": {"name": "혜성", "symbol": "☄️"},
    "trophy": {"name": "트로피", "symbol": "🏆"},
    "ghost": {"name": "유령", "symbol": "👻"},
    "clover": {"name": "클로버", "symbol": "🍀"},
    "heart": {"name": "하트", "symbol": "💖"},
    "duelist": {"name": "듀얼리스트 파란 주사위", "symbol": ""},
    "mirang": {"name": "미랑 번개", "symbol": ""},
}
TITLE_EFFECT_PALETTE: dict[str, dict[str, str]] = {
    "none": {"name": "없음"},
    "glow": {"name": "은은한 빛"},
    "shine": {"name": "광택"},
    "pulse": {"name": "맥박"},
    "sparkle": {"name": "반짝임"},
    "rainbow": {"name": "무지개 흐름"},
    "shake": {"name": "살짝 흔들림"},
    "flame": {"name": "불꽃 오라"},
    "aurora": {"name": "오로라"},
    "crystal": {"name": "크리스탈 반짝임"},
}
RANK_TITLE_ID = "rank-top"
DUELIST_TITLE_ID = "duelist"
DEVELOPER_TITLE_ID = "developer"
MIRANG_TITLE_ID = "mirang"
TIER_ORDER = ["bronze", "silver", "gold", "platinum", "diamond", "master"]
TIER_LABELS = {
    "bronze": "브론즈",
    "silver": "실버",
    "gold": "골드",
    "platinum": "플레티넘",
    "diamond": "다이아",
    "master": "마스터",
}
BASE_TIER = "bronze"
BASE_TIER_GRADE = 5
BASE_TIER_STARS = 0
MASTER_START_POINTS = 100
DEFAULT_STATS_DB_PATH = (
    Path(__file__).resolve().parents[3] / "tikatuka-data" / "tikatuka_stats.sqlite3"
)


@dataclass
class PlayerTitle:
    title_id: str
    label: str
    color: str = "gold"
    icon: str = "star"
    effect: str = "glow"

    def to_dict(self) -> dict[str, Any]:
        icon_info = TITLE_ICON_PALETTE.get(self.icon, TITLE_ICON_PALETTE["star"])
        return {
            "id": self.title_id,
            "label": self.label,
            "color": self.color,
            "icon": self.icon,
            "iconText": icon_info["symbol"],
            "effect": self.effect,
        }


@dataclass
class PlayerStats:
    name: str = "플레이어"
    score: int = 0
    wins: int = 0
    losses: int = 0
    streak: int = 0
    tier: str = BASE_TIER
    tier_grade: int = BASE_TIER_GRADE
    tier_stars: int = BASE_TIER_STARS
    master_points: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "wins": self.wins,
            "losses": self.losses,
            "streak": self.streak,
            "tier": tier_payload(self),
        }


@dataclass
class TournamentMatch:
    match_id: str
    round_index: int
    match_index: int
    player_ids: list[str | None]
    scores: list[int] = field(default_factory=lambda: [0, 0])
    winner_id: str | None = None
    completed: bool = False
    active: bool = False


@dataclass
class TournamentState:
    host_id: str
    host_name: str
    host_participates: bool
    size: int
    target_wins: int
    status: str = "lobby"
    participant_ids: list[str] = field(default_factory=list)
    participant_names: dict[str, str] = field(default_factory=dict)
    slots: list[str | None] = field(default_factory=list)
    rounds: list[list[TournamentMatch]] = field(default_factory=list)
    current_match_id: str | None = None
    winner_id: str | None = None


@dataclass
class Room:
    code: str
    random_match: bool = False
    streamer_mode: bool = False
    tournament_mode: bool = False
    queue_limit: int = 0
    ranked: bool = False
    ranked_recorded: bool = False
    friendly_wins: list[int] = field(default_factory=lambda: [0, 0])
    friendly_result_recorded: bool = False
    game: GameEngine = field(default_factory=GameEngine)
    player_ids: list[str | None] = field(default_factory=lambda: [None, None])
    player_names: list[str] = field(default_factory=lambda: PLAYER_NAMES.copy())
    player_ips: list[str] = field(default_factory=lambda: ["", ""])
    connected: list[bool] = field(default_factory=lambda: [False, False])
    sockets: dict[str, WebSocket] = field(default_factory=dict)
    started: bool = False
    rolloff: dict[str, Any] | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    random_wait_started_at: float = field(default_factory=time.time)
    log: list[dict[str, Any]] = field(default_factory=list)
    rematch_votes: set[str] = field(default_factory=set)
    ready_players: set[str] = field(default_factory=set)
    waiting_ids: list[str] = field(default_factory=list)
    waiting_names: dict[str, str] = field(default_factory=dict)
    tournament: TournamentState | None = None
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
        if self.tournament_mode and self.tournament:
            active_ids = {client_id for client_id in self.player_ids if client_id}
            return [
                {
                    "position": position,
                    "name": self.tournament.participant_names.get(client_id, "참가자"),
                    "stats": stats_payload(client_id),
                }
                for position, client_id in enumerate(
                    [
                        client_id
                        for client_id in self.tournament.participant_ids
                        if client_id not in active_ids
                    ],
                    start=1,
                )
            ]
        return [
            {
                "position": position,
                "name": self.waiting_names.get(client_id, "대기자"),
                "stats": stats_payload(client_id),
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

    def assign_tournament_client(self, client_id: str, nickname: str) -> str | None:
        if not self.tournament:
            return None
        display_name = clean_nickname(nickname, "참가자")
        if client_id == self.tournament.host_id:
            self.tournament.host_name = display_name
            if self.tournament.host_participates:
                add_tournament_participant(self, client_id, display_name)
            return "host"
        if client_id in self.tournament.participant_ids:
            self.tournament.participant_names[client_id] = display_name
            return "participant"
        if self.tournament.status != "lobby":
            return None
        if len(self.tournament.participant_ids) >= self.tournament.size:
            return None
        add_tournament_participant(self, client_id, display_name)
        return "participant"

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
        tournament_position = (
            self.tournament.participant_ids.index(client_id) + 1
            if (
                client_id
                and self.tournament_mode
                and self.tournament
                and client_id in self.tournament.participant_ids
                and client_id not in self.player_ids
            )
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
                "tournamentMode": self.tournament_mode,
                "tournament": tournament_payload(self),
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
                "tournamentPosition": tournament_position,
                "stats": stats_payload(client_id, include_titles=True) if client_id else None,
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
player_titles: dict[str, PlayerTitle] = {}
player_title_inventory: dict[str, dict[str, PlayerTitle]] = {}
client_last_seen: dict[str, float] = {}
last_random_opponents: dict[str, str] = {}
leaderboard_cache: list[dict[str, Any]] | None = None
leaderboard_rank_cache: dict[str, int] = {}
maintenance_drain_enabled = False


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
                tier TEXT NOT NULL DEFAULT 'bronze',
                tier_grade INTEGER NOT NULL DEFAULT 5,
                tier_stars INTEGER NOT NULL DEFAULT 0,
                master_points INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL
            )
            """
        )
        stats_columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(player_stats)").fetchall()
        }
        for column_name, column_definition in [
            ("tier", "TEXT NOT NULL DEFAULT 'bronze'"),
            ("tier_grade", "INTEGER NOT NULL DEFAULT 5"),
            ("tier_stars", "INTEGER NOT NULL DEFAULT 0"),
            ("master_points", "INTEGER NOT NULL DEFAULT 0"),
        ]:
            if column_name not in stats_columns:
                connection.execute(
                    f"ALTER TABLE player_stats ADD COLUMN {column_name} {column_definition}"
                )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS player_titles (
                client_id TEXT PRIMARY KEY,
                title_id TEXT NOT NULL DEFAULT '',
                label TEXT NOT NULL,
                color TEXT NOT NULL,
                icon TEXT NOT NULL,
                effect TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(player_titles)").fetchall()
        }
        if "title_id" not in columns:
            connection.execute(
                "ALTER TABLE player_titles ADD COLUMN title_id TEXT NOT NULL DEFAULT ''"
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS player_title_inventory (
                client_id TEXT NOT NULL,
                title_id TEXT NOT NULL,
                label TEXT NOT NULL,
                color TEXT NOT NULL,
                icon TEXT NOT NULL,
                effect TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (client_id, title_id)
            )
            """
        )


def load_stats_from_db() -> None:
    if not stats_db_enabled():
        return
    init_stats_db()
    with sqlite3.connect(stats_db_path()) as connection:
        rows = connection.execute(
            """
            SELECT client_id, name, score, wins, losses, streak,
                   tier, tier_grade, tier_stars, master_points
            FROM player_stats
            """
        ).fetchall()
        inventory_rows = connection.execute(
            """
            SELECT client_id, title_id, label, color, icon, effect
            FROM player_title_inventory
            """
        ).fetchall()
        title_rows = connection.execute(
            "SELECT client_id, title_id, label, color, icon, effect FROM player_titles"
        ).fetchall()
    for (
        client_id,
        name,
        score,
        wins,
        losses,
        streak,
        tier,
        tier_grade,
        tier_stars,
        master_points,
    ) in rows:
        player_stats[str(client_id)] = PlayerStats(
            name=str(name),
            score=int(score),
            wins=int(wins),
            losses=int(losses),
            streak=int(streak),
            tier=normalize_tier_key(str(tier)),
            tier_grade=normalize_tier_grade(tier_grade),
            tier_stars=normalize_tier_stars(tier_stars),
            master_points=max(0, int(master_points or 0)),
        )
    for client_id, title_id, label, color, icon, effect in inventory_rows:
        client_key = str(client_id)
        title = PlayerTitle(
            title_id=clean_title_id(str(title_id), str(label)),
            label=clean_title_label(str(label)),
            color=safe_palette_key(str(color), TITLE_COLOR_PALETTE, "gold"),
            icon=safe_palette_key(str(icon), TITLE_ICON_PALETTE, "star"),
            effect=safe_palette_key(str(effect), TITLE_EFFECT_PALETTE, "glow"),
        )
        player_title_inventory.setdefault(client_key, {})[title.title_id] = title
    for client_id, title_id, label, color, icon, effect in title_rows:
        client_key = str(client_id)
        title = PlayerTitle(
            title_id=clean_title_id(str(title_id), str(label)),
            label=clean_title_label(str(label)),
            color=safe_palette_key(str(color), TITLE_COLOR_PALETTE, "gold"),
            icon=safe_palette_key(str(icon), TITLE_ICON_PALETTE, "star"),
            effect=safe_palette_key(str(effect), TITLE_EFFECT_PALETTE, "glow"),
        )
        player_titles[client_key] = title
        player_title_inventory.setdefault(client_key, {})[title.title_id] = title
    invalidate_leaderboard_cache()


def persist_stats(client_id: str | None) -> None:
    if not client_id or not stats_db_enabled() or client_id not in player_stats:
        return
    init_stats_db()
    stats = player_stats[client_id]
    with sqlite3.connect(stats_db_path()) as connection:
        connection.execute(
            """
            INSERT INTO player_stats (
                client_id, name, score, wins, losses, streak,
                tier, tier_grade, tier_stars, master_points, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(client_id) DO UPDATE SET
                name = excluded.name,
                score = excluded.score,
                wins = excluded.wins,
                losses = excluded.losses,
                streak = excluded.streak,
                tier = excluded.tier,
                tier_grade = excluded.tier_grade,
                tier_stars = excluded.tier_stars,
                master_points = excluded.master_points,
                updated_at = excluded.updated_at
            """,
            (
                client_id,
                stats.name,
                stats.score,
                stats.wins,
                stats.losses,
                stats.streak,
                normalize_tier_key(stats.tier),
                normalize_tier_grade(stats.tier_grade),
                normalize_tier_stars(stats.tier_stars),
                max(0, int(stats.master_points)),
                time.time(),
            ),
        )


def persist_title(client_id: str | None) -> None:
    if not client_id or not stats_db_enabled() or client_id not in player_titles:
        return
    init_stats_db()
    title = player_titles[client_id]
    with sqlite3.connect(stats_db_path()) as connection:
        connection.execute(
            """
            INSERT INTO player_titles (client_id, title_id, label, color, icon, effect, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(client_id) DO UPDATE SET
                title_id = excluded.title_id,
                label = excluded.label,
                color = excluded.color,
                icon = excluded.icon,
                effect = excluded.effect,
                updated_at = excluded.updated_at
            """,
            (
                client_id,
                title.title_id,
                title.label,
                title.color,
                title.icon,
                title.effect,
                time.time(),
            ),
        )
    persist_title_inventory(client_id, title)


def persist_title_inventory(client_id: str | None, title: PlayerTitle | None) -> None:
    if not client_id or not title or not stats_db_enabled():
        return
    init_stats_db()
    with sqlite3.connect(stats_db_path()) as connection:
        connection.execute(
            """
            INSERT INTO player_title_inventory
                (client_id, title_id, label, color, icon, effect, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(client_id, title_id) DO UPDATE SET
                label = excluded.label,
                color = excluded.color,
                icon = excluded.icon,
                effect = excluded.effect,
                updated_at = excluded.updated_at
            """,
            (
                client_id,
                title.title_id,
                title.label,
                title.color,
                title.icon,
                title.effect,
                time.time(),
            ),
        )


def delete_title(client_id: str | None) -> None:
    if not client_id or not stats_db_enabled():
        return
    init_stats_db()
    with sqlite3.connect(stats_db_path()) as connection:
        connection.execute("DELETE FROM player_titles WHERE client_id = ?", (client_id,))


def delete_title_inventory(client_id: str | None, title_id: str | None = None) -> None:
    if not client_id or not stats_db_enabled():
        return
    init_stats_db()
    with sqlite3.connect(stats_db_path()) as connection:
        if title_id:
            connection.execute(
                "DELETE FROM player_title_inventory WHERE client_id = ? AND title_id = ?",
                (client_id, title_id),
            )
        else:
            connection.execute(
                "DELETE FROM player_title_inventory WHERE client_id = ?",
                (client_id,),
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


@app.post("/api/titles/equip")
async def equip_title(payload: dict[str, Any]) -> dict[str, Any]:
    client_id = clean_client_id(str(payload.get("clientId", "")))
    if not client_id:
        raise HTTPException(status_code=400, detail="clientId가 필요합니다.")
    title_id = clean_title_id(str(payload.get("titleId", "")))
    title = available_titles(client_id).get(title_id)
    if title is None:
        raise HTTPException(status_code=404, detail="보유하지 않은 칭호입니다.")

    player_titles[client_id] = title
    persist_title(client_id)
    await broadcast_title_update(client_id)
    return status_payload(client_id)


@app.post("/api/titles/unequip")
async def unequip_title(payload: dict[str, Any]) -> dict[str, Any]:
    client_id = clean_client_id(str(payload.get("clientId", "")))
    if not client_id:
        raise HTTPException(status_code=400, detail="clientId가 필요합니다.")

    player_titles.pop(client_id, None)
    delete_title(client_id)
    await broadcast_title_update(client_id)
    return status_payload(client_id)


@app.get("/api/admin/titles/palette")
async def admin_title_palette(
    authorization: str | None = Header(default=None),
    x_admin_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    require_admin_access(authorization, x_admin_secret)
    return title_palette_payload()


@app.get("/api/admin/players")
async def admin_find_players(
    nickname: str | None = None,
    client_id: str | None = None,
    limit: int = 20,
    authorization: str | None = Header(default=None),
    x_admin_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    require_admin_access(authorization, x_admin_secret)
    cleaned_client_id = clean_client_id(client_id or "")
    cleaned_nickname = " ".join((nickname or "").strip().split())
    limit = max(1, min(50, limit))
    needle = cleaned_nickname.casefold()
    now = time.time()
    matches: list[dict[str, Any]] = []

    for candidate_id in set(player_stats) | set(player_titles) | set(player_title_inventory):
        stats = player_stats.get(candidate_id, PlayerStats())
        if cleaned_client_id and candidate_id != cleaned_client_id:
            continue
        name = stats.name
        if needle and needle not in name.casefold():
            continue
        seen_at = client_last_seen.get(candidate_id)
        online = bool(seen_at and now - seen_at <= ONLINE_WINDOW_SECONDS)
        title = title_payload(candidate_id)
        matches.append(
            {
                "clientId": candidate_id,
                "name": name,
                "score": stats.score,
                "wins": stats.wins,
                "losses": stats.losses,
                "streak": stats.streak,
                "tier": tier_payload(stats),
                "online": online,
                "lastSeen": seen_at,
                "title": title,
                "exactMatch": bool(needle and name.casefold() == needle),
            }
        )

    matches.sort(
        key=lambda item: (
            -int(item["exactMatch"]),
            -int(item["online"]),
            -(item["lastSeen"] or 0),
            item["name"],
            item["clientId"],
        )
    )
    players = [
        {key: value for key, value in item.items() if key != "exactMatch"}
        for item in matches[:limit]
    ]
    return {"players": players, "count": len(matches)}


@app.post("/api/admin/players/stats")
async def admin_update_player_stats(
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
    x_admin_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    require_admin_access(authorization, x_admin_secret)
    client_id = clean_client_id(str(payload.get("clientId", "")))
    if not client_id:
        raise HTTPException(status_code=400, detail="clientId가 필요합니다.")
    stats = stats_for(client_id)

    if "name" in payload:
        stats.name = clean_nickname(str(payload.get("name", "")), stats.name)
    if "score" in payload:
        stats.score = max(0, int(payload.get("score") or 0))
    if "wins" in payload:
        stats.wins = max(0, int(payload.get("wins") or 0))
    if "losses" in payload:
        stats.losses = max(0, int(payload.get("losses") or 0))
    if "streak" in payload:
        stats.streak = int(payload.get("streak") or 0)
    if "tier" in payload:
        set_stats_tier(stats, normalize_tier_payload(payload.get("tier"), stats))

    persist_stats(client_id)
    invalidate_leaderboard_cache()
    await broadcast_stats_update(client_id)
    return {"clientId": client_id, "stats": stats_payload(client_id, include_titles=True)}


@app.post("/api/admin/players/reset-stats")
async def admin_reset_all_player_stats(
    authorization: str | None = Header(default=None),
    x_admin_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    require_admin_access(authorization, x_admin_secret)
    changed_ids = list(player_stats.keys())
    for stats in player_stats.values():
        reset_stats_to_bronze(stats)
    if stats_db_enabled():
        init_stats_db()
        with sqlite3.connect(stats_db_path()) as connection:
            connection.execute(
                """
                UPDATE player_stats
                SET score = 0,
                    wins = 0,
                    losses = 0,
                    streak = 0,
                    tier = ?,
                    tier_grade = ?,
                    tier_stars = ?,
                    master_points = 0,
                    updated_at = ?
                """,
                (BASE_TIER, BASE_TIER_GRADE, BASE_TIER_STARS, time.time()),
            )
    invalidate_leaderboard_cache()
    for client_id in changed_ids:
        await broadcast_stats_update(client_id)
    return {"reset": len(changed_ids), "tier": tier_payload(PlayerStats())}


@app.post("/api/admin/titles/grant")
async def admin_grant_title(
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
    x_admin_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    require_admin_access(authorization, x_admin_secret)
    client_id = clean_client_id(str(payload.get("clientId", "")))
    if not client_id:
        raise HTTPException(status_code=400, detail="clientId가 필요합니다.")

    title_label = clean_title_label(str(payload.get("label", "")))
    title = PlayerTitle(
        title_id=clean_title_id(str(payload.get("titleId", "")), title_label),
        label=title_label,
        color=coerce_palette_key(
            str(payload.get("color", "gold")),
            TITLE_COLOR_PALETTE,
            "gold",
        ),
        icon=coerce_palette_key(
            str(payload.get("icon", "star")),
            TITLE_ICON_PALETTE,
            "star",
        ),
        effect=coerce_palette_key(
            str(payload.get("effect", "glow")),
            TITLE_EFFECT_PALETTE,
            "glow",
        ),
    )
    player_title_inventory.setdefault(client_id, {})[title.title_id] = title
    persist_title_inventory(client_id, title)
    if payload.get("equip") is not False:
        player_titles[client_id] = title
        persist_title(client_id)
    await broadcast_title_update(client_id)
    return {"clientId": client_id, "title": title.to_dict()}


@app.post("/api/admin/titles/revoke")
async def admin_revoke_title(
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
    x_admin_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    require_admin_access(authorization, x_admin_secret)
    client_id = clean_client_id(str(payload.get("clientId", "")))
    if not client_id:
        raise HTTPException(status_code=400, detail="clientId가 필요합니다.")

    title_id_raw = str(payload.get("titleId", "")).strip()
    title_id = clean_title_id(title_id_raw) if title_id_raw else None
    removed = False
    if title_id:
        removed = player_title_inventory.get(client_id, {}).pop(title_id, None) is not None
        if not player_title_inventory.get(client_id):
            player_title_inventory.pop(client_id, None)
        if player_titles.get(client_id) and player_titles[client_id].title_id == title_id:
            player_titles.pop(client_id, None)
            delete_title(client_id)
        delete_title_inventory(client_id, title_id)
    else:
        removed_title = player_titles.pop(client_id, None)
        removed_inventory = player_title_inventory.pop(client_id, None)
        removed = bool(removed_title or removed_inventory)
        delete_title(client_id)
        delete_title_inventory(client_id)
    await broadcast_title_update(client_id)
    return {"clientId": client_id, "removed": removed}


@app.get("/api/admin/rooms/summary")
async def admin_rooms_summary(
    authorization: str | None = Header(default=None),
    x_admin_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    require_admin_access(authorization, x_admin_secret)
    return rooms_summary_payload()


@app.get("/api/admin/streamer-rooms")
async def admin_streamer_rooms(
    authorization: str | None = Header(default=None),
    x_admin_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    require_admin_access(authorization, x_admin_secret)
    payload = rooms_summary_payload()
    return {
        "onlineUsers": payload["onlineUsers"],
        "rooms": payload["streamerRooms"],
        "count": len(payload["streamerRooms"]),
    }


@app.get("/api/admin/random-waiting-rooms")
async def admin_random_waiting_rooms(
    minWaitSeconds: int = RANDOM_RECENT_REMATCH_BLOCK_SECONDS,
    authorization: str | None = Header(default=None),
    x_admin_secret: str | None = Header(default=None),
    x_bot_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    require_admin_or_bot_access(authorization, x_admin_secret, x_bot_secret)
    return random_waiting_rooms_payload(minWaitSeconds)


@app.get("/api/admin/server/state")
async def admin_server_state(
    authorization: str | None = Header(default=None),
    x_admin_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    require_admin_access(authorization, x_admin_secret)
    return server_state_payload()


@app.post("/api/admin/server/drain")
async def admin_server_drain(
    authorization: str | None = Header(default=None),
    x_admin_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    require_admin_access(authorization, x_admin_secret)
    global maintenance_drain_enabled
    maintenance_drain_enabled = True
    return server_state_payload()


@app.post("/api/admin/server/resume")
async def admin_server_resume(
    authorization: str | None = Header(default=None),
    x_admin_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    require_admin_access(authorization, x_admin_secret)
    global maintenance_drain_enabled
    maintenance_drain_enabled = False
    return server_state_payload()


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


@app.post("/api/tournament-rooms")
async def create_tournament_room(payload: dict[str, Any]) -> dict[str, Any]:
    cleanup_rooms()
    client_id = clean_client_id(str(payload.get("clientId", "")))
    if not client_id:
        raise HTTPException(status_code=400, detail="clientId가 필요합니다.")
    nickname = clean_nickname(str(payload.get("nickname", "")), PLAYER_NAMES[0])
    try:
        size = int(payload.get("size", 4))
        target_wins = int(payload.get("targetWins", 1))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="토너먼트 설정이 올바르지 않습니다.")
    if size not in TOURNAMENT_SIZES:
        raise HTTPException(status_code=400, detail="참가 인원은 4, 8, 16명만 가능합니다.")
    if target_wins not in TOURNAMENT_TARGET_WINS:
        raise HTTPException(status_code=400, detail="경기 방식은 단판, 3판2선승, 5판3선승만 가능합니다.")
    host_participates = bool(payload.get("hostParticipates", True))

    for _ in range(200):
        code = f"{secrets.randbelow(10_000):04d}"
        if code not in rooms:
            tournament = TournamentState(
                host_id=client_id,
                host_name=nickname,
                host_participates=host_participates,
                size=size,
                target_wins=target_wins,
                slots=[None for _ in range(size)],
            )
            room = Room(code=code, tournament_mode=True, tournament=tournament)
            if host_participates:
                add_tournament_participant(room, client_id, nickname)
            rooms[code] = room
            touch_client(client_id)
            remember_player_name(client_id, nickname)
            return {"code": code, "size": size, "targetWins": target_wins}
    raise HTTPException(status_code=503, detail="토너먼트 방 번호를 만들 수 없습니다.")


@app.post("/api/random-match")
async def random_match(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    cleanup_rooms()
    client_id = clean_client_id(str(payload.get("clientId", "")))
    if not client_id:
        raise HTTPException(status_code=400, detail="clientId가 필요합니다.")
    nickname = clean_nickname(str(payload.get("nickname", "")), PLAYER_NAMES[0])
    client_ip = request_ip(request)
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
            room.player_ips[0] = client_ip
            room.touch()
            return {"code": room.code, "matched": False, "player": 0}

    for room in sorted(rooms.values(), key=lambda item: item.created_at):
        if is_joinable_random_room(room, client_id, client_ip):
            room.player_ids[1] = client_id
            room.player_names[1] = clean_nickname(nickname, PLAYER_NAMES[1])
            room.player_ips[1] = client_ip
            room.touch()
            return {"code": room.code, "matched": True, "player": 1}

    for _ in range(200):
        code = f"{secrets.randbelow(10_000):04d}"
        if code not in rooms:
            room = Room(code=code, random_match=True, ranked=True)
            room.player_ids[0] = client_id
            room.player_names[0] = clean_nickname(nickname, PLAYER_NAMES[0])
            room.player_ips[0] = client_ip
            room.random_wait_started_at = time.time()
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
        "tournamentMode": room.tournament_mode,
        "tournament": tournament_payload(room),
        "queueLimit": room.queue_limit,
        "waitingCount": len(room.waiting_payload()),
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
        if room.tournament_mode:
            role = room.assign_tournament_client(client_id, nickname)
            if role is None:
                await websocket.send_json(
                    {
                        "type": "room_closed",
                        "message": "토너먼트 참가 정원이 가득 찼거나 이미 시작되었습니다.",
                    }
                )
                await websocket.close(code=1008, reason="tournament unavailable")
                return
            slot = room.existing_slot_for(client_id)
        elif room.streamer_mode:
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
        elif room.tournament_mode and room.tournament:
            display_name = (
                room.tournament.host_name
                if client_id == room.tournament.host_id
                else room.tournament.participant_names.get(client_id, "참가자")
            )
        else:
            display_name = room.waiting_names[client_id]
        remember_player_name(client_id, display_name)
        room.sockets[client_id] = websocket
        if (
            not room.streamer_mode
            and not room.tournament_mode
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

            if maintenance_drain_enabled:
                if slot is not None:
                    room.connected[slot] = False
                if is_waiting:
                    room.waiting_ids.remove(client_id)
                    room.waiting_names.pop(client_id, None)
                    room.ready_players.discard(client_id)
                room.touch()
                await broadcast(room)
                return

            if room.tournament_mode:
                if room.tournament and client_id == room.tournament.host_id and rooms.get(room.code) is room:
                    await destroy_room(room, "토너먼트 방장이 나가 방이 종료되었습니다.")
                    return
                if slot is not None and room.started and room.game.result is None:
                    room.add_events(room.force_loss(slot, "leave"))
                    apply_ranked_result(room)
                    finalize_tournament_game(room)
                    await broadcast(room)
                    return
                if slot is not None:
                    room.connected[slot] = False
                    await broadcast(room)
                    return
                if room.tournament and room.tournament.status == "lobby":
                    remove_tournament_participant(room, client_id)
                    await broadcast(room)
                    return
                await broadcast(room)
                return

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

        if msg_type.startswith("tournament_"):
            await handle_tournament_message(room, client_id, payload)
            return

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

        if msg_type == "timeout_check":
            events = room.charge_clock()
            if events:
                room.add_events(events)
                room.ready_players.clear()
                apply_ranked_result(room)
                finalize_tournament_game(room)
                await broadcast(room)
                timeout_event = next(
                    (event for event in events if event.get("type") == "timeout_loss"),
                    None,
                )
                if room.random_match and timeout_event:
                    await evict_random_timeout_loser(room, int(timeout_event["loser"]))
            return

        if slot is None:
            await send_error(room, client_id, "현재 대기 순서라 게임을 조작할 수 없습니다.")
            return

        if msg_type == "ready":
            if not room.streamer_mode:
                await send_error(room, client_id, "방송인 모드에서만 준비할 수 있습니다.")
                return
            if slot != 0:
                await send_error(room, client_id, "방송인만 게임을 시작할 수 있습니다.")
                return
            if room.started or room.game.result:
                await send_error(room, client_id, "지금은 준비할 수 없습니다.")
                return
            if not all(room.player_ids) or not all(room.connected):
                await send_error(room, client_id, "상대가 입장할 때까지 기다려주세요.")
                return
            room.started = True
            room.add_events([{"type": "room_started"}])
            room.add_events(room.start_game_events())
            await broadcast(room)
            return

        if msg_type == "kick_opponent":
            if room.random_match or room.tournament_mode or slot != 0:
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

        if not room.started:
            await send_error(room, client_id, "상대가 입장할 때까지 기다려주세요.")
            return

        if msg_type == "surrender":
            if room.game.result:
                await send_error(room, client_id, "이미 종료된 게임입니다.")
                return
            room.add_events(room.force_loss(slot, "surrender"))
            room.ready_players.clear()
            apply_ranked_result(room)
            finalize_tournament_game(room)
            await broadcast(room)
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
            if room.tournament_mode:
                await send_error(room, client_id, "토너먼트는 시작 버튼으로 다음 경기를 진행합니다.")
                return
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
            finalize_tournament_game(room)
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
        finalize_tournament_game(room)
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


async def handle_tournament_message(
    room: Room,
    client_id: str,
    payload: dict[str, Any],
) -> None:
    tournament = room.tournament
    if not room.tournament_mode or not tournament:
        await send_error(room, client_id, "토너먼트 방이 아닙니다.")
        return
    if client_id != tournament.host_id:
        await send_error(room, client_id, "토너먼트 방장만 진행할 수 있습니다.")
        return

    msg_type = str(payload.get("type", ""))
    if msg_type == "tournament_seed_random":
        try:
            seed_tournament_random(room)
        except ValueError as exc:
            await send_error(room, client_id, str(exc))
            return
        await broadcast(room)
        return

    if msg_type == "tournament_seed_manual":
        try:
            seed_tournament_manual(room, payload.get("slots", []))
        except ValueError as exc:
            await send_error(room, client_id, str(exc))
            return
        await broadcast(room)
        return

    if msg_type == "tournament_start":
        try:
            start_tournament_next_game(room)
        except ValueError as exc:
            await send_error(room, client_id, str(exc))
            return
        await broadcast(room)
        return

    await send_error(room, client_id, "알 수 없는 토너먼트 명령입니다.")


def add_tournament_participant(room: Room, client_id: str, name: str) -> None:
    tournament = room.tournament
    if not tournament:
        return
    if client_id not in tournament.participant_ids:
        tournament.participant_ids.append(client_id)
    tournament.participant_names[client_id] = clean_nickname(name, "참가자")


def remove_tournament_participant(room: Room, client_id: str) -> None:
    tournament = room.tournament
    if not tournament or client_id == tournament.host_id:
        return
    if client_id in tournament.participant_ids:
        tournament.participant_ids.remove(client_id)
    tournament.participant_names.pop(client_id, None)
    tournament.slots = [
        None if slot_id == client_id else slot_id
        for slot_id in tournament.slots
    ]


def seed_tournament_random(room: Room) -> None:
    tournament = require_tournament_ready_for_seeding(room)
    slots = tournament.participant_ids.copy()
    secrets.SystemRandom().shuffle(slots)
    seed_tournament_manual(room, slots)


def seed_tournament_manual(room: Room, slots_payload: Any) -> None:
    tournament = require_tournament_ready_for_seeding(room)
    if not isinstance(slots_payload, list) or len(slots_payload) != tournament.size:
        raise ValueError("대진 슬롯 수가 올바르지 않습니다.")
    slots: list[str | None] = []
    for raw_id in slots_payload:
        client_id = clean_client_id(str(raw_id or ""))
        slots.append(client_id or None)
    expected = set(tournament.participant_ids)
    provided = {slot for slot in slots if slot}
    if len(provided) != tournament.size or provided != expected:
        raise ValueError("참가자를 모두 한 번씩 배치해야 합니다.")
    tournament.slots = slots
    tournament.rounds = build_tournament_rounds(slots)
    tournament.current_match_id = None
    tournament.winner_id = None
    tournament.status = "seeded"
    room.add_events([{"type": "tournament_seeded"}])


def require_tournament_ready_for_seeding(room: Room) -> TournamentState:
    tournament = room.tournament
    if not tournament:
        raise ValueError("토너먼트 방이 아닙니다.")
    if tournament.status not in {"lobby", "seeded"}:
        raise ValueError("진행 중인 토너먼트는 다시 배치할 수 없습니다.")
    if len(tournament.participant_ids) != tournament.size:
        raise ValueError(f"참가자 {tournament.size}명이 모두 들어와야 배치할 수 있습니다.")
    return tournament


def build_tournament_rounds(slots: list[str | None]) -> list[list[TournamentMatch]]:
    rounds: list[list[TournamentMatch]] = []
    match_count = len(slots) // 2
    first_round: list[TournamentMatch] = []
    for index in range(match_count):
        first_round.append(
            TournamentMatch(
                match_id=f"r0m{index}",
                round_index=0,
                match_index=index,
                player_ids=[slots[index * 2], slots[index * 2 + 1]],
            )
        )
    rounds.append(first_round)
    round_index = 1
    match_count //= 2
    while match_count >= 1:
        rounds.append(
            [
                TournamentMatch(
                    match_id=f"r{round_index}m{index}",
                    round_index=round_index,
                    match_index=index,
                    player_ids=[None, None],
                )
                for index in range(match_count)
            ]
        )
        round_index += 1
        match_count //= 2
    return rounds


def start_tournament_next_game(room: Room) -> None:
    tournament = room.tournament
    if not tournament or not tournament.rounds:
        raise ValueError("대진 배치 후 시작할 수 있습니다.")
    if tournament.status == "finished":
        raise ValueError("이미 종료된 토너먼트입니다.")
    if room.started and room.game.result is None:
        raise ValueError("현재 경기가 진행 중입니다.")

    match = current_or_next_tournament_match(tournament)
    if match is None or not all(match.player_ids):
        raise ValueError("시작할 수 있는 다음 경기가 없습니다.")

    tournament.current_match_id = match.match_id
    tournament.status = "playing"
    match.active = True
    room.player_ids = [match.player_ids[0], match.player_ids[1]]
    room.player_names = [
        tournament.participant_names.get(match.player_ids[0] or "", PLAYER_NAMES[0]),
        tournament.participant_names.get(match.player_ids[1] or "", PLAYER_NAMES[1]),
    ]
    room.player_ips = ["", ""]
    room.connected = [
        bool(room.player_ids[0] in room.sockets),
        bool(room.player_ids[1] in room.sockets),
    ]
    room.started = True
    room.rolloff = None
    room.friendly_result_recorded = False
    room.add_events(room.start_game_events(include_reset=True))
    room.add_events(
        [
            {
                "type": "tournament_match_started",
                "matchId": match.match_id,
                "players": room.player_names.copy(),
            }
        ]
    )


def current_or_next_tournament_match(
    tournament: TournamentState,
) -> TournamentMatch | None:
    if tournament.current_match_id:
        current = find_tournament_match(tournament, tournament.current_match_id)
        if current and not current.completed and all(current.player_ids):
            return current
    for round_matches in tournament.rounds:
        for match in round_matches:
            if not match.completed and all(match.player_ids):
                return match
    return None


def find_tournament_match(
    tournament: TournamentState,
    match_id: str | None,
) -> TournamentMatch | None:
    if not match_id:
        return None
    for round_matches in tournament.rounds:
        for match in round_matches:
            if match.match_id == match_id:
                return match
    return None


def finalize_tournament_game(room: Room) -> None:
    tournament = room.tournament
    if not room.tournament_mode or not tournament or not tournament.current_match_id:
        return
    if not room.game.result:
        return
    match = find_tournament_match(tournament, tournament.current_match_id)
    if not match or match.completed or not match.active:
        return
    winner_slot = room.game.result.get("winner")
    if winner_slot not in (0, 1):
        match.active = False
        return
    winner_id = room.player_ids[int(winner_slot)]
    if winner_id not in match.player_ids:
        match.active = False
        return
    score_slot = match.player_ids.index(winner_id)
    match.scores[score_slot] += 1
    match.active = False
    if match.scores[score_slot] >= tournament.target_wins:
        complete_tournament_match(room, match, winner_id)
    else:
        tournament.status = "between_sets"
        room.add_events(
            [
                {
                    "type": "tournament_set_finished",
                    "matchId": match.match_id,
                    "winner": tournament.participant_names.get(winner_id, "승자"),
                    "scores": match.scores.copy(),
                }
            ]
        )


def complete_tournament_match(
    room: Room,
    match: TournamentMatch,
    winner_id: str,
) -> None:
    tournament = room.tournament
    if not tournament:
        return
    match.completed = True
    match.winner_id = winner_id
    tournament.current_match_id = None
    next_round_index = match.round_index + 1
    if next_round_index >= len(tournament.rounds):
        tournament.winner_id = winner_id
        tournament.status = "finished"
        room.add_events(
            [
                {
                    "type": "tournament_finished",
                    "winner": tournament.participant_names.get(winner_id, "우승자"),
                }
            ]
        )
        return
    next_match = tournament.rounds[next_round_index][match.match_index // 2]
    next_slot = match.match_index % 2
    next_match.player_ids[next_slot] = winner_id
    tournament.status = "between_matches"
    room.add_events(
        [
            {
                "type": "tournament_match_finished",
                "matchId": match.match_id,
                "winner": tournament.participant_names.get(winner_id, "승자"),
            }
        ]
    )


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
    room.player_ips[1] = ""
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

    room.friendly_wins = [0, 0]
    room.friendly_result_recorded = False
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
    keep_ip = room.player_ips[keep_slot]
    keep_connected = room.connected[keep_slot]
    room.player_ids = [keep_id, None]
    room.player_names = [keep_name, WAITING_PLAYER_NAME]
    room.player_ips = [keep_ip, ""]
    room.connected = [keep_connected, False]
    room.started = False
    room.rolloff = None
    room.random_wait_started_at = time.time()
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


def is_joinable_random_room(room: Room, client_id: str, client_ip: str = "") -> bool:
    waiting_id = room.player_ids[0]
    waiting_ip = room.player_ips[0] if room.player_ips else ""
    wait_seconds = time.time() - room.random_wait_started_at
    return (
        room.random_match
        and not room.started
        and waiting_id is not None
        and waiting_id != client_id
        and room.player_ids[1] is None
        and random_waiting_player_alive(room)
        and not random_same_ip_blocked(waiting_ip, client_ip)
        and not random_recent_opponent_blocked(waiting_id, client_id, wait_seconds)
    )


def random_same_ip_blocked(waiting_ip: str, client_ip: str) -> bool:
    return bool(waiting_ip and client_ip and waiting_ip == client_ip)


def random_recent_opponent_blocked(
    first_id: str | None,
    second_id: str | None,
    wait_seconds: float = 0,
) -> bool:
    if not first_id or not second_id:
        return False
    if wait_seconds >= RANDOM_RECENT_REMATCH_BLOCK_SECONDS:
        return False
    return (
        last_random_opponents.get(first_id) == second_id
        or last_random_opponents.get(second_id) == first_id
    )


def remember_random_opponents(first_id: str | None, second_id: str | None) -> None:
    if not first_id or not second_id or first_id == second_id:
        return
    last_random_opponents[first_id] = second_id
    last_random_opponents[second_id] = first_id


def request_ip(request: Request) -> str:
    for header in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for"):
        value = request.headers.get(header, "").strip()
        if not value:
            continue
        return value.split(",", 1)[0].strip()[:80]
    host = request.client.host if request.client else ""
    if host == "testclient":
        return ""
    return host.strip()[:80]


def clean_nickname(value: str, fallback: str) -> str:
    nickname = " ".join(value.strip().split())
    if not nickname:
        return fallback
    return nickname[:16]


def clean_emoticon_id(value: str) -> str | None:
    emoticon = value.strip().lower()
    if not emoticon or len(emoticon) > 40:
        return None
    if any(not (char.isalnum() or char in {"_", "-"}) for char in emoticon):
        return None
    return emoticon if emoticon in ALLOWED_EMOTICONS else None


def clean_client_id(value: str) -> str:
    return value.strip()[:80]


def clean_title_label(value: str) -> str:
    label = " ".join(value.strip().split())
    if not label:
        raise HTTPException(status_code=400, detail="칭호 이름이 필요합니다.")
    return label[:TITLE_LABEL_MAX_LENGTH]


def clean_title_id(value: str, fallback_label: str = "") -> str:
    source = value.strip() or fallback_label.strip()
    known_ids = {
        "듀얼리스트": DUELIST_TITLE_ID,
        "duelist": DUELIST_TITLE_ID,
        "개발자": DEVELOPER_TITLE_ID,
        "developer": DEVELOPER_TITLE_ID,
        "미랑": MIRANG_TITLE_ID,
        "mirang": MIRANG_TITLE_ID,
        "rank-top": RANK_TITLE_ID,
        "top": RANK_TITLE_ID,
        "랭커": "ranker",
        "ranker": "ranker",
    }
    normalized_source = source.lower()
    if source in known_ids:
        return known_ids[source]
    if normalized_source in known_ids:
        return known_ids[normalized_source]
    title_id = "".join(
        char.lower()
        for char in source
        if char.isalnum() or char in {"-", "_"}
    )
    if not title_id:
        raise HTTPException(status_code=400, detail="칭호 ID가 필요합니다.")
    return title_id[:48]


def coerce_palette_key(
    value: str,
    palette: dict[str, dict[str, str]],
    fallback: str,
) -> str:
    key = value.strip().lower().replace("_", "-")
    if key in palette:
        return key
    if key:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 팔레트 값입니다: {key}")
    return fallback


def safe_palette_key(
    value: str,
    palette: dict[str, dict[str, str]],
    fallback: str,
) -> str:
    key = value.strip().lower().replace("_", "-")
    return key if key in palette else fallback


def title_payload(client_id: str | None) -> dict[str, Any] | None:
    if not client_id or client_id not in player_titles:
        return None
    equipped_id = player_titles[client_id].title_id
    title = available_titles(client_id).get(equipped_id)
    return title.to_dict() if title else None


def title_inventory_payload(client_id: str | None) -> list[dict[str, Any]]:
    if not client_id:
        return []
    equipped_id = player_titles.get(client_id).title_id if client_id in player_titles else None
    titles = [
        {
            **title.to_dict(),
            "equipped": title.title_id == equipped_id,
        }
        for title in available_titles(client_id).values()
    ]
    titles.sort(key=lambda item: (not item["equipped"], title_sort_order(item), item["label"], item["id"]))
    return titles


def title_sort_order(title: dict[str, Any]) -> int:
    title_id = str(title.get("id", ""))
    if title_id == RANK_TITLE_ID:
        return 0
    if title_id == DUELIST_TITLE_ID:
        return 1
    return 2


def available_titles(client_id: str | None) -> dict[str, PlayerTitle]:
    if not client_id:
        return {}
    refresh_automatic_titles(client_id)
    titles = dict(player_title_inventory.get(client_id, {}))
    rank_title = rank_title_for(client_id)
    if rank_title:
        titles[RANK_TITLE_ID] = rank_title
    return titles


def refresh_automatic_titles(client_id: str | None) -> None:
    if not client_id:
        return
    stats = player_stats.get(client_id)
    if stats and stats.streak >= 10:
        grant_owned_title(client_id, duelist_title(), persist=True)


def grant_owned_title(
    client_id: str | None,
    title: PlayerTitle,
    persist: bool = True,
) -> bool:
    if not client_id:
        return False
    inventory = player_title_inventory.setdefault(client_id, {})
    existing = inventory.get(title.title_id)
    if existing and existing.to_dict() == title.to_dict():
        return False
    inventory[title.title_id] = title
    if persist:
        persist_title_inventory(client_id, title)
    return True


def rank_title_for(client_id: str | None) -> PlayerTitle | None:
    rank = leaderboard_rank(client_id)
    if rank is None:
        return None
    return PlayerTitle(
        title_id=RANK_TITLE_ID,
        label=f"TOP {rank}",
        color="gold",
        icon="crown",
        effect="shine",
    )


def duelist_title() -> PlayerTitle:
    return PlayerTitle(
        title_id=DUELIST_TITLE_ID,
        label="듀얼리스트",
        color="duelist",
        icon="duelist",
        effect="crystal",
    )


def title_palette_payload() -> dict[str, Any]:
    return {
        "colors": TITLE_COLOR_PALETTE,
        "icons": TITLE_ICON_PALETTE,
        "effects": TITLE_EFFECT_PALETTE,
        "maxLabelLength": TITLE_LABEL_MAX_LENGTH,
    }


def normalize_tier_key(value: str | None) -> str:
    tier = str(value or BASE_TIER).strip().lower().replace("_", "-")
    return tier if tier in TIER_ORDER else BASE_TIER


def normalize_tier_grade(value: Any) -> int:
    try:
        grade = int(value)
    except (TypeError, ValueError):
        grade = BASE_TIER_GRADE
    return max(1, min(5, grade))


def normalize_tier_stars(value: Any) -> int:
    try:
        stars = int(value)
    except (TypeError, ValueError):
        stars = BASE_TIER_STARS
    return max(0, min(5, stars))


def normalize_master_points(value: Any) -> int:
    try:
        points = int(value)
    except (TypeError, ValueError):
        points = 0
    return max(0, points)


def normalize_tier_payload(raw: Any, current: PlayerStats | None = None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    current = current or PlayerStats()
    tier = normalize_tier_key(raw.get("tier") or raw.get("key") or raw.get("name") or current.tier)
    grade = normalize_tier_grade(raw.get("grade", current.tier_grade))
    stars = normalize_tier_stars(raw.get("stars", current.tier_stars))
    points = normalize_master_points(
        raw.get("points", raw.get("masterPoints", current.master_points))
    )
    if tier == "master":
        grade = 1
        stars = 0
    else:
        points = 0
    return {
        "tier": tier,
        "grade": grade,
        "stars": stars,
        "points": points,
    }


def tier_payload(stats: PlayerStats) -> dict[str, Any]:
    tier = normalize_tier_key(stats.tier)
    if tier == "master":
        return {
            "tier": "master",
            "label": TIER_LABELS["master"],
            "points": normalize_master_points(stats.master_points),
        }
    grade = normalize_tier_grade(stats.tier_grade)
    return {
        "tier": tier,
        "label": TIER_LABELS[tier],
        "grade": grade,
        "stars": normalize_tier_stars(stats.tier_stars),
        "promotionStars": 5 if grade == 1 else 3,
    }


def set_stats_tier(stats: PlayerStats, tier_info: dict[str, Any]) -> None:
    stats.tier = normalize_tier_key(tier_info.get("tier"))
    stats.tier_grade = normalize_tier_grade(tier_info.get("grade"))
    stats.tier_stars = normalize_tier_stars(tier_info.get("stars"))
    stats.master_points = normalize_master_points(tier_info.get("points"))
    if stats.tier == "master":
        stats.tier_grade = 1
        stats.tier_stars = 0
    else:
        stats.master_points = 0


def reset_stats_to_bronze(stats: PlayerStats) -> None:
    stats.score = 0
    stats.wins = 0
    stats.losses = 0
    stats.streak = 0
    stats.tier = BASE_TIER
    stats.tier_grade = BASE_TIER_GRADE
    stats.tier_stars = BASE_TIER_STARS
    stats.master_points = 0


def tier_index(stats: PlayerStats) -> int:
    return TIER_ORDER.index(normalize_tier_key(stats.tier))


def tier_sort_key(item: dict[str, Any]) -> tuple[int, int, int, int, int, str, str]:
    tier = item.get("tier", {}) if isinstance(item.get("tier"), dict) else {}
    tier_key = normalize_tier_key(str(tier.get("tier", BASE_TIER)))
    tier_order = TIER_ORDER.index(tier_key)
    points = normalize_master_points(tier.get("points", 0)) if tier_key == "master" else 0
    grade_score = 6 - normalize_tier_grade(tier.get("grade", BASE_TIER_GRADE))
    stars = normalize_tier_stars(tier.get("stars", 0))
    return (
        points,
        tier_order,
        grade_score,
        stars,
        int(item.get("wins", 0)) - int(item.get("losses", 0)),
        str(item.get("name", "")),
        str(item.get("clientId", "")),
    )


def has_tier_progress(stats: PlayerStats) -> bool:
    return (
        stats.wins > 0
        or stats.losses > 0
        or normalize_tier_key(stats.tier) != BASE_TIER
        or normalize_tier_grade(stats.tier_grade) != BASE_TIER_GRADE
        or normalize_tier_stars(stats.tier_stars) != BASE_TIER_STARS
        or normalize_master_points(stats.master_points) > 0
    )


def ranked_star_gain(new_streak: int) -> int:
    if new_streak >= 5:
        return 3
    if new_streak >= 3:
        return 2
    return 1


def ranked_master_gain(new_streak: int) -> int:
    if new_streak >= 5:
        return 15
    if new_streak == 4:
        return 14
    if new_streak == 3:
        return 13
    if new_streak == 2:
        return 11
    return 10


def add_tier_stars(stats: PlayerStats, amount: int) -> None:
    if normalize_tier_key(stats.tier) == "master":
        stats.master_points = normalize_master_points(stats.master_points) + amount
        return
    stats.tier = normalize_tier_key(stats.tier)
    stats.tier_grade = normalize_tier_grade(stats.tier_grade)
    stats.tier_stars = normalize_tier_stars(stats.tier_stars) + max(0, amount)
    while stats.tier != "master":
        threshold = 5 if stats.tier_grade == 1 else 3
        if stats.tier_stars < threshold:
            break
        stats.tier_stars -= threshold
        if stats.tier_grade > 1:
            stats.tier_grade -= 1
            continue
        next_index = min(len(TIER_ORDER) - 1, TIER_ORDER.index(stats.tier) + 1)
        next_tier = TIER_ORDER[next_index]
        if next_tier == "master":
            stats.tier = "master"
            stats.tier_grade = 1
            stats.tier_stars = 0
            stats.master_points = MASTER_START_POINTS
            break
        stats.tier = next_tier
        stats.tier_grade = 5


def remove_tier_star(stats: PlayerStats) -> None:
    if normalize_tier_key(stats.tier) == "master":
        stats.master_points = max(0, normalize_master_points(stats.master_points) - 10)
        return
    stats.tier_stars = max(0, normalize_tier_stars(stats.tier_stars) - 1)


def apply_tier_result(winner_stats: PlayerStats, loser_stats: PlayerStats) -> None:
    winner_new_streak = winner_stats.streak + 1 if winner_stats.streak > 0 else 1
    lower_tier_loser_protected = tier_index(loser_stats) < tier_index(winner_stats)

    winner_stats.wins += 1
    winner_stats.streak = winner_new_streak
    if normalize_tier_key(winner_stats.tier) == "master":
        winner_stats.master_points = normalize_master_points(winner_stats.master_points) + ranked_master_gain(
            winner_new_streak
        )
        winner_stats.score = winner_stats.master_points
    else:
        add_tier_stars(winner_stats, ranked_star_gain(winner_new_streak))

    loser_stats.losses += 1
    loser_stats.streak = loser_stats.streak - 1 if loser_stats.streak < 0 else -1
    if not lower_tier_loser_protected:
        remove_tier_star(loser_stats)
    if normalize_tier_key(loser_stats.tier) == "master":
        loser_stats.score = loser_stats.master_points


def require_admin_access(
    authorization: str | None,
    x_admin_secret: str | None,
) -> None:
    if has_admin_access(authorization, x_admin_secret):
        return
    expected = os.getenv("TIKATUKA_ADMIN_SECRET", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="칭호 관리자 API가 비활성화되어 있습니다.")
    raise HTTPException(status_code=401, detail="관리자 인증이 필요합니다.")


def has_admin_access(
    authorization: str | None,
    x_admin_secret: str | None,
) -> bool:
    expected = os.getenv("TIKATUKA_ADMIN_SECRET", "").strip()
    if not expected:
        return False

    provided = (x_admin_secret or "").strip()
    if authorization and authorization.strip().lower().startswith("bearer "):
        provided = authorization.strip()[7:].strip()
    return bool(provided and secrets.compare_digest(provided, expected))


def require_admin_or_bot_access(
    authorization: str | None,
    x_admin_secret: str | None,
    x_bot_secret: str | None,
) -> None:
    if has_admin_access(authorization, x_admin_secret):
        return
    expected = os.getenv("TIKATUKA_BOT_SECRET", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="봇 조회 API가 비활성화되어 있습니다.")
    provided = (x_bot_secret or "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="봇 조회 인증이 필요합니다.")


async def broadcast_title_update(client_id: str) -> None:
    for room in list(rooms.values()):
        if (
            client_id not in room.sockets
            and client_id not in room.player_ids
            and client_id not in room.waiting_ids
        ):
            continue
        async with room.lock:
            await broadcast(room)


async def broadcast_stats_update(client_id: str) -> None:
    await broadcast_title_update(client_id)


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


def rooms_summary_payload() -> dict[str, Any]:
    cleanup_rooms()
    counts: dict[str, dict[str, int]] = {
        "random": {"rooms": 0, "connectedPlayers": 0, "occupiedPlayers": 0, "waitingPlayers": 0},
        "friendly": {"rooms": 0, "connectedPlayers": 0, "occupiedPlayers": 0, "waitingPlayers": 0},
        "streamer": {"rooms": 0, "connectedPlayers": 0, "occupiedPlayers": 0, "waitingPlayers": 0},
        "tournament": {"rooms": 0, "connectedPlayers": 0, "occupiedPlayers": 0, "waitingPlayers": 0},
    }
    streamer_rooms: list[dict[str, Any]] = []
    all_rooms: list[dict[str, Any]] = []
    for room in sorted(rooms.values(), key=lambda item: item.created_at):
        summary = admin_room_payload(room)
        mode = summary["mode"]
        counts[mode]["rooms"] += 1
        counts[mode]["connectedPlayers"] += summary["connectedPlayers"]
        counts[mode]["occupiedPlayers"] += summary["occupiedPlayers"]
        counts[mode]["waitingPlayers"] += summary["waitingCount"]
        all_rooms.append(summary)
        if room.streamer_mode:
            streamer_rooms.append(summary)
    return {
        "onlineUsers": online_user_count(),
        "totalRooms": len(rooms),
        "counts": counts,
        "streamerRooms": streamer_rooms,
        "rooms": all_rooms,
    }


def random_waiting_rooms_payload(min_wait_seconds: int = RANDOM_RECENT_REMATCH_BLOCK_SECONDS) -> dict[str, Any]:
    cleanup_rooms()
    min_wait_seconds = max(0, min(600, int(min_wait_seconds or 0)))
    now = time.time()
    waiting_rooms: list[dict[str, Any]] = []
    for room in sorted(rooms.values(), key=lambda item: item.random_wait_started_at):
        waiting_id = room.player_ids[0]
        if (
            not room.random_match
            or room.started
            or not waiting_id
            or room.player_ids[1] is not None
            or not (room.connected[0] or waiting_id in room.sockets)
        ):
            continue
        wait_seconds = max(0.0, now - room.random_wait_started_at)
        if wait_seconds < min_wait_seconds:
            continue
        waiting_rooms.append(
            {
                "code": room.code,
                "waitingSeconds": round(wait_seconds, 3),
                "waitingSince": room.random_wait_started_at,
                "createdAt": room.created_at,
                "updatedAt": room.updated_at,
                "player": {
                    "clientId": waiting_id,
                    "name": room.player_names[0],
                    "connected": bool(room.connected[0] or waiting_id in room.sockets),
                    "stats": stats_payload(waiting_id),
                },
                "join": {
                    "wsPath": f"/ws/{room.code}",
                    "roomPath": f"/api/rooms/{room.code}",
                },
            }
        )
    return {
        "minWaitSeconds": min_wait_seconds,
        "count": len(waiting_rooms),
        "rooms": waiting_rooms,
    }


def server_state_payload() -> dict[str, Any]:
    cleanup_rooms()
    active_games = [
        room
        for room in rooms.values()
        if room.started and room.game.result is None
    ]
    return {
        "drain": maintenance_drain_enabled,
        "onlineUsers": online_user_count(),
        "totalRooms": len(rooms),
        "activeGames": len(active_games),
        "randomWaiting": random_waiting_rooms_payload(0)["count"],
    }


def admin_room_payload(room: Room) -> dict[str, Any]:
    mode = (
        "tournament"
        if room.tournament_mode
        else "streamer"
        if room.streamer_mode
        else "random"
        if room.random_match
        else "friendly"
    )
    players = [
        admin_room_player_payload(room, index)
        for index in range(2)
    ]
    connected_players = sum(
        1 for player in players if player["occupied"] and player["connected"]
    )
    occupied_players = sum(1 for player in players if player["occupied"])
    return {
        "code": room.code,
        "mode": mode,
        "started": room.started,
        "phase": room.game.phase,
        "result": room.game.result,
        "createdAt": room.created_at,
        "updatedAt": room.updated_at,
        "queueLimit": room.queue_limit,
        "waitingCount": len(room.waiting_payload()),
        "connectedPlayers": connected_players,
        "occupiedPlayers": occupied_players,
        "players": players,
        "host": players[0],
        "challenger": players[1],
        "waitingPlayers": [
            {
                "position": position,
                "clientId": client_id,
                "name": (
                    room.tournament.participant_names.get(client_id, "참가자")
                    if room.tournament_mode and room.tournament
                    else room.waiting_names.get(client_id, "대기자")
                ),
                "connected": client_id in room.sockets,
            }
            for position, client_id in enumerate(
                [
                    item_id
                    for item_id in (
                        room.tournament.participant_ids
                        if room.tournament_mode and room.tournament
                        else room.waiting_ids
                    )
                    if item_id not in room.player_ids
                ],
                start=1,
            )
        ],
    }


def admin_room_player_payload(room: Room, index: int) -> dict[str, Any]:
    client_id = room.player_ids[index]
    return {
        "index": index,
        "clientId": client_id,
        "name": room.player_names[index] if client_id else WAITING_PLAYER_NAME,
        "occupied": client_id is not None,
        "connected": room.connected[index],
        "ready": bool(client_id and client_id in room.ready_players),
    }


def tournament_payload(room: Room) -> dict[str, Any] | None:
    tournament = room.tournament
    if not room.tournament_mode or not tournament:
        return None
    active_match = find_tournament_match(tournament, tournament.current_match_id)
    next_match = current_or_next_tournament_match(tournament)
    return {
        "hostId": tournament.host_id,
        "hostName": tournament.host_name,
        "hostParticipates": tournament.host_participates,
        "size": tournament.size,
        "targetWins": tournament.target_wins,
        "status": tournament.status,
        "seeded": bool(tournament.rounds),
        "readyToSeed": len(tournament.participant_ids) == tournament.size,
        "canStart": bool(
            tournament.rounds
            and tournament.status != "finished"
            and not (room.started and room.game.result is None)
            and current_or_next_tournament_match(tournament)
        ),
        "currentMatchId": tournament.current_match_id,
        "winnerId": tournament.winner_id,
        "winnerName": tournament.participant_names.get(tournament.winner_id or "", ""),
        "participants": [
            {
                "clientId": client_id,
                "name": tournament.participant_names.get(client_id, "참가자"),
                "connected": client_id in room.sockets,
                "active": client_id in room.player_ids,
                "stats": stats_payload(client_id),
            }
            for client_id in tournament.participant_ids
        ],
        "slots": [
            tournament_slot_payload(tournament, client_id, index)
            for index, client_id in enumerate(tournament.slots)
        ],
        "rounds": [
            [
                tournament_match_payload(tournament, match)
                for match in round_matches
            ]
            for round_matches in tournament.rounds
        ],
        "activeMatch": tournament_match_payload(tournament, active_match)
        if active_match
        else None,
        "nextMatch": tournament_match_payload(tournament, next_match)
        if next_match
        else None,
    }


def tournament_slot_payload(
    tournament: TournamentState,
    client_id: str | None,
    index: int,
) -> dict[str, Any]:
    return {
        "index": index,
        "clientId": client_id,
        "name": tournament.participant_names.get(client_id or "", ""),
        "stats": stats_payload(client_id) if client_id else None,
    }


def tournament_match_payload(
    tournament: TournamentState,
    match: TournamentMatch | None,
) -> dict[str, Any] | None:
    if not match:
        return None
    return {
        "matchId": match.match_id,
        "roundIndex": match.round_index,
        "matchIndex": match.match_index,
        "players": [
            {
                "clientId": client_id,
                "name": tournament.participant_names.get(client_id or "", ""),
                "stats": stats_payload(client_id) if client_id else None,
            }
            for client_id in match.player_ids
        ],
        "scores": match.scores.copy(),
        "winnerId": match.winner_id,
        "winnerName": tournament.participant_names.get(match.winner_id or "", ""),
        "completed": match.completed,
        "active": match.active,
    }


def status_payload(client_id: str | None = None) -> dict[str, Any]:
    cleanup_rooms()
    return {
        "onlineUsers": online_user_count(),
        "stats": stats_payload(client_id, include_titles=True) if client_id else PlayerStats().to_dict(),
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
        if has_tier_progress(stats)
    ]
    ranked_players.sort(
        key=lambda item: (
            -tier_sort_key(item)[0],
            -tier_sort_key(item)[1],
            -tier_sort_key(item)[2],
            -tier_sort_key(item)[3],
            -tier_sort_key(item)[4],
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


def stats_payload(client_id: str | None, include_titles: bool = False) -> dict[str, Any]:
    stats = stats_for(client_id).to_dict()
    rank = leaderboard_rank(client_id)
    if rank is not None:
        stats["rank"] = rank
    title = title_payload(client_id)
    if title:
        stats["title"] = title
    if include_titles:
        stats["titles"] = title_inventory_payload(client_id)
    return stats


def apply_ranked_result(room: Room) -> None:
    if (
        not room.random_match
        and not room.tournament_mode
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

    remember_random_opponents(winner_id, loser_id)

    winner_stats = stats_for(winner_id)
    loser_stats = stats_for(loser_id)

    apply_tier_result(winner_stats, loser_stats)

    room.ranked_recorded = True
    invalidate_leaderboard_cache()
    if winner_stats.streak >= 10:
        grant_owned_title(winner_id, duelist_title(), persist=True)
    persist_stats(winner_id)
    persist_stats(loser_id)


load_stats_from_db()
