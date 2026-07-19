from collections import Counter
from quart import Blueprint, request, jsonify, render_template, redirect, url_for
import discord

from dashboard.app import app, is_admin
from loadnsave import load_karma_settings, save_karma_settings

karma_bp = Blueprint('karma', __name__)

# --- Karma Routes ---

@karma_bp.route('/admin/karma')
async def admin_karma():
    if not is_admin(): return redirect(url_for('core.login'))

    if not app.bot:
        return "Bot not initialized", 500

    karma_settings = await load_karma_settings()
    guilds_data = []

    for guild in app.bot.guilds:
        channels = []
        for channel in guild.text_channels:
             channels.append({"id": str(channel.id), "name": channel.name})

        # Fetch roles for dropdown
        roles_list = []
        for role in guild.roles:
            if not role.is_default() and not role.managed:
                roles_list.append({"id": str(role.id), "name": role.name})
        roles_list.sort(key=lambda x: x['name'])

        guild_id_str = str(guild.id)
        current_settings = karma_settings.get(guild_id_str, {})

        # Resolve existing roles
        resolved_roles = []
        if "roles" in current_settings:
            for thresh, role_id in current_settings["roles"].items():
                role_obj = guild.get_role(int(role_id))
                role_name = role_obj.name if role_obj else f"Unknown Role ({role_id})"
                resolved_roles.append({
                    "threshold": thresh,
                    "role_id": str(role_id),
                    "role_name": role_name
                })
            # Sort by threshold
            resolved_roles.sort(key=lambda x: int(x['threshold']))

        guilds_data.append({
            "id": guild_id_str,
            "name": guild.name,
            "channels": channels,
            "roles_list": roles_list,
            "settings": current_settings,
            "resolved_roles": resolved_roles
        })

    return await render_template('karma_settings.html', guilds=guilds_data)

@karma_bp.route('/api/karma/save', methods=['POST'])
async def save_karma():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    channel_id = data.get('channel_id')
    notification_channel_id = data.get('notification_channel_id')
    upvote_emoji = data.get('upvote_emoji')
    downvote_emoji = data.get('downvote_emoji')

    if not guild_id:
        return jsonify({"status": "error", "message": "Missing guild_id"}), 400

    karma_settings = await load_karma_settings()

    # If all fields are empty/null, maybe we should clear the settings?
    # But for now, let's assume if they send data, they want to set it.
    # If channel_id is "none" or empty, we could disable it.

    if not channel_id or channel_id == "none":
        if str(guild_id) in karma_settings:
            del karma_settings[str(guild_id)]
    else:
        # Preserve existing roles
        existing_roles = {}
        if str(guild_id) in karma_settings and "roles" in karma_settings[str(guild_id)]:
            existing_roles = karma_settings[str(guild_id)]["roles"]

        karma_settings[str(guild_id)] = {
            "channel_id": int(channel_id),
            "notification_channel_id": int(notification_channel_id) if notification_channel_id and notification_channel_id != "none" else None,
            "upvote_emoji": upvote_emoji if upvote_emoji else "👌",
            "downvote_emoji": downvote_emoji if downvote_emoji else "🤏",
            "roles": existing_roles
        }

    await save_karma_settings(karma_settings)

    return jsonify({"status": "success"})

@karma_bp.route('/api/karma/roles/save', methods=['POST'])
async def save_karma_roles():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    roles_data = data.get('roles') # List of {threshold: x, role_id: y}

    if not guild_id:
        return jsonify({"status": "error", "message": "Missing guild_id"}), 400

    karma_settings = await load_karma_settings()

    if str(guild_id) not in karma_settings:
        # Should initiate base settings first ideally, but we can create empty dict
        karma_settings[str(guild_id)] = {}

    # Convert list to dict format for storage: {"10": 123, "50": 456}
    new_roles_map = {}
    if roles_data:
        for item in roles_data:
            thresh = str(item.get('threshold'))
            r_id = int(item.get('role_id'))
            new_roles_map[thresh] = r_id

    karma_settings[str(guild_id)]["roles"] = new_roles_map
    await save_karma_settings(karma_settings)

    # Trigger Update
    if app.bot:
        cog = app.bot.get_cog("Karma")
        if cog:
            app.bot.loop.create_task(cog.run_guild_karma_update(guild_id))

    return jsonify({"status": "success"})

@karma_bp.route('/api/karma/users/<guild_id>')
async def get_karma_users(guild_id):
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify([])

    cog = app.bot.get_cog("Karma")
    if cog:
        data = await cog.get_guild_leaderboard_data(guild_id)
        return jsonify(data)

    return jsonify([])

@karma_bp.route('/api/karma/recalculate', methods=['POST'])
async def recalculate_karma():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')

    if not guild_id:
        return jsonify({"status": "error", "message": "Missing guild_id"}), 400

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    cog = app.bot.get_cog("Karma")
    if cog:
        # Run in background
        app.bot.loop.create_task(cog.recalculate_karma(guild_id))
        return jsonify({"status": "success", "message": "Recalculation started in background."})

    return jsonify({"status": "error", "message": "Karma Cog not loaded"}), 500

@karma_bp.route('/api/karma/detect_emojis', methods=['POST'])
async def detect_karma_emojis():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    channel_id = data.get('channel_id')

    if not guild_id or not channel_id:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    try:
        guild = app.bot.get_guild(int(guild_id))
        if not guild:
            return jsonify({"status": "error", "message": "Guild not found"}), 404

        channel = guild.get_channel(int(channel_id))
        if not channel:
            return jsonify({"status": "error", "message": "Channel not found"}), 404

        # Scan last 20 messages
        emoji_counter = Counter()

        async for message in channel.history(limit=20):
            for reaction in message.reactions:
                emoji_str = str(reaction.emoji)
                emoji_counter[emoji_str] += reaction.count

        if not emoji_counter:
             return jsonify({"status": "error", "message": "No reactions found in the last 20 messages."}), 400

        most_common = emoji_counter.most_common(2)

        if len(most_common) < 2:
             return jsonify({"status": "error", "message": "Insufficient data: Less than 2 unique emojis found."}), 400

        upvote = most_common[0][0]
        downvote = most_common[1][0]

        return jsonify({
            "status": "success",
            "upvote": upvote,
            "downvote": downvote
        })

    except Exception as e:
        print(f"Error detecting emojis: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
