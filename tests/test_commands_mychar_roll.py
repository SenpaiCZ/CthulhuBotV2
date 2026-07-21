import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands._mychar_roll import SkillSearchModal, SkillRollSelect
from commands._roll_views import RollResultView


def make_interaction(user=None):
    interaction = MagicMock()
    interaction.user = user or MagicMock(id=222)
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    return interaction


def make_dashboard_view(**overrides):
    view = MagicMock()
    view.server_id = overrides.get("server_id", "111")
    view.owner_id = overrides.get("owner_id", "222")
    view.char_data = overrides.get("char_data", {"Spot Hidden": 50, "Listen": 40})
    view.refresh_dashboard = AsyncMock()
    view._get_skill_list = MagicMock(return_value=list(view.char_data.items()))
    view._get_skill_emoji = MagicMock(return_value=None)
    return view


class TestSkillSearchModal:
    @pytest.mark.asyncio
    async def test_exact_substring_match_wins_over_fuzzy(self):
        view = make_dashboard_view(char_data={"Spot Hidden": 50, "Listen": 40})
        modal = SkillSearchModal(view)
        modal.skill_name._value = "spot"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.edit_message.assert_awaited_once()
        _, kwargs = interaction.response.edit_message.call_args
        select = next(c for c in kwargs["view"].children if isinstance(c, SkillRollSelect))
        assert [o.value for o in select.options] == ["Spot Hidden"]

    @pytest.mark.asyncio
    async def test_no_matches_sends_ephemeral_failure(self):
        view = make_dashboard_view(char_data={"Spot Hidden": 50})
        modal = SkillSearchModal(view)
        modal.skill_name._value = "zzzznomatch"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "No skills found similar to" in interaction.response.send_message.call_args.args[0]
        interaction.response.edit_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_back_button_in_results_returns_to_dashboard(self):
        view = make_dashboard_view(char_data={"Spot Hidden": 50})
        modal = SkillSearchModal(view)
        modal.skill_name._value = "spot"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        _, kwargs = interaction.response.edit_message.call_args
        back_btn = next(c for c in kwargs["view"].children if getattr(c, "label", None) == "Back")

        back_interaction = make_interaction()
        await back_btn.callback(back_interaction)

        view.refresh_dashboard.assert_awaited_once_with(back_interaction)


class TestSkillRollSelect:
    @pytest.mark.asyncio
    async def test_callback_rolls_and_sends_result_publicly(self):
        char_data = {"Spot Hidden": 50}
        view = make_dashboard_view(char_data=char_data)
        select = SkillRollSelect(view, [("Spot Hidden", 50)])
        select._values = ["Spot Hidden"]

        roll_cog = MagicMock()
        roll_cog.calculate_roll_result = MagicMock(return_value=("Regular Success", 2))

        interaction = make_interaction()
        interaction.client.get_cog = MagicMock(return_value=roll_cog)
        sent_message = MagicMock()
        interaction.channel.send = AsyncMock(return_value=sent_message)

        with patch("loadnsave.load_luck_stats", new=AsyncMock(return_value={"111": 10})):
            await select.callback(interaction)

        interaction.channel.send.assert_awaited_once()
        _, kwargs = interaction.channel.send.call_args
        assert isinstance(kwargs["view"], RollResultView)
        assert kwargs["view"].message is sent_message
        interaction.response.edit_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_callback_reports_when_roll_system_unavailable(self):
        view = make_dashboard_view()
        select = SkillRollSelect(view, [("Spot Hidden", 50)])
        select._values = ["Spot Hidden"]

        interaction = make_interaction()
        interaction.client.get_cog = MagicMock(return_value=None)

        await select.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("Roll system unavailable.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_back_to_sheet_button_after_roll_refreshes_dashboard(self):
        char_data = {"Spot Hidden": 50}
        view = make_dashboard_view(char_data=char_data)
        select = SkillRollSelect(view, [("Spot Hidden", 50)])
        select._values = ["Spot Hidden"]

        roll_cog = MagicMock()
        roll_cog.calculate_roll_result = MagicMock(return_value=("Regular Success", 2))
        interaction = make_interaction()
        interaction.client.get_cog = MagicMock(return_value=roll_cog)
        interaction.channel.send = AsyncMock(return_value=MagicMock())

        with patch("loadnsave.load_luck_stats", new=AsyncMock(return_value={"111": 10})):
            await select.callback(interaction)

        _, kwargs = interaction.response.edit_message.call_args
        back_btn = next(c for c in kwargs["view"].children if getattr(c, "label", None) == "Back to Sheet")

        back_interaction = make_interaction()
        await back_btn.callback(back_interaction)

        view.refresh_dashboard.assert_awaited_once_with(back_interaction)
