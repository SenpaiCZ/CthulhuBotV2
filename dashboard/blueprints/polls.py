from quart import Blueprint, request, jsonify, redirect, url_for, render_template

from dashboard.app import app, is_admin
from loadnsave import load_polls_data

polls_bp = Blueprint('polls', __name__)

# --- Polls Routes ---

@polls_bp.route('/admin/polls')
async def admin_polls():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('polls_dashboard.html')

@polls_bp.route('/api/polls/data')
async def polls_data():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"guilds": []})

    data = await load_polls_data()
    guilds_data = []

    for guild in app.bot.guilds:
        guild_id_str = str(guild.id)

        # Channels
        channels = []
        for channel in guild.text_channels:
             channels.append({"id": str(channel.id), "name": channel.name})

        # Polls for this guild
        guild_polls = []
        if data:
             for msg_id, poll in data.items():
                 if str(poll.get('guild_id')) == guild_id_str:
                     poll_copy = poll.copy()
                     poll_copy['message_id'] = msg_id

                     # Resolve channel name
                     cid = poll.get('channel_id')
                     poll_copy['channel_name'] = "Unknown"
                     if cid:
                         chan = guild.get_channel(int(cid))
                         if chan: poll_copy['channel_name'] = chan.name

                     # Count votes
                     votes = poll.get('votes', {})
                     poll_copy['vote_count'] = len(votes)

                     guild_polls.append(poll_copy)

        guilds_data.append({
            "id": guild_id_str,
            "name": guild.name,
            "channels": channels,
            "polls": guild_polls
        })

    return jsonify({"guilds": guilds_data})

@polls_bp.route('/api/polls/create', methods=['POST'])
async def polls_create():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    channel_id = data.get('channel_id')
    question = data.get('question')
    options_str = data.get('options') # Comma separated or list

    if not all([guild_id, channel_id, question, options_str]):
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    cog = app.bot.get_cog("Polls")
    if not cog:
        return jsonify({"status": "error", "message": "Polls Cog not loaded"}), 500

    if isinstance(options_str, str):
        options = options_str.split(',')
    else:
        options = options_str

    success, result = await cog.create_poll_api(guild_id, channel_id, question, options)

    if success:
        return jsonify({"status": "success", "poll_id": result})
    else:
        return jsonify({"status": "error", "message": result}), 500

@polls_bp.route('/api/polls/end', methods=['POST'])
async def polls_end():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    poll_id = data.get('poll_id')

    if not poll_id:
        return jsonify({"status": "error", "message": "Missing poll_id"}), 400

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    cog = app.bot.get_cog("Polls")
    if not cog:
        return jsonify({"status": "error", "message": "Polls Cog not loaded"}), 500

    success, result = await cog.end_poll_api(poll_id)

    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": result}), 500
