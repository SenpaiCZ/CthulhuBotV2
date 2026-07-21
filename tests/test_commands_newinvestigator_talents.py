import discord
import pytest
from unittest.mock import AsyncMock, MagicMock

from commands._newinvestigator_talents import (
    TalentCategorySelect,
    CategoryView,
    TalentSelect,
    TalentOptionView,
)


def make_interaction():
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    return interaction


@pytest.fixture
def cog():
    c = AsyncMock()
    return c


@pytest.fixture
def pulp_data():
    return {
        "mundane": ["**Fast Talker**: Gain bonus to Fast Talk.", "**Tough**: Gain bonus HP."],
        "combat": ["**Gunslinger**: Bonus to Firearms."],
    }


class TestTalentCategorySelect:
    @pytest.mark.asyncio
    async def test_options_are_capitalized_category_names(self, pulp_data):
        select = TalentCategorySelect(pulp_data)
        labels = {opt.label for opt in select.options}
        assert labels == {"Mundane", "Combat"}
        values = {opt.value for opt in select.options}
        assert values == {"mundane", "combat"}

    @pytest.mark.asyncio
    async def test_callback_delegates_to_cog_with_full_context(self, cog, pulp_data):
        char_data = {"NAME": "Jane"}
        player_stats = {"1": {"2": char_data}}
        view = CategoryView(cog, pulp_data, ["a_talent"], 2, {"a_talent": "mundane"}, char_data, player_stats)
        select = view.children[0]
        assert isinstance(select, TalentCategorySelect)

        select._values = ["mundane"]
        interaction = make_interaction()
        await select.callback(interaction)

        cog.pulp_talent_category_selected.assert_awaited_once_with(
            interaction, "mundane", pulp_data, ["a_talent"], 2, {"a_talent": "mundane"}, char_data, player_stats
        )


class TestCategoryView:
    @pytest.mark.asyncio
    async def test_stores_context_and_adds_select(self, cog, pulp_data):
        char_data = {}
        player_stats = {}
        view = CategoryView(cog, pulp_data, [], 3, {}, char_data, player_stats)

        assert view.cog is cog
        assert view.pulp_data is pulp_data
        assert view.slots_total == 3
        assert view.char_data is char_data
        assert view.player_stats is player_stats
        assert len(view.children) == 1
        assert isinstance(view.children[0], TalentCategorySelect)


class TestTalentSelect:
    def test_filters_already_selected_and_parses_name_description(self):
        # already_selected is compared against the raw "**Name**: desc" strings, not
        # parsed names -- this matches how commands/newinvestigator.py actually populates
        # current_list (via full_map, which maps name -> full raw string).
        talents = ["**Fast Talker**: Gain bonus to Fast Talk.", "**Tough**: Gain bonus HP."]
        select = TalentSelect(talents, already_selected=["**Tough**: Gain bonus HP."])
        assert len(select.options) == 1
        opt = select.options[0]
        assert opt.label == "Fast Talker"
        assert opt.description == "Gain bonus to Fast Talk."
        assert opt.value == "Fast Talker"

    def test_no_options_available_falls_back_to_placeholder_option(self):
        select = TalentSelect(["**Tough**: desc"], already_selected=["**Tough**: desc"])
        assert len(select.options) == 1
        assert select.options[0].value == "none"

    @pytest.mark.asyncio
    async def test_callback_delegates_to_cog_with_full_context(self, cog):
        char_data = {"NAME": "Jane"}
        player_stats = {"1": {"2": char_data}}
        view = TalentOptionView(
            cog, ["**Fast Talker**: desc"], [], {"Fast Talker": "mundane"},
            {"mundane": ["**Fast Talker**: desc"]}, ["current"], 2, char_data, player_stats,
        )
        # TalentOptionView has a decorated back_button, which discord.py adds to
        # _children during super().__init__() -- before the TalentSelect is add_item'd
        # -- so children[0] is the Back button, not the select. Look it up by type.
        select = next(c for c in view.children if isinstance(c, TalentSelect))

        select._values = ["Fast Talker"]
        interaction = make_interaction()
        await select.callback(interaction)

        cog.pulp_talent_selected.assert_awaited_once_with(
            interaction, "Fast Talker", {"mundane": ["**Fast Talker**: desc"]}, ["current"], 2,
            {"Fast Talker": "mundane"}, char_data, player_stats,
        )


class TestTalentOptionViewBackNavigation:
    @pytest.mark.asyncio
    async def test_back_button_returns_to_pulp_talent_selection_loop_with_original_state(self, cog):
        char_data = {"NAME": "Jane"}
        player_stats = {"1": {"2": char_data}}
        pulp_data = {"mundane": ["**Fast Talker**: desc"]}
        current_list = ["Fast Talker", "Tough"]
        full_map = {"Fast Talker": "mundane"}

        view = TalentOptionView(
            cog, ["**Fast Talker**: desc"], [], full_map, pulp_data, current_list, 2, char_data, player_stats,
        )
        interaction = make_interaction()

        await view.back_button.callback(interaction)

        # Back navigation must return to the category/talent selection loop with the
        # exact same char_data/player_stats/pulp_data/current_list/slots/full_map it was
        # constructed with -- i.e. no state is mutated or reset on Back.
        cog.pulp_talent_selection_loop.assert_awaited_once_with(
            interaction, char_data, player_stats, pulp_data, current_list, 2, full_map
        )

    @pytest.mark.asyncio
    async def test_back_button_present_on_view(self, cog):
        view = TalentOptionView(cog, ["**Fast Talker**: desc"], [], {}, {}, [], 0, {}, {})
        assert any(getattr(c, "label", None) == "Back" for c in view.children)
