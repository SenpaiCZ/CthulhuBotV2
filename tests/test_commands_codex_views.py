import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from commands._codex_views import (
    PaginatedListView,
    OptionsView,
    RenderView,
    CodexView,
    SelectionView,
)


def make_interaction(user=None):
    interaction = MagicMock()
    interaction.user = user or MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.data = {}
    return interaction


class TestPaginatedListView:
    def test_pagination_math_and_select_options_built(self):
        user = MagicMock()
        cog = MagicMock()
        items = [f"Item {i}" for i in range(45)]
        view = PaginatedListView(user, items, "Title", per_page=20, data={}, cog=cog, type_slug="monster")

        assert view.total_pages == 3
        assert view.select_menu is not None
        assert len(view.select_menu.options) == 20

    def test_no_items_on_page_adds_disabled_placeholder(self):
        user = MagicMock()
        cog = MagicMock()
        view = PaginatedListView(user, [], "Title", data={}, cog=cog, type_slug="monster")
        assert view.select_menu.options[0].value == "__none__"
        assert view.select_menu.disabled is True

    @pytest.mark.asyncio
    async def test_select_callback_rejects_non_owner(self):
        owner = MagicMock()
        cog = MagicMock()
        view = PaginatedListView(owner, ["Item A"], "Title", data={}, cog=cog, type_slug="monster")
        interaction = make_interaction(user=MagicMock())

        await view.select_callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("This isn't for you!", ephemeral=True)

    @pytest.mark.asyncio
    async def test_select_callback_displays_entry_when_found(self):
        owner = MagicMock()
        cog = MagicMock()
        cog._get_entry_data = MagicMock(return_value={"name": "Item A"})
        cog._display_entry = AsyncMock()
        view = PaginatedListView(owner, ["Item A"], "Title", data={"k": 1}, cog=cog, type_slug="monster")
        interaction = make_interaction(user=owner)
        interaction.data = {"values": ["Item A"]}

        await view.select_callback(interaction)

        cog._display_entry.assert_awaited_once_with(interaction, "Item A", "monster", {"name": "Item A"}, ephemeral=True)

    @pytest.mark.asyncio
    async def test_select_callback_falls_back_to_render_poster_when_missing(self):
        owner = MagicMock()
        cog = MagicMock()
        cog._get_entry_data = MagicMock(return_value=None)
        cog._render_poster = AsyncMock()
        view = PaginatedListView(owner, ["Item A"], "Title", data={}, cog=cog, type_slug="monster")
        interaction = make_interaction(user=owner)
        interaction.data = {"values": ["Item A"]}

        await view.select_callback(interaction)

        cog._render_poster.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_next_and_prev_buttons_update_page_and_embed(self):
        owner = MagicMock()
        items = [f"Item {i}" for i in range(25)]
        view = PaginatedListView(owner, items, "Title", per_page=20)
        interaction = make_interaction(user=owner)

        await view.next_button.callback(interaction)
        assert view.current_page == 1
        interaction.response.edit_message.assert_awaited_once()

        interaction2 = make_interaction(user=owner)
        await view.prev_button.callback(interaction2)
        assert view.current_page == 0

    @pytest.mark.asyncio
    async def test_close_button_clears_message_and_stops(self):
        owner = MagicMock()
        view = PaginatedListView(owner, ["Item A"], "Title")
        interaction = make_interaction(user=owner)

        await view.close_button.callback(interaction)

        interaction.response.edit_message.assert_awaited_once_with(content="List closed.", embed=None, view=None)
        assert view.is_finished()

    @pytest.mark.asyncio
    async def test_on_timeout_deletes_message(self):
        owner = MagicMock()
        view = PaginatedListView(owner, ["Item A"], "Title")
        view.message = MagicMock()
        view.message.delete = AsyncMock()

        await view.on_timeout()

        view.message.delete.assert_awaited_once()
        assert view.is_finished()


class TestOptionsView:
    @pytest.mark.asyncio
    async def test_list_button_loads_and_sorts_dict_keys(self):
        user = MagicMock()
        cog = MagicMock()
        loader = AsyncMock(return_value={"Zeta": {}, "Alpha": {}})
        view = OptionsView(user, loader, "monster", data_key=None, flatten_pulp=False, cog=cog, title="Monsters")
        interaction = make_interaction(user=user)

        await view.list_button.callback(interaction)

        interaction.response.edit_message.assert_awaited_once()
        _, kwargs = interaction.response.edit_message.call_args
        sub_view = kwargs["view"]
        assert isinstance(sub_view, PaginatedListView)
        assert sub_view.items == ["Alpha", "Zeta"]

    @pytest.mark.asyncio
    async def test_list_button_rejects_non_owner(self):
        user = MagicMock()
        loader = AsyncMock(return_value={})
        view = OptionsView(user, loader, "monster", None, False, MagicMock(), "Monsters")
        interaction = make_interaction(user=MagicMock())

        await view.list_button.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("This isn't for you!", ephemeral=True)
        loader.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_random_button_shows_entry(self):
        user = MagicMock()
        cog = MagicMock()
        cog._get_entry_data = MagicMock(return_value={"name": "Nyarlathotep"})
        cog._display_entry = AsyncMock()
        loader = AsyncMock(return_value={"Nyarlathotep": {}})
        view = OptionsView(user, loader, "deity", None, False, cog, "Deities")
        interaction = make_interaction(user=user)

        await view.random_button.callback(interaction)

        cog._display_entry.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_random_button_no_entries_edits_error(self):
        user = MagicMock()
        loader = AsyncMock(return_value={})
        view = OptionsView(user, loader, "deity", None, False, MagicMock(), "Deities")
        interaction = make_interaction(user=user)

        await view.random_button.callback(interaction)

        interaction.edit_original_response.assert_awaited_once_with(content="No entries found.", embed=None, view=None)

    @pytest.mark.asyncio
    async def test_cancel_button_dismisses_and_stops(self):
        user = MagicMock()
        view = OptionsView(user, AsyncMock(), "deity", None, False, MagicMock(), "Deities")
        interaction = make_interaction(user=user)

        await view.cancel_button.callback(interaction)

        interaction.response.edit_message.assert_awaited_once_with(content="Dismissed.", embed=None, view=None)
        assert view.is_finished()


class TestRenderView:
    def test_weapon_type_adds_inventory_button(self):
        view = RenderView(MagicMock(), MagicMock(), "Revolver", "weapon")
        assert any(getattr(c, "label", None) == "Add to Inventory" for c in view.children)

    def test_monster_type_adds_origin_button(self):
        view = RenderView(MagicMock(), MagicMock(), "Nyarlathotep", "monster")
        assert any(getattr(c, "label", None) == "📜 View Origin" for c in view.children)

    def test_occupation_type_has_no_extra_buttons(self):
        view = RenderView(MagicMock(), MagicMock(), "Detective", "occupation")
        labels = {getattr(c, "label", None) for c in view.children}
        assert "Add to Inventory" not in labels
        assert "📜 View Origin" not in labels

    @pytest.mark.asyncio
    async def test_poster_button_calls_cog_render_poster(self):
        user = MagicMock()
        cog = MagicMock()
        cog._render_poster = AsyncMock()
        view = RenderView(user, cog, "Nyarlathotep", "monster")
        interaction = make_interaction(user=user)

        await view.poster_button.callback(interaction)

        cog._render_poster.assert_awaited_once()
        assert cog._render_poster.call_args.args[2] == "Nyarlathotep"

    @pytest.mark.asyncio
    async def test_add_to_inventory_requires_guild(self):
        view = RenderView(MagicMock(), MagicMock(), "Revolver", "weapon")
        interaction = make_interaction()
        interaction.guild = None

        await view.add_to_inventory_button(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "only be performed in a server" in interaction.response.send_message.call_args.args[0]

    @pytest.mark.asyncio
    async def test_add_to_inventory_appends_item_to_backstory(self):
        view = RenderView(MagicMock(), MagicMock(), "Revolver", "weapon")
        interaction = make_interaction()
        interaction.guild = MagicMock(id=111)
        interaction.user.id = 222

        player_stats = {"111": {"222": {"NAME": "Jane"}}}
        with patch("commands._codex_views.load_player_stats", new=AsyncMock(return_value=player_stats)), \
             patch("commands._codex_views.save_player_stats", new=AsyncMock()) as mock_save:
            await view.add_to_inventory_button(interaction)

        assert "Revolver" in player_stats["111"]["222"]["Backstory"]["Gear and Possessions"]
        mock_save.assert_awaited_once_with(player_stats)
        interaction.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_to_inventory_requires_existing_investigator(self):
        view = RenderView(MagicMock(), MagicMock(), "Revolver", "weapon")
        interaction = make_interaction()
        interaction.guild = MagicMock(id=111)
        interaction.user.id = 999

        with patch("commands._codex_views.load_player_stats", new=AsyncMock(return_value={})):
            await view.add_to_inventory_button(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "don't have an investigator" in interaction.response.send_message.call_args.args[0]


class TestCodexView:
    @pytest.mark.asyncio
    async def test_check_owner_rejects_non_owner(self):
        owner = MagicMock()
        view = CodexView(owner, MagicMock())
        interaction = make_interaction(user=MagicMock())

        result = await view._check_owner(interaction)

        assert result is False
        interaction.response.send_message.assert_awaited_once_with("This menu isn't for you.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_monsters_button_launches_list_with_loaded_data(self):
        owner = MagicMock()
        cog = MagicMock()
        view = CodexView(owner, cog)
        interaction = make_interaction(user=owner)

        monsters_data = {"monsters": [{"monster_entry": {"name": "Shoggoth"}}]}
        with patch("commands._codex_views.load_monsters_data", new=AsyncMock(return_value=monsters_data)):
            await view.monsters_button.callback(interaction)

        interaction.response.edit_message.assert_awaited_once()
        interaction.edit_original_response.assert_awaited_once()
        _, kwargs = interaction.edit_original_response.call_args
        assert kwargs["view"].items == ["Shoggoth"]

    @pytest.mark.asyncio
    async def test_talents_button_flattens_pulp_talent_names(self):
        owner = MagicMock()
        cog = MagicMock()
        view = CodexView(owner, cog)
        interaction = make_interaction(user=owner)

        talents_data = {"mundane": ["**Fast Talker**: desc"]}
        with patch("commands._codex_views.load_pulp_talents_data", new=AsyncMock(return_value=talents_data)):
            await view.talents_button.callback(interaction)

        _, kwargs = interaction.edit_original_response.call_args
        assert kwargs["view"].items == ["Fast Talker"]

    @pytest.mark.asyncio
    async def test_launch_list_no_choices_shows_error_embed(self):
        owner = MagicMock()
        cog = MagicMock()
        view = CodexView(owner, cog)
        interaction = make_interaction(user=owner)

        with patch("commands._codex_views.load_monsters_data", new=AsyncMock(return_value={"monsters": []})):
            await view.monsters_button.callback(interaction)

        interaction.edit_original_response.assert_awaited_once()
        _, kwargs = interaction.edit_original_response.call_args
        assert kwargs["embed"].title == "No entries found"

    @pytest.mark.asyncio
    async def test_on_timeout_deletes_message(self):
        view = CodexView(MagicMock(), MagicMock())
        view.message = MagicMock()
        view.message.delete = AsyncMock()

        await view.on_timeout()

        view.message.delete.assert_awaited_once()


class TestSelectionView:
    def test_options_indexed_by_position_to_avoid_length_limit(self):
        options = ["Alpha", "Beta"]
        view = SelectionView(MagicMock(), options, "monster", AsyncMock(), MagicMock())
        select = view.children[0]
        assert [o.value for o in select.options] == ["0", "1"]

    @pytest.mark.asyncio
    async def test_select_callback_resolves_index_and_displays_entry(self):
        user = MagicMock()
        cog = MagicMock()
        cog._get_entry_data = MagicMock(return_value={"name": "Beta"})
        cog._display_entry = AsyncMock()
        loader = AsyncMock(return_value={"k": 1})
        view = SelectionView(user, ["Alpha", "Beta"], "monster", loader, cog)
        interaction = make_interaction(user=user)
        interaction.data = {"values": ["1"]}

        await view.select_callback(interaction)

        cog._display_entry.assert_awaited_once_with(interaction, "Beta", "monster", {"name": "Beta"}, ephemeral=True)
        assert all(c.disabled for c in view.children)

    @pytest.mark.asyncio
    async def test_select_callback_rejects_non_owner(self):
        owner = MagicMock()
        view = SelectionView(owner, ["Alpha"], "monster", AsyncMock(), MagicMock())
        interaction = make_interaction(user=MagicMock())
        interaction.data = {"values": ["0"]}

        await view.select_callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("This selection is not for you.", ephemeral=True)
