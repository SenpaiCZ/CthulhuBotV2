import asyncio
from quart import Blueprint, request, jsonify, redirect, url_for, render_template

from dashboard.app import app, is_admin
from dashboard.state import SOUNDBOARD_FOLDER
from loadnsave import (
    load_luck_stats, save_luck_stats,
    load_skill_settings, save_skill_settings,
    load_loot_settings, save_loot_settings,
    load_skill_sound_settings, save_skill_sound_settings,
    load_skills_data,
)
from ..file_utils import sync_get_soundboard_files

game_settings_bp = Blueprint('game_settings', __name__)


# --- Game Settings Routes ---

@game_settings_bp.route('/admin/game_settings')
async def admin_game_settings():
    if not is_admin(): return redirect(url_for('core.login'))
    skills_data = await load_skills_data()
    return await render_template('game_settings.html', skills=sorted(list(skills_data.keys())))

@game_settings_bp.route('/api/game/settings/data')
async def game_settings_data():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"guilds": []})

    luck_stats = await load_luck_stats()
    skill_settings = await load_skill_settings()

    guilds_data = []

    for guild in app.bot.guilds:
        guild_id_str = str(guild.id)
        current_luck = luck_stats.get(guild_id_str, 10)

        # Skill settings
        current_max_skill = 75
        if guild_id_str in skill_settings:
            current_max_skill = skill_settings[guild_id_str].get("max_starting_skill", 75)

        guilds_data.append({
            "id": guild_id_str,
            "name": guild.name,
            "luck_threshold": current_luck,
            "max_starting_skill": current_max_skill
        })

    return jsonify({"guilds": guilds_data})

@game_settings_bp.route('/api/game/settings/save_general', methods=['POST'])
async def save_general_settings():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    luck_value = data.get('luck_value')
    max_skill_value = data.get('max_skill_value')

    if not guild_id:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    # Save Luck
    if luck_value is not None:
        try:
            luck_val = int(luck_value)
            if luck_val < 0: raise ValueError

            luck_stats = await load_luck_stats()
            luck_stats[str(guild_id)] = luck_val
            await save_luck_stats(luck_stats)
        except ValueError:
            return jsonify({"status": "error", "message": "Invalid luck value"}), 400

    # Save Max Skill
    if max_skill_value is not None:
        try:
            skill_val = int(max_skill_value)
            if skill_val < 1 or skill_val > 99: raise ValueError

            skill_settings = await load_skill_settings()
            if str(guild_id) not in skill_settings:
                skill_settings[str(guild_id)] = {}

            skill_settings[str(guild_id)]["max_starting_skill"] = skill_val
            await save_skill_settings(skill_settings)
        except ValueError:
            return jsonify({"status": "error", "message": "Invalid max skill value (1-99)"}), 400

    return jsonify({"status": "success"})

# --- Loot Settings Routes ---

@game_settings_bp.route('/api/game/loot/data')
async def game_loot_data():
    if not is_admin(): return "Unauthorized", 401

    data = await load_loot_settings()
    return jsonify(data)

@game_settings_bp.route('/api/game/loot/save', methods=['POST'])
async def game_loot_save():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()

    # Validation
    try:
        # Construct sanitized object to save
        save_data = {
            "items": data.get("items", []),
            "money_chance": int(data.get("money_chance", 25)),
            "money_min": float(data.get("money_min", 0.01)),
            "money_max": float(data.get("money_max", 5.00)),
            "currency_symbol": str(data.get("currency_symbol", "$")),
            "num_items_min": int(data.get("num_items_min", 1)),
            "num_items_max": int(data.get("num_items_max", 5))
        }

        await save_loot_settings(save_data)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# --- Skill Sound Settings Routes ---

@game_settings_bp.route('/api/game/sounds/data')
async def game_sounds_data():
    if not is_admin(): return "Unauthorized", 401

    settings = await load_skill_sound_settings()
    files = await asyncio.to_thread(sync_get_soundboard_files, SOUNDBOARD_FOLDER)

    # Flatten files dict to list for easier consumption
    # sync_get_soundboard_files returns a dict { "Folder": [ {name, path}, ... ] }

    flat_files = []
    for folder_name, file_list in files.items():
        if isinstance(file_list, list):
            for file_info in file_list:
                if 'path' in file_info:
                    # path is relative to SOUNDBOARD_FOLDER already (e.g. "Root/file.mp3" or just "file.mp3"?)
                    # file_utils says:
                    # Root: entry (just filename)
                    # Subdir: os.path.join(entry, f) (subdir/filename)
                    # So we just take 'path'.
                    flat_files.append(file_info['path'].replace("\\", "/"))

    flat_files.sort()

    return jsonify({
        "settings": settings,
        "files": flat_files
    })

@game_settings_bp.route('/api/game/sounds/save', methods=['POST'])
async def game_sounds_save():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')

    if not guild_id:
        return jsonify({"status": "error", "message": "Missing guild_id"}), 400

    settings = await load_skill_sound_settings()

    # Update for specific guild
    # Structure:
    # {
    #   "default": { "critical": "file", ... },
    #   "skills": { "Skill Name": { "critical": "file", ... }, ... }
    # }

    settings[str(guild_id)] = {
        "default": data.get("default", {}),
        "skills": data.get("skills", {})
    }

    await save_skill_sound_settings(settings)
    return jsonify({"status": "success"})
