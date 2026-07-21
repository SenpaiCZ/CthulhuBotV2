import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands._newinvestigator_basicinfo import (
    BasicInfoModal,
    RetireCharacterView,
    BasicInfoStartView,
)


def make_interaction(user_id="222"):
    interaction = MagicMock()
    interaction.user = MagicMock(id=int(user_id))
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    return interaction


class TestBasicInfoModal:
    @pytest.mark.asyncio
    async def test_valid_submission_advances_to_gamemode_step(self):
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        modal = BasicInfoModal(cog, MagicMock(), char_data, player_stats)
        modal.name.component._value = "Jane Doe"
        modal.residence.component._value = "Arkham"
        modal.age.component._value = "30"
        modal.language.component._value = "English"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        assert char_data["NAME"] == "Jane Doe"
        assert char_data["Residence"] == "Arkham"
        assert char_data["Age"] == 30
        assert char_data["First Language"] == "English"
        cog.step_gamemode.assert_awaited_once_with(interaction, char_data, player_stats)

    @pytest.mark.asyncio
    async def test_age_out_of_bounds_rejected(self):
        cog = AsyncMock()
        char_data = {}
        modal = BasicInfoModal(cog, MagicMock(), char_data, {})
        modal.name.component._value = "Jane"
        modal.residence.component._value = ""
        modal.age.component._value = "5"
        modal.language.component._value = "English"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "Age must be a number between 15 and 90.", ephemeral=True
        )
        cog.step_gamemode.assert_not_awaited()
        assert "NAME" not in char_data

    @pytest.mark.asyncio
    async def test_missing_residence_defaults_to_unknown(self):
        cog = AsyncMock()
        char_data = {}
        modal = BasicInfoModal(cog, MagicMock(), char_data, {})
        modal.name.component._value = "Jane"
        modal.residence.component._value = ""
        modal.age.component._value = "40"
        modal.language.component._value = ""

        interaction = make_interaction()
        await modal.on_submit(interaction)

        assert char_data["Residence"] == "Unknown"
        assert char_data["First Language"] == "Own"


class TestRetireCharacterView:
    @pytest.mark.asyncio
    async def test_interaction_check_rejects_other_users(self):
        view = RetireCharacterView(MagicMock(), user_id="222", server_id="111", player_stats={})
        interaction = make_interaction(user_id="999")

        result = await view.interaction_check(interaction)

        assert result is False
        interaction.response.send_message.assert_awaited_once_with("Not your session!", ephemeral=True)

    @pytest.mark.asyncio
    async def test_retire_moves_character_to_retired_and_restarts_wizard(self):
        cog = AsyncMock()
        player_stats = {"111": {"222": {"NAME": "Old Detective"}}}
        view = RetireCharacterView(cog, user_id="222", server_id="111", player_stats=player_stats)
        interaction = make_interaction()

        with patch("commands._newinvestigator_basicinfo.load_retired_characters_data", new=AsyncMock(return_value={})), \
             patch("commands._newinvestigator_basicinfo.save_retired_characters_data", new=AsyncMock()) as mock_save_retired, \
             patch("commands._newinvestigator_basicinfo.save_player_stats", new=AsyncMock()) as mock_save_stats:
            await view.retire.callback(interaction)

        assert view.value is True
        assert "222" not in player_stats["111"]
        mock_save_retired.assert_awaited_once()
        retired_arg = mock_save_retired.call_args.args[0]
        assert retired_arg["222"][0]["NAME"] == "Old Detective"
        mock_save_stats.assert_awaited_once_with(player_stats)
        cog.start_wizard.assert_awaited_once_with(interaction, player_stats)
        assert view.is_finished()

    @pytest.mark.asyncio
    async def test_cancel_sets_value_false_and_stops(self):
        view = RetireCharacterView(MagicMock(), user_id="222", server_id="111", player_stats={})
        interaction = make_interaction()

        await view.cancel.callback(interaction)

        assert view.value is False
        interaction.response.send_message.assert_awaited_once_with("Character creation cancelled.", ephemeral=True)
        assert view.is_finished()


class TestBasicInfoStartView:
    @pytest.mark.asyncio
    async def test_enter_details_opens_basic_info_modal(self):
        cog = MagicMock()
        char_data = {}
        player_stats = {}
        view = BasicInfoStartView(cog, char_data, player_stats)
        interaction = make_interaction()

        await view.enter_details.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        modal = interaction.response.send_modal.call_args.args[0]
        assert isinstance(modal, BasicInfoModal)
        assert modal.char_data is char_data
        assert modal.player_stats is player_stats
