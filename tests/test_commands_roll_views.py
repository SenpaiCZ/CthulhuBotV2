import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands._roll_views import (
    SessionView,
    DisambiguationSelect,
    DisambiguationView,
    DamageSelect,
    DamageSelectView,
    RollResultView,
    QuickSkillSelect,
    DiceTrayView,
)


def make_interaction(user=None):
    interaction = MagicMock()
    interaction.user = user or MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    # RollResultView.done_button and DiceTrayView.roll_btn unconditionally
    # `await interaction.response.defer(...)` before doing anything else -- a plain
    # MagicMock attribute isn't awaitable, so every interaction needs this as an
    # AsyncMock even for tests that don't otherwise care about deferral.
    interaction.response.defer = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup.send = AsyncMock()
    interaction.message = MagicMock(embeds=[discord.Embed(description="orig")])
    interaction.message.edit = AsyncMock()
    return interaction


class TestSessionView:
    @pytest.mark.asyncio
    async def test_yes_by_author_sets_create_session_true_and_disables_buttons(self):
        author = MagicMock()
        ctx = MagicMock(author=author)
        view = SessionView(ctx)
        interaction = make_interaction(user=author)

        await view.yes_button.callback(interaction)

        assert view.create_session is True
        assert all(c.disabled for c in view.children)
        interaction.response.edit_message.assert_awaited_once_with(view=view)

    @pytest.mark.asyncio
    async def test_no_by_non_author_is_rejected(self):
        ctx = MagicMock(author=MagicMock())
        view = SessionView(ctx)
        other_user = MagicMock()
        interaction = make_interaction(user=other_user)

        await view.no_button.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("Not for you!", ephemeral=True)
        assert view.create_session is False  # unchanged default, not flipped by rejected click


class TestDisambiguation:
    @pytest.mark.asyncio
    async def test_select_sets_selected_stat_and_stops_view(self):
        ctx = MagicMock(author=MagicMock())
        view = DisambiguationView(ctx, ["Spot Hidden", "Listen"])
        # DisambiguationView has a decorated Cancel button, which discord.py adds to
        # _children during super().__init__() -- before the DisambiguationSelect is
        # add_item'd in the body of __init__ -- so children[0] is Cancel, not the
        # select. Look it up by type instead of assuming position.
        select = next(c for c in view.children if isinstance(c, DisambiguationSelect))
        select._values = ["Listen"]

        interaction = make_interaction()
        await select.callback(interaction)

        assert view.selected_stat == "Listen"
        interaction.response.defer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_interaction_check_rejects_other_users(self):
        author = MagicMock()
        ctx = MagicMock(author=author)
        view = DisambiguationView(ctx, ["Spot Hidden"])
        interaction = make_interaction(user=MagicMock())

        result = await view.interaction_check(interaction)

        assert result is False
        interaction.response.send_message.assert_awaited_once_with("Not your session!", ephemeral=True)


class TestDamageSelect:
    @pytest.mark.asyncio
    async def test_callback_dispatches_chosen_formula_and_label(self):
        damage_data = [{"label": "1d6", "value": "1d6"}, {"label": "1d8+1", "value": "1d8+1"}]
        parent_view = MagicMock(damage_data=damage_data)
        parent_view.perform_damage_roll = AsyncMock()
        select = DamageSelect(damage_data, parent_view)
        select._values = ["1d8+1"]

        interaction = make_interaction()
        await select.callback(interaction)

        parent_view.perform_damage_roll.assert_awaited_once_with(interaction, "1d8+1", "1d8+1")


def make_roll_view(**overrides):
    cog = MagicMock()
    cog.calculate_roll_result = MagicMock(return_value=("Regular Success", 2))
    cog.evaluate_dice_expression = MagicMock(return_value=(5, "1d6 -> 5"))

    ctx = MagicMock(author=overrides.get("author", MagicMock()))
    player_stats = overrides.get(
        "player_stats", {"srv": {"usr": {"LUCK": 50}}}
    )
    kwargs = dict(
        ctx=ctx, cog=cog, player_stats=player_stats, server_id="srv", user_id="usr",
        stat_name="Spot Hidden", current_value=50, ones_roll=5, tens_rolls=[20],
        net_dice=0, result_tier=2, luck_threshold=10,
    )
    kwargs.update(overrides.get("kwargs", {}))
    return RollResultView(**kwargs), cog, ctx, player_stats


class TestRollResultView:
    @pytest.mark.asyncio
    async def test_constructor_removes_damage_button_when_no_damage_data(self):
        view, *_ = make_roll_view()
        assert not any(getattr(c, "label", None) == "Roll Damage" for c in view.children)

    @pytest.mark.asyncio
    async def test_constructor_enables_damage_button_on_success_with_damage_data(self):
        view, *_ = make_roll_view(kwargs={"damage_data": [{"label": "1d6", "value": "1d6"}], "damage_bonus": "0"})
        damage_btn = next(c for c in view.children if getattr(c, "label", None) == "Roll Damage")
        assert damage_btn.disabled is False

    @pytest.mark.asyncio
    async def test_constructor_detects_malfunction_and_overrides_success(self):
        view, *_ = make_roll_view(kwargs={"malfunction_threshold": "20"})
        # roll = tens(20) + ones(5) = 25 >= limit 20 -> malfunction
        assert view.is_malfunction is True
        assert view.success is False

    @pytest.mark.asyncio
    async def test_bonus_die_increments_net_dice_and_recalculates(self):
        view, cog, *_ = make_roll_view()
        interaction = make_interaction()

        await view.add_bonus_btn.callback(interaction)

        assert view.net_dice == 1
        assert len(view.tens_rolls) >= 2
        cog.calculate_roll_result.assert_called_once()
        interaction.response.edit_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_penalty_die_decrements_net_dice(self):
        view, cog, *_ = make_roll_view()
        interaction = make_interaction()

        await view.add_penalty_btn.callback(interaction)

        assert view.net_dice == -1

    @pytest.mark.asyncio
    async def test_luck_button_deducts_cost_and_marks_used(self):
        # Fail tier(1) target = current_value(50); roll = 25 -> target_val=50 means cost negative;
        # use a Fail-tier roll so cost is positive and luck applies cleanly.
        view, cog, ctx, player_stats = make_roll_view(kwargs={"result_tier": 1, "ones_roll": 9, "tens_rolls": [90]})
        # roll = 99, target = current_value (50) on a Fail -> Regular upgrade, cost = 49
        interaction = make_interaction()

        await view.luck_button.callback(interaction)

        assert view.luck_used is True
        assert view.success is True
        assert view.result_tier == 2
        assert player_stats["srv"]["usr"]["LUCK"] == 50 - 49
        interaction.response.edit_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_push_roll_disables_all_buttons_and_clears_view(self):
        view, cog, *_ = make_roll_view(kwargs={"result_tier": 1})
        cog.calculate_roll_result = MagicMock(return_value=("Failure", 0))
        interaction = make_interaction()

        with patch("commands._roll_views.random.randint", return_value=1):
            await view.push_button.callback(interaction)

        assert all(c.disabled for c in view.children)
        interaction.response.edit_message.assert_awaited_once()
        _, kwargs = interaction.response.edit_message.call_args
        assert kwargs["view"] is None

    @pytest.mark.asyncio
    async def test_done_button_invokes_async_on_complete_and_stops(self):
        on_complete = AsyncMock()
        view, *_ = make_roll_view(kwargs={"on_complete": on_complete})
        interaction = make_interaction()

        await view.done_button.callback(interaction)

        on_complete.assert_awaited_once_with(view.roll, view.result_tier, view.is_malfunction)
        assert view.is_finished()
        interaction.message.edit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_done_button_invokes_sync_on_complete(self):
        on_complete = MagicMock()
        view, *_ = make_roll_view(kwargs={"on_complete": on_complete})
        interaction = make_interaction()

        await view.done_button.callback(interaction)

        on_complete.assert_called_once_with(view.roll, view.result_tier, view.is_malfunction)

    @pytest.mark.asyncio
    async def test_damage_btn_single_item_rolls_directly(self):
        view, cog, *_ = make_roll_view(
            kwargs={"damage_data": [{"label": "1d6", "value": "1d6"}], "damage_bonus": "0"}
        )
        interaction = make_interaction()

        await view.damage_btn.callback(interaction)

        cog.evaluate_dice_expression.assert_called_once_with("1d6")
        interaction.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_damage_btn_multiple_items_shows_selection_view(self):
        damage_data = [{"label": "1d6", "value": "1d6"}, {"label": "1d8", "value": "1d8"}]
        view, cog, *_ = make_roll_view(kwargs={"damage_data": damage_data, "damage_bonus": "0"})
        interaction = make_interaction()

        await view.damage_btn.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        assert isinstance(kwargs["view"], DamageSelectView)

    @pytest.mark.asyncio
    async def test_interaction_check_rejects_non_author(self):
        view, *_ = make_roll_view()
        interaction = make_interaction(user=MagicMock())

        result = await view.interaction_check(interaction)

        assert result is False


class TestQuickSkillSelect:
    @pytest.mark.asyncio
    async def test_options_limited_to_top_25_skills_sorted_descending(self):
        char_data = {f"Skill{i}": i for i in range(30)}
        select = QuickSkillSelect(char_data, "srv", "usr")
        assert len(select.options) == 25
        assert select.options[0].value == "Skill29"

    @pytest.mark.asyncio
    async def test_callback_rolls_and_sends_channel_message(self):
        char_data = {"Spot Hidden": 50}
        select = QuickSkillSelect(char_data, "srv", "usr")
        select._values = ["Spot Hidden"]

        roll_cog = MagicMock()
        roll_cog.calculate_roll_result = MagicMock(return_value=("Regular Success", 2))

        interaction = make_interaction()
        interaction.client.get_cog = MagicMock(return_value=roll_cog)
        sent_message = MagicMock()
        interaction.channel.send = AsyncMock(return_value=sent_message)

        with patch("commands._roll_views.load_luck_stats", new=AsyncMock(return_value={"srv": 10})), \
             patch("commands._roll_views.load_player_stats", new=AsyncMock(return_value={"srv": {"usr": char_data}})):
            await select.callback(interaction)

        interaction.channel.send.assert_awaited_once()
        _, kwargs = interaction.channel.send.call_args
        assert isinstance(kwargs["view"], RollResultView)
        assert kwargs["view"].message is sent_message
        interaction.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_callback_noop_when_roll_cog_missing(self):
        char_data = {"Spot Hidden": 50}
        select = QuickSkillSelect(char_data, "srv", "usr")
        select._values = ["Spot Hidden"]

        interaction = make_interaction()
        interaction.client.get_cog = MagicMock(return_value=None)

        await select.callback(interaction)

        interaction.response.send_message.assert_not_awaited()


class TestDiceTrayView:
    @pytest.mark.asyncio
    async def test_add_term_appends_expression_and_updates_display(self):
        view = DiceTrayView(MagicMock(), MagicMock())
        interaction = make_interaction()

        await view.d6.callback(interaction)
        assert view.expression == "1d6"
        interaction.response.edit_message.assert_awaited_once()

        interaction2 = make_interaction()
        await view.d20.callback(interaction2)
        assert view.expression == "1d6 + 1d20"

    @pytest.mark.asyncio
    async def test_clear_resets_expression(self):
        view = DiceTrayView(MagicMock(), MagicMock())
        view.expression = "1d6 + 5"
        interaction = make_interaction()

        await view.clear.callback(interaction)

        assert view.expression == ""

    @pytest.mark.asyncio
    async def test_roll_with_empty_expression_is_rejected(self):
        cog = MagicMock()
        cog._perform_roll = AsyncMock()
        view = DiceTrayView(cog, MagicMock())
        interaction = make_interaction()

        await view.roll_btn.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("Add dice first!", ephemeral=True)
        cog._perform_roll.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_roll_with_expression_invokes_cog_perform_roll(self):
        cog = MagicMock()
        cog._perform_roll = AsyncMock()
        view = DiceTrayView(cog, MagicMock())
        view.expression = "1d20 + 5"
        interaction = make_interaction()
        interaction.delete_original_response = AsyncMock()

        await view.roll_btn.callback(interaction)

        cog._perform_roll.assert_awaited_once_with(interaction, "1d20 + 5", 0, 0, True, "Regular")

    @pytest.mark.asyncio
    async def test_interaction_check_rejects_other_users(self):
        owner = MagicMock()
        view = DiceTrayView(MagicMock(), owner)
        interaction = make_interaction(user=MagicMock())

        result = await view.interaction_check(interaction)

        assert result is False
