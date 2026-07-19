import discord
from quart import Blueprint, request, jsonify, redirect, url_for, render_template

from dashboard.app import app, is_admin
from loadnsave import load_bot_status, save_bot_status, load_server_stats, save_server_stats

bot_config_bp = Blueprint('bot_config', __name__)


# --- Bot Config Routes ---

@bot_config_bp.route('/admin/bot_config')
async def admin_bot_config():
    if not is_admin(): return redirect(url_for('core.login'))

    if not app.bot:
        return "Bot not initialized", 500

    # Load Prefixes
    server_stats = await load_server_stats()
    guilds_data = []

    for guild in app.bot.guilds:
        guild_id_str = str(guild.id)
        current_prefix = server_stats.get(guild_id_str, "!")
        guilds_data.append({
            "id": guild_id_str,
            "name": guild.name,
            "prefix": current_prefix
        })

    # Load Bot Status
    bot_status = await load_bot_status()

    return await render_template('bot_config.html', guilds=guilds_data, status=bot_status)

@bot_config_bp.route('/api/save_status', methods=['POST'])
async def save_status():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    status_type = data.get('type')
    status_text = data.get('text')

    if not status_type or not status_text:
        return jsonify({"status": "error", "message": "Missing type or text"}), 400

    # Save to file
    new_status = {"type": status_type, "text": status_text}
    await save_bot_status(new_status)

    # Update Bot Presence immediately
    if app.bot and app.bot.is_ready():
        activity = None
        if status_type == 'playing':
            activity = discord.Game(name=status_text)
        elif status_type == 'watching':
            activity = discord.Activity(type=discord.ActivityType.watching, name=status_text)
        elif status_type == 'listening':
            activity = discord.Activity(type=discord.ActivityType.listening, name=status_text)
        elif status_type == 'competing':
            activity = discord.Activity(type=discord.ActivityType.competing, name=status_text)

        if activity:
            await app.bot.change_presence(activity=activity)

    return jsonify({"status": "success"})

@bot_config_bp.route('/api/save_prefix', methods=['POST'])
async def save_prefix():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    prefix = data.get('prefix')

    if not guild_id or not prefix:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    server_stats = await load_server_stats()
    server_stats[str(guild_id)] = prefix
    await save_server_stats(server_stats)

    return jsonify({"status": "success"})
