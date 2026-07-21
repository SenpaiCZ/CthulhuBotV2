import discord
import pytest
from unittest.mock import AsyncMock, MagicMock

from commands._newinvestigator_stats import (
    StatGenerationView,
    StatsBulkEntryModal,
    AssistedRollView,
    StatsDeductionView,
)


def make_interaction():
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    return interaction


class TestStatGenerationView:
    @pytest.mark.asyncio
    async def test_each_mode_button_delegates_to_matching_cog_method(self):
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        view = StatGenerationView(cog, char_data, player_stats)
        interaction = make_interaction()

        await view.auto.callback(interaction)
        cog.mode_full_auto.assert_awaited_once_with(interaction, char_data, player_stats)

        await view.quick.callback(interaction)
        cog.mode_quick_fire.assert_awaited_once_with(interaction, char_data, player_stats)

        await view.assisted.callback(interaction)
        cog.mode_assisted.assert_awaited_once_with(interaction, char_data, player_stats)

        await view.forced.callback(interaction)
        cog.mode_forced.assert_awaited_once_with(interaction, char_data, player_stats)


class TestStatsBulkEntryModal:
    @pytest.mark.asyncio
    async def test_parses_valid_stat_lines_and_ignores_invalid_ones(self):
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        modal = StatsBulkEntryModal(cog, MagicMock(), char_data, player_stats, mode="bulk")
        modal.stats_input.component._value = "STR 60\nCON 70\nNOTASTAT 99\nSIZ abc\nDEX 55"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        assert char_data == {"STR": 60, "CON": 70, "DEX": 55}
        interaction.response.send_message.assert_awaited_once_with("Stats applied.", ephemeral=True)
        cog.display_stats_and_continue.assert_awaited_once_with(interaction, char_data, player_stats)


class TestAssistedRollView:
    @pytest.mark.asyncio
    async def test_keep_applies_value_and_continues_loop(self):
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        queue = ["CON", "SIZ"]
        view = AssistedRollView(cog, char_data, player_stats, queue, "STR", "3D6 * 5", 65)
        interaction = make_interaction()

        await view.keep.callback(interaction)

        assert char_data["STR"] == 65
        cog.assisted_loop.assert_awaited_once_with(interaction, char_data, player_stats, queue)

    @pytest.mark.asyncio
    async def test_reroll_uses_formula_and_replaces_value(self):
        cog = AsyncMock()
        cog.roll_stat_formula = MagicMock(return_value=80)
        char_data = {}
        player_stats = {}
        queue = ["CON"]
        view = AssistedRollView(cog, char_data, player_stats, queue, "STR", "3D6 * 5", 65)
        interaction = make_interaction()

        await view.reroll.callback(interaction)

        cog.roll_stat_formula.assert_called_once_with("3D6 * 5")
        assert char_data["STR"] == 80
        interaction.response.edit_message.assert_awaited_once()
        cog.assisted_loop.assert_awaited_once_with(interaction, char_data, player_stats, queue)


class TestStatsDeductionView:
    @pytest.mark.asyncio
    async def test_deduct_reduces_stat_and_tracks_remaining(self):
        cog = AsyncMock()
        char_data = {"STR": 50}
        player_stats = {}
        view = StatsDeductionView(cog, char_data, player_stats, deduction_remaining=10)
        interaction = make_interaction()

        await view.str_minus.callback(interaction)

        assert char_data["STR"] == 45
        assert view.deduction_remaining == 5
        interaction.response.edit_message.assert_awaited_once()
        cog.finalize_age_modifiers.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_deduct_completes_and_finalizes_when_remaining_hits_zero(self):
        cog = AsyncMock()
        char_data = {"STR": 50}
        player_stats = {}
        view = StatsDeductionView(cog, char_data, player_stats, deduction_remaining=5)
        interaction = make_interaction()

        await view.str_minus.callback(interaction)

        assert view.deduction_remaining == 0
        cog.finalize_age_modifiers.assert_awaited_once_with(interaction, char_data, player_stats)

    @pytest.mark.asyncio
    async def test_deduct_rejects_reduction_below_zero(self):
        cog = AsyncMock()
        char_data = {"STR": 2}
        view = StatsDeductionView(cog, char_data, {}, deduction_remaining=10)
        interaction = make_interaction()

        await view.str_minus.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("Cannot reduce STR below 0.", ephemeral=True)
        assert char_data["STR"] == 2
