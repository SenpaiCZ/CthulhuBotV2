import discord
import pytest
from unittest.mock import AsyncMock, MagicMock

from commands._newinvestigator_gamemode import (
    GameModeView,
    EraSelectView,
    ArchetypeSelect,
    ArchetypeSelectView,
    CoreStatSelectView,
)
from commands._newinvestigator_data import ERA_SKILLS


def make_interaction():
    interaction = MagicMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.send_message = AsyncMock()
    return interaction


class TestGameModeView:
    @pytest.mark.asyncio
    async def test_coc_button_sets_mode_and_advances_to_era(self):
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        view = GameModeView(cog, char_data, player_stats)
        interaction = make_interaction()

        await view.coc_button.callback(interaction)

        assert char_data["Game Mode"] == "Call of Cthulhu"
        interaction.response.edit_message.assert_awaited_once()
        cog.step_era.assert_awaited_once_with(interaction, char_data, player_stats)

    @pytest.mark.asyncio
    async def test_pulp_button_sets_mode_and_advances_to_era(self):
        cog = AsyncMock()
        char_data = {}
        view = GameModeView(cog, char_data, {})
        interaction = make_interaction()

        await view.pulp_button.callback(interaction)

        assert char_data["Game Mode"] == "Pulp of Cthulhu"
        cog.step_era.assert_awaited_once()


class TestEraSelectView:
    @pytest.mark.asyncio
    async def test_selecting_era_applies_skills_and_clears_previous_era_skills(self):
        cog = AsyncMock()
        char_data = {"Game Mode": "Call of Cthulhu", "Ride Horse": 5}  # stale Dark Ages skill
        player_stats = {}
        view = EraSelectView(cog, char_data, player_stats)
        interaction = make_interaction()

        await view.era_1920s.callback(interaction)

        assert char_data["Era"] == "1920s Era"
        assert char_data["Climb"] == ERA_SKILLS["1920s Era"]["Climb"]
        assert "Ride Horse" not in char_data
        cog.step_stats.assert_awaited_once_with(interaction, char_data, player_stats)

    @pytest.mark.asyncio
    async def test_pulp_game_mode_routes_to_archetype_selection_instead_of_stats(self):
        cog = AsyncMock()
        char_data = {"Game Mode": "Pulp of Cthulhu"}
        player_stats = {}
        view = EraSelectView(cog, char_data, player_stats)
        interaction = make_interaction()

        await view.era_gaslight.callback(interaction)

        assert char_data["Era"] == "Cthulhu by Gaslight"
        cog.select_pulp_archetype.assert_awaited_once_with(interaction, char_data, player_stats)
        cog.step_stats.assert_not_awaited()


class TestArchetypeSelectAndView:
    @pytest.mark.asyncio
    async def test_select_callback_stores_choice_and_updates_info(self):
        archetypes_data = {"Daredevil": {"description": "Fast and reckless.", "adjustments": ["+5 DEX"]}}
        cog = AsyncMock()
        view = ArchetypeSelectView(cog, {}, {}, archetypes_data)
        select = next(c for c in view.children if isinstance(c, ArchetypeSelect))
        select._values = ["Daredevil"]

        interaction = make_interaction()
        await select.callback(interaction)

        assert view.selected_archetype == "Daredevil"
        interaction.response.edit_message.assert_awaited_once()
        embed = interaction.response.edit_message.call_args.kwargs["embed"]
        assert embed.title == "Archetype: Daredevil"

    @pytest.mark.asyncio
    async def test_confirm_without_selection_is_rejected(self):
        cog = AsyncMock()
        view = ArchetypeSelectView(cog, {}, {}, {"Daredevil": {}})
        interaction = make_interaction()

        await view.confirm.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("Please select an archetype first.", ephemeral=True)
        cog.step_stats.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_confirm_applies_archetype_and_advances_to_stats(self):
        archetypes_data = {"Daredevil": {"description": "Fast", "adjustments": []}}
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        view = ArchetypeSelectView(cog, char_data, player_stats, archetypes_data)
        view.selected_archetype = "Daredevil"
        interaction = make_interaction()

        await view.confirm.callback(interaction)

        assert char_data["Archetype"] == "Daredevil"
        assert char_data["Archetype Info"] == archetypes_data["Daredevil"]
        cog.step_stats.assert_awaited_once_with(interaction, char_data, player_stats)


class TestCoreStatSelectView:
    @pytest.mark.asyncio
    async def test_button_click_invokes_cog_apply_core_stat_logic(self):
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        view = CoreStatSelectView(["STR", "DEX"], cog, char_data, player_stats)
        assert {c.label for c in view.children} == {"STR", "DEX"}

        str_btn = next(c for c in view.children if c.label == "STR")
        interaction = make_interaction()
        await str_btn.callback(interaction)

        cog.apply_core_stat_logic.assert_awaited_once_with(interaction, char_data, player_stats, "STR")
