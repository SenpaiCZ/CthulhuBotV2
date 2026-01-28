import json
import aiofiles
import os

DATA_FOLDER = "data"
INFODATA_FOLDER = "infodata"
GAMEDATA_FOLDER = "gamedata"

async def _load_json_file(folder, filename):
    """Helper function to asynchronously load JSON data from a file."""
    file_path = os.path.join(folder, filename)
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
            data = await file.read()
            return json.loads(data)
    except FileNotFoundError:
        return {}

async def _save_json_file(folder, filename, data, ensure_ascii=True):
    """Helper function to asynchronously save JSON data to a file."""
    if not os.path.exists(folder):
        os.makedirs(folder)
    file_path = os.path.join(folder, filename)
    async with aiofiles.open(file_path, 'w', encoding='utf-8') as file:
        await file.write(json.dumps(data, indent=4, ensure_ascii=ensure_ascii))

# --- Player Stats ---
async def load_player_stats():
    return await _load_json_file(DATA_FOLDER, 'player_stats.json')

async def save_player_stats(player_stats):
    await _save_json_file(DATA_FOLDER, 'player_stats.json', player_stats)

# --- Settings ---
def load_settings():
    """Synchronous load for settings with priority: ENV > settings.json > config.json"""
    settings = {}

    # 1. Load config.json (Defaults)
    config_path = 'config.json'
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                settings.update(json.load(file))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    # 2. Load settings.json (Local overrides)
    file_path = os.path.join(DATA_FOLDER, 'settings.json')
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                settings.update(json.load(file))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    # 3. Environment Variables
    if os.getenv("DISCORD_TOKEN"):
        settings["token"] = os.getenv("DISCORD_TOKEN")
    if os.getenv("YOUTUBE_API_KEY"):
        settings["youtubetoken"] = os.getenv("YOUTUBE_API_KEY")

    return settings

async def save_settings(settings_data):
    """Asynchronously save settings to settings.json (overrides config.json)"""
    await _save_json_file(DATA_FOLDER, 'settings.json', settings_data)

# --- Server Stats ---
async def load_server_stats():
    return await _load_json_file(DATA_FOLDER, 'server_stats.json')

async def save_server_stats(server_stats):
    await _save_json_file(DATA_FOLDER, 'server_stats.json', server_stats)

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

# --- YouTube Feed ---
async def youtube_load():
    return await _load_json_file(DATA_FOLDER, 'youtube_feed.json')

async def youtube_save(youtube_feed):
    await _save_json_file(DATA_FOLDER, 'youtube_feed.json', youtube_feed)

# --- Session Data ---
async def load_session_data():
    return await _load_json_file(DATA_FOLDER, 'session_data.json')

async def save_session_data(session_data):
    await _save_json_file(DATA_FOLDER, 'session_data.json', session_data)

# --- Info Data (Read-only mostly) ---
async def load_madness_group_data():
    return await _load_json_file(INFODATA_FOLDER, 'madness_with_group.json')

async def load_madness_solo_data():
    return await _load_json_file(INFODATA_FOLDER, 'madness_alone.json')

async def load_madness_insane_talent_data():
    return await _load_json_file(INFODATA_FOLDER, 'insane_talents.json')

async def load_phobias_data():
    return await _load_json_file(INFODATA_FOLDER, 'phobias.json')

async def load_manias_data():
    return await _load_json_file(INFODATA_FOLDER, 'manias.json')

async def load_names_male_data():
    return await _load_json_file(INFODATA_FOLDER, 'names_male.json')

async def load_names_female_data():
    return await _load_json_file(INFODATA_FOLDER, 'names_female.json')

async def load_names_last_data():
    return await _load_json_file(INFODATA_FOLDER, 'names_last.json')

async def load_archetype_data():
    return await _load_json_file(INFODATA_FOLDER, 'archetype_info.json')

async def load_firearms_data():
    return await _load_json_file(INFODATA_FOLDER, 'firearms_info.json')

async def load_inventions_data():
    return await _load_json_file(INFODATA_FOLDER, 'inventions_info.json')

async def load_occupations_data():
    return await _load_json_file(INFODATA_FOLDER, 'occupations_info.json')

async def load_skills_data():
    return await _load_json_file(INFODATA_FOLDER, 'skills_info.json')

async def load_years_data():
    return await _load_json_file(INFODATA_FOLDER, 'years_info.json')

async def load_poisons_data():
    return await _load_json_file(INFODATA_FOLDER, 'poisions_info.json')

async def load_macguffin_data():
    return await _load_json_file(INFODATA_FOLDER, 'macguffin_info.json')

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
