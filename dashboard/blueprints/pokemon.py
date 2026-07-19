from quart import Blueprint, request, jsonify, redirect, url_for, render_template

from dashboard.app import app, is_admin
from loadnsave import load_pogo_settings, save_pogo_settings, load_pogo_events

pokemon_bp = Blueprint('pokemon', __name__)

# --- Pokemon GO Routes ---

@pokemon_bp.route('/admin/pokemon')
async def admin_pokemon():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('pokemon_dashboard.html')

@pokemon_bp.route('/api/pokemon/data')
async def pokemon_data():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"guilds": [], "events": []})

    settings = await load_pogo_settings()
    events = await load_pogo_events()

    guilds_data = []
    for guild in app.bot.guilds:
        guild_id_str = str(guild.id)

        # Channels
        channels = []
        for channel in guild.text_channels:
             channels.append({"id": str(channel.id), "name": channel.name})

        # Roles
        roles = []
        for role in guild.roles:
            if not role.is_default() and not role.managed:
                roles.append({"id": str(role.id), "name": role.name})
        roles.sort(key=lambda x: x['name'])

        current_config = settings.get(guild_id_str, {})

        # Resolve role name if set
        role_id = current_config.get('role_id')
        role_name = "Unknown Role"
        if role_id:
            role_obj = guild.get_role(int(role_id))
            if role_obj:
                role_name = role_obj.name

        guilds_data.append({
            "id": guild_id_str,
            "name": guild.name,
            "channels": channels,
            "roles": roles,
            "config": {
                "channel_id": str(current_config.get("channel_id", "")),
                "role_id": str(role_id) if role_id else "",
                "role_name": role_name,
                "daily_summary_enabled": current_config.get("daily_summary_enabled", True),
                "event_start_enabled": current_config.get("event_start_enabled", True),
                "weekly_summary_enabled": current_config.get("weekly_summary_enabled", True),
                "advance_minutes": current_config.get("advance_minutes", 120)
            }
        })

    return jsonify({
        "guilds": guilds_data,
        "events": events or []
    })

@pokemon_bp.route('/api/pokemon/save', methods=['POST'])
async def pokemon_save():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')

    if not guild_id:
        return jsonify({"status": "error", "message": "Missing guild_id"}), 400

    settings = await load_pogo_settings()

    if str(guild_id) not in settings:
        settings[str(guild_id)] = {}

    if 'channel_id' in data:
        cid = data.get('channel_id')
        if cid:
            settings[str(guild_id)]['channel_id'] = int(cid)
        elif 'channel_id' in settings[str(guild_id)]:
            del settings[str(guild_id)]['channel_id']

    if 'role_id' in data:
        rid = data.get('role_id')
        if rid:
            settings[str(guild_id)]['role_id'] = int(rid)
        elif 'role_id' in settings[str(guild_id)]:
            del settings[str(guild_id)]['role_id']

    if 'daily_summary_enabled' in data:
        settings[str(guild_id)]['daily_summary_enabled'] = bool(data.get('daily_summary_enabled'))

    if 'event_start_enabled' in data:
        settings[str(guild_id)]['event_start_enabled'] = bool(data.get('event_start_enabled'))

    if 'weekly_summary_enabled' in data:
        settings[str(guild_id)]['weekly_summary_enabled'] = bool(data.get('weekly_summary_enabled'))

    if 'advance_minutes' in data:
        try:
            settings[str(guild_id)]['advance_minutes'] = int(data.get('advance_minutes'))
        except:
            pass

    await save_pogo_settings(settings)

    # Reload settings in Cog
    if app.bot:
        cog = app.bot.get_cog("PokemonGo")
        if cog:
            cog.settings = settings

    return jsonify({"status": "success"})

@pokemon_bp.route('/api/pokemon/refresh', methods=['POST'])
async def pokemon_refresh():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    cog = app.bot.get_cog("PokemonGo")
    if not cog:
        return jsonify({"status": "error", "message": "PokemonGo Cog not loaded"}), 500

    # Trigger scrape
    await cog.scrape_events()
    events = cog.events

    return jsonify({"status": "success", "count": len(events)})

@pokemon_bp.route('/api/pokemon/push_weekly', methods=['POST'])
async def pokemon_push_weekly():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')

    if not guild_id:
        return jsonify({"status": "error", "message": "Missing guild_id"}), 400

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    cog = app.bot.get_cog("PokemonGo")
    if not cog:
        return jsonify({"status": "error", "message": "PokemonGo Cog not loaded"}), 500

    success, msg = await cog.send_weekly_summary_to_guild(guild_id, ping=False)

    if success:
        return jsonify({"status": "success", "message": msg})
    else:
        return jsonify({"status": "error", "message": msg}), 500

@pokemon_bp.route('/api/pokemon/push_next', methods=['POST'])
async def pokemon_push_next():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')

    if not guild_id:
        return jsonify({"status": "error", "message": "Missing guild_id"}), 400

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    cog = app.bot.get_cog("PokemonGo")
    if not cog:
        return jsonify({"status": "error", "message": "PokemonGo Cog not loaded"}), 500

    success, msg = await cog.send_next_event_to_guild(guild_id, ping=False)

    if success:
        return jsonify({"status": "success", "message": msg})
    else:
        return jsonify({"status": "error", "message": msg}), 500
