import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands.chase import ChaseActionsView, ChaseSession, ChaseParticipant


def make_session_with_hazard_at(index, check="DEX"):
    session = ChaseSession(guild_id=1, channel_id=2, environment="Urban", mode="Foot")
    session.ensure_track_length(index)
    session.track[index].hazard = {"name": "Test Hazard", "check": check, "difficulty": "Regular", "desc": "..."}
    session.track[index].description = f"⚠️ Test Hazard ({check} Check)"
    return session


def make_participant(position=0, dex=50, move_actions=1, actions=1):
    p = ChaseParticipant(user_id="99", name="Investigator")
    p.position = position
    p.dex = dex
    p.move_actions_remaining = move_actions
    p.actions_remaining = actions
    return p


def make_interaction():
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    return interaction


def make_view(session, participant):
    cog = MagicMock()
    view = ChaseActionsView(cog, session, participant)
    view.update_dashboard = AsyncMock()
    return view


# --- move_button: hazard pass/fail branch ---

@pytest.mark.asyncio
async def test_move_button_passes_hazard_check_advances_position():
    session = make_session_with_hazard_at(1, check="DEX")
    participant = make_participant(position=0, dex=80, move_actions=1)
    view = make_view(session, participant)
    interaction = make_interaction()

    with patch("commands.chase.random.randint", return_value=10):  # 10 <= 80 dex -> pass
        await view.move_button.callback(interaction)

    assert participant.position == 1
    assert participant.move_actions_remaining == 0
    assert "Passed" in session.log[-1]
    view.update_dashboard.assert_awaited_once()


@pytest.mark.asyncio
async def test_move_button_fails_hazard_check_stays_but_still_consumes_move_action():
    session = make_session_with_hazard_at(1, check="DEX")
    participant = make_participant(position=0, dex=20, move_actions=1)
    view = make_view(session, participant)
    interaction = make_interaction()

    with patch("commands.chase.random.randint", return_value=95):  # 95 > 20 dex -> fail
        await view.move_button.callback(interaction)

    assert participant.position == 0  # unchanged, stuck at hazard
    assert participant.move_actions_remaining == 0  # still consumed on failure
    assert "stumbled" in session.log[-1].lower()
    view.update_dashboard.assert_awaited_once()


@pytest.mark.asyncio
async def test_move_button_no_hazard_at_next_location_always_advances():
    session = ChaseSession(guild_id=1, channel_id=2, environment="Urban", mode="Foot")
    session.ensure_track_length(1)
    session.track[1].hazard = None
    participant = make_participant(position=0, move_actions=1)
    view = make_view(session, participant)
    interaction = make_interaction()

    await view.move_button.callback(interaction)

    assert participant.position == 1
    assert participant.move_actions_remaining == 0


@pytest.mark.asyncio
async def test_move_button_no_move_actions_remaining_rejects_without_consuming_state():
    session = ChaseSession(guild_id=1, channel_id=2)
    participant = make_participant(position=0, move_actions=0)
    view = make_view(session, participant)
    interaction = make_interaction()

    await view.move_button.callback(interaction)

    interaction.response.send_message.assert_awaited_once_with(
        "❌ No Movement Actions remaining!", ephemeral=True
    )
    assert participant.position == 0
    view.update_dashboard.assert_not_awaited()


# --- dash_button: converts a standard action into +1 move action ---

@pytest.mark.asyncio
async def test_dash_button_converts_standard_action_to_move_action():
    session = ChaseSession(guild_id=1, channel_id=2)
    participant = make_participant(actions=1, move_actions=1)
    view = make_view(session, participant)
    interaction = make_interaction()

    await view.dash_button.callback(interaction)

    assert participant.actions_remaining == 0
    assert participant.move_actions_remaining == 2
    view.update_dashboard.assert_awaited_once()


@pytest.mark.asyncio
async def test_dash_button_no_actions_remaining_rejects():
    session = ChaseSession(guild_id=1, channel_id=2)
    participant = make_participant(actions=0, move_actions=1)
    view = make_view(session, participant)
    interaction = make_interaction()

    await view.dash_button.callback(interaction)

    interaction.response.send_message.assert_awaited_once_with(
        "❌ No Standard Actions remaining!", ephemeral=True
    )
    assert participant.move_actions_remaining == 1  # unchanged
    view.update_dashboard.assert_not_awaited()


# --- attack_button: consumes a standard action ---

@pytest.mark.asyncio
async def test_attack_button_consumes_standard_action():
    session = ChaseSession(guild_id=1, channel_id=2)
    participant = make_participant(actions=1)
    view = make_view(session, participant)
    interaction = make_interaction()

    await view.attack_button.callback(interaction)

    assert participant.actions_remaining == 0
    assert "attacks" in session.log[-1].lower()
    view.update_dashboard.assert_awaited_once()


@pytest.mark.asyncio
async def test_attack_button_no_actions_remaining_rejects():
    session = ChaseSession(guild_id=1, channel_id=2)
    participant = make_participant(actions=0)
    view = make_view(session, participant)
    interaction = make_interaction()

    await view.attack_button.callback(interaction)

    interaction.response.send_message.assert_awaited_once_with(
        "❌ No Actions remaining!", ephemeral=True
    )
    view.update_dashboard.assert_not_awaited()
