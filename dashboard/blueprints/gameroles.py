import re
from quart import Blueprint, request, jsonify, render_template, redirect, url_for

from dashboard.app import app, is_admin
from loadnsave import load_gamerole_settings, save_gamerole_settings

gameroles_bp = Blueprint('gameroles', __name__)

# --- Gamer Roles Routes ---

@gameroles_bp.route('/admin/gameroles')
async def admin_gameroles():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('gameroles.html')

@gameroles_bp.route('/api/gameroles/data')
async def gameroles_data():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"guilds": []})

    settings = await load_gamerole_settings()
    guilds_data = []

    for guild in app.bot.guilds:
        guild_id_str = str(guild.id)
        guild_settings = settings.get(guild_id_str, {})

        guilds_data.append({
            "id": guild_id_str,
            "name": guild.name,
            "settings": {
                "enabled": guild_settings.get("enabled", False),
                "color": guild_settings.get("color", "#0000FF"),
                "ignored_activities": guild_settings.get("ignored_activities", ["Custom Status"]),
                "activity_emojis": guild_settings.get("activity_emojis", {})
            }
        })

    return jsonify({"guilds": guilds_data})

@gameroles_bp.route('/api/gameroles/emoji/set', methods=['POST'])
async def gameroles_emoji_set():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    activity = data.get('activity')
    emoji_char = data.get('emoji')

    if not guild_id or not activity or not emoji_char:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    guild = app.bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"status": "error", "message": "Guild not found"}), 404

    cog = app.bot.get_cog("GamerRoles")
    if cog:
        try:
            await cog.update_activity_emoji(guild, activity, emoji_char)
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "error", "message": "GamerRoles Cog not loaded"}), 500

@gameroles_bp.route('/api/gameroles/emoji/delete', methods=['POST'])
async def gameroles_emoji_delete():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    activity = data.get('activity')

    if not guild_id or not activity:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    guild = app.bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"status": "error", "message": "Guild not found"}), 404

    cog = app.bot.get_cog("GamerRoles")
    if cog:
        try:
            await cog.update_activity_emoji(guild, activity, None)
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "error", "message": "GamerRoles Cog not loaded"}), 500

@gameroles_bp.route('/api/gameroles/save', methods=['POST'])
async def gameroles_save():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')

    if not guild_id:
        return jsonify({"status": "error", "message": "Missing guild_id"}), 400

    # Try to update via Cog first to keep cache in sync
    if app.bot:
        cog = app.bot.get_cog("GamerRoles")
        if cog:
            if 'enabled' in data:
                await cog.update_settings(guild_id, 'enabled', bool(data.get('enabled')))
            if 'color' in data:
                color = data.get('color')
                if re.match(r'^#[0-9A-Fa-f]{6}$', color):
                    await cog.update_settings(guild_id, 'color', color)
            return jsonify({"status": "success"})

    # Fallback
    settings = await load_gamerole_settings()
    if str(guild_id) not in settings: settings[str(guild_id)] = {}

    if 'enabled' in data:
        settings[str(guild_id)]['enabled'] = bool(data.get('enabled'))

    if 'color' in data:
        color = data.get('color')
        # Validate hex
        if re.match(r'^#[0-9A-Fa-f]{6}$', color):
            settings[str(guild_id)]['color'] = color

    await save_gamerole_settings(settings)
    return jsonify({"status": "success"})

@gameroles_bp.route('/api/gameroles/ignore/add', methods=['POST'])
async def gameroles_ignore_add():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    activity = data.get('activity')

    if not guild_id or not activity:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    if app.bot:
        cog = app.bot.get_cog("GamerRoles")
        if cog:
            # We need to expose a method for list manipulation in Cog or just use update_settings with full list?
            # Cog doesn't have a specific method for appending to ignore list exposed publicly in a simple way
            # except `update_settings` which takes a key/value.
            # But we need to READ the list first.
            settings = await cog.get_settings(guild_id)
            ignored = settings.get("ignored_activities", ["Custom Status"])
            if activity not in ignored:
                ignored.append(activity)
                await cog.update_settings(guild_id, "ignored_activities", ignored)
            return jsonify({"status": "success"})

    settings = await load_gamerole_settings()
    if str(guild_id) not in settings: settings[str(guild_id)] = {}

    ignored = settings[str(guild_id)].get("ignored_activities", ["Custom Status"])
    if activity not in ignored:
        ignored.append(activity)
        settings[str(guild_id)]["ignored_activities"] = ignored
        await save_gamerole_settings(settings)

    return jsonify({"status": "success"})

@gameroles_bp.route('/api/gameroles/ignore/remove', methods=['POST'])
async def gameroles_ignore_remove():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    activity = data.get('activity')

    if not guild_id or not activity:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    if app.bot:
        cog = app.bot.get_cog("GamerRoles")
        if cog:
            settings = await cog.get_settings(guild_id)
            ignored = settings.get("ignored_activities", ["Custom Status"])
            if activity in ignored:
                ignored.remove(activity)
                await cog.update_settings(guild_id, "ignored_activities", ignored)
            return jsonify({"status": "success"})

    settings = await load_gamerole_settings()
    if str(guild_id) in settings:
        ignored = settings[str(guild_id)].get("ignored_activities", ["Custom Status"])
        if activity in ignored:
            ignored.remove(activity)
            settings[str(guild_id)]["ignored_activities"] = ignored
            await save_gamerole_settings(settings)

    return jsonify({"status": "success"})
