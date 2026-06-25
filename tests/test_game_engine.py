import pytest

from app.game_engine import Die, GameEngine


class FixedRng:
    def __init__(self, values):
        self.values = list(values)

    def randint(self, low, high):
        assert low == 1
        assert high == 6
        if not self.values:
            raise AssertionError("fixed rng exhausted")
        return self.values.pop(0)


def die(die_id, value, *, shield=False, owner=0):
    return Die(id=die_id, value=value, shield=shield, owner=owner)


def ready_to_place(game, player, value, *, shield=False):
    game.current_player = player
    game.phase = "place_normal"
    game.held_die = game.make_die(value=value, shield=shield, owner=player)


def test_egg_flick_removes_unshielded_matches_but_keeps_shields():
    game = GameEngine()
    game.boards[1][0] = [
        die(100, 2, owner=1),
        die(101, 2, shield=True, owner=1),
        die(102, 5, owner=1),
    ]
    ready_to_place(game, 0, 2)

    events = game.place_normal(0, 0)

    assert [event["type"] for event in events] == ["normal_die_placed", "egg_flick"]
    assert [(d.value, d.shield, d.owner) for d in game.boards[1][0]] == [
        (2, True, 1),
        (5, False, 1),
    ]
    assert game.boards[0][0] == []
    assert game.phase == "place_bonus"
    assert game.held_die is not None
    assert game.held_die.shield is True
    assert game.held_die.owner == 0


def test_shield_only_match_does_not_trigger_egg_flick_or_bonus():
    game = GameEngine()
    game.boards[1][0] = [
        die(100, 2, shield=True, owner=1),
        die(101, 2, shield=True, owner=1),
    ]
    ready_to_place(game, 0, 2)

    events = game.place_normal(0, 0)

    assert [event["type"] for event in events[:2]] == [
        "normal_die_placed",
        "shield_only_match",
    ]
    assert [(d.value, d.shield, d.owner) for d in game.boards[1][0]] == [
        (2, True, 1),
        (2, True, 1),
    ]
    assert [(d.value, d.shield, d.owner) for d in game.boards[0][0]] == [
        (2, False, 0),
    ]
    assert game.phase != "place_bonus"
    assert game.held_die is not None  # next player's auto roll


def test_bonus_die_can_be_placed_on_opponent_board_with_original_owner_color():
    game = GameEngine()
    game.boards[1][0] = [die(100, 4, owner=1)]
    ready_to_place(game, 0, 4)
    game.place_normal(0, 0)
    bonus = game.held_die

    events = game.place_bonus(0, 1, 0)

    assert events[0]["type"] == "bonus_die_placed"
    assert game.boards[1][0][-1].id == bonus.id
    assert game.boards[1][0][-1].shield is True
    assert game.boards[1][0][-1].owner == 0


def test_combo_insert_keeps_existing_order_except_adjacent_match():
    game = GameEngine()
    game.boards[0][0] = [die(100, 3), die(101, 1)]
    ready_to_place(game, 0, 3)
    game.place_normal(0, 0)
    assert [d.value for d in game.boards[0][0]] == [3, 3, 1]

    game = GameEngine()
    game.boards[0][0] = [die(100, 3), die(101, 1)]
    ready_to_place(game, 0, 1)
    game.place_normal(0, 0)
    assert [d.value for d in game.boards[0][0]] == [3, 1, 1]


def test_opening_hand_trick_reroll_is_also_shield_and_avoids_same_value():
    game = GameEngine()
    game.rng = FixedRng([2, 2, 5])

    game.ensure_turn_ready()
    events = game.use_hand_trick(0)

    assert events[0]["kept"]["shield"] is True
    assert events[0]["rerolled"]["shield"] is True
    assert events[0]["kept"]["value"] == 2
    assert events[0]["rerolled"]["value"] == 5
    assert [d.value for d in game.rolled_dice] == [2, 5]
    assert all(d.shield for d in game.rolled_dice)


def test_opening_shield_belongs_to_selected_first_player():
    game = GameEngine()
    game.rng = FixedRng([6])

    game.set_first_player(1)
    events = game.ensure_turn_ready()

    assert game.current_player == 1
    assert events[0]["player"] == 1
    assert events[0]["die"]["shield"] is True
    assert game.held_die is not None
    assert game.held_die.owner == 1
    assert game.held_die.shield is True


def test_score_double_triple_and_tiebreak():
    assert GameEngine.score_field([die(1, 5), die(2, 5)]) == 15
    assert GameEngine.score_field([die(1, 5), die(2, 5), die(3, 5)]) == 25

    game = GameEngine()
    game.boards[0] = [[die(1, 5)], [die(2, 1)], [die(3, 2)]]
    game.boards[1] = [[die(4, 1)], [die(5, 6)], [die(6, 2)]]
    result = game.evaluate_result()

    assert result["fieldWins"] == [1, 1]
    assert result["usedTiebreak"] is True
    assert result["winner"] == 1


def test_invalid_actions_are_rejected():
    game = GameEngine()
    game.ensure_turn_ready()

    with pytest.raises(ValueError):
        game.apply_action(1, {"action": "place_normal", "field": 0})
