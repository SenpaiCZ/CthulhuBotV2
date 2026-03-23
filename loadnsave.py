import json
import aiofiles
import os
import shutil
import logging

logger = logging.getLogger("loadnsave")

USE_DATABASE = True

DATA_FOLDER = "data"
INFODATA_FOLDER = "infodata"
GAMEDATA_FOLDER = "gamedata"

_INFODATA_CACHE = {}

def _get_db():
    from models.database import SessionLocal
    return SessionLocal()

async def _db_get_setting(guild_id: str, key: str, default=None):
    from services.settings_service import SettingsService
    db = _get_db()
    try:
        val = SettingsService.get_setting(db, guild_id, key)
        return val if val is not None else default
    finally:
        db.close()

async def _db_save_setting(guild_id: str, key: str, value):
    from services.settings_service import SettingsService
    from schemas.settings import SettingUpdate
    db = _get_db()
    try:
        SettingsService.set_setting(db, guild_id, key, value)
    finally:
        db.close()

async def _db_get_all_guild_settings(key: str):
    from services.settings_service import SettingsService
    db = _get_db()
    try:
        return SettingsService.get_all_guild_settings(db, key)
    finally:
        db.close()

async def _db_save_all_guild_settings(key: str, settings_dict: dict):
    from services.settings_service import SettingsService
    db = _get_db()
    try:
        for guild_id, value in settings_dict.items():
            SettingsService.set_setting(db, str(guild_id), key, value)
    finally:
        db.close()

def _to_legacy_format(inv):
    """Converts an Investigator model to the legacy dictionary format."""
    data = {
        "NAME": inv.name,
        "STR": inv.str,
        "CON": inv.con,
        "SIZ": inv.siz,
        "DEX": inv.dex,
        "APP": inv.app,
        "INT": inv.int,
        "POW": inv.pow,
        "EDU": inv.edu,
        "LUCK": inv.luck,
        "Occupation": inv.occupation,
        "is_retired": inv.is_retired
    }
    # Add skills
    if inv.skills:
        data.update(inv.skills)
    # Add extra data
    if inv.extra_data:
        data.update(inv.extra_data)
    return data

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
        logger.error(f"Error decoding JSON from {file_path}: {e}")
        # Backup corrupted file
        try:
            shutil.copy2(file_path, file_path + ".bak")
            logger.warning(f"Backed up corrupted file to {file_path}.bak")
        except Exception as backup_error:
            logger.error(f"Failed to backup corrupted file: {backup_error}")
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
_PLAYER_STATS_CACHE = None

async def load_player_stats():
    global _PLAYER_STATS_CACHE
    if _PLAYER_STATS_CACHE is not None:
        return _PLAYER_STATS_CACHE

    if USE_DATABASE:
        try:
            from models.database import SessionLocal
            from services.character_service import CharacterService
            db = SessionLocal()
            try:
                investigators = CharacterService.get_all_investigators(db)
                stats = {}
                for inv in investigators:
                    guild_id = inv.guild_id
                    user_id = inv.discord_user_id
                    if guild_id not in stats:
                        stats[guild_id] = {}
                    stats[guild_id][user_id] = _to_legacy_format(inv)
                _PLAYER_STATS_CACHE = stats
                return _PLAYER_STATS_CACHE
            finally:
                db.close()
        except ImportError:
            logger.warning("Database models or services not found, falling back to JSON.")

    _PLAYER_STATS_CACHE = await _load_json_file(DATA_FOLDER, 'player_stats.json')
    return _PLAYER_STATS_CACHE

async def save_player_stats(player_stats):
    global _PLAYER_STATS_CACHE
    _PLAYER_STATS_CACHE = player_stats

    if USE_DATABASE:
        try:
            from models.database import SessionLocal
            from services.character_service import CharacterService
            from schemas.investigator import InvestigatorCreate
            db = SessionLocal()
            try:
                for guild_id, users in player_stats.items():
                    for user_id, char_data in users.items():
                        inv = CharacterService.get_investigator_by_guild_and_user(db, str(guild_id), str(user_id))
                        
                        # Prepare update data
                        standard_fields = ["NAME", "STR", "CON", "SIZ", "DEX", "APP", "INT", "POW", "EDU", "LUCK", "Occupation", "is_retired"]
                        skills = {}
                        extra_data = {}
                        for k, v in char_data.items():
                            if k in standard_fields: continue
                            if isinstance(v, int): skills[k] = v
                            else: extra_data[k] = v

                        update_map = {
                            "name": char_data.get("NAME"),
                            "str": char_data.get("STR"),
                            "con": char_data.get("CON"),
                            "siz": char_data.get("SIZ"),
                            "dex": char_data.get("DEX"),
                            "app": char_data.get("APP"),
                            "int": char_data.get("INT"),
                            "pow": char_data.get("POW"),
                            "edu": char_data.get("EDU"),
                            "luck": char_data.get("LUCK"),
                            "occupation": char_data.get("Occupation"),
                            "skills": skills,
                            "extra_data": extra_data,
                            "is_retired": char_data.get("is_retired", False)
                        }

                        if inv:
                            CharacterService.update_investigator(db, inv.id, update_map)
                        else:
                            # Create new
                            new_inv_data = InvestigatorCreate(
                                guild_id=str(guild_id),
                                discord_user_id=str(user_id),
                                name=char_data.get("NAME", "Unknown"),
                                occupation=char_data.get("Occupation"),
                                str=char_data.get("STR", 50),
                                con=char_data.get("CON", 50),
                                siz=char_data.get("SIZ", 50),
                                dex=char_data.get("DEX", 50),
                                app=char_data.get("APP", 50),
                                int=char_data.get("INT", 50),
                                pow=char_data.get("POW", 50),
                                edu=char_data.get("EDU", 50),
                                luck=char_data.get("LUCK", 50),
                                skills=skills,
                                extra_data=extra_data,
                                is_retired=char_data.get("is_retired", False)
                            )
                            CharacterService.create_investigator(db, new_inv_data)
                return # Successfully saved to DB
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to save player stats to database: {e}")

    await _save_json_file(DATA_FOLDER, 'player_stats.json', player_stats)


# --- Settings ---
_SETTINGS_CACHE = None

def load_settings():
    """Synchronous load for settings with priority: ENV > config.json"""
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is not None:
        return _SETTINGS_CACHE.copy()

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

    if USE_DATABASE:
        try:
            from models.database import SessionLocal
            from services.settings_service import SettingsService
            db = SessionLocal()
            try:
                db_settings = SettingsService.get_all_settings(db, "global")
                if db_settings:
                    settings.update(db_settings)
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to load global settings from database: {e}")

    _SETTINGS_CACHE = settings
    return settings.copy()

async def load_settings_async():
    """Asynchronous load for settings with priority: ENV > config.json"""
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is not None:
        return _SETTINGS_CACHE.copy()

    settings = await _load_json_file('.', 'config.json')

    # 2. Environment Variables
    if os.getenv("DISCORD_TOKEN"):
        settings["token"] = os.getenv("DISCORD_TOKEN")

    if USE_DATABASE:
        db_settings = await _db_get_setting("global", "all_settings")
        # SettingsService.get_setting(db, "global", "all_settings") might not be what we want if we want individual keys
        # Actually, SettingsService.get_all_settings(db, "global") is better.
        # Let's adjust _db_get_all_settings helper.
        try:
            from models.database import SessionLocal
            from services.settings_service import SettingsService
            db = SessionLocal()
            try:
                db_settings = SettingsService.get_all_settings(db, "global")
                if db_settings:
                    settings.update(db_settings)
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to load global settings from database: {e}")

    _SETTINGS_CACHE = settings
    return settings.copy()

async def save_settings(settings_data):
    """Asynchronously save settings to config.json and database"""
    global _SETTINGS_CACHE
    _SETTINGS_CACHE = settings_data.copy()

    if USE_DATABASE:
        try:
            from models.database import SessionLocal
            from services.settings_service import SettingsService
            db = SessionLocal()
            try:
                # Save individual keys to "global" guild
                for k, v in settings_data.items():
                    SettingsService.set_setting(db, "global", k, v)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to save global settings to database: {e}")

    await _save_json_file('.', 'config.json', settings_data)

# --- Bot Status ---
_BOT_STATUS_CACHE = None

async def load_bot_status():
    global _BOT_STATUS_CACHE
    if _BOT_STATUS_CACHE is not None:
        return _BOT_STATUS_CACHE.copy()

    if USE_DATABASE:
        db_status = await _db_get_setting("global", "bot_status")
        if db_status:
            _BOT_STATUS_CACHE = db_status
            return _BOT_STATUS_CACHE.copy()

    data = await _load_json_file(DATA_FOLDER, 'bot_status.json')
    if not data:
        data = {"type": "playing", "text": "Call of Cthulhu"}
    _BOT_STATUS_CACHE = data
    return data.copy()

async def save_bot_status(data):
    global _BOT_STATUS_CACHE
    _BOT_STATUS_CACHE = data.copy()

    if USE_DATABASE:
        await _db_save_setting("global", "bot_status", data)

    await _save_json_file(DATA_FOLDER, 'bot_status.json', data)

# --- Server Stats ---
_SERVER_STATS_CACHE = None

async def load_server_stats():
    global _SERVER_STATS_CACHE
    if _SERVER_STATS_CACHE is not None:
        return _SERVER_STATS_CACHE

    if USE_DATABASE:
        all_prefixes = await _db_get_all_guild_settings("prefix")
        if all_prefixes:
            _SERVER_STATS_CACHE = all_prefixes
            return _SERVER_STATS_CACHE

    _SERVER_STATS_CACHE = await _load_json_file(DATA_FOLDER, 'server_stats.json')
    return _SERVER_STATS_CACHE

async def save_server_stats(server_stats):
    global _SERVER_STATS_CACHE
    _SERVER_STATS_CACHE = server_stats.copy()

    if USE_DATABASE:
        await _db_save_all_guild_settings("prefix", server_stats)

    await _save_json_file(DATA_FOLDER, 'server_stats.json', server_stats)


# --- Server Volumes ---
_SERVER_VOLUMES_CACHE = None

async def load_server_volumes():
    global _SERVER_VOLUMES_CACHE
    if _SERVER_VOLUMES_CACHE is not None:
        return _SERVER_VOLUMES_CACHE.copy()

    if USE_DATABASE:
        all_volumes = await _db_get_all_guild_settings("volumes")
        if all_volumes:
            _SERVER_VOLUMES_CACHE = all_volumes
            return _SERVER_VOLUMES_CACHE.copy()

    _SERVER_VOLUMES_CACHE = await _load_json_file(DATA_FOLDER, 'server_volumes.json')
    return _SERVER_VOLUMES_CACHE.copy()

async def save_server_volumes(volumes):
    global _SERVER_VOLUMES_CACHE
    _SERVER_VOLUMES_CACHE = volumes.copy()

    if USE_DATABASE:
        await _db_save_all_guild_settings("volumes", volumes)

    await _save_json_file(DATA_FOLDER, 'server_volumes.json', volumes)

# --- Smart React ---
_SMART_REACT_CACHE = None

async def smartreact_load():
    global _SMART_REACT_CACHE
    if _SMART_REACT_CACHE is not None:
        return _SMART_REACT_CACHE.copy()

    if USE_DATABASE:
        all_smartreact = await _db_get_all_guild_settings("smart_react")
        if all_smartreact:
            _SMART_REACT_CACHE = all_smartreact
            return _SMART_REACT_CACHE.copy()

    _SMART_REACT_CACHE = await _load_json_file(DATA_FOLDER, 'smart_react.json')
    return _SMART_REACT_CACHE.copy()

async def smartreact_save(smart_react):
    global _SMART_REACT_CACHE
    _SMART_REACT_CACHE = smart_react.copy()

    if USE_DATABASE:
        await _db_save_all_guild_settings("smart_react", smart_react)

    await _save_json_file(DATA_FOLDER, 'smart_react.json', smart_react, ensure_ascii=False)

# --- Auto Room ---
_AUTOROOM_CACHE = None

async def autoroom_load():
    global _AUTOROOM_CACHE
    if _AUTOROOM_CACHE is not None:
        return _AUTOROOM_CACHE.copy()

    if USE_DATABASE:
        all_autorooms = await _db_get_all_guild_settings("autorooms")
        if all_autorooms:
            _AUTOROOM_CACHE = all_autorooms
            return _AUTOROOM_CACHE.copy()

    _AUTOROOM_CACHE = await _load_json_file(DATA_FOLDER, 'autorooms.json')
    return _AUTOROOM_CACHE.copy()

async def autoroom_save(autorooms):
    global _AUTOROOM_CACHE
    _AUTOROOM_CACHE = autorooms.copy()

    if USE_DATABASE:
        await _db_save_all_guild_settings("autorooms", autorooms)

    await _save_json_file(DATA_FOLDER, 'autorooms.json', autorooms)

# --- Session Data ---
_SESSION_DATA_CACHE = None

async def load_session_data():
    global _SESSION_DATA_CACHE
    if _SESSION_DATA_CACHE is None:
        _SESSION_DATA_CACHE = await _load_json_file(DATA_FOLDER, 'session_data.json')
    return _SESSION_DATA_CACHE

async def save_session_data(session_data):
    global _SESSION_DATA_CACHE
    _SESSION_DATA_CACHE = session_data
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

async def load_names_data():
    return await _load_infodata_cached('names.json')

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
_LUCK_STATS_CACHE = None

async def load_luck_stats():
    global _LUCK_STATS_CACHE
    if _LUCK_STATS_CACHE is not None:
        return _LUCK_STATS_CACHE.copy()

    if USE_DATABASE:
        all_luck = await _db_get_all_guild_settings("luck_threshold")
        if all_luck:
            _LUCK_STATS_CACHE = all_luck
            return _LUCK_STATS_CACHE.copy()

    _LUCK_STATS_CACHE = await _load_json_file(DATA_FOLDER, 'luck_stats.json')
    return _LUCK_STATS_CACHE.copy()

async def save_luck_stats(server_stats):
    global _LUCK_STATS_CACHE
    _LUCK_STATS_CACHE = server_stats.copy()

    if USE_DATABASE:
        await _db_save_all_guild_settings("luck_threshold", server_stats)

    await _save_json_file(DATA_FOLDER, 'luck_stats.json', server_stats)

# --- Skill Settings ---
_SKILL_SETTINGS_CACHE = None

async def load_skill_settings():
    global _SKILL_SETTINGS_CACHE
    if _SKILL_SETTINGS_CACHE is not None:
        return _SKILL_SETTINGS_CACHE.copy()

    if USE_DATABASE:
        all_skills = await _db_get_all_guild_settings("skill_settings")
        if all_skills:
            _SKILL_SETTINGS_CACHE = all_skills
            return _SKILL_SETTINGS_CACHE.copy()

    _SKILL_SETTINGS_CACHE = await _load_json_file(DATA_FOLDER, 'skill_settings.json')
    return _SKILL_SETTINGS_CACHE.copy()

async def save_skill_settings(settings):
    global _SKILL_SETTINGS_CACHE
    _SKILL_SETTINGS_CACHE = settings.copy()

    if USE_DATABASE:
        await _db_save_all_guild_settings("skill_settings", settings)

    await _save_json_file(DATA_FOLDER, 'skill_settings.json', settings)

# --- Chase Data ---
_CHASE_DATA_CACHE = None

async def load_chase_data():
    global _CHASE_DATA_CACHE
    if _CHASE_DATA_CACHE is None:
        _CHASE_DATA_CACHE = await _load_json_file(DATA_FOLDER, 'chase_data.json')
    return _CHASE_DATA_CACHE.copy()

async def save_chase_data(session_data):
    global _CHASE_DATA_CACHE
    _CHASE_DATA_CACHE = session_data.copy()
    await _save_json_file(DATA_FOLDER, 'chase_data.json', session_data)

# --- Deleter Data ---
_DELETER_DATA_CACHE = None

async def load_deleter_data():
    global _DELETER_DATA_CACHE
    if _DELETER_DATA_CACHE is None:
        _DELETER_DATA_CACHE = await _load_json_file(DATA_FOLDER, 'deleter_data.json')
    return _DELETER_DATA_CACHE.copy()

async def save_deleter_data(session_data):
    global _DELETER_DATA_CACHE
    _DELETER_DATA_CACHE = session_data.copy()
    await _save_json_file(DATA_FOLDER, 'deleter_data.json', session_data)

# --- RSS Data ---
_RSS_DATA_CACHE = None

async def load_rss_data():
    global _RSS_DATA_CACHE
    if _RSS_DATA_CACHE is None:
        _RSS_DATA_CACHE = await _load_json_file(DATA_FOLDER, 'rss_data.json')
    return _RSS_DATA_CACHE

async def save_rss_data(session_data):
    global _RSS_DATA_CACHE
    _RSS_DATA_CACHE = session_data
    await _save_json_file(DATA_FOLDER, 'rss_data.json', session_data)

# --- Soundboard Settings ---
_SOUNDBOARD_SETTINGS_CACHE = None

async def load_soundboard_settings():
    global _SOUNDBOARD_SETTINGS_CACHE
    if _SOUNDBOARD_SETTINGS_CACHE is None:
        _SOUNDBOARD_SETTINGS_CACHE = await _load_json_file(DATA_FOLDER, 'soundboard_settings.json')
    return _SOUNDBOARD_SETTINGS_CACHE.copy()

async def save_soundboard_settings(settings_data):
    global _SOUNDBOARD_SETTINGS_CACHE
    _SOUNDBOARD_SETTINGS_CACHE = settings_data.copy()
    await _save_json_file(DATA_FOLDER, 'soundboard_settings.json', settings_data)

# --- Music Blacklist ---
_MUSIC_BLACKLIST_CACHE = None

async def load_music_blacklist():
    global _MUSIC_BLACKLIST_CACHE
    if _MUSIC_BLACKLIST_CACHE is None:
        _MUSIC_BLACKLIST_CACHE = await _load_json_file(DATA_FOLDER, 'music_blacklist.json')
    # List
    if isinstance(_MUSIC_BLACKLIST_CACHE, list):
        return _MUSIC_BLACKLIST_CACHE.copy()
    return _MUSIC_BLACKLIST_CACHE

async def save_music_blacklist(blacklist):
    global _MUSIC_BLACKLIST_CACHE
    if isinstance(blacklist, list):
        _MUSIC_BLACKLIST_CACHE = blacklist.copy()
    else:
        _MUSIC_BLACKLIST_CACHE = blacklist
    await _save_json_file(DATA_FOLDER, 'music_blacklist.json', blacklist)

# --- Reminder Data ---
_REMINDER_DATA_CACHE = None

async def load_reminder_data():
    global _REMINDER_DATA_CACHE
    if _REMINDER_DATA_CACHE is None:
        _REMINDER_DATA_CACHE = await _load_json_file(DATA_FOLDER, 'reminder_data.json')
    return _REMINDER_DATA_CACHE.copy()

async def save_reminder_data(session_data):
    global _REMINDER_DATA_CACHE
    _REMINDER_DATA_CACHE = session_data.copy()
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
_RETIRED_CHARACTERS_CACHE = None

async def load_retired_characters_data():
    global _RETIRED_CHARACTERS_CACHE
    if _RETIRED_CHARACTERS_CACHE is None:
        _RETIRED_CHARACTERS_CACHE = await _load_json_file(DATA_FOLDER, 'retired_characters_data.json')
    return _RETIRED_CHARACTERS_CACHE

async def save_retired_characters_data(session_data):
    global _RETIRED_CHARACTERS_CACHE
    _RETIRED_CHARACTERS_CACHE = session_data
    await _save_json_file(DATA_FOLDER, 'retired_characters_data.json', session_data)

# --- Gamemode Stats ---
_GAMEMODE_STATS_CACHE = None

async def load_gamemode_stats():
    global _GAMEMODE_STATS_CACHE
    if _GAMEMODE_STATS_CACHE is None:
        _GAMEMODE_STATS_CACHE = await _load_json_file(DATA_FOLDER, 'gamemode.json')
    return _GAMEMODE_STATS_CACHE

async def save_gamemode_stats(server_stats):
    global _GAMEMODE_STATS_CACHE
    _GAMEMODE_STATS_CACHE = server_stats
    await _save_json_file(DATA_FOLDER, 'gamemode.json', server_stats)

# --- Karma System ---
async def load_karma_settings():
    if USE_DATABASE:
        all_karma = await _db_get_all_guild_settings("karma_settings")
        if all_karma:
            return all_karma

    return await _load_json_file(DATA_FOLDER, 'karma_settings.json')

async def save_karma_settings(settings):
    if USE_DATABASE:
        await _db_save_all_guild_settings("karma_settings", settings)

    await _save_json_file(DATA_FOLDER, 'karma_settings.json', settings)

async def load_karma_stats():
    return await _load_json_file(DATA_FOLDER, 'karma_stats.json')

async def save_karma_stats(stats):
    await _save_json_file(DATA_FOLDER, 'karma_stats.json', stats)

# --- Reaction Roles ---
_REACTION_ROLES_CACHE = None

async def load_reaction_roles():
    global _REACTION_ROLES_CACHE
    if _REACTION_ROLES_CACHE is None:
        _REACTION_ROLES_CACHE = await _load_json_file(DATA_FOLDER, 'reaction_roles.json')
    return _REACTION_ROLES_CACHE

async def save_reaction_roles(roles_data):
    global _REACTION_ROLES_CACHE
    _REACTION_ROLES_CACHE = roles_data
    await _save_json_file(DATA_FOLDER, 'reaction_roles.json', roles_data)

# --- Pokemon GO Data ---
_POGO_SETTINGS_CACHE = None
_POGO_EVENTS_CACHE = None

async def load_pogo_settings():
    global _POGO_SETTINGS_CACHE
    if _POGO_SETTINGS_CACHE is not None:
        return _POGO_SETTINGS_CACHE

    if USE_DATABASE:
        pogo_settings = await _db_get_setting("global", "pogo_settings")
        if pogo_settings:
            _POGO_SETTINGS_CACHE = pogo_settings
            return _POGO_SETTINGS_CACHE

    _POGO_SETTINGS_CACHE = await _load_json_file(DATA_FOLDER, 'pogo_settings.json')
    return _POGO_SETTINGS_CACHE

async def save_pogo_settings(settings):
    global _POGO_SETTINGS_CACHE
    _POGO_SETTINGS_CACHE = settings

    if USE_DATABASE:
        await _db_save_setting("global", "pogo_settings", settings)

    await _save_json_file(DATA_FOLDER, 'pogo_settings.json', settings)

async def load_pogo_events():
    global _POGO_EVENTS_CACHE
    if _POGO_EVENTS_CACHE is None:
        _POGO_EVENTS_CACHE = await _load_json_file(DATA_FOLDER, 'pogo_events.json')
    return _POGO_EVENTS_CACHE

async def save_pogo_events(events):
    global _POGO_EVENTS_CACHE
    _POGO_EVENTS_CACHE = events
    await _save_json_file(DATA_FOLDER, 'pogo_events.json', events)

# --- Giveaway Data ---
_GIVEAWAY_DATA_CACHE = None

async def load_giveaway_data():
    global _GIVEAWAY_DATA_CACHE
    if _GIVEAWAY_DATA_CACHE is None:
        _GIVEAWAY_DATA_CACHE = await _load_json_file(DATA_FOLDER, 'giveaway_data.json')
    return _GIVEAWAY_DATA_CACHE

async def save_giveaway_data(data):
    global _GIVEAWAY_DATA_CACHE
    _GIVEAWAY_DATA_CACHE = data
    await _save_json_file(DATA_FOLDER, 'giveaway_data.json', data)

# --- Polls Data ---
_POLLS_DATA_CACHE = None

async def load_polls_data():
    global _POLLS_DATA_CACHE
    if _POLLS_DATA_CACHE is None:
        _POLLS_DATA_CACHE = await _load_json_file(DATA_FOLDER, 'polls_data.json')
    return _POLLS_DATA_CACHE

async def save_polls_data(data):
    global _POLLS_DATA_CACHE
    _POLLS_DATA_CACHE = data
    await _save_json_file(DATA_FOLDER, 'polls_data.json', data)

# --- Journal Data ---
_JOURNAL_DATA_CACHE = None

async def load_journal_data():
    global _JOURNAL_DATA_CACHE
    if _JOURNAL_DATA_CACHE is None:
        _JOURNAL_DATA_CACHE = await _load_json_file(DATA_FOLDER, 'journal_data.json')
    return _JOURNAL_DATA_CACHE

async def save_journal_data(data):
    global _JOURNAL_DATA_CACHE
    _JOURNAL_DATA_CACHE = data
    await _save_json_file(DATA_FOLDER, 'journal_data.json', data)

# --- Gamer Roles Data ---
_GAMEROLE_SETTINGS_CACHE = None

async def load_gamerole_settings():
    global _GAMEROLE_SETTINGS_CACHE
    if _GAMEROLE_SETTINGS_CACHE is not None:
        return _GAMEROLE_SETTINGS_CACHE

    if USE_DATABASE:
        all_gameroles = await _db_get_all_guild_settings("gamerole_settings")
        if all_gameroles:
            _GAMEROLE_SETTINGS_CACHE = all_gameroles
            return _GAMEROLE_SETTINGS_CACHE

    _GAMEROLE_SETTINGS_CACHE = await _load_json_file(DATA_FOLDER, 'gamerole_settings.json')
    return _GAMEROLE_SETTINGS_CACHE

async def save_gamerole_settings(data):
    global _GAMEROLE_SETTINGS_CACHE
    _GAMEROLE_SETTINGS_CACHE = data

    if USE_DATABASE:
        await _db_save_all_guild_settings("gamerole_settings", data)

    await _save_json_file(DATA_FOLDER, 'gamerole_settings.json', data)

# --- Enroll Wizard Settings ---
_ENROLL_SETTINGS_CACHE = None

async def load_enroll_settings():
    global _ENROLL_SETTINGS_CACHE
    if _ENROLL_SETTINGS_CACHE is not None:
        return _ENROLL_SETTINGS_CACHE

    if USE_DATABASE:
        all_enroll = await _db_get_all_guild_settings("enroll_settings")
        if all_enroll:
            _ENROLL_SETTINGS_CACHE = all_enroll
            return _ENROLL_SETTINGS_CACHE

    _ENROLL_SETTINGS_CACHE = await _load_json_file(DATA_FOLDER, 'enroll_settings.json')
    return _ENROLL_SETTINGS_CACHE

async def save_enroll_settings(data):
    global _ENROLL_SETTINGS_CACHE
    _ENROLL_SETTINGS_CACHE = data

    if USE_DATABASE:
        await _db_save_all_guild_settings("enroll_settings", data)

    await _save_json_file(DATA_FOLDER, 'enroll_settings.json', data)

# --- Loot Settings ---
_LOOT_SETTINGS_CACHE = None

DEFAULT_LOOT_ITEMS = [
    "A Mysterious Journal", "A Cultist Robes", "A Whispering Locket",
    "A Mysterious Puzzle Box", "A Map of the area", "An Ornate dagger",
    "Binoculars", "An Old journal", "A Gas mask", "Handcuffs",
    "A Pocket watch", "A Police badge", "A Vial of poison",
    "A Rope (20 m)", "A Vial of holy water", "A Hunting knife",
    "A Lockpick", "A Vial of acid", "A Hammer", "Pliers", "A Bear trap",
    "A Bottle of poison", "A Perfume", "Flint and steel",
    "A Vial of blood", "A Round mirror", "A Pocket knife", "Matchsticks",
    "Cigarettes", "Sigars", "A Compass", "An Opium pipe",
    "A Vial of snake venom", "A Handkerchief", "A Personal diary",
    "A Wooden cross", "A Business card", "A Cultist's mask",
    "Cultist’s robes", "A Pocket watch", "A Bottle of absinthe",
    "A Vial of morphine", "A Vial of ether", "A Black candle",
    "A Flashlight", "A Baton", "A Bottle of whiskey", "A Bulletproof vest",
    "A First-aid kit", "A Baseball bat", "A Crowbar", "A Cigarillo case",
    "Brass knuckles", "A Switchblade knife", "A Bottle of chloroform",
    "Leather gloves", "A Sewing kit", "A Deck of cards", "Fishing Line",
    "An Axe", "A Saw", "A Rope (150 ft)", "A Water bottle", "A Lantern",
    "A Signaling mirror", "A Steel helmet", "A Waterproof cape",
    "A Colt 1911 Auto Handgun", "A Luger P08 Handgun",
    "A S&W .44 Double Action Handgun", "A Colt NS Revolver",
    "A Colt M1877 Pump-Action Rifle",
    "A Remington Model 12 Pump-Action Rifle",
    "A Savage Model 99 Lever-Action Rifle",
    "A Winchester M1897 Pump-Action Rifle", "A Browning Auto-5 Shotgun",
    "A Remington Model 11 Shotgun", "A Winchester Model 12 Shotgun",
    "A Beretta M1918 Submachine Gun", "An MP28 Submachine Gun",
    "Handgun Bullets (10)", "Handgun Bullets (20)", "Handgun Bullets (30)",
    "Rifle Bullets (10)", "Rifle Bullets (20)", "Rifle Bullets (30)",
    "Shotgun Shells (10)", "Shotgun Shells (20)", "Shotgun Shells (30)",
    "A Bowie Knife", "A Katana Sword", "Nunchucks", "A Tomahawk",
    "A Bayonet", "A Rifle Scope", "A Rifle Bipod", "A Shotgun Stock",
    "A Dynamite Stick", "A Dissecting Kit", "A Bolt Cutter", "A Hacksaw",
    "A Screwdriver Set", "A Sledge Hammer", "A Wire Cutter", "Canned Meat",
    "Dried Meat", "An Airmail Stamp", "A Postage Stamp", "A Camera",
    "A Chemical Test Kit", "A Codebreaking Kit", "A Geiger Counter",
    "A Magnifying Glass", "A Sextant", "Federal agent credentials",
    "Moonshine", "A Skeleton key", "A Can of tear gas", "A Trench coat",
    "Leather gloves", "A Fountain pen", "A Shoe shine kit",
    "A Straight razor", "Cufflinks", "A Snuff box", "A Perfume bottle",
    "Playing cards", "An Oil lantern", "A Mess kit", "A Folding shovel",
    "A Sewing kit", "A Grappling hook", "A Portable radio", "A Dice set",
    "Poker chips", "A Pipe", "Pipe tobacco", "A Hairbrush",
    "Reading glasses", "A Police whistle", "An Altimeter", "A Barometer",
    "A Scalpel", "A Chemistry set", "A Glass cutter", "A Trench periscope",
    "A Hand Grenade", "A Signal flare", "An Army ration",
    "A Can of kerosene", "A Butcher's knife", "A Pickaxe", "A Fishing kit",
    "An Antiseptic ointment", "Bandages", "A Cigarette Case", "A Matchbox",
    "A pair of Cufflinks", "A pair of Spectacles", "A pair of Sunglasses",
    "A set of Keys", "A tube of Lipstick", "A set of Hairpins",
    "A Checkbook", "An Address Book", "An Umbrella", "A pair of Gloves",
    "A Notebook", "A Gas cooker", "Rubber Bands", "A Water Bottle",
    "A Towel", "A Cigar Cutter", "A Magnifying Glass", "A Magnesium Flare",
    "A Hairbrush", "A Sketchbook", "A Police Badge",
    "A Fingerprinting Kit", "Lecture Notes", "A Measuring Tape",
    "Charcoal", "A Pencil Sharpener", "An Ink Bottle", "Research Notes",
    "A Crowbar", "A Fake ID", "A Stethoscope", "Bandages",
    "Business Cards", "A Leather-bound Journal", "A Prescription Pad",
    "Dog Tags", "A Pipe", "A Chocolate bar", "Strange bones",
    "A Prayer Book", "Surgical Instruments", "Fishing Lures",
    "Fishing Line", "Pliers", "A Bottle Opener", "A Wire Cutter",
    "A Wrench", "A Pocket Watch", "A Travel Guidebook", "A Passport",
    "Dental Tools", "A Surgical Mask", "A Bottle of red paint",
    "An Electricity cable (15 ft)", "A Smoke Grenade ",
    "A Heavy duty jacket", "A pair of Heavy duty trousers", "Motor Oil",
    "Army overalls", "A small scale", "A bottle of Snake Oil",
    "A Cane with a hidden sword", "A Monocle on a chain",
    "A Carved ivory chess piece", "Antique marbles", "A Bullwhip",
    "A Folding Fan", "A Folding Pocket Knife", "A Travel Chess Set",
    "A Pocket Book of Etiquette", "A Pocket Guide to Stars",
    "A Pocket Book of Flowers", "A Mandolin", "An Ukulele",
    "A Vial of Laudanum", "A Leather Bound Flask (empty)",
    "A Lock of Hair", "A Tobacco Pouch", "A flare gun", "A pipe bomb",
    "A Molotov cocktail", "An anti-personnel mine", "A machete",
    "A postcard", "A wristwatch", "A shovel", "A padlock",
    "A light chain (20 ft)", "A heavy chain (20 ft)", "A handsaw",
    "A telescope", "A water pipe", "A box of candles",
    "Aspirin (16 pills)", "Chewing Tobacco", "A Gentleman's Pocket Comb",
    "A Sailor's Knot Tying Guide", "A Leather Map Case", "A Camera",
    "Crystal Rosary Beads", "A Handmade Silver Bracelet",
    "Herbal Supplements", "A Bloodletting Tool",
    "A Spiritualist Seance Kit", "A Morphine Syringe",
    "A Bottle of Radioactive Water", "An Astrology Chart",
    "An Alchemy Kit", "A Mortar and Pestle", "A Scalpel",
    "An Erlenmeyer Flask", "A Chemistry Textbook", "Nautical Charts",
    "A Bottle of Sulfuric Acid", "Protective Gloves", "Safety Goggles",
    "A Kerosene Lamp", "Painkillers"
]

async def load_loot_settings():
    global _LOOT_SETTINGS_CACHE
    if _LOOT_SETTINGS_CACHE is not None:
        return _LOOT_SETTINGS_CACHE

    if USE_DATABASE:
        loot_settings = await _db_get_setting("global", "loot_settings")
        if loot_settings:
            _LOOT_SETTINGS_CACHE = loot_settings
            return _LOOT_SETTINGS_CACHE

    data = await _load_json_file(DATA_FOLDER, 'loot_settings.json')
    if not data:
        # Return defaults
        data = {
            "items": DEFAULT_LOOT_ITEMS,
            "money_chance": 25,
            "money_min": 0.01,
            "money_max": 5.00,
            "currency_symbol": "$",
            "num_items_min": 1,
            "num_items_max": 5
        }
    _LOOT_SETTINGS_CACHE = data
    return data

async def save_loot_settings(data):
    global _LOOT_SETTINGS_CACHE
    _LOOT_SETTINGS_CACHE = data

    if USE_DATABASE:
        await _db_save_setting("global", "loot_settings", data)

    await _save_json_file(DATA_FOLDER, 'loot_settings.json', data)

# --- Skill Sound Settings ---
_SKILL_SOUND_SETTINGS_CACHE = None

async def load_skill_sound_settings():
    global _SKILL_SOUND_SETTINGS_CACHE
    if _SKILL_SOUND_SETTINGS_CACHE is not None:
        return _SKILL_SOUND_SETTINGS_CACHE.copy()

    if USE_DATABASE:
        all_sounds = await _db_get_all_guild_settings("skill_sound_settings")
        if all_sounds:
            _SKILL_SOUND_SETTINGS_CACHE = all_sounds
            return _SKILL_SOUND_SETTINGS_CACHE.copy()

    _SKILL_SOUND_SETTINGS_CACHE = await _load_json_file(DATA_FOLDER, 'skill_sound_settings.json')
    return _SKILL_SOUND_SETTINGS_CACHE.copy()

async def save_skill_sound_settings(data):
    global _SKILL_SOUND_SETTINGS_CACHE
    _SKILL_SOUND_SETTINGS_CACHE = data

    if USE_DATABASE:
        await _db_save_all_guild_settings("skill_sound_settings", data)

    await _save_json_file(DATA_FOLDER, 'skill_sound_settings.json', data)

# --- Fonts Config ---
_FONTS_CONFIG_CACHE = None

async def load_fonts_config():
    global _FONTS_CONFIG_CACHE
    if _FONTS_CONFIG_CACHE is not None:
        return _FONTS_CONFIG_CACHE.copy()

    if USE_DATABASE:
        fonts_config = await _db_get_setting("global", "fonts_config")
        if fonts_config:
            _FONTS_CONFIG_CACHE = fonts_config
            return _FONTS_CONFIG_CACHE.copy()

    _FONTS_CONFIG_CACHE = await _load_json_file(DATA_FOLDER, 'fonts_config.json')
    return _FONTS_CONFIG_CACHE.copy()

async def save_fonts_config(data):
    global _FONTS_CONFIG_CACHE
    _FONTS_CONFIG_CACHE = data

    if USE_DATABASE:
        await _db_save_setting("global", "fonts_config", data)

    await _save_json_file(DATA_FOLDER, 'fonts_config.json', data)
