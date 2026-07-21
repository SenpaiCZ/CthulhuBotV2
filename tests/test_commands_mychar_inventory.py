import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands._mychar_inventory import (
    AddItemModal,
    EditItemModal,
    GiveUserSelect,
    ItemActionsView,
    InventorySelect,
)


def make_interaction(user=None, guild_id=111):
    interaction = MagicMock()
    interaction.user = user or MagicMock(id=222)
    interaction.guild_id = guild_id
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.delete_original_response = AsyncMock()
    return interaction


def make_dashboard_view(**overrides):
    view = MagicMock()
    view.server_id = overrides.get("server_id", "111")
    view.owner_id = overrides.get("owner_id", "222")
    view.char_data = overrides.get("char_data", {})
    view.can_edit = overrides.get("can_edit", True)
    view.refresh_dashboard = AsyncMock()
    view.user = overrides.get("user", MagicMock())
    view.inventory_page = 0
    view.update_components = MagicMock()
    view.launch_item_actions = AsyncMock()
    return view


class TestAddItemModal:
    @pytest.mark.asyncio
    async def test_adds_item_with_details_to_gear_and_possessions(self):
        view = make_dashboard_view(char_data={})
        modal = AddItemModal(view)
        modal.item_name._value = "Flashlight"
        modal.details._value = "1x"

        interaction = make_interaction()
        player_stats = {}
        with patch("commands._mychar_inventory.load_player_stats", new=AsyncMock(return_value=player_stats)), \
             patch("commands._mychar_inventory.save_player_stats", new=AsyncMock()) as mock_save:
            await modal.on_submit(interaction)

        assert view.char_data["Backstory"]["Gear and Possessions"] == ["Flashlight 1x"]
        mock_save.assert_awaited_once()
        view.refresh_dashboard.assert_awaited_once_with(interaction)

    @pytest.mark.asyncio
    async def test_creates_server_entry_if_missing(self):
        view = make_dashboard_view(char_data={})
        modal = AddItemModal(view)
        modal.item_name._value = "Revolver"
        modal.details._value = ""

        interaction = make_interaction()
        player_stats = {}
        with patch("commands._mychar_inventory.load_player_stats", new=AsyncMock(return_value=player_stats)), \
             patch("commands._mychar_inventory.save_player_stats", new=AsyncMock()):
            await modal.on_submit(interaction)

        assert "111" in player_stats
        assert player_stats["111"]["222"] is view.char_data


class TestEditItemModal:
    @pytest.mark.asyncio
    async def test_updates_item_at_index(self):
        char_data = {"Backstory": {"Gear and Possessions": ["Old Item"]}}
        view = make_dashboard_view(char_data=char_data)
        modal = EditItemModal(view, "Gear and Possessions", 0, "Old Item")
        modal.item_input._value = "New Item"

        interaction = make_interaction()
        player_stats = {"111": {"222": {}}}
        with patch("commands._mychar_inventory.load_player_stats", new=AsyncMock(return_value=player_stats)), \
             patch("commands._mychar_inventory.save_player_stats", new=AsyncMock()) as mock_save:
            await modal.on_submit(interaction)

        assert char_data["Backstory"]["Gear and Possessions"][0] == "New Item"
        mock_save.assert_awaited_once()
        view.refresh_dashboard.assert_awaited_once_with(interaction)

    @pytest.mark.asyncio
    async def test_out_of_bounds_index_reports_error(self):
        char_data = {"Backstory": {"Gear and Possessions": ["Only Item"]}}
        view = make_dashboard_view(char_data=char_data)
        modal = EditItemModal(view, "Gear and Possessions", 5, "Only Item")
        modal.item_input._value = "New text"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once_with("Error: Item index out of bounds.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_missing_category_reports_error(self):
        char_data = {"Backstory": {}}
        view = make_dashboard_view(char_data=char_data)
        modal = EditItemModal(view, "Unknown Category", 0, "text")
        modal.item_input._value = "New text"

        interaction = make_interaction()
        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once_with("Error: Category not found.", ephemeral=True)


class TestGiveUserSelect:
    @pytest.mark.asyncio
    async def test_transfers_item_from_sender_to_target(self):
        dashboard_view = make_dashboard_view(server_id="111", owner_id="222", char_data={"Backstory": {"Gear and Possessions": ["Revolver"]}})
        action_view = MagicMock(dashboard_view=dashboard_view)
        action_view.stop = MagicMock()
        select = GiveUserSelect(action_view, "Gear and Possessions", "Revolver", 0)
        target_user = MagicMock(id=999, bot=False)
        target_user.display_name = "Bob"
        select._values = [target_user]

        interaction = make_interaction(guild_id=111)
        player_stats = {
            "111": {
                "222": {"Backstory": {"Gear and Possessions": ["Revolver"]}},
                "999": {},
            }
        }
        with patch("commands._mychar_inventory.load_player_stats", new=AsyncMock(return_value=player_stats)), \
             patch("commands._mychar_inventory.save_player_stats", new=AsyncMock()) as mock_save:
            await select.callback(interaction)

        assert player_stats["111"]["222"]["Backstory"]["Gear and Possessions"] == []
        assert player_stats["111"]["999"]["Backstory"]["Gear and Possessions"] == ["Revolver"]
        assert dashboard_view.char_data["Backstory"]["Gear and Possessions"] == []
        mock_save.assert_awaited_once()
        dashboard_view.refresh_dashboard.assert_awaited_once_with(interaction)
        action_view.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_cannot_give_to_self(self):
        dashboard_view = make_dashboard_view(owner_id="222")
        action_view = MagicMock(dashboard_view=dashboard_view)
        select = GiveUserSelect(action_view, "Gear and Possessions", "Revolver", 0)
        target_user = MagicMock(id=222, bot=False)
        select._values = [target_user]

        interaction = make_interaction()
        await select.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("You cannot give items to yourself.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_cannot_give_to_bot(self):
        dashboard_view = make_dashboard_view(owner_id="222")
        action_view = MagicMock(dashboard_view=dashboard_view)
        select = GiveUserSelect(action_view, "Gear and Possessions", "Revolver", 0)
        target_user = MagicMock(id=999, bot=True)
        select._values = [target_user]

        interaction = make_interaction()
        await select.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("You cannot give items to bots.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_target_without_investigator_rejected(self):
        dashboard_view = make_dashboard_view(owner_id="222")
        action_view = MagicMock(dashboard_view=dashboard_view)
        select = GiveUserSelect(action_view, "Gear and Possessions", "Revolver", 0)
        target_user = MagicMock(id=999, bot=False)
        target_user.display_name = "Bob"
        select._values = [target_user]

        interaction = make_interaction(guild_id=111)
        with patch("commands._mychar_inventory.load_player_stats", new=AsyncMock(return_value={"111": {}})):
            await select.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "does not have an active investigator" in interaction.response.send_message.call_args.args[0]


class TestItemActionsView:
    def test_give_select_only_added_when_can_edit(self):
        dashboard_view = make_dashboard_view(can_edit=True)
        view = ItemActionsView(dashboard_view, "Gear and Possessions", "Revolver", 0)
        assert any(isinstance(c, GiveUserSelect) for c in view.children)

        dashboard_view2 = make_dashboard_view(can_edit=False)
        view2 = ItemActionsView(dashboard_view2, "Gear and Possessions", "Revolver", 0)
        assert not any(isinstance(c, GiveUserSelect) for c in view2.children)

    @pytest.mark.asyncio
    async def test_show_item_sends_to_channel(self):
        dashboard_view = make_dashboard_view()
        view = ItemActionsView(dashboard_view, "Gear and Possessions", "Revolver", 0)
        interaction = make_interaction()
        interaction.channel.send = AsyncMock()

        await view.show_item.callback(interaction)

        interaction.channel.send.assert_awaited_once()
        interaction.response.send_message.assert_awaited_once_with("✅ Item shown to chat.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_edit_denied_without_permission(self):
        dashboard_view = make_dashboard_view(can_edit=False)
        view = ItemActionsView(dashboard_view, "Gear and Possessions", "Revolver", 0)
        interaction = make_interaction()

        await view.edit.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("You cannot edit this.", ephemeral=True)
        interaction.response.send_modal.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_edit_opens_modal_and_stops(self):
        dashboard_view = make_dashboard_view(can_edit=True)
        view = ItemActionsView(dashboard_view, "Gear and Possessions", "Revolver", 0)
        interaction = make_interaction()

        await view.edit.callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        assert view.is_finished()

    @pytest.mark.asyncio
    async def test_discard_removes_item_from_both_stats_and_local_view(self):
        char_data = {"Backstory": {"Gear and Possessions": ["Revolver"]}}
        dashboard_view = make_dashboard_view(can_edit=True, char_data=char_data, owner_id="222")
        view = ItemActionsView(dashboard_view, "Gear and Possessions", "Revolver", 0)
        interaction = make_interaction(guild_id=111)

        player_stats = {"111": {"222": {"Backstory": {"Gear and Possessions": ["Revolver"]}}}}
        with patch("commands._mychar_inventory.load_player_stats", new=AsyncMock(return_value=player_stats)), \
             patch("commands._mychar_inventory.save_player_stats", new=AsyncMock()) as mock_save:
            await view.discard.callback(interaction)

        assert player_stats["111"]["222"]["Backstory"]["Gear and Possessions"] == []
        assert char_data["Backstory"]["Gear and Possessions"] == []
        mock_save.assert_awaited_once()
        dashboard_view.refresh_dashboard.assert_awaited_once_with(interaction)
        assert view.is_finished()

    @pytest.mark.asyncio
    async def test_cancel_deletes_ephemeral_message_and_stops(self):
        dashboard_view = make_dashboard_view()
        view = ItemActionsView(dashboard_view, "Gear and Possessions", "Revolver", 0)
        interaction = make_interaction()

        await view.cancel.callback(interaction)

        interaction.response.defer.assert_awaited_once()
        interaction.delete_original_response.assert_awaited_once()
        assert view.is_finished()


class TestInventorySelect:
    def test_adds_pagination_options_when_more_items_exist(self):
        dashboard_view = make_dashboard_view()
        items = [("Gear and Possessions", f"Item {i}") for i in range(30)]
        select = InventorySelect(dashboard_view, items, page=0)

        values = [o.value for o in select.options]
        assert "next_page" in values
        assert "prev_page" not in values
        assert len(select.options) == 25  # 24 items + next_page marker

    @pytest.mark.asyncio
    async def test_selecting_next_page_advances_dashboard(self):
        dashboard_view = make_dashboard_view()
        items = [("Gear and Possessions", f"Item {i}") for i in range(30)]
        select = InventorySelect(dashboard_view, items, page=0)
        select._values = ["next_page"]
        interaction = make_interaction()
        interaction.user = dashboard_view.user

        await select.callback(interaction)

        assert dashboard_view.inventory_page == 1
        dashboard_view.update_components.assert_called_once()

    @pytest.mark.asyncio
    async def test_selecting_item_launches_item_actions(self):
        dashboard_view = make_dashboard_view()
        items = [("Gear and Possessions", "Revolver")]
        select = InventorySelect(dashboard_view, items, page=0)
        select._values = ["0"]
        interaction = make_interaction()
        interaction.user = dashboard_view.user

        await select.callback(interaction)

        dashboard_view.launch_item_actions.assert_awaited_once_with(interaction, "Gear and Possessions", "Revolver", 0)

    @pytest.mark.asyncio
    async def test_non_owner_rejected(self):
        dashboard_view = make_dashboard_view()
        items = [("Gear and Possessions", "Revolver")]
        select = InventorySelect(dashboard_view, items, page=0)
        select._values = ["0"]
        interaction = make_interaction(user=MagicMock())

        await select.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("Not your dashboard!", ephemeral=True)
        dashboard_view.launch_item_actions.assert_not_awaited()
