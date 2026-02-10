import json
import aiofiles
import os
import shutil

DATA_FOLDER = "data"
INFODATA_FOLDER = "infodata"
GAMEDATA_FOLDER = "gamedata"

_INFODATA_CACHE = {}

async def _load_json_file(folder, filename):
    """Helper function to asynchronously load JSON data from a file."""
    file_path = os.path.join(folder, filename)
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
            data = await file.read()
            return json.loads(data)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {file_path}: {e}")
        # Backup corrupted file
        try:
            shutil.copy2(file_path, file_path + ".bak")
            print(f"Backed up corrupted file to {file_path}.bak")
        except Exception as backup_error:
            print(f"Failed to backup corrupted file: {backup_error}")
        return {}

async def _load_infodata_cached(filename):
    """Helper function to load infodata from cache or disk."""
    if filename not in _INFODATA_CACHE:
        _INFODATA_CACHE[filename] = await _load_json_file(INFODATA_FOLDER, filename)
    return _INFODATA_CACHE[filename]

async def _save_json_file(folder, filename, data, ensure_ascii=True):
    """Helper function to asynchronously save JSON data to a file."""
    if not os.path.exists(folder):
        os.makedirs(folder)
    file_path = os.path.join(folder, filename)
    async with aiofiles.open(file_path, 'w', encoding='utf-8') as file:
        await file.write(json.dumps(data, indent=4, ensure_ascii=ensure_ascii))

    # Update cache if applicable
    if folder == INFODATA_FOLDER:
        _INFODATA_CACHE[filename] = data

# --- Player Stats ---
async def load_player_stats():
    return await _load_json_file(DATA_FOLDER, 'player_stats.json')

async def save_player_stats(player_stats):
    await _save_json_file(DATA_FOLDER, 'player_stats.json', player_stats)

# --- Settings ---
def load_settings():
    """Synchronous load for settings with priority: ENV > config.json"""
    settings = {}

    # 1. Load config.json (Defaults)
    config_path = 'config.json'
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                settings.update(json.load(file))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    # 2. Environment Variables
    if os.getenv("DISCORD_TOKEN"):
        settings["token"] = os.getenv("DISCORD_TOKEN")

    return settings

async def save_settings(settings_data):
    """Asynchronously save settings to config.json"""
    await _save_json_file('.', 'config.json', settings_data)

# --- Bot Status ---
async def load_bot_status():
    data = await _load_json_file(DATA_FOLDER, 'bot_status.json')
    if not data:
        return {"type": "playing", "text": "Call of Cthulhu"}
    return data

async def save_bot_status(data):
    await _save_json_file(DATA_FOLDER, 'bot_status.json', data)

# --- Server Stats ---
_SERVER_STATS_CACHE = None

async def load_server_stats():
    global _SERVER_STATS_CACHE
    if _SERVER_STATS_CACHE is None:
        _SERVER_STATS_CACHE = await _load_json_file(DATA_FOLDER, 'server_stats.json')
    return _SERVER_STATS_CACHE.copy()

async def save_server_stats(server_stats):
    global _SERVER_STATS_CACHE
    await _save_json_file(DATA_FOLDER, 'server_stats.json', server_stats)
    _SERVER_STATS_CACHE = server_stats.copy()

# --- Server Volumes ---
async def load_server_volumes():
    return await _load_json_file(DATA_FOLDER, 'server_volumes.json')

async def save_server_volumes(volumes):
    await _save_json_file(DATA_FOLDER, 'server_volumes.json', volumes)

# --- Smart React ---
async def smartreact_load():
    return await _load_json_file(DATA_FOLDER, 'smart_react.json')

async def smartreact_save(smart_react):
    await _save_json_file(DATA_FOLDER, 'smart_react.json', smart_react, ensure_ascii=False)

# --- Auto Room ---
async def autoroom_load():
    return await _load_json_file(DATA_FOLDER, 'autorooms.json')

async def autoroom_save(autorooms):
    await _save_json_file(DATA_FOLDER, 'autorooms.json', autorooms)

# --- Session Data ---
async def load_session_data():
    return await _load_json_file(DATA_FOLDER, 'session_data.json')

async def save_session_data(session_data):
    await _save_json_file(DATA_FOLDER, 'session_data.json', session_data)

# --- Info Data (Read-only mostly) ---
async def load_monsters_data():
    return await _load_infodata_cached('monsters.json')

async def load_spells_data():
    return await _load_infodata_cached('spells.json')

async def load_deities_data():
    return await _load_infodata_cached('deities.json')

async def load_madness_group_data():
    return await _load_infodata_cached('madness_with_group.json')

async def load_madness_solo_data():
    return await _load_infodata_cached('madness_alone.json')

async def load_madness_insane_talent_data():
    return await _load_infodata_cached('insane_talents.json')

async def load_pulp_talents_data():
    return await _load_infodata_cached('pulp_talents.json')

async def load_phobias_data():
    return await _load_infodata_cached('phobias.json')

async def load_manias_data():
    return await _load_infodata_cached('manias.json')

async def load_names_male_data():
    return await _load_infodata_cached('names_male.json')

async def load_names_female_data():
    return await _load_infodata_cached('names_female.json')

async def load_names_last_data():
    return await _load_infodata_cached('names_last.json')

async def load_archetype_data():
    return await _load_infodata_cached('archetype_info.json')

async def load_weapons_data():
    return await _load_infodata_cached('weapons.json')

async def load_inventions_data():
    return await _load_infodata_cached('inventions_info.json')

async def load_occupations_data():
    return await _load_infodata_cached('occupations_info.json')

async def load_skills_data():
    return await _load_infodata_cached('skills_info.json')

async def load_years_data():
    return await _load_infodata_cached('years_info.json')

async def load_poisons_data():
    return await _load_infodata_cached('poisions_info.json')

async def load_macguffin_data():
    return await _load_infodata_cached('macguffin_info.json')

# --- Luck Stats ---
async def load_luck_stats():
    return await _load_json_file(DATA_FOLDER, 'luck_stats.json')

async def save_luck_stats(server_stats):
    await _save_json_file(DATA_FOLDER, 'luck_stats.json', server_stats)

# --- Chase Data ---
async def load_chase_data():
    return await _load_json_file(DATA_FOLDER, 'chase_data.json')

async def save_chase_data(session_data):
    await _save_json_file(DATA_FOLDER, 'chase_data.json', session_data)

# --- Deleter Data ---
async def load_deleter_data():
    return await _load_json_file(DATA_FOLDER, 'deleter_data.json')

async def save_deleter_data(session_data):
    await _save_json_file(DATA_FOLDER, 'deleter_data.json', session_data)

# --- RSS Data ---
async def load_rss_data():
    return await _load_json_file(DATA_FOLDER, 'rss_data.json')

async def save_rss_data(session_data):
    await _save_json_file(DATA_FOLDER, 'rss_data.json', session_data)

# --- Soundboard Settings ---
async def load_soundboard_settings():
    return await _load_json_file(DATA_FOLDER, 'soundboard_settings.json')

async def save_soundboard_settings(settings_data):
    await _save_json_file(DATA_FOLDER, 'soundboard_settings.json', settings_data)

# --- Music Blacklist ---
async def load_music_blacklist():
    return await _load_json_file(DATA_FOLDER, 'music_blacklist.json')

async def save_music_blacklist(blacklist):
    await _save_json_file(DATA_FOLDER, 'music_blacklist.json', blacklist)

# --- Reminder Data ---
async def load_reminder_data():
    return await _load_json_file(DATA_FOLDER, 'reminder_data.json')

async def save_reminder_data(session_data):
    await _save_json_file(DATA_FOLDER, 'reminder_data.json', session_data)

# --- Game Data ---
async def game_load_player_data():
    return await _load_json_file(GAMEDATA_FOLDER, 'player_data.json')

async def game_save_player_data(session_data):
    await _save_json_file(GAMEDATA_FOLDER, 'player_data.json', session_data)

async def game_load_questions_data():
    return await _load_json_file(GAMEDATA_FOLDER, 'questions_data.json')

async def game_save_questions_data(session_data):
    await _save_json_file(GAMEDATA_FOLDER, 'questions_data.json', session_data)

# --- Retired Characters ---
async def load_retired_characters_data():
    return await _load_json_file(DATA_FOLDER, 'retired_characters_data.json')

async def save_retired_characters_data(session_data):
    await _save_json_file(DATA_FOLDER, 'retired_characters_data.json', session_data)

# --- Gamemode Stats ---
async def load_gamemode_stats():
    return await _load_json_file(DATA_FOLDER, 'gamemode.json')

async def save_gamemode_stats(server_stats):
    await _save_json_file(DATA_FOLDER, 'gamemode.json', server_stats)

# --- Karma System ---
async def load_karma_settings():
    return await _load_json_file(DATA_FOLDER, 'karma_settings.json')

async def save_karma_settings(settings):
    await _save_json_file(DATA_FOLDER, 'karma_settings.json', settings)

async def load_karma_stats():
    return await _load_json_file(DATA_FOLDER, 'karma_stats.json')

async def save_karma_stats(stats):
    await _save_json_file(DATA_FOLDER, 'karma_stats.json', stats)

# --- Reaction Roles ---
async def load_reaction_roles():
    return await _load_json_file(DATA_FOLDER, 'reaction_roles.json')

async def save_reaction_roles(roles_data):
    await _save_json_file(DATA_FOLDER, 'reaction_roles.json', roles_data)

# --- Pokemon GO Data ---
async def load_pogo_settings():
    return await _load_json_file(DATA_FOLDER, 'pogo_settings.json')

async def save_pogo_settings(settings):
    await _save_json_file(DATA_FOLDER, 'pogo_settings.json', settings)

async def load_pogo_events():
    return await _load_json_file(DATA_FOLDER, 'pogo_events.json')

async def save_pogo_events(events):
    await _save_json_file(DATA_FOLDER, 'pogo_events.json', events)

# --- Giveaway Data ---
async def load_giveaway_data():
    return await _load_json_file(DATA_FOLDER, 'giveaway_data.json')

async def save_giveaway_data(data):
    await _save_json_file(DATA_FOLDER, 'giveaway_data.json', data)

# --- Gamer Roles Data ---
async def load_gamerole_settings():
    return await _load_json_file(DATA_FOLDER, 'gamerole_settings.json')

async def save_gamerole_settings(data):
    await _save_json_file(DATA_FOLDER, 'gamerole_settings.json', data)
