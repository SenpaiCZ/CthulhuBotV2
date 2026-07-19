from quart import Blueprint, request, jsonify, redirect, url_for, render_template

from dashboard.app import app, is_admin
from loadnsave import autoroom_load, autoroom_save

autorooms_bp = Blueprint('autorooms', __name__)

# --- Auto Room Routes ---

@autorooms_bp.route('/admin/autorooms')
async def admin_autorooms():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('autoroom_dashboard.html')

@autorooms_bp.route('/api/autorooms/data')
async def autorooms_data():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"guilds": []})

    autorooms = await autoroom_load()
    guilds_data = []

    for guild in app.bot.guilds:
        guild_id_str = str(guild.id)

        # Voice Channels for Source
        voice_channels = []
        for channel in guild.voice_channels:
             voice_channels.append({"id": str(channel.id), "name": channel.name})

        # Categories for Target
        categories = []
        for category in guild.categories:
            categories.append({"id": str(category.id), "name": category.name})

        current_config = autorooms.get(guild_id_str, {})

        guilds_data.append({
            "id": guild_id_str,
            "name": guild.name,
            "voice_channels": voice_channels,
            "categories": categories,
            "config": {
                "channel_id": str(current_config.get("channel_id", "")),
                "category_id": str(current_config.get("category_id", ""))
            }
        })

    return jsonify({"guilds": guilds_data})

@autorooms_bp.route('/api/autorooms/save', methods=['POST'])
async def autorooms_save():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    channel_id = data.get('channel_id')
    category_id = data.get('category_id')

    if not guild_id:
        return jsonify({"status": "error", "message": "Missing guild_id"}), 400

    autorooms = await autoroom_load()

    if str(guild_id) not in autorooms:
        autorooms[str(guild_id)] = {}

    if channel_id:
        autorooms[str(guild_id)]["channel_id"] = int(channel_id)
    elif "channel_id" in autorooms[str(guild_id)]:
        del autorooms[str(guild_id)]["channel_id"]

    if category_id:
        autorooms[str(guild_id)]["category_id"] = int(category_id)
    elif "category_id" in autorooms[str(guild_id)]:
        del autorooms[str(guild_id)]["category_id"]

    await autoroom_save(autorooms)

    return jsonify({"status": "success"})
