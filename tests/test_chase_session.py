import random
import pytest
from commands.chase import ChaseLocation, ChaseParticipant, ChaseSession


def test_chase_location_index_zero_never_has_hazard():
    for _ in range(20):
        loc = ChaseLocation(0, "Urban")
        assert loc.hazard is None
        assert loc.description == "Clear path"


def test_chase_location_round_trip():
    random.seed(1)
    loc = ChaseLocation(3, "Wilderness")
    restored = ChaseLocation.from_dict(loc.to_dict())
    assert restored.to_dict() == loc.to_dict()


def test_chase_participant_set_stats_and_round_trip():
    p = ChaseParticipant("42", "Investigator", is_npc=False)
    p.set_stats({"MOV": 9, "DEX": 65, "STR": 55, "CON": 60, "Drive Auto": 40})

    assert p.mov == 9
    assert p.dex == 65

    restored = ChaseParticipant.from_dict(p.to_dict())
    assert restored.to_dict() == p.to_dict()


def test_chase_participant_reset_round_actions():
    p = ChaseParticipant("42", "Investigator")
    p.actions_remaining = 0
    p.move_actions_remaining = 0
    p.reset_round_actions()
    assert p.actions_remaining == 1
    assert p.move_actions_remaining == 1


def test_chase_session_initial_track_has_five_locations_with_clear_start():
    session = ChaseSession(guild_id=1, channel_id=2)
    assert len(session.track) == 5
    assert session.track[0].hazard is None
    assert session.track[0].description == "Start Line"


def test_chase_session_sort_turn_order_by_dex_descending():
    session = ChaseSession(guild_id=1, channel_id=2)
    slow = ChaseParticipant("1", "Slow")
    slow.dex = 30
    fast = ChaseParticipant("2", "Fast")
    fast.dex = 80
    session.participants = [slow, fast]

    session.sort_turn_order()

    assert session.turn_order == ["2", "1"]
    assert session.participants[0] is fast


def test_chase_session_next_round_resets_actions_and_advances_round():
    session = ChaseSession(guild_id=1, channel_id=2)
    p = ChaseParticipant("1", "Runner")
    p.actions_remaining = 0
    p.move_actions_remaining = 0
    session.participants = [p]
    session.current_turn_index = 1

    session.next_round()

    assert session.round_number == 2
    assert session.current_turn_index == 0
    assert p.actions_remaining == 1
    assert p.move_actions_remaining == 1


def test_chase_session_ensure_track_length_extends_track():
    session = ChaseSession(guild_id=1, channel_id=2)
    session.ensure_track_length(10)
    assert len(session.track) >= 12


def test_chase_session_round_trip():
    session = ChaseSession(guild_id=1, channel_id=2, environment="Driving", mode="Driving")
    p = ChaseParticipant("1", "Runner")
    p.set_stats({"MOV": 8, "DEX": 55, "STR": 50, "CON": 50, "Drive Auto": 60})
    session.participants = [p]
    session.sort_turn_order()

    restored = ChaseSession.from_dict(session.to_dict())
    assert restored.to_dict() == session.to_dict()
