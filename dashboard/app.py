import os
import sys
import subprocess
import json
import secrets
import re
import zipfile
import shutil
import discord
import asyncio
import emoji
import emojis
from quart import Quart, render_template, request, redirect, url_for, session, jsonify, abort, send_from_directory
from markupsafe import escape
from loadnsave import (
    load_player_stats, save_player_stats, load_retired_characters_data, save_retired_characters_data, load_settings, load_settings_async, save_settings,
    load_server_volumes,
    load_pogo_settings, save_pogo_settings, load_pogo_events, save_pogo_events,
    load_giveaway_data,
    load_polls_data, load_reminder_data,
    load_enroll_settings, save_enroll_settings,
    load_monsters_data, load_deities_data, load_spells_data, load_weapons_data,
    load_archetype_data, load_pulp_talents_data, load_madness_insane_talent_data,
    load_manias_data, load_phobias_data, load_poisons_data,
    load_inventions_data, load_years_data, load_occupations_data,
    load_fonts_config, save_fonts_config,
)
from .file_utils import (
    sanitize_filename,
    ALLOWED_IMAGE_EXTENSIONS
)

from dashboard.state import (
    IMAGES_FOLDER, FONTS_FOLDER, OLD_FONTS_FOLDER,
    server_volumes, BASIC_FONTS, _PUBLIC_API,
    MORSE_CODE_MAP,
)

app = Quart(__name__)
app.secret_key = os.urandom(24)
app.bot = None  # Placeholder for the Discord bot instance

@app.before_serving
async def app_startup():
    # Sentinel: Secure Default Password Check
    settings = await load_settings_async()
    admin_password = settings.get('admin_password')

    if not admin_password or admin_password == "changeme":
        new_password = secrets.token_urlsafe(16)
        settings['admin_password'] = new_password
        await save_settings(settings)
        print("\n" + "="*60)
        print("🛡️  SECURITY ALERT: Default or weak admin password detected.")
        print(f"🔑  A new secure password has been generated: {new_password}")
        print("📝  This password has been updated in config.json.")
        print("="*60 + "\n")

    global server_volumes
    loaded = await load_server_volumes()
    server_volumes.update(loaded)

    # Ensure images folder exists
    if not os.path.exists(IMAGES_FOLDER):
        os.makedirs(IMAGES_FOLDER)

    # Ensure fonts folder exists
    if not os.path.exists(FONTS_FOLDER):
        os.makedirs(FONTS_FOLDER)

    # Migrate old fonts if they exist
    if os.path.exists(OLD_FONTS_FOLDER):
        try:
            for filename in os.listdir(OLD_FONTS_FOLDER):
                old_path = os.path.join(OLD_FONTS_FOLDER, filename)
                new_path = os.path.join(FONTS_FOLDER, filename)
                if os.path.isfile(old_path):
                    shutil.move(old_path, new_path)
            shutil.rmtree(OLD_FONTS_FOLDER)
            print(f"Migrated fonts from {OLD_FONTS_FOLDER} to {FONTS_FOLDER}")
        except Exception as e:
            print(f"Error migrating fonts: {e}")

@app.after_request
async def add_security_headers(response):
    """
    Sentinel: Add security headers to prevent Clickjacking, MIME sniffing, and information leakage.
    - X-Frame-Options: SAMEORIGIN
    - X-Content-Type-Options: nosniff
    - Referrer-Policy: strict-origin-when-cross-origin
    """
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

@app.before_request
async def check_csrf():
    """
    Sentinel: Mitigate CSRF by checking Origin and Referer headers for state-changing requests.
    """
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        if not session.get('logged_in'):
            return

        origin = request.headers.get('Origin')
        referrer = request.headers.get('Referer')

        # Construct trusted origin (scheme://host:port)
        trusted_origin = f"{request.scheme}://{request.host}"

        is_api = request.path.startswith('/api/')

        def csrf_deny(reason):
            if is_api:
                return jsonify({"status": "error", "message": f"Forbidden: {reason}"}), 403
            abort(403, description=reason)

        if origin:
            if origin != trusted_origin:
                return csrf_deny("CSRF: Origin Mismatch")
        elif referrer:
            if referrer != trusted_origin and not referrer.startswith(trusted_origin + "/"):
                return csrf_deny("CSRF: Referrer Mismatch")
        else:
            return csrf_deny("CSRF: No Origin/Referer")

@app.before_request
async def check_api_auth():
    if request.path.startswith('/api/') and request.path not in _PUBLIC_API and not session.get('logged_in'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

# Helper to check login
def is_admin():
    return session.get('logged_in', False)

def format_bold(text):
    if not isinstance(text, str):
        return text
    return re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)

app.add_template_filter(format_bold, 'format_bold')

def format_custom_emoji(text):
    if not isinstance(text, str):
        return text

    # 1. Handle standard Unicode shortcodes first (e.g. :muscle: -> 💪)
    text = emoji.emojize(text, language='alias')

    # Escape text to prevent XSS, as this filter is used with | safe
    text = str(escape(text))

    # 3. Handle explicit Discord format <(a):name:id> (escaped as &lt;...&gt;)
    def replace_discord_fmt(match):
        animated = match.group(1) == 'a'
        name = match.group(2)
        emoji_id = match.group(3)
        ext = 'gif' if animated else 'png'
        # Remove colons from alt/title to prevent subsequent regex matches (recursion)
        return f'<img src="https://cdn.discordapp.com/emojis/{emoji_id}.{ext}" alt="{name}" title="{name}" class="discord-emoji" style="width: 1.5em; height: 1.5em; vertical-align: middle;">'

    text = re.sub(r'&lt;([a]?):(\w+):(\d+)&gt;', replace_discord_fmt, text)

    # 4. Handle shortcodes :name: via bot lookup (Custom Emojis)
    if app.bot:
        def replace_shortcode(match):
            name = match.group(1)
            # Search in all guilds the bot is in
            emoji_obj = discord.utils.get(app.bot.emojis, name=name)
            if emoji_obj:
                ext = 'gif' if emoji_obj.animated else 'png'
                return f'<img src="https://cdn.discordapp.com/emojis/{emoji_obj.id}.{ext}" alt="{name}" title="{name}" class="discord-emoji" style="width: 1.5em; height: 1.5em; vertical-align: middle;">'
            return match.group(0) # No change if not found

        text = re.sub(r':(\w+):', replace_shortcode, text)

    # 5. Handle Discord Flag shortcodes (e.g. :flag_us: -> 🇺🇸)
    # Done last so custom emojis take precedence if they exist
    def replace_flag(match):
        name = match.group(1)
        if len(name) == 7 and name.startswith('flag_'):
             code = name[5:].lower()
             if len(code) == 2 and code.isalpha():
                  return chr(ord(code[0]) - 97 + 0x1F1E6) + chr(ord(code[1]) - 97 + 0x1F1E6)
        return match.group(0)

    text = re.sub(r':(flag_[a-zA-Z]{2}):', replace_flag, text)

    return text

app.add_template_filter(format_custom_emoji, 'format_custom_emoji')

def parse_pulp_talent(text):
    if not isinstance(text, str):
        return {"name": "Unknown", "description": str(text)}

    # Pattern: **Name**: Description
    match = re.match(r'\*\*(.*?)\*\*:\s*(.*)', text)
    if match:
        return {"name": match.group(1), "description": match.group(2)}

    # Fallback if no bold name
    return {"name": "Talent", "description": text}

app.add_template_filter(parse_pulp_talent, 'parse_pulp_talent')

def get_image_url(type_slug, name):
    """Checks if an image exists for the given type and name, returning the URL if so."""
    safe_name = sanitize_filename(name)
    target_dir = os.path.join(IMAGES_FOLDER, type_slug)

    if not os.path.exists(target_dir):
        return None

    for ext in ALLOWED_IMAGE_EXTENSIONS:
        filename = f"{safe_name}{ext}"
        if os.path.exists(os.path.join(target_dir, filename)):
            return f"/images/{type_slug}/{filename}"

    return None

from dashboard.blueprints.core import core_bp
app.register_blueprint(core_bp)

from dashboard.blueprints.characters import characters_bp
app.register_blueprint(characters_bp)

@app.context_processor
def inject_user():
    return dict(is_admin=is_admin())

@app.context_processor
async def inject_theme():
    settings = await load_settings_async()
    theme = settings.get('dashboard_theme', 'cthulhu')
    fonts = settings.get('dashboard_fonts', {
        'headers': '',
        'body': '',
        'special': ''
    })
    origin_fonts = settings.get('origin_fonts', {
        'headers': '',
        'body': '',
        'special': ''
    })
    return dict(dashboard_theme=theme, dashboard_fonts=fonts, origin_fonts=origin_fonts)

from dashboard.blueprints.render import render_bp
app.register_blueprint(render_bp)

from dashboard.blueprints.fonts_admin import fonts_admin_bp
app.register_blueprint(fonts_admin_bp)

from dashboard.blueprints.admin import admin_bp
app.register_blueprint(admin_bp)

from dashboard.blueprints.grimoire import grimoire_bp
app.register_blueprint(grimoire_bp)

from dashboard.blueprints.file_browser import file_browser_bp
app.register_blueprint(file_browser_bp)

from dashboard.blueprints.bot_config import bot_config_bp
app.register_blueprint(bot_config_bp)

from dashboard.blueprints.game_settings import game_settings_bp
app.register_blueprint(game_settings_bp)

from dashboard.blueprints.karma import karma_bp
app.register_blueprint(karma_bp)

from dashboard.blueprints.soundboard import soundboard_bp
app.register_blueprint(soundboard_bp)

from dashboard.blueprints.reaction_roles import reaction_roles_bp
app.register_blueprint(reaction_roles_bp)

from dashboard.blueprints.music import music_bp
app.register_blueprint(music_bp)

from dashboard.blueprints.rss import rss_bp
app.register_blueprint(rss_bp)

from dashboard.blueprints.gameroles import gameroles_bp
app.register_blueprint(gameroles_bp)

from dashboard.blueprints.autorooms import autorooms_bp
app.register_blueprint(autorooms_bp)

from dashboard.blueprints.deleter import deleter_bp
app.register_blueprint(deleter_bp)

from dashboard.blueprints.backup import backup_bp
app.register_blueprint(backup_bp)

# --- Pokemon GO Routes ---

@app.route('/admin/pokemon')
async def admin_pokemon():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('pokemon_dashboard.html')

@app.route('/api/pokemon/data')
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

@app.route('/api/pokemon/save', methods=['POST'])
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

@app.route('/api/pokemon/refresh', methods=['POST'])
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

@app.route('/api/pokemon/push_weekly', methods=['POST'])
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

@app.route('/api/pokemon/push_next', methods=['POST'])
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

# --- Giveaway Routes ---

@app.route('/admin/giveaway')
async def admin_giveaway():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('giveaway_dashboard.html')

@app.route('/api/giveaway/data')
async def giveaway_data():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"guilds": []})

    data = await load_giveaway_data()
    guilds_data = []

    for guild in app.bot.guilds:
        guild_id_str = str(guild.id)

        # Channels
        channels = []
        for channel in guild.text_channels:
             channels.append({"id": str(channel.id), "name": channel.name})

        # Giveaways for this guild
        guild_giveaways = []
        if guild_id_str in data:
            for msg_id, gw in data[guild_id_str].items():
                try:
                    gw_copy = gw.copy()
                    gw_copy['message_id'] = msg_id

                    # Fetch participant count
                    participants = gw.get('participants')
                    if not isinstance(participants, list):
                        participants = []
                    gw_copy['participant_count'] = len(participants)

                    # Resolve channel name
                    channel_id = gw.get('channel_id')
                    gw_copy['channel_name'] = "Unknown Channel"
                    if channel_id:
                        try:
                            chan = guild.get_channel(int(channel_id))
                            if chan:
                                gw_copy['channel_name'] = chan.name
                        except (ValueError, TypeError):
                            pass

                    # Resolve winner name
                    if 'winner_id' in gw:
                        winner_id = gw.get('winner_id')
                        if winner_id:
                            try:
                                mem = guild.get_member(int(winner_id))
                                gw_copy['winner_name'] = mem.display_name if mem else f"User {winner_id}"
                            except (ValueError, TypeError):
                                gw_copy['winner_name'] = f"User {winner_id}"

                    guild_giveaways.append(gw_copy)
                except Exception as e:
                    print(f"Error processing giveaway {msg_id} in guild {guild_id_str}: {e}")
                    continue

        # Sort by status (active first) then title
        guild_giveaways.sort(key=lambda x: (x.get('status', 'ended') == 'ended', x.get('title', 'Unknown')))

        guilds_data.append({
            "id": guild_id_str,
            "name": guild.name,
            "channels": channels,
            "giveaways": guild_giveaways
        })

    return jsonify({"guilds": guilds_data})

@app.route('/api/giveaway/create', methods=['POST'])
async def giveaway_create():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    channel_id = data.get('channel_id')
    title = data.get('title')
    description = data.get('description')
    prize_secret = data.get('prize_secret')
    duration_str = data.get('duration')

    if not all([guild_id, channel_id, title, prize_secret]):
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

        # Calculate End Time
        end_time = None
        if duration_str and str(duration_str).lower() not in ["forever", "none", "no"]:
             total_seconds = 0
             matches = re.findall(r'(\d+)\s*([dhms])', str(duration_str).lower())
             for amount, unit in matches:
                amount = int(amount)
                if unit == 'd': total_seconds += amount * 86400
                elif unit == 'h': total_seconds += amount * 3600
                elif unit == 'm': total_seconds += amount * 60
                elif unit == 's': total_seconds += amount

             if total_seconds > 0:
                 from datetime import datetime, timezone
                 end_time = datetime.now(timezone.utc).timestamp() + total_seconds

        # Create Embed
        embed = discord.Embed(title=f"🎉 GIVEAWAY: {title}", description=description, color=discord.Color.gold())
        if end_time:
             embed.add_field(name="Ends", value=f"<t:{int(end_time)}:R>", inline=False)

        embed.add_field(name="How to win?", value="React with 🎉 to enter!\nKarma increases your chance to win!", inline=False)
        embed.set_footer(text=f"Hosted by Admins")

        # Import View
        from commands.giveaway import GiveawayView
        view = GiveawayView()

        message = await channel.send(embed=embed, view=view)

        # Save Data
        gw_data = await load_giveaway_data()
        if str(guild_id) not in gw_data:
            gw_data[str(guild_id)] = {}

        from loadnsave import save_giveaway_data

        gw_data[str(guild_id)][str(message.id)] = {
            "creator_id": app.bot.user.id, # Bot created via dashboard
            "channel_id": int(channel_id),
            "title": title,
            "description": description,
            "prize_secret": prize_secret,
            "status": "active",
            "participants": [],
            "end_time": end_time
        }

        await save_giveaway_data(gw_data)

        return jsonify({"status": "success", "message_id": str(message.id)})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/giveaway/end', methods=['POST'])
async def giveaway_end():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    message_id = data.get('message_id')

    if not guild_id or not message_id:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    cog = app.bot.get_cog("Giveaway")
    if not cog:
        return jsonify({"status": "error", "message": "Giveaway Cog not loaded"}), 500

    # Execute end logic via Cog
    # I need to update Giveaway cog to have a public method or just call a helper
    # I'll rely on calling `_end_giveaway_logic` or similar which I will add to Cog,
    # OR since I am in app.py, I can just use the command function if it wasn't a command.
    # But it IS a command.

    # I'll manually implement the logic here using helper functions I'll assume exist or copy-paste (DRY violation but safe for now)
    # Actually, calling a command function is hard.
    # Best way: Add `api_end_giveaway` to Cog in next step.
    # I will assume `cog.api_end_giveaway(guild_id, message_id)` exists.

    try:
        if hasattr(cog, 'api_end_giveaway'):
             success, msg = await cog.api_end_giveaway(guild_id, message_id)
             if success:
                 return jsonify({"status": "success", "message": msg})
             else:
                 return jsonify({"status": "error", "message": msg}), 500
        else:
             return jsonify({"status": "error", "message": "API method not implemented on Cog"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/giveaway/reroll', methods=['POST'])
async def giveaway_reroll():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    message_id = data.get('message_id')

    if not guild_id or not message_id:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    cog = app.bot.get_cog("Giveaway")
    if not cog:
        return jsonify({"status": "error", "message": "Giveaway Cog not loaded"}), 500

    try:
        if hasattr(cog, 'api_reroll_giveaway'):
             success, msg = await cog.api_reroll_giveaway(guild_id, message_id)
             if success:
                 return jsonify({"status": "success", "message": msg})
             else:
                 return jsonify({"status": "error", "message": msg}), 500
        else:
             return jsonify({"status": "error", "message": "API method not implemented on Cog"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Polls Routes ---

@app.route('/admin/polls')
async def admin_polls():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('polls_dashboard.html')

@app.route('/api/polls/data')
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

@app.route('/api/polls/create', methods=['POST'])
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

@app.route('/api/polls/end', methods=['POST'])
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

# --- Reminders Routes ---

@app.route('/admin/reminders')
async def admin_reminders():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('reminders_dashboard.html')

@app.route('/api/reminders/data')
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

@app.route('/api/reminders/create', methods=['POST'])
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

@app.route('/api/reminders/delete', methods=['POST'])
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

# --- Enrollment Wizard Routes ---

@app.route('/admin/enroll')
async def admin_enroll():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('enroll_dashboard.html')

@app.route('/admin/newspaper')
async def admin_newspaper():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('newspaper_dashboard.html')

@app.route('/api/enroll/data')
async def enroll_data():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"guilds": []})

    settings = await load_enroll_settings()
    guilds_data = []

    for guild in app.bot.guilds:
        guild_id_str = str(guild.id)

        # Roles for dropdown
        roles = []
        for role in guild.roles:
            if not role.is_default() and not role.managed:
                roles.append({"id": str(role.id), "name": role.name, "color": str(role.color)})
        roles.sort(key=lambda x: x['name'])

        guild_settings = settings.get(guild_id_str, {})

        # Ensure defaults structure
        config = {
            "enabled": guild_settings.get("enabled", False),
            "final_message": guild_settings.get("final_message", "You have successfully enrolled!"),
            "pages": guild_settings.get("pages", [])
        }

        guilds_data.append({
            "id": guild_id_str,
            "name": guild.name,
            "roles": roles,
            "config": config
        })

    return jsonify({"guilds": guilds_data})

@app.route('/api/enroll/save', methods=['POST'])
async def enroll_save():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')

    if not guild_id:
        return jsonify({"status": "error", "message": "Missing guild_id"}), 400

    settings = await load_enroll_settings()

    # Update settings for this guild
    settings[str(guild_id)] = {
        "enabled": bool(data.get('enabled', False)),
        "final_message": data.get('final_message', ""),
        "pages": data.get('pages', [])
    }

    await save_enroll_settings(settings)
    return jsonify({"status": "success"})

@app.route('/api/admin/update', methods=['POST'])
async def admin_update_bot():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json(silent=True)
    update_infodata = False
    if data:
        update_infodata = data.get('update_infodata', False)

    updater_script = "updater.py"
    if not os.path.exists(updater_script):
        return jsonify({"status": "error", "message": "Updater script not found"}), 500

    pid = str(os.getpid())
    python_exe = sys.executable

    cmd = [python_exe, updater_script, pid]
    if update_infodata:
        cmd.append("--update-infodata")

    try:
        if os.name == 'nt':
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen(cmd, start_new_session=True)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    # We need to shut down the bot/app.
    # Since this is running in Hypercorn via bot.py (which imports app),
    # we can try to close the bot if available, or just exit.

    if app.bot:
        await app.bot.close()

    # We schedule a sys.exit shortly to allow the response to return
    app.add_background_task(shutdown_process)

    return jsonify({"status": "success", "message": "Update started. Bot is restarting..."})

async def shutdown_process():
    await asyncio.sleep(1)
    sys.exit(0)
