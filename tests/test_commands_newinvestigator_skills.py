import discord
import pytest
from unittest.mock import AsyncMock, MagicMock

from commands._newinvestigator_skills import (
    SkillPointSetModal,
    SkillSpecializationModal,
    CustomSkillModal,
    CthulhuMythosWarningView,
    SkillPageSelect,
    SkillPointAllocationView,
    FinishConfirmationView,
)


def make_interaction():
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    return interaction


def make_view(**overrides):
    view = MagicMock()
    view.char_data = overrides.get("char_data", {"Spot Hidden": 25})
    view.max_skill = overrides.get("max_skill", 75)
    view.remaining_points = overrides.get("remaining_points", 50)
    view.min_cr = overrides.get("min_cr", 0)
    view.max_cr = overrides.get("max_cr", 99)
    view.all_skills = overrides.get("all_skills", ["Spot Hidden"])
    view.refresh = AsyncMock()
    return view


class TestSkillPointSetModal:
    @pytest.mark.asyncio
    async def test_valid_increase_applies_cost_and_refreshes(self):
        view = make_view()
        modal = SkillPointSetModal(view, "Spot Hidden", current_val=25, base_val=25)
        modal.value_input.component._value = "40"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        assert view.char_data["Spot Hidden"] == 40
        assert view.remaining_points == 50 - 15
        view.refresh.assert_awaited_once_with(interaction)

    @pytest.mark.asyncio
    async def test_non_numeric_value_rejected(self):
        view = make_view()
        modal = SkillPointSetModal(view, "Spot Hidden", current_val=25, base_val=25)
        modal.value_input.component._value = "not-a-number"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "valid number" in interaction.response.send_message.call_args.args[0]
        view.refresh.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_credit_rating_uses_min_max_cr_bounds(self):
        view = make_view(min_cr=10, max_cr=90, char_data={"Credit Rating": 10}, remaining_points=100)
        modal = SkillPointSetModal(view, "Credit Rating", current_val=10, base_val=10)
        modal.value_input.component._value = "5"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "Credit Rating must be between" in interaction.response.send_message.call_args.args[0]

    @pytest.mark.asyncio
    async def test_below_base_value_rejected(self):
        view = make_view()
        modal = SkillPointSetModal(view, "Spot Hidden", current_val=25, base_val=25)
        modal.value_input.component._value = "10"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "below base value" in interaction.response.send_message.call_args.args[0]

    @pytest.mark.asyncio
    async def test_not_enough_points_rejected(self):
        view = make_view(remaining_points=5)
        modal = SkillPointSetModal(view, "Spot Hidden", current_val=25, base_val=25)
        modal.value_input.component._value = "50"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "Not enough points" in interaction.response.send_message.call_args.args[0]
        assert view.char_data["Spot Hidden"] == 25


class TestSkillSpecializationModal:
    @pytest.mark.asyncio
    async def test_creates_new_named_specialization(self):
        view = make_view(char_data={}, all_skills=[], remaining_points=50)
        modal = SkillSpecializationModal(view, "Art/Craft (Any)", base_val=5)
        modal.spec_name.component._value = "Painting"
        modal.value_input.component._value = "30"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        assert view.char_data["Art/Craft (Painting)"] == 30
        assert view.remaining_points == 50 - 25
        assert "Art/Craft (Painting)" in view.all_skills
        view.refresh.assert_awaited_once_with(interaction)

    @pytest.mark.asyncio
    async def test_duplicate_specialization_rejected(self):
        view = make_view(char_data={"Art/Craft (Painting)": 30})
        modal = SkillSpecializationModal(view, "Art/Craft (Any)", base_val=5)
        modal.spec_name.component._value = "Painting"
        modal.value_input.component._value = "30"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "already have this specialization" in interaction.response.send_message.call_args.args[0]


class TestCustomSkillModal:
    @pytest.mark.asyncio
    async def test_adds_custom_skill_with_emoji(self):
        view = make_view(char_data={}, all_skills=[], remaining_points=50)
        modal = CustomSkillModal(view)
        modal.skill_name.component._value = "Lore (Vampires)"
        modal.base_val.component._value = "5"
        modal.value_input.component._value = "20"
        modal.emoji_input.component._value = "🧛"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        assert view.char_data["Lore (Vampires)"] == 20
        assert view.remaining_points == 50 - 15
        assert "Lore (Vampires)" in view.all_skills
        assert view.char_data["Custom Emojis"]["Lore (Vampires)"] == "🧛"
        view.refresh.assert_awaited_once_with(interaction)

    @pytest.mark.asyncio
    async def test_duplicate_skill_name_rejected(self):
        view = make_view(char_data={"Lore (Vampires)": 20})
        modal = CustomSkillModal(view)
        modal.skill_name.component._value = "Lore (Vampires)"
        modal.base_val.component._value = "5"
        modal.value_input.component._value = "20"
        modal.emoji_input.component._value = ""

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "already exists" in interaction.response.send_message.call_args.args[0]


class TestCthulhuMythosWarningView:
    @pytest.mark.asyncio
    async def test_assign_opens_skill_point_set_modal(self):
        parent_view = make_view()
        view = CthulhuMythosWarningView(parent_view, "Cthulhu Mythos", current_val=0, base_val=0)
        interaction = make_interaction()

        await view.assign.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        modal = interaction.response.send_modal.call_args.args[0]
        assert isinstance(modal, SkillPointSetModal)
        assert modal.skill_name == "Cthulhu Mythos"

    @pytest.mark.asyncio
    async def test_cancel_edits_message_and_clears_view(self):
        parent_view = make_view()
        view = CthulhuMythosWarningView(parent_view, "Cthulhu Mythos", current_val=0, base_val=0)
        interaction = make_interaction()

        await view.cancel.callback(interaction)

        interaction.response.edit_message.assert_awaited_once_with(content="Action cancelled.", view=None)


class TestSkillPageSelect:
    @pytest.mark.asyncio
    async def test_selecting_cthulhu_mythos_shows_warning_view(self):
        parent_view = make_view(char_data={"Cthulhu Mythos": 0})
        options = [discord.SelectOption(label="Cthulhu Mythos: 0%", value="Cthulhu Mythos")]
        select = SkillPageSelect(options)
        select._view = parent_view
        select._values = ["Cthulhu Mythos"]

        interaction = make_interaction()
        await select.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        assert isinstance(kwargs["view"], CthulhuMythosWarningView)

    @pytest.mark.asyncio
    async def test_selecting_any_skill_opens_specialization_modal(self):
        parent_view = make_view(char_data={"Art/Craft (Any)": 5})
        options = [discord.SelectOption(label="Art/Craft (Any): 5%", value="Art/Craft (Any)")]
        select = SkillPageSelect(options)
        select._view = parent_view
        select._values = ["Art/Craft (Any)"]

        interaction = make_interaction()
        await select.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        assert isinstance(interaction.response.send_modal.call_args.args[0], SkillSpecializationModal)

    @pytest.mark.asyncio
    async def test_selecting_normal_skill_opens_point_set_modal(self):
        parent_view = make_view(char_data={"Spot Hidden": 25})
        options = [discord.SelectOption(label="Spot Hidden: 25%", value="Spot Hidden")]
        select = SkillPageSelect(options)
        select._view = parent_view
        select._values = ["Spot Hidden"]

        interaction = make_interaction()
        await select.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        assert isinstance(interaction.response.send_modal.call_args.args[0], SkillPointSetModal)


@pytest.fixture
def alloc_cog():
    cog = MagicMock()
    cog.is_skill_allowed_for_archetype = MagicMock(return_value=True)
    cog.finish_skill_assignment = AsyncMock()
    return cog


class TestSkillPointAllocationView:
    @pytest.mark.asyncio
    async def test_get_skill_list_excludes_known_metadata_keys(self, alloc_cog):
        char_data = {
            "NAME": "Jane", "STR": 50, "Spot Hidden": 25, "Listen": 20, "Age": 24,
            "Backstory": {}, "Credit Rating": 10,
        }
        view = SkillPointAllocationView(alloc_cog, char_data, {}, remaining_points=50, min_cr=0, max_cr=99, is_occupation=False)

        assert "NAME" not in view.all_skills
        assert "STR" not in view.all_skills
        assert "Age" not in view.all_skills
        assert "Backstory" not in view.all_skills
        assert "Spot Hidden" in view.all_skills
        assert "Listen" in view.all_skills
        assert "Credit Rating" in view.all_skills

    @pytest.mark.asyncio
    async def test_finish_button_disabled_while_points_remain(self, alloc_cog):
        char_data = {"Spot Hidden": 25, "Credit Rating": 0}
        view = SkillPointAllocationView(alloc_cog, char_data, {}, remaining_points=10, min_cr=0, max_cr=99, is_occupation=False)

        finish_btn = next(c for c in view.children if getattr(c, "label", None) == "Finish")
        assert finish_btn.disabled is True

    @pytest.mark.asyncio
    async def test_finish_button_enabled_when_no_points_remain(self, alloc_cog):
        char_data = {"Spot Hidden": 25, "Credit Rating": 0}
        view = SkillPointAllocationView(alloc_cog, char_data, {}, remaining_points=0, min_cr=0, max_cr=99, is_occupation=False)

        finish_btn = next(c for c in view.children if getattr(c, "label", None) == "Finish")
        assert finish_btn.disabled is False

    @pytest.mark.asyncio
    async def test_finish_calls_cog_finish_skill_assignment(self, alloc_cog):
        char_data = {"Spot Hidden": 25, "Credit Rating": 0}
        view = SkillPointAllocationView(alloc_cog, char_data, {}, remaining_points=0, min_cr=0, max_cr=99, is_occupation=False)
        interaction = make_interaction()

        finish_btn = next(c for c in view.children if getattr(c, "label", None) == "Finish")
        await finish_btn.callback(interaction)

        alloc_cog.finish_skill_assignment.assert_awaited_once_with(interaction, view)

    @pytest.mark.asyncio
    async def test_pagination_next_and_prev(self, alloc_cog):
        char_data = {f"Skill {i}": i for i in range(30)}
        char_data["Credit Rating"] = 0
        view = SkillPointAllocationView(alloc_cog, char_data, {}, remaining_points=50, min_cr=0, max_cr=99, is_occupation=False)
        interaction = make_interaction()

        next_btn = next(c for c in view.children if getattr(c, "label", None) == "Next")
        await next_btn.callback(interaction)
        assert view.page == 1
        interaction.response.edit_message.assert_awaited_once()

        interaction2 = make_interaction()
        prev_btn = next(c for c in view.children if getattr(c, "label", None) == "Previous")
        await prev_btn.callback(interaction2)
        assert view.page == 0

    @pytest.mark.asyncio
    async def test_add_custom_skill_opens_modal(self, alloc_cog):
        char_data = {"Spot Hidden": 25, "Credit Rating": 0}
        view = SkillPointAllocationView(alloc_cog, char_data, {}, remaining_points=50, min_cr=0, max_cr=99, is_occupation=False)
        interaction = make_interaction()

        custom_btn = next(c for c in view.children if getattr(c, "label", None) == "Add Custom Skill")
        await custom_btn.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        assert isinstance(interaction.response.send_modal.call_args.args[0], CustomSkillModal)

    @pytest.mark.asyncio
    async def test_get_embed_lists_suggested_occupation_skills(self, alloc_cog):
        char_data = {
            "Spot Hidden": 40, "Credit Rating": 0,
            "Occupation Info": {"skills": "Spot Hidden, Listen"},
        }
        view = SkillPointAllocationView(alloc_cog, char_data, {}, remaining_points=10, min_cr=0, max_cr=99, is_occupation=True)
        embed = view.get_embed()
        assert "Suggested Occupation Skills" in embed.description
        assert "Improved Skills" in [f.name for f in embed.fields]


class TestFinishConfirmationViewBackNavigation:
    @pytest.mark.asyncio
    async def test_yes_proceeds_via_cog(self):
        cog = AsyncMock()
        parent_view = make_view()
        view = FinishConfirmationView(cog, parent_view, message=MagicMock())
        interaction = make_interaction()

        await view.yes.callback(interaction)

        cog.proceed_after_skills.assert_awaited_once_with(interaction, parent_view)

    @pytest.mark.asyncio
    async def test_no_back_button_only_sends_message_and_does_not_touch_cog_or_parent_state(self):
        # This is the wizard's "NO (Back)" step: unlike other back-navigations in this
        # codebase it does NOT re-render a prior view or call any cog method -- it simply
        # tells the user to keep using the still-open SkillPointAllocationView underneath.
        # It must not mutate remaining_points/char_data on the parent view at all.
        cog = AsyncMock()
        parent_view = make_view(remaining_points=5, char_data={"Spot Hidden": 25})
        view = FinishConfirmationView(cog, parent_view, message=MagicMock())
        interaction = make_interaction()

        await view.no.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "Cancelled. Continue assigning points.", ephemeral=True
        )
        cog.proceed_after_skills.assert_not_awaited()
        assert parent_view.remaining_points == 5
        assert parent_view.char_data == {"Spot Hidden": 25}
