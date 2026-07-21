import discord
import pytest
from unittest.mock import AsyncMock, MagicMock

from commands._newinvestigator_occupation import (
    OccupationSearchModal,
    OccupationSelectView,
    OccupationSelect,
    PaginatedOccupationListView,
    OccupationPageSelect,
    OccupationSearchStartView,
)


def make_interaction():
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    return interaction


OCCUPATIONS = {
    "Detective": {"skills": "Spot Hidden, Law"},
    "Doctor": {"skills": "Medicine, First Aid"},
    "Antiquarian": {"skills": "Appraise, History"},
}


class TestOccupationSearchModal:
    @pytest.mark.asyncio
    async def test_matching_search_shows_select_view(self):
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        modal = OccupationSearchModal(cog, MagicMock(), char_data, player_stats, OCCUPATIONS)
        modal.search_term.component._value = "doc"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        assert isinstance(kwargs["view"], OccupationSelectView)

    @pytest.mark.asyncio
    async def test_no_matches_reports_failure(self):
        cog = AsyncMock()
        modal = OccupationSearchModal(cog, MagicMock(), {}, {}, OCCUPATIONS)
        modal.search_term.component._value = "zzznomatch"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "No occupations found matching that term.", ephemeral=True
        )


class TestOccupationSelect:
    @pytest.mark.asyncio
    async def test_callback_assigns_occupation_skills_via_cog(self):
        cog = AsyncMock()
        char_data = {}
        player_stats = {}
        view = OccupationSelectView(cog, char_data, player_stats, OCCUPATIONS, ["Detective", "Doctor"])
        select = view.children[0]
        assert isinstance(select, OccupationSelect)
        select._values = ["Detective"]

        interaction = make_interaction()
        await select.callback(interaction)

        cog.assign_occupation_skills.assert_awaited_once_with(
            interaction, char_data, player_stats, "Detective", OCCUPATIONS["Detective"]
        )


class TestPaginatedOccupationListView:
    def test_sorts_by_points_descending_by_default(self):
        cog = MagicMock()
        cog.calculate_occupation_points = MagicMock(side_effect=lambda char_data, info: {"Detective": 50, "Doctor": 70, "Antiquarian": 50}[[k for k, v in OCCUPATIONS.items() if v is info][0]])
        view = PaginatedOccupationListView(cog, {}, {}, OCCUPATIONS, sort_mode="points")

        names = [name for name, pts in view.sorted_list]
        assert names[0] == "Doctor"  # highest points first

    def test_alpha_sort_mode_orders_by_name(self):
        cog = MagicMock()
        cog.calculate_occupation_points = MagicMock(return_value=10)
        view = PaginatedOccupationListView(cog, {}, {}, OCCUPATIONS, sort_mode="alpha")

        names = [name for name, pts in view.sorted_list]
        assert names == sorted(OCCUPATIONS.keys())

    @pytest.mark.asyncio
    async def test_pagination_updates_page_and_embed(self):
        cog = MagicMock()
        cog.calculate_occupation_points = MagicMock(return_value=10)
        many_occupations = {f"Occ {i}": {"skills": ""} for i in range(30)}
        view = PaginatedOccupationListView(cog, {}, {}, many_occupations, sort_mode="alpha")
        interaction = make_interaction()

        next_btn = next(c for c in view.children if getattr(c, "label", None) == "Next")
        await next_btn.callback(interaction)

        assert view.page == 1
        interaction.response.edit_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_select_callback_assigns_occupation(self):
        cog = MagicMock()
        cog.calculate_occupation_points = MagicMock(return_value=10)
        cog.assign_occupation_skills = AsyncMock()
        char_data = {}
        player_stats = {}
        view = PaginatedOccupationListView(cog, char_data, player_stats, OCCUPATIONS, sort_mode="alpha")

        select = next(c for c in view.children if isinstance(c, OccupationPageSelect))
        select._values = ["Detective"]
        interaction = make_interaction()

        await select.callback(interaction)

        cog.assign_occupation_skills.assert_awaited_once_with(
            interaction, char_data, player_stats, "Detective", OCCUPATIONS["Detective"]
        )


class TestOccupationSearchStartView:
    @pytest.mark.asyncio
    async def test_search_button_opens_search_modal(self):
        cog = MagicMock()
        view = OccupationSearchStartView(cog, {}, {}, OCCUPATIONS)
        interaction = make_interaction()
        interaction.response.send_modal = AsyncMock()

        await view.search.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        assert isinstance(interaction.response.send_modal.call_args.args[0], OccupationSearchModal)

    @pytest.mark.asyncio
    async def test_browse_button_shows_points_sorted_list(self):
        cog = MagicMock()
        cog.calculate_occupation_points = MagicMock(return_value=10)
        view = OccupationSearchStartView(cog, {}, {}, OCCUPATIONS)
        interaction = make_interaction()

        await view.browse.callback(interaction)

        interaction.response.edit_message.assert_awaited_once()
        _, kwargs = interaction.response.edit_message.call_args
        assert isinstance(kwargs["view"], PaginatedOccupationListView)
        assert kwargs["view"].sort_mode == "points"

    @pytest.mark.asyncio
    async def test_browse_alpha_button_shows_alpha_sorted_list(self):
        cog = MagicMock()
        cog.calculate_occupation_points = MagicMock(return_value=10)
        view = OccupationSearchStartView(cog, {}, {}, OCCUPATIONS)
        interaction = make_interaction()

        await view.browse_alpha.callback(interaction)

        _, kwargs = interaction.response.edit_message.call_args
        assert kwargs["view"].sort_mode == "alpha"
