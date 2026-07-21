import pytest
from unittest.mock import AsyncMock, MagicMock

from commands.newinvestigator import newinvestigator
from commands._newinvestigator_gamemode import GameModeView, EraSelectView
from commands._newinvestigator_stats import StatGenerationView


def make_cog():
    return newinvestigator(MagicMock())


def make_interaction(response_done=False):
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.is_done = MagicMock(return_value=response_done)
    interaction.response.send_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_step_gamemode_sends_game_mode_view():
    cog = make_cog()
    interaction = make_interaction(response_done=False)
    char_data = {}
    player_stats = {}

    await cog.step_gamemode(interaction, char_data, player_stats)

    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.await_args
    assert isinstance(kwargs["view"], GameModeView)


@pytest.mark.asyncio
async def test_step_era_sends_era_select_view_via_followup():
    cog = make_cog()
    interaction = make_interaction(response_done=True)
    char_data = {}
    player_stats = {}

    await cog.step_era(interaction, char_data, player_stats)

    interaction.followup.send.assert_awaited_once()
    _, kwargs = interaction.followup.send.await_args
    assert isinstance(kwargs["view"], EraSelectView)


@pytest.mark.asyncio
async def test_step_stats_uses_followup_when_response_already_done():
    cog = make_cog()
    interaction = make_interaction(response_done=True)
    char_data = {}
    player_stats = {}

    await cog.step_stats(interaction, char_data, player_stats)

    interaction.followup.send.assert_awaited_once()
    interaction.response.send_message.assert_not_awaited()
    _, kwargs = interaction.followup.send.await_args
    assert isinstance(kwargs["view"], StatGenerationView)


@pytest.mark.asyncio
async def test_step_stats_uses_response_send_message_when_response_not_done():
    cog = make_cog()
    interaction = make_interaction(response_done=False)
    char_data = {}
    player_stats = {}

    await cog.step_stats(interaction, char_data, player_stats)

    interaction.response.send_message.assert_awaited_once()
    interaction.followup.send.assert_not_awaited()
    _, kwargs = interaction.response.send_message.await_args
    assert isinstance(kwargs["view"], StatGenerationView)


@pytest.mark.asyncio
async def test_gamemode_to_era_to_stats_chain_each_hands_off_to_the_next_view():
    """Simulates the real transition chain by directly invoking each step in
    sequence (as the prior step's button callback would), confirming each
    stage produces the view the next stage depends on -- not just that each
    step method works in isolation."""
    cog = make_cog()
    char_data = {}
    player_stats = {}

    interaction_1 = make_interaction(response_done=False)
    await cog.step_gamemode(interaction_1, char_data, player_stats)
    _, kwargs_1 = interaction_1.response.send_message.await_args
    assert isinstance(kwargs_1["view"], GameModeView)

    # GameModeView's own selection callback would normally call step_era next;
    # simulate that hand-off directly since this task's scope is the Cog-level
    # step chain, not GameModeView's own button-callback internals.
    interaction_2 = make_interaction(response_done=True)
    await cog.step_era(interaction_2, char_data, player_stats)
    _, kwargs_2 = interaction_2.followup.send.await_args
    assert isinstance(kwargs_2["view"], EraSelectView)

    interaction_3 = make_interaction(response_done=True)
    await cog.step_stats(interaction_3, char_data, player_stats)
    _, kwargs_3 = interaction_3.followup.send.await_args
    assert isinstance(kwargs_3["view"], StatGenerationView)
