from __future__ import annotations

from dataclasses import dataclass
from random import SystemRandom
from typing import Any


FIELD_NAMES = ["TOP", "MIDDLE", "BOTTOM"]
PLAYER_NAMES = ["FrangGabriel", "레온하트 네리아"]


@dataclass(slots=True)
class Die:
    id: int
    value: int
    shield: bool = False
    owner: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "value": self.value,
            "shield": self.shield,
            "owner": self.owner,
        }


class GameEngine:
    """Server-authoritative TikaTuka game engine for the web MVP."""

    def __init__(self) -> None:
        self.rng = SystemRandom()
        self.reset()

    def reset(self) -> list[dict[str, Any]]:
        self.boards: list[list[list[Die]]] = [[[], [], []], [[], [], []]]
        self.current_player = 0
        self.phase = "roll"
        self.hand_trick_used = [False, False]
        self.holding = [False, False]
        self.opening_shield_pending = True
        self.rolled_dice: list[Die] = []
        self.held_die: Die | None = None
        self.result: dict[str, Any] | None = None
        self.next_die_id = 1
        return [{"type": "game_reset"}]

    def make_die(self, value: int | None = None, shield: bool = False, owner: int | None = None) -> Die:
        die = Die(
            id=self.next_die_id,
            value=value if value is not None else self.roll_value(),
            shield=shield,
            owner=owner,
        )
        self.next_die_id += 1
        return die

    def roll_value(self) -> int:
        return self.rng.randint(1, 6)

    def snapshot(self) -> dict[str, Any]:
        return {
            "boards": [
                [[die.to_dict() for die in field] for field in player_board]
                for player_board in self.boards
            ],
            "currentPlayer": self.current_player,
            "phase": self.phase,
            "handTrickUsed": self.hand_trick_used,
            "holding": self.holding,
            "openingShieldPending": self.opening_shield_pending,
            "rolledDice": [die.to_dict() for die in self.rolled_dice],
            "heldDie": self.held_die.to_dict() if self.held_die else None,
            "result": self.result,
            "scores": [[self.score_field(self.boards[p][f]) for f in range(3)] for p in range(2)],
        }

    def ensure_turn_ready(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if self.phase != "roll" or self.result is not None:
            return events
        if not self.can_continue(self.current_player):
            events.extend(self.end_turn())
            return events

        player = self.current_player
        opening_shield = player == 0 and self.opening_shield_pending
        die = self.make_die(shield=opening_shield, owner=player)
        self.rolled_dice = []
        self.held_die = die
        if opening_shield:
            self.opening_shield_pending = False
        self.phase = "place_normal"
        events.append(
            {
                "type": "die_rolled",
                "player": player,
                "die": die.to_dict(),
                "openingShield": opening_shield,
            }
        )
        return events

    def apply_action(self, player: int, payload: dict[str, Any]) -> list[dict[str, Any]]:
        if self.result is not None:
            raise ValueError("이미 종료된 게임입니다.")
        if player != self.current_player:
            raise ValueError("현재 턴이 아닙니다.")

        action = str(payload.get("action", ""))
        if action == "use_hand_trick":
            return self.use_hand_trick(player)
        if action == "select_die":
            return self.select_die(player, int(payload.get("index", -1)))
        if action == "hold":
            return self.hold(player)
        if action == "place_normal":
            return self.place_normal(player, int(payload.get("field", -1)))
        if action == "place_bonus":
            return self.place_bonus(
                player,
                int(payload.get("targetPlayer", -1)),
                int(payload.get("field", -1)),
            )
        raise ValueError("알 수 없는 행동입니다.")

    def use_hand_trick(self, player: int) -> list[dict[str, Any]]:
        if self.phase != "place_normal" or not self.held_die:
            raise ValueError("타짜의 손놀림을 사용할 수 없는 상태입니다.")
        if self.hand_trick_used[player]:
            raise ValueError("타짜의 손놀림은 이미 사용했습니다.")

        kept = self.held_die
        value = self.roll_value()
        while value == kept.value:
            value = self.roll_value()
        rerolled = self.make_die(value=value, shield=kept.shield, owner=player)
        self.hand_trick_used[player] = True
        self.held_die = None
        self.rolled_dice = [kept, rerolled]
        self.phase = "select_die"
        return [
            {
                "type": "hand_trick",
                "player": player,
                "kept": kept.to_dict(),
                "rerolled": rerolled.to_dict(),
            }
        ]

    def select_die(self, player: int, index: int) -> list[dict[str, Any]]:
        if self.phase != "select_die":
            raise ValueError("선택할 주사위가 없습니다.")
        if index < 0 or index >= len(self.rolled_dice):
            raise ValueError("잘못된 주사위 선택입니다.")
        selected = self.rolled_dice[index]
        discarded = [die for die in self.rolled_dice if die.id != selected.id]
        self.rolled_dice = []
        self.held_die = selected
        self.phase = "place_normal"
        return [
            {
                "type": "die_selected",
                "player": player,
                "selected": selected.to_dict(),
                "discarded": [die.to_dict() for die in discarded],
            }
        ]

    def hold(self, player: int) -> list[dict[str, Any]]:
        if self.phase not in {"place_normal", "select_die"}:
            raise ValueError("홀드할 수 없는 상태입니다.")
        discarded = []
        if self.held_die:
            discarded.append(self.held_die.to_dict())
        discarded.extend(die.to_dict() for die in self.rolled_dice)
        self.held_die = None
        self.rolled_dice = []
        self.holding[player] = True
        events = [{"type": "hold", "player": player, "discarded": discarded}]
        events.extend(self.end_turn())
        events.extend(self.ensure_turn_ready())
        return events

    def place_normal(self, player: int, field: int) -> list[dict[str, Any]]:
        if self.phase != "place_normal" or not self.held_die:
            raise ValueError("배치할 일반 주사위가 없습니다.")
        if field not in (0, 1, 2):
            raise ValueError("잘못된 필드입니다.")
        if not self.has_space(player, field):
            raise ValueError("해당 필드는 가득 찼습니다.")

        opponent = 1 - player
        placed = self.held_die
        placed.owner = player
        self.held_die = None
        self.insert_die(player, field, placed)
        events: list[dict[str, Any]] = [
            {"type": "normal_die_placed", "player": player, "field": field, "die": placed.to_dict()}
        ]

        opponent_field = self.boards[opponent][field]
        matching = [die for die in opponent_field if die.value == placed.value]
        removed = [die for die in matching if not die.shield]
        blocked = [die for die in matching if die.shield]
        can_place_bonus = self.has_any_space_after_removing_die(player, placed.id)

        if removed and can_place_bonus:
            self.boards[player][field] = [
                die for die in self.boards[player][field] if die.id != placed.id
            ]
            self.boards[opponent][field] = [
                die for die in opponent_field if die.value != placed.value or die.shield
            ]
            bonus = self.make_die(shield=True, owner=player)
            self.held_die = bonus
            self.phase = "place_bonus"
            events.append(
                {
                    "type": "egg_flick",
                    "player": player,
                    "field": field,
                    "value": placed.value,
                    "placedDieRemoved": True,
                    "opponentDiceRemoved": [die.to_dict() for die in removed],
                    "shieldedDiceBlocked": [die.to_dict() for die in blocked],
                    "bonusDie": bonus.to_dict(),
                }
            )
            return events

        if matching and not removed:
            events.append({"type": "shield_only_match", "player": player, "field": field, "value": placed.value})

        events.extend(self.end_turn())
        events.extend(self.ensure_turn_ready())
        return events

    def place_bonus(self, player: int, target_player: int, field: int) -> list[dict[str, Any]]:
        if self.phase != "place_bonus" or not self.held_die or not self.held_die.shield:
            raise ValueError("배치할 보너스 실드 주사위가 없습니다.")
        if target_player not in (0, 1) or field not in (0, 1, 2):
            raise ValueError("잘못된 보너스 배치 위치입니다.")
        if not self.has_space(target_player, field):
            raise ValueError("해당 필드는 가득 찼습니다.")

        bonus = self.held_die
        bonus.owner = player
        self.held_die = None
        self.insert_die(target_player, field, bonus)
        events: list[dict[str, Any]] = [
            {
                "type": "bonus_die_placed",
                "player": player,
                "targetPlayer": target_player,
                "field": field,
                "die": bonus.to_dict(),
            }
        ]
        events.extend(self.end_turn())
        events.extend(self.ensure_turn_ready())
        return events

    def end_turn(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if self.no_player_can_continue():
            self.finish_game()
            events.append({"type": "game_finished", "result": self.result})
            return events

        self.current_player = 1 - self.current_player
        while not self.can_continue(self.current_player):
            events.append({"type": "turn_passed", "player": self.current_player})
            self.current_player = 1 - self.current_player
        self.phase = "roll"
        return events

    def finish_game(self) -> None:
        self.result = self.evaluate_result()
        self.phase = "game_over"
        self.held_die = None
        self.rolled_dice = []

    def insert_die(self, player: int, field: int, die: Die) -> None:
        dice = self.boards[player][field]
        insert_after = -1
        for idx, existing in enumerate(dice):
            if existing.value == die.value:
                insert_after = idx
        if insert_after >= 0:
            dice.insert(insert_after + 1, die)
        else:
            dice.append(die)

    def has_space(self, player: int, field: int) -> bool:
        return len(self.boards[player][field]) < 3

    def has_any_space(self, player: int) -> bool:
        return any(self.has_space(player, field) for field in range(3))

    def has_any_space_after_removing_die(self, player: int, die_id: int) -> bool:
        return any(
            len([die for die in self.boards[player][field] if die.id != die_id]) < 3
            for field in range(3)
        )

    def can_continue(self, player: int) -> bool:
        return not self.holding[player] and self.has_any_space(player)

    def no_player_can_continue(self) -> bool:
        return not self.can_continue(0) and not self.can_continue(1)

    @staticmethod
    def score_field(dice: list[Die]) -> int:
        score = sum(die.value for die in dice)
        for value in range(1, 7):
            count = sum(1 for die in dice if die.value == value)
            if count == 3:
                score += value * 2
            elif count == 2:
                score += value
        return score

    def evaluate_result(self) -> dict[str, Any]:
        field_scores = [
            [self.score_field(self.boards[0][field]), self.score_field(self.boards[1][field])]
            for field in range(3)
        ]
        field_winners: list[int | None] = []
        for left, right in field_scores:
            if left == right:
                field_winners.append(None)
            else:
                field_winners.append(0 if left > right else 1)
        field_wins = [
            sum(1 for winner in field_winners if winner == 0),
            sum(1 for winner in field_winners if winner == 1),
        ]
        total_scores = [
            sum(score[0] for score in field_scores),
            sum(score[1] for score in field_scores),
        ]
        used_tiebreak = field_wins[0] == 1 and field_wins[1] == 1
        winner: int | None = None
        if field_wins[0] > field_wins[1]:
            winner = 0
        elif field_wins[1] > field_wins[0]:
            winner = 1
        elif used_tiebreak and total_scores[0] != total_scores[1]:
            winner = 0 if total_scores[0] > total_scores[1] else 1
        return {
            "fieldScores": field_scores,
            "fieldWinners": field_winners,
            "fieldWins": field_wins,
            "totalScores": total_scores,
            "winner": winner,
            "usedTiebreak": used_tiebreak,
        }

