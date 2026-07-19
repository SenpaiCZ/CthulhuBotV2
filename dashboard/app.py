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

from dashboard.blueprints.pokemon import pokemon_bp
app.register_blueprint(pokemon_bp)

from dashboard.blueprints.giveaway import giveaway_bp
app.register_blueprint(giveaway_bp)

from dashboard.blueprints.polls import polls_bp
app.register_blueprint(polls_bp)

from dashboard.blueprints.reminders import reminders_bp
app.register_blueprint(reminders_bp)

from dashboard.blueprints.enroll import enroll_bp
app.register_blueprint(enroll_bp)

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
