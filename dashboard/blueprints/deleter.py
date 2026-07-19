from quart import Blueprint, request, jsonify, redirect, url_for, render_template

from dashboard.app import app, is_admin
from loadnsave import load_deleter_data, save_deleter_data

deleter_bp = Blueprint('deleter', __name__)

# --- Auto Deleter Routes ---

@deleter_bp.route('/admin/deleter')
async def admin_deleter():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('deleter_dashboard.html')

@deleter_bp.route('/api/deleter/data')
async def deleter_data():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"guilds": []})

    deleter_data = await load_deleter_data() # {"channel_id": seconds}
    guilds_data = []

    for guild in app.bot.guilds:
        guild_id_str = str(guild.id)

        # Text Channels
        text_channels = []
        for channel in guild.text_channels:
             # Check if active
             is_active = str(channel.id) in deleter_data
             seconds = deleter_data.get(str(channel.id), 0)

             text_channels.append({
                 "id": str(channel.id),
                 "name": channel.name,
                 "is_active": is_active,
                 "seconds": seconds
             })

        guilds_data.append({
            "id": guild_id_str,
            "name": guild.name,
            "channels": text_channels
        })

    return jsonify({"guilds": guilds_data})

@deleter_bp.route('/api/deleter/save', methods=['POST'])
async def deleter_save():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    channel_id = data.get('channel_id')
    seconds = data.get('seconds')

    if not channel_id or seconds is None:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    try:
        sec_val = int(seconds)
        if sec_val < 0: raise ValueError
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid time limit"}), 400

    deleter_data = await load_deleter_data()
    deleter_data[str(channel_id)] = sec_val
    await save_deleter_data(deleter_data)

    return jsonify({"status": "success"})

@deleter_bp.route('/api/deleter/delete', methods=['POST'])
async def deleter_delete():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    channel_id = data.get('channel_id')

    if not channel_id:
        return jsonify({"status": "error", "message": "Missing channel_id"}), 400

    deleter_data = await load_deleter_data()
    if str(channel_id) in deleter_data:
        del deleter_data[str(channel_id)]
        await save_deleter_data(deleter_data)
        return jsonify({"status": "success"})

    return jsonify({"status": "error", "message": "Rule not found"}), 404

@deleter_bp.route('/api/deleter/bulk_delete', methods=['POST'])
async def deleter_bulk():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    channel_id = data.get('channel_id')
    amount = data.get('amount')

    if not channel_id or not amount:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    cog = app.bot.get_cog("deleter")
    if cog:
        success, result = await cog.api_bulk_delete(channel_id, amount)
        if success:
             return jsonify({"status": "success", "count": result})
        else:
             return jsonify({"status": "error", "message": result}), 500

    return jsonify({"status": "error", "message": "Deleter Cog not loaded"}), 500
