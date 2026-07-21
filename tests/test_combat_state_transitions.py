import pytest
from discord.ui import View
from unittest.mock import AsyncMock, MagicMock, patch

from commands.combat import CombatView


def make_view(**overrides):
    view = CombatView.__new__(CombatView)
    # View.__init__ must run so update_components()/clear_items()/add_item() have
    # the internal _children/_View__weights state discord.py's View class relies on
    # (only CombatView's own __init__ logic is skipped here, not discord.ui.View's).
    View.__init__(view, timeout=900)
    view.char_data = overrides.get("char_data", {
        "Backstory": {"Gear and Possessions": ["Shotgun [1/2]"]},
        "Rifle/Shotgun": 50,
    })
    view.weapon_db = overrides.get("weapon_db", {
        "Shotgun": {"capacity": "2", "damage": "4D6 (buckshot) or 2D6 (slug)", "malfunction": "96", "Skill": "Rifle/Shotgun"},
    })
    view.available_weapons = overrides.get("available_weapons", [
        {"key": "Shotgun", "display": "Shotgun [1/2]", "clean_name": "Shotgun",
         "ammo": 1, "cap": 2, "original": "Shotgun [1/2]", "is_jammed": False},
    ])
    view.weapon_states = overrides.get("weapon_states", {0: {"ammo": 1, "cap": 2, "jammed": False}})
    view.active_weapon_idx = overrides.get("active_weapon_idx", 0)
    view.player_stats = overrides.get("player_stats", {"1": {"2": view.char_data}})
    view.server_id = overrides.get("server_id", "1")
    view.user_id = overrides.get("user_id", "2")
    view.last_action = "Combat started."
    view.message = None
    return view


def make_interaction(response_done=False):
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.is_done = MagicMock(return_value=response_done)
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction


# --- _parse_damage_string ---

def test_parse_damage_string_splits_or_alternatives_with_labels():
    view = CombatView.__new__(CombatView)
    options = view._parse_damage_string("1D10+5 (slug) or 4D6 (buckshot)", "Shotgun")
    assert options == [
        {"label": "slug", "value": "1D10+5"},
        {"label": "buckshot", "value": "4D6"},
    ]


def test_parse_damage_string_no_label_uses_weapon_name():
    view = CombatView.__new__(CombatView)
    options = view._parse_damage_string("1D8", "Knife")
    assert options == [{"label": "Knife", "value": "1D8"}]


def test_parse_damage_string_unknown_returns_empty():
    view = CombatView.__new__(CombatView)
    assert view._parse_damage_string("Unknown", "Fists") == []
    assert view._parse_damage_string("", "Fists") == []


# --- shoot_callback: ammo depletion + malfunction (jam) transition ---

@pytest.mark.asyncio
async def test_shoot_callback_out_of_ammo_sends_ephemeral_message_and_does_not_roll():
    view = make_view(weapon_states={0: {"ammo": 0, "cap": 2, "jammed": False}})
    view.perform_roll = AsyncMock()
    interaction = make_interaction()

    await view.shoot_callback(interaction)

    interaction.response.send_message.assert_awaited_once_with("Click... (Out of Ammo!)", ephemeral=True)
    view.perform_roll.assert_not_awaited()


@pytest.mark.asyncio
async def test_shoot_callback_decrements_ammo_and_persists_inventory_string():
    view = make_view()
    view.perform_roll = AsyncMock()
    interaction = make_interaction()

    with patch("commands.combat.save_player_stats", new_callable=AsyncMock) as mock_save:
        await view.shoot_callback(interaction)

    assert view.weapon_states[0]["ammo"] == 0
    mock_save.assert_awaited_once()
    updated_str = view.char_data["Backstory"]["Gear and Possessions"][0]
    assert updated_str == "Shotgun [0/2]"
    view.perform_roll.assert_awaited_once()


@pytest.mark.asyncio
async def test_shoot_callback_malfunction_jams_weapon_via_on_complete_callback():
    view = make_view()
    view.perform_roll = AsyncMock()
    interaction = make_interaction()

    with patch("commands.combat.save_player_stats", new_callable=AsyncMock):
        await view.shoot_callback(interaction)

    on_complete = view.perform_roll.await_args.kwargs["on_complete"]
    assert view.weapon_states[0]["jammed"] is False

    with patch("commands.combat.save_player_stats", new_callable=AsyncMock):
        await on_complete(roll=97, tier=0, is_malf=True)

    assert view.weapon_states[0]["jammed"] is True
    assert "(JAMMED!)" in view.last_action


@pytest.mark.asyncio
async def test_shoot_callback_non_malfunction_does_not_jam_weapon():
    view = make_view()
    view.perform_roll = AsyncMock()
    interaction = make_interaction()

    with patch("commands.combat.save_player_stats", new_callable=AsyncMock):
        await view.shoot_callback(interaction)

    on_complete = view.perform_roll.await_args.kwargs["on_complete"]
    await on_complete(roll=40, tier=2, is_malf=False)

    assert view.weapon_states[0]["jammed"] is False


# --- reload_callback: refills ammo, clears jam, persists ---

@pytest.mark.asyncio
async def test_reload_callback_refills_ammo_and_clears_jam():
    view = make_view(
        weapon_states={0: {"ammo": 0, "cap": 2, "jammed": True}},
        available_weapons=[{"key": "Shotgun", "display": "🔴 Shotgun [0/2] (JAMMED)", "clean_name": "Shotgun",
                             "ammo": 0, "cap": 2, "original": "🔴 Shotgun [0/2] (JAMMED)", "is_jammed": True}],
        char_data={"Backstory": {"Gear and Possessions": ["🔴 Shotgun [0/2] (JAMMED)"]}, "Rifle/Shotgun": 50},
    )
    view.player_stats = {"1": {"2": view.char_data}}
    interaction = make_interaction(response_done=False)

    with patch("commands.combat.save_player_stats", new_callable=AsyncMock) as mock_save:
        await view.reload_callback(interaction)

    assert view.weapon_states[0]["ammo"] == 2
    assert view.weapon_states[0]["jammed"] is False
    mock_save.assert_awaited_once()
    assert view.char_data["Backstory"]["Gear and Possessions"][0] == "Shotgun [2/2]"
    interaction.response.edit_message.assert_awaited_once()


# --- fix_jam_callback: malfunction-roll boundary for clearing a jam ---

@pytest.mark.asyncio
async def test_fix_jam_callback_regular_success_or_better_clears_jam():
    view = make_view(weapon_states={0: {"ammo": 1, "cap": 2, "jammed": True}})
    view.perform_roll = AsyncMock()
    interaction = make_interaction()

    with patch("commands.combat.save_player_stats", new_callable=AsyncMock):
        await view.fix_jam_callback(interaction)

    on_complete = view.perform_roll.await_args.kwargs["on_complete"]

    with patch("commands.combat.save_player_stats", new_callable=AsyncMock):
        await on_complete(roll=40, tier=2, is_malf=False)  # tier 2 == Regular Success

    assert view.weapon_states[0]["jammed"] is False
    assert "Cleared jam" in view.last_action


@pytest.mark.asyncio
async def test_fix_jam_callback_failure_leaves_weapon_jammed():
    view = make_view(weapon_states={0: {"ammo": 1, "cap": 2, "jammed": True}})
    view.perform_roll = AsyncMock()
    interaction = make_interaction()

    await view.fix_jam_callback(interaction)
    on_complete = view.perform_roll.await_args.kwargs["on_complete"]

    await on_complete(roll=90, tier=1, is_malf=False)  # tier 1 == Fail

    assert view.weapon_states[0]["jammed"] is True
    assert "Failed to clear jam" in view.last_action
