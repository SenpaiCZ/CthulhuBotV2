from quart import Blueprint, request, jsonify, redirect, url_for, render_template

from dashboard.app import app, is_admin
from loadnsave import load_reminder_data

reminders_bp = Blueprint('reminders', __name__)

# --- Reminders Routes ---

@reminders_bp.route('/admin/reminders')
async def admin_reminders():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('reminders_dashboard.html')

@reminders_bp.route('/api/reminders/data')
async def reminders_data():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"guilds": []})

    data = await load_reminder_data()
    guilds_data = []

    for guild in app.bot.guilds:
        guild_id_str = str(guild.id)

        # Channels
        channels = []
        for channel in guild.text_channels:
             channels.append({"id": str(channel.id), "name": channel.name})

        # Users (for dropdown?) - fetching all users is heavy. Maybe just current members?
        # For simplicity, we might just let them input user ID or pick from cached members.
        users = []
        for member in guild.members:
            users.append({"id": str(member.id), "name": member.display_name})

        # Reminders for this guild
        guild_reminders = []
        if guild_id_str in data:
            for rem in data[guild_id_str]:
                rem_copy = rem.copy()

                # Resolve channel name
                cid = rem.get('channel_id')
                rem_copy['channel_name'] = "Unknown"
                if cid:
                    chan = guild.get_channel(int(cid))
                    if chan: rem_copy['channel_name'] = chan.name

                # Resolve User name
                uid = rem.get('user_id')
                rem_copy['user_name'] = f"User {uid}"
                if uid:
                    mem = guild.get_member(int(uid))
                    if mem: rem_copy['user_name'] = mem.display_name

                guild_reminders.append(rem_copy)

        guilds_data.append({
            "id": guild_id_str,
            "name": guild.name,
            "channels": channels,
            "users": users,
            "reminders": guild_reminders
        })

    return jsonify({"guilds": guilds_data})

@reminders_bp.route('/api/reminders/create', methods=['POST'])
async def reminders_create():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    channel_id = data.get('channel_id')
    user_id = data.get('user_id')
    message = data.get('message')
    duration_str = data.get('duration')

    if not all([guild_id, channel_id, user_id, message, duration_str]):
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    cog = app.bot.get_cog("Reminders")
    if not cog:
        return jsonify({"status": "error", "message": "Reminders Cog not loaded"}), 500

    seconds = cog.parse_duration(duration_str)
    if seconds <= 0:
        return jsonify({"status": "error", "message": "Invalid duration"}), 400

    success, result = await cog.create_reminder_api(guild_id, channel_id, user_id, message, seconds)

    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": result}), 500

@reminders_bp.route('/api/reminders/delete', methods=['POST'])
async def reminders_delete():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    reminder_id = data.get('reminder_id')

    if not guild_id or not reminder_id:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    cog = app.bot.get_cog("Reminders")
    if not cog:
        return jsonify({"status": "error", "message": "Reminders Cog not loaded"}), 500

    success, result = await cog.delete_reminder_api(guild_id, reminder_id)

    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": result}), 500
