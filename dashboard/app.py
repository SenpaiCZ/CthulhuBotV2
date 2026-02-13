import os
import sys
import subprocess
import json
import re
import zipfile
import shutil
from collections import Counter
import discord
import asyncio
import emoji
import emojis
import feedparser
import datetime
from quart import Quart, render_template, request, redirect, url_for, session, jsonify, abort, send_from_directory
from markupsafe import escape
from loadnsave import (
    load_player_stats, save_player_stats, load_retired_characters_data, save_retired_characters_data, load_settings, save_settings,
    load_soundboard_settings, save_soundboard_settings, load_music_blacklist, save_music_blacklist,
    load_server_stats, save_server_stats, load_server_volumes, save_server_volumes,
    load_karma_settings, save_karma_settings,
    load_reaction_roles, save_reaction_roles,
    load_luck_stats, save_luck_stats,
    load_rss_data, save_rss_data,
    load_deleter_data, save_deleter_data,
    autoroom_load, autoroom_save,
    load_pogo_settings, save_pogo_settings, load_pogo_events, save_pogo_events,
    load_giveaway_data,
    load_polls_data, load_reminder_data,
    load_gamerole_settings, save_gamerole_settings,
    load_enroll_settings, save_enroll_settings,
    load_loot_settings, save_loot_settings,
    load_monsters_data, load_deities_data, load_spells_data, load_weapons_data,
    load_archetype_data, load_pulp_talents_data, load_madness_insane_talent_data,
    load_manias_data, load_phobias_data, load_poisons_data, load_skills_data,
    load_inventions_data, load_years_data, load_occupations_data,
    load_bot_status, save_bot_status,
    _load_json_file, _save_json_file, DATA_FOLDER, INFODATA_FOLDER
)
from .audio_mixer import MixingAudioSource
from rss_utils import get_youtube_rss_url
from .file_utils import (
    sanitize_filename, sync_get_soundboard_files, sync_save_bytes,
    sync_extract_zip, sync_delete_path, sync_rename_path, sync_create_directory,
    ALLOWED_AUDIO_EXTENSIONS as ALLOWED_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS
)

SOUNDBOARD_FOLDER = "soundboard"
BACKUP_FOLDER = "backups"
IMAGES_FOLDER = "images"
FONTS_FOLDER = os.path.join("data", "fonts")
OLD_FONTS_FOLDER = os.path.join("dashboard", "static", "fonts")
server_volumes = {} # guild_id (str) -> {'music': 1.0, 'soundboard': 0.5}
guild_mixers = {} # guild_id (str) -> MixingAudioSource

app = Quart(__name__)
app.secret_key = os.urandom(24)
app.bot = None  # Placeholder for the Discord bot instance

@app.before_serving
async def app_startup():
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

    # Escape text to prevent XSS, as this filter is used with | safe
    text = str(escape(text))

    # 1. Handle explicit Discord format <(a):name:id> (escaped as &lt;...&gt;)
    def replace_discord_fmt(match):
        animated = match.group(1) == 'a'
        name = match.group(2)
        emoji_id = match.group(3)
        ext = 'gif' if animated else 'png'
        return f'<img src="https://cdn.discordapp.com/emojis/{emoji_id}.{ext}" alt=":{name}:" title=":{name}:" class="discord-emoji" style="width: 1.5em; height: 1.5em; vertical-align: middle;">'

    text = re.sub(r'&lt;([a]?):(\w+):(\d+)&gt;', replace_discord_fmt, text)

    # 2. Handle shortcodes :name: via bot lookup
    if app.bot:
        def replace_shortcode(match):
            name = match.group(1)
            # Search in all guilds the bot is in
            emoji_obj = discord.utils.get(app.bot.emojis, name=name)
            if emoji_obj:
                ext = 'gif' if emoji_obj.animated else 'png'
                return f'<img src="https://cdn.discordapp.com/emojis/{emoji_obj.id}.{ext}" alt=":{name}:" title=":{name}:" class="discord-emoji" style="width: 1.5em; height: 1.5em; vertical-align: middle;">'
            return match.group(0) # No change if not found

        text = re.sub(r':(\w+):', replace_shortcode, text)

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

async def get_or_join_voice_channel(guild_id, channel_id):
    if not app.bot:
        return None, "Bot not initialized"

    guild = app.bot.get_guild(int(guild_id))
    if not guild:
        return None, "Guild not found"

    channel = guild.get_channel(int(channel_id))
    if not channel:
        return None, "Channel not found"

    voice_client = guild.voice_client

    try:
        if voice_client:
            if not voice_client.is_connected():
                # Stale connection object? try to cleanup and reconnect
                await voice_client.disconnect(force=True)
                voice_client = await channel.connect()
            elif voice_client.channel.id != channel.id:
                await voice_client.move_to(channel)
        else:
            voice_client = await channel.connect()
    except Exception as e:
        return None, str(e)

    if voice_client is None:
        return None, "Failed to connect to voice channel."

    return voice_client, None

@app.context_processor
def inject_user():
    return dict(is_admin=is_admin())

@app.route('/api/status')
async def bot_status():
    is_ready = False
    if app.bot and app.bot.is_ready():
        is_ready = True
    return jsonify({"status": "online", "ready": is_ready})

@app.route('/fonts/<path:filename>')
async def serve_fonts(filename):
    return await send_from_directory(FONTS_FOLDER, filename)

@app.route('/images/<path:filename>')
async def serve_image(filename):
    return await send_from_directory(IMAGES_FOLDER, filename)

@app.route('/api/images/upload', methods=['POST'])
async def upload_image():
    if not is_admin(): return "Unauthorized", 401

    form = await request.form
    files = await request.files

    type_slug = form.get('type_slug')
    name = form.get('name')
    file = files.get('file')

    if not type_slug or not name or not file:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    if not file.filename:
        return jsonify({"status": "error", "message": "No file selected"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"status": "error", "message": "Invalid file type"}), 400

    # Ensure type directory exists
    safe_type = sanitize_filename(type_slug)
    target_dir = os.path.join(IMAGES_FOLDER, safe_type)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    # Sanitize name
    safe_name = sanitize_filename(name)
    filename = f"{safe_name}{ext}"
    target_path = os.path.join(target_dir, filename)

    # Remove any existing images with different extensions for this entry
    for other_ext in ALLOWED_IMAGE_EXTENSIONS:
        other_filename = f"{safe_name}{other_ext}"
        other_path = os.path.join(target_dir, other_filename)
        if os.path.exists(other_path):
            os.remove(other_path)

    try:
        # Save file
        file_bytes = file.read()
        if asyncio.iscoroutine(file_bytes):
            file_bytes = await file_bytes

        with open(target_path, 'wb') as f:
            f.write(file_bytes)

        return jsonify({"status": "success", "url": f"/images/{safe_type}/{filename}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/images/delete', methods=['POST'])
async def delete_image():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    type_slug = data.get('type_slug')
    name = data.get('name')

    if not type_slug or not name:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    safe_type = sanitize_filename(type_slug)
    safe_name = sanitize_filename(name)
    target_dir = os.path.join(IMAGES_FOLDER, safe_type)

    deleted = False

    if os.path.exists(target_dir):
        for ext in ALLOWED_IMAGE_EXTENSIONS:
            filename = f"{safe_name}{ext}"
            target_path = os.path.join(target_dir, filename)
            if os.path.exists(target_path):
                try:
                    os.remove(target_path)
                    deleted = True
                except Exception as e:
                    return jsonify({"status": "error", "message": str(e)}), 500

    if deleted:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Image not found"}), 404

@app.route('/api/images/check', methods=['GET'])
async def check_image():
    type_slug = request.args.get('type_slug')
    name = request.args.get('name')

    if not type_slug or not name:
        return jsonify({"found": False}), 400

    url = get_image_url(type_slug, name)
    if url:
        return jsonify({"found": True, "url": url})
    else:
        return jsonify({"found": False})

@app.route('/')
async def index():
    return await render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        form = await request.form
        password = form.get('password')
        settings = load_settings()
        if password == settings.get('admin_password', 'changeme'):
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return await render_template('login.html', error="Invalid Password")
    return await render_template('login.html')

@app.route('/logout')
async def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/characters')
async def characters():
    stats = await load_player_stats()

    # Resolve display names
    user_names = {}
    if app.bot:
        all_user_ids = set()
        for guild_users in stats.values():
            all_user_ids.update(guild_users.keys())

        for user_id in all_user_ids:
            try:
                user = app.bot.get_user(int(user_id))
                if user:
                    user_names[user_id] = user.display_name
                else:
                    user_names[user_id] = f"User {user_id}"
            except:
                user_names[user_id] = f"User {user_id}"

    return await render_template(
        'list_characters.html',
        title="Active Characters",
        data=stats,
        type="active",
        user_names=user_names,
        emojis=emojis,
        emoji_lib=emoji
    )

@app.route('/retired')
async def retired():
    stats = await load_retired_characters_data()

    # Resolve display names
    user_names = {}
    if app.bot:
        for user_id in stats.keys():
            try:
                user = app.bot.get_user(int(user_id))
                if user:
                    user_names[user_id] = user.display_name
                else:
                    user_names[user_id] = f"User {user_id}"
            except:
                user_names[user_id] = f"User {user_id}"

    return await render_template(
        'list_characters.html',
        title="Retired Characters",
        data=stats,
        type="retired",
        user_names=user_names,
        emojis=emojis,
        emoji_lib=emoji
    )

@app.route('/api/character/delete', methods=['POST'])
async def delete_character():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    char_type = data.get('type')
    name_confirmation = data.get('name')

    if not char_type or not name_confirmation:
         return jsonify({"status": "error", "message": "Missing arguments"}), 400

    if char_type == 'active':
        server_id = data.get('server_id')
        user_id = data.get('user_id')
        if not server_id or not user_id:
             return jsonify({"status": "error", "message": "Missing server_id or user_id"}), 400

        stats = await load_player_stats()
        if server_id in stats and user_id in stats[server_id]:
            char_data = stats[server_id][user_id]
            # Normalize names for comparison (strip whitespace)
            if char_data.get('NAME', '').strip() != name_confirmation.strip():
                return jsonify({"status": "error", "message": "Name confirmation failed. Names do not match."}), 400

            del stats[server_id][user_id]

            # Clean up empty guild entry
            if not stats[server_id]:
                del stats[server_id]

            await save_player_stats(stats)
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": "Character not found"}), 404

    elif char_type == 'retired':
        user_id = data.get('user_id')
        index = data.get('index')

        if not user_id or index is None:
             return jsonify({"status": "error", "message": "Missing user_id or index"}), 400

        stats = await load_retired_characters_data()
        if user_id in stats:
            try:
                idx = int(index)
                if idx < 0 or idx >= len(stats[user_id]):
                    raise ValueError

                char_data = stats[user_id][idx]
                if char_data.get('NAME', '').strip() != name_confirmation.strip():
                    return jsonify({"status": "error", "message": "Name confirmation failed. Names do not match."}), 400

                stats[user_id].pop(idx)

                # Clean up if empty list
                if not stats[user_id]:
                    del stats[user_id]

                await save_retired_characters_data(stats)
                return jsonify({"status": "success"})
            except ValueError:
                 return jsonify({"status": "error", "message": "Invalid index"}), 400
        else:
             return jsonify({"status": "error", "message": "User not found in retired data"}), 404

    else:
        return jsonify({"status": "error", "message": "Invalid type"}), 400

@app.route('/render/character/<guild_id>/<user_id>')
async def render_character_view(guild_id, user_id):
    # This endpoint is intended for local bot use
    stats = await load_player_stats()

    guild_data = stats.get(str(guild_id))
    if not guild_data:
        return "Guild not found", 404

    char_data = guild_data.get(str(user_id))
    if not char_data:
        return "Character not found", 404

    return await render_template(
        'render_character.html',
        char=char_data,
        emojis=emojis,
        emoji_lib=emoji
    )

@app.route('/render/karma/<guild_id>/<user_id>')
async def render_karma_notification(guild_id, user_id):
    # Fetch User data
    username = "Unknown User"
    avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"

    if app.bot:
        try:
            guild = app.bot.get_guild(int(guild_id))
            if guild:
                member = guild.get_member(int(user_id))
                if not member:
                    # Try fetching user if not in cache (though member implies in guild)
                    try:
                         member = await guild.fetch_member(int(user_id))
                    except:
                         pass

                if member:
                    username = member.display_name
                    if member.display_avatar:
                        avatar_url = str(member.display_avatar.url)
        except Exception as e:
            print(f"Error fetching user for karma render: {e}")

    rank_name = request.args.get('rank', 'New Rank')
    change_type = request.args.get('type', 'up')

    return await render_template(
        'karma_notification.html',
        username=username,
        avatar_url=avatar_url,
        rank_name=rank_name,
        change_type=change_type
    )

@app.route('/render/monster')
async def render_monster_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_monsters_data()
    monsters = data.get('monsters', [])

    # Find monster
    target = None
    name_lower = name.lower()

    for item in monsters:
        m = item.get('monster_entry')
        if m and m.get('name', '').lower() == name_lower:
            target = m
            break

    if not target:
        return f"Monster '{name}' not found", 404

    image_url = get_image_url("monster", target['name'])
    return await render_template('render_monster.html', monster=target, emojis=emojis, emoji_lib=emoji, image_url=image_url)

@app.route('/render/deity')
async def render_deity_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_deities_data()
    deities = data.get('deities', [])

    # Find deity
    target = None
    name_lower = name.lower()

    for item in deities:
        d = item.get('deity_entry')
        if d and d.get('name', '').lower() == name_lower:
            target = d
            break

    if not target:
        return f"Deity '{name}' not found", 404

    image_url = get_image_url("deity", target['name'])
    return await render_template('render_deity.html', deity=target, emojis=emojis, emoji_lib=emoji, image_url=image_url)

@app.route('/render/spell')
async def render_spell_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_spells_data()
    spells = data.get('spells', [])

    # Find spell
    target = None
    name_lower = name.lower()

    for item in spells:
        s = item.get('spell_entry')
        if s and s.get('name', '').lower() == name_lower:
            target = s
            break

    if not target:
        return f"Spell '{name}' not found", 404

    image_url = get_image_url("spell", target['name'])
    return await render_template('render_spell.html', spell=target, emojis=emojis, emoji_lib=emoji, image_url=image_url)

@app.route('/render/weapon')
async def render_weapon_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await _load_json_file(INFODATA_FOLDER, 'weapons.json')

    # Find weapon (case-insensitive lookup in dict keys)
    target_key = None
    name_lower = name.lower()

    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Weapon '{name}' not found", 404

    weapon = data[target_key]
    image_url = get_image_url("weapon", target_key)
    return await render_template('render_weapon.html', weapon=weapon, weapon_name=target_key, image_url=image_url)

# --- New Render Routes ---

@app.route('/render/archetype')
async def render_archetype_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_archetype_data()
    # Archetype data is Dict[Name, Info]

    target_key = None
    name_lower = name.lower()

    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Archetype '{name}' not found", 404

    # Process emojis
    archetype = data[target_key]
    if 'description' in archetype:
        archetype['description'] = emoji.emojize(archetype['description'], language='alias')
    if 'adjustments' in archetype:
        archetype['adjustments'] = [emoji.emojize(adj, language='alias') for adj in archetype['adjustments']]

    image_url = get_image_url("archetype", target_key)
    return await render_template('render_archetype.html', archetype=archetype, name=target_key, emojis=emojis, emoji_lib=emoji, image_url=image_url)

@app.route('/render/pulp_talent')
async def render_pulp_talent_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_pulp_talents_data()
    # Dict[Category, List[String]]

    target_talent = None
    name_lower = name.lower()

    for category, talents in data.items():
        for t_str in talents:
            # Parse "**Name**: Desc"
            match = re.match(r'\*\*(.*?)\*\*:\s*(.*)', t_str)
            if match:
                t_name = match.group(1)
                t_desc = match.group(2)
                if t_name.lower() == name_lower:
                    target_talent = {
                        "name": t_name,
                        "description": t_desc,
                        "category": category
                    }
                    break
        if target_talent:
            break

    if not target_talent:
        return f"Talent '{name}' not found", 404

    image_url = get_image_url("pulp_talent", target_talent['name'])
    return await render_template('render_pulp_talent.html', talent=target_talent, emojis=emojis, emoji_lib=emoji, image_url=image_url)

@app.route('/render/insane_talent')
async def render_insane_talent_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_madness_insane_talent_data()

    target_key = None
    name_lower = name.lower()
    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Insane Talent '{name}' not found", 404

    image_url = get_image_url("insane_talent", target_key)
    return await render_template('render_simple_entry.html', title=target_key, description=data[target_key], type="Insane Talent", emojis=emojis, emoji_lib=emoji, image_url=image_url)

@app.route('/render/mania')
async def render_mania_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_manias_data()

    target_key = None
    name_lower = name.lower()
    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Mania '{name}' not found", 404

    image_url = get_image_url("mania", target_key)
    return await render_template('render_simple_entry.html', title=target_key, description=data[target_key], type="Mania", emojis=emojis, emoji_lib=emoji, image_url=image_url)

@app.route('/render/phobia')
async def render_phobia_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_phobias_data()

    target_key = None
    name_lower = name.lower()
    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Phobia '{name}' not found", 404

    image_url = get_image_url("phobia", target_key)
    return await render_template('render_simple_entry.html', title=target_key, description=data[target_key], type="Phobia", emojis=emojis, emoji_lib=emoji, image_url=image_url)

@app.route('/render/poison')
async def render_poison_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_poisons_data()

    target_key = None
    name_lower = name.lower()
    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Poison '{name}' not found", 404

    image_url = get_image_url("poison", target_key)
    return await render_template('render_poison.html', title=target_key, poison=data[target_key], type="Poison", emojis=emojis, emoji_lib=emoji, image_url=image_url)

@app.route('/render/skill')
async def render_skill_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_skills_data()

    target_key = None
    name_lower = name.lower()
    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Skill '{name}' not found", 404

    image_url = get_image_url("skill", target_key)
    return await render_template('render_simple_entry.html', title=target_key, description=data[target_key], type="Skill", emojis=emojis, emoji_lib=emoji, image_url=image_url)

@app.route('/render/invention')
async def render_invention_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_inventions_data()

    target_key = None
    name_lower = name.lower()
    # Inventions keys are decades (e.g. "1920s")
    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Invention decade '{name}' not found", 404

    image_url = get_image_url("invention", target_key)
    return await render_template('render_timeline.html', title=target_key, events=data[target_key], type="Inventions", emojis=emojis, emoji_lib=emoji, image_url=image_url)

@app.route('/render/year')
async def render_year_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_years_data()

    target_key = None
    name_lower = name.lower()
    # Keys are years (e.g. "1920")
    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Year '{name}' not found", 404

    image_url = get_image_url("year", target_key)
    return await render_template('render_timeline.html', title=target_key, events=data[target_key], type="Timeline", emojis=emojis, emoji_lib=emoji, image_url=image_url)

@app.route('/render/occupation')
async def render_occupation_view():
    name = request.args.get('name')
    if not name:
        return "Missing name parameter", 400

    data = await load_occupations_data()

    target_key = None
    name_lower = name.lower()

    for key in data.keys():
        if key.lower() == name_lower:
            target_key = key
            break

    if not target_key:
        return f"Occupation '{name}' not found", 404

    image_url = get_image_url("occupation", target_key)
    return await render_template('render_occupation.html', occupation=data[target_key], name=target_key, image_url=image_url)

@app.route('/render/newspaper')
async def render_newspaper_view():
    headline = request.args.get('headline', 'Extra! Extra!')
    body = request.args.get('body', 'No content provided.')
    date = request.args.get('date', 'October 24, 1929')
    city = request.args.get('city', 'Arkham')
    name = request.args.get('name', 'The Arkham Advertiser')
    width = request.args.get('width', '500')
    clip_path = request.args.get('clip_path', '0% 0%, 100% 0%, 100% 100%, 0% 100%')

    return await render_template(
        'render_newspaper.html',
        headline=headline,
        body=body,
        date=date,
        city=city,
        name=name,
        width=width,
        clip_path=clip_path
    )

@app.route('/render/telegram')
async def render_telegram_view():
    body = request.args.get('body', 'STOP')
    date = request.args.get('date', 'OCT 24 1929')
    origin = request.args.get('origin', 'ARKHAM')
    recipient = request.args.get('recipient', 'INVESTIGATOR')
    sender = request.args.get('sender', 'UNKNOWN')

    return await render_template(
        'render_telegram.html',
        body=body,
        date=date,
        origin=origin,
        recipient=recipient,
        sender=sender
    )

@app.route('/render/letter')
async def render_letter_view():
    body = request.args.get('body', 'Dearest Friend...')
    date = request.args.get('date', 'October 24, 1929')
    salutation = request.args.get('salutation', 'To whom it may concern,')
    signature = request.args.get('signature', 'Sincerely, Unknown')

    return await render_template(
        'render_letter.html',
        body=body,
        date=date,
        salutation=salutation,
        signature=signature
    )

@app.route('/render/script')
async def render_script_view():
    text = request.args.get('text', 'Ph\'nglui mglw\'nafh Cthulhu R\'lyeh wgah\'nagl fhtagn')
    font = request.args.get('font', 'default') # Font filename or key

    # Verify font exists in FONTS_FOLDER
    font_filename = None
    if font != 'default':
        safe_font = sanitize_filename(font)
        # Check extensions
        for ext in ['.ttf', '.otf', '.woff', '.woff2']:
             if os.path.exists(os.path.join(FONTS_FOLDER, safe_font + ext)):
                 font_filename = safe_font + ext
                 break
             # Also check if exact filename passed
             if os.path.exists(os.path.join(FONTS_FOLDER, safe_font)):
                 font_filename = safe_font
                 break

    return await render_template(
        'render_script.html',
        text=text,
        font_filename=font_filename,
        font_name=font if font_filename else 'Default'
    )


# --- Font Management Routes ---

@app.route('/admin/fonts')
async def admin_fonts():
    if not is_admin(): return redirect(url_for('login'))
    return await render_template('fonts_dashboard.html')

@app.route('/api/fonts/list')
async def fonts_list():
    if not is_admin(): return "Unauthorized", 401

    files = []
    if os.path.exists(FONTS_FOLDER):
        for f in os.listdir(FONTS_FOLDER):
            if f.lower().endswith(('.ttf', '.otf', '.woff', '.woff2')):
                files.append(f)
    files.sort()
    return jsonify({"fonts": files})

@app.route('/api/fonts/upload', methods=['POST'])
async def fonts_upload():
    if not is_admin(): return "Unauthorized", 401

    files = await request.files
    uploaded_files = files.getlist('files')

    if not uploaded_files:
        return jsonify({"status": "error", "message": "No files uploaded"}), 400

    results = []
    for file in uploaded_files:
        if not file.filename: continue

        filename = sanitize_filename(file.filename)
        # Preserve extension properly (sanitize might strip dots if not careful, but usually file_utils preserves it or we assume it doesn't)
        # Let's check sanitize_filename in file_utils... assumed safe.
        # But wait, sanitize_filename often replaces '.'
        # I should probably split ext first.

        base, ext = os.path.splitext(file.filename)
        safe_base = sanitize_filename(base)
        ext = ext.lower()

        if ext not in ['.ttf', '.otf', '.woff', '.woff2']:
            results.append(f"Skipped {file.filename} (invalid type)")
            continue

        safe_filename = f"{safe_base}{ext}"
        target_path = os.path.join(FONTS_FOLDER, safe_filename)

        try:
            file_bytes = file.read()
            if asyncio.iscoroutine(file_bytes):
                file_bytes = await file_bytes

            with open(target_path, 'wb') as f:
                f.write(file_bytes)
            results.append(f"Uploaded {safe_filename}")
        except Exception as e:
            results.append(f"Error {file.filename}: {e}")

    return jsonify({"status": "success", "results": results})

@app.route('/api/fonts/delete', methods=['POST'])
async def fonts_delete():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    filename = data.get('filename')

    if not filename:
        return jsonify({"status": "error", "message": "Missing filename"}), 400

    if '..' in filename or '/' in filename:
        return jsonify({"status": "error", "message": "Invalid filename"}), 400

    target_path = os.path.join(FONTS_FOLDER, filename)

    if os.path.exists(target_path):
        try:
            os.remove(target_path)
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "error", "message": "File not found"}), 404

# --- Admin Routes ---

@app.route('/admin')
async def admin_dashboard():
    if not is_admin(): return redirect(url_for('login'))
    return await render_template('admin_dashboard.html')

@app.route('/monsters')
async def admin_monsters():
    monsters_data = await _load_json_file(INFODATA_FOLDER, 'monsters.json')
    stat_emojis = {k: emoji.emojize(v, language='alias') for k, v in emojis.stat_emojis.items()}
    return await render_template('monsters.html', data=monsters_data, stat_emojis=stat_emojis, type_slug="monster")

@app.route('/deities')
async def admin_deities():
    deities_data = await _load_json_file(INFODATA_FOLDER, 'deities.json')
    stat_emojis = {k: emoji.emojize(v, language='alias') for k, v in emojis.stat_emojis.items()}
    return await render_template('deities.html', data=deities_data, stat_emojis=stat_emojis, type_slug="deity")

@app.route('/spells')
async def admin_spells():
    spells_data = await _load_json_file(INFODATA_FOLDER, 'spells.json')
    stat_emojis = {k: emoji.emojize(v, language='alias') for k, v in emojis.stat_emojis.items()}
    return await render_template('spells.html', data=spells_data, stat_emojis=stat_emojis, type_slug="spell")

@app.route('/weapons')
async def admin_weapons():
    weapons_data = await _load_json_file(INFODATA_FOLDER, 'weapons.json')
    if not weapons_data:
        print(f"Warning: Weapons data is empty or file not found. Path: {os.path.join(INFODATA_FOLDER, 'weapons.json')} CWD: {os.getcwd()}")
    return await render_template('weapons.html', data=weapons_data, type_slug="weapon")

# --- New Admin Views ---

@app.route('/archetypes')
async def admin_archetypes():
    data = await load_archetype_data()
    # Process emojis in descriptions and adjustments
    for key, archetype in data.items():
        if 'description' in archetype:
            archetype['description'] = emoji.emojize(archetype['description'], language='alias')
        if 'adjustments' in archetype:
            archetype['adjustments'] = [emoji.emojize(adj, language='alias') for adj in archetype['adjustments']]
    return await render_template('archetypes.html', data=data, type_slug="archetype")

@app.route('/pulp_talents')
async def admin_pulp_talents():
    data = await load_pulp_talents_data()
    return await render_template('pulp_talents.html', data=data, type_slug="pulp_talent")

@app.route('/insane_talents')
async def admin_insane_talents():
    data = await load_madness_insane_talent_data()
    return await render_template('generic_list.html', data=data, title="Insane Talents", type_slug="insane_talent")

@app.route('/manias')
async def admin_manias():
    data = await load_manias_data()
    return await render_template('generic_list.html', data=data, title="Manias", type_slug="mania")

@app.route('/phobias')
async def admin_phobias():
    data = await load_phobias_data()
    return await render_template('generic_list.html', data=data, title="Phobias", type_slug="phobia")

@app.route('/poisons')
async def admin_poisons():
    data = await load_poisons_data()
    return await render_template('poisons.html', data=data, title="Poisons", type_slug="poison")

@app.route('/skills')
async def admin_skills():
    data = await load_skills_data()
    # Process emojis in descriptions
    processed_data = {}
    for key, description in data.items():
        processed_data[key] = emoji.emojize(description, language='alias')
    return await render_template('generic_list.html', data=processed_data, title="Skills", type_slug="skill")

@app.route('/inventions')
async def admin_inventions():
    data = await load_inventions_data()
    return await render_template('timeline_list.html', data=data, title="Inventions", type_slug="invention")

@app.route('/years')
async def admin_years():
    data = await load_years_data()
    return await render_template('timeline_list.html', data=data, title="Years Timeline", type_slug="year")

@app.route('/occupations')
async def admin_occupations():
    data = await load_occupations_data()
    return await render_template('occupations.html', data=data, type_slug="occupation")

@app.route('/admin/browse/<folder_name>')
async def browse_files(folder_name):
    if not is_admin(): return redirect(url_for('login'))

    if folder_name == 'root':
        files = ['config.json'] if os.path.exists('config.json') else []
        return await render_template('file_browser.html', folder=folder_name, files=files)

    if folder_name == 'infodata':
        target_dir = INFODATA_FOLDER
    elif folder_name == 'data':
        target_dir = DATA_FOLDER
    else:
        return "Invalid folder", 400

    if not os.path.exists(target_dir):
        files = []
    else:
        files = [f for f in os.listdir(target_dir) if f.endswith('.json')]

    files.sort()
    return await render_template('file_browser.html', folder=folder_name, files=files)

@app.route('/admin/edit/<folder_name>/<filename>')
async def edit_file(folder_name, filename):
    if not is_admin(): return redirect(url_for('login'))

    if folder_name == 'infodata':
        target_dir = INFODATA_FOLDER
    elif folder_name == 'data':
        target_dir = DATA_FOLDER
    elif folder_name == 'root' and filename == 'config.json':
        target_dir = '.'
    else:
        return "Invalid folder", 400

    # Security check
    if '..' in filename or '/' in filename:
        return "Invalid filename", 400

    content = await _load_json_file(target_dir, filename)
    formatted_json = json.dumps(content, indent=4)
    return await render_template('json_editor.html', folder=folder_name, filename=filename, content=formatted_json)

@app.route('/api/save/<folder_name>/<filename>', methods=['POST'])
async def save_file(folder_name, filename):
    if not is_admin(): return "Unauthorized", 401

    if folder_name == 'infodata':
        target_dir = INFODATA_FOLDER
    elif folder_name == 'data':
        target_dir = DATA_FOLDER
    else:
        return "Invalid folder", 400

    if '..' in filename or '/' in filename:
        return "Invalid filename", 400

    try:
        data = await request.get_json()
        json_content = data.get('content')
        # Validate JSON
        parsed = json.loads(json_content)

        await _save_json_file(target_dir, filename, parsed)
        return jsonify({"status": "success"})
    except json.JSONDecodeError:
        return jsonify({"status": "error", "message": "Invalid JSON format"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Bot Config Routes ---

@app.route('/admin/bot_config')
async def admin_bot_config():
    if not is_admin(): return redirect(url_for('login'))

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

@app.route('/api/save_status', methods=['POST'])
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

@app.route('/api/save_prefix', methods=['POST'])
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

# --- Game Settings Routes ---

@app.route('/admin/game_settings')
async def admin_game_settings():
    if not is_admin(): return redirect(url_for('login'))
    return await render_template('game_settings.html')

@app.route('/api/game/settings/data')
async def game_settings_data():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"guilds": []})

    luck_stats = await load_luck_stats()
    guilds_data = []

    for guild in app.bot.guilds:
        guild_id_str = str(guild.id)
        current_luck = luck_stats.get(guild_id_str, 10)

        guilds_data.append({
            "id": guild_id_str,
            "name": guild.name,
            "luck_threshold": current_luck
        })

    return jsonify({"guilds": guilds_data})

@app.route('/api/game/luck/save', methods=['POST'])
async def save_luck_threshold():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    luck_value = data.get('luck_value')

    if not guild_id or luck_value is None:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    try:
        luck_val = int(luck_value)
        if luck_val < 0: raise ValueError
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid integer"}), 400

    luck_stats = await load_luck_stats()
    luck_stats[str(guild_id)] = luck_val
    await save_luck_stats(luck_stats)

    return jsonify({"status": "success"})

# --- Loot Settings Routes ---

@app.route('/api/game/loot/data')
async def game_loot_data():
    if not is_admin(): return "Unauthorized", 401

    data = await load_loot_settings()
    return jsonify(data)

@app.route('/api/game/loot/save', methods=['POST'])
async def game_loot_save():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()

    # Validation
    try:
        # Construct sanitized object to save
        save_data = {
            "items": data.get("items", []),
            "money_chance": int(data.get("money_chance", 25)),
            "money_min": float(data.get("money_min", 0.01)),
            "money_max": float(data.get("money_max", 5.00)),
            "currency_symbol": str(data.get("currency_symbol", "$")),
            "num_items_min": int(data.get("num_items_min", 1)),
            "num_items_max": int(data.get("num_items_max", 5))
        }

        await save_loot_settings(save_data)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# --- Karma Routes ---

@app.route('/admin/karma')
async def admin_karma():
    if not is_admin(): return redirect(url_for('login'))

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

@app.route('/api/karma/save', methods=['POST'])
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

@app.route('/api/karma/roles/save', methods=['POST'])
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

@app.route('/api/karma/users/<guild_id>')
async def get_karma_users(guild_id):
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify([])

    cog = app.bot.get_cog("Karma")
    if cog:
        data = await cog.get_guild_leaderboard_data(guild_id)
        return jsonify(data)

    return jsonify([])

@app.route('/api/karma/recalculate', methods=['POST'])
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

@app.route('/api/karma/detect_emojis', methods=['POST'])
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

# --- Soundboard Routes ---

@app.route('/admin/soundboard')
async def soundboard_page():
    if not is_admin(): return redirect(url_for('login'))
    return await render_template('soundboard.html')

@app.route('/api/soundboard/data')
async def soundboard_data():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"guilds": [], "files": {}, "status": {}, "settings": {}})

    guilds_data = []
    status_data = {}

    for guild in app.bot.guilds:
        channels = []
        for channel in guild.voice_channels:
             channels.append({"id": str(channel.id), "name": channel.name})

        guilds_data.append({
            "id": str(guild.id),
            "name": guild.name,
            "channels": channels
        })

        voice_client = guild.voice_client

        # Get active tracks
        mixer = guild_mixers.get(str(guild.id))
        tracks = []
        if mixer:
            # Filter out finished tracks that might be lingering before cleanup
            active_tracks = [t for t in mixer.tracks if not t.finished]
            for t in active_tracks:
                tracks.append({
                    "id": t.id,
                    "name": os.path.basename(t.file_path),
                    "volume": int(t.volume * 100),
                    "loop": t.loop,
                    "paused": t.paused
                })

        vol_data = server_volumes.get(str(guild.id), {'music': 1.0, 'soundboard': 0.5})
        sb_vol = vol_data.get('soundboard', 0.5)
        status = {
            "is_connected": voice_client is not None,
            "channel_id": str(voice_client.channel.id) if voice_client else None,
            "is_playing": voice_client.is_playing() if voice_client else False,
            "volume": int(sb_vol * 100),
            "tracks": tracks
        }
        status_data[str(guild.id)] = status

    files = await asyncio.to_thread(sync_get_soundboard_files, SOUNDBOARD_FOLDER)
    settings = await load_soundboard_settings()

    return jsonify({
        "guilds": guilds_data,
        "files": files,
        "status": status_data,
        "settings": settings
    })

@app.route('/api/soundboard/folder/color', methods=['POST'])
async def soundboard_folder_color():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    folder_name = data.get('folder_name')
    color = data.get('color')

    if not folder_name or not color:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    settings = await load_soundboard_settings()
    if 'folder_colors' not in settings:
        settings['folder_colors'] = {}

    settings['folder_colors'][folder_name] = color
    await save_soundboard_settings(settings)

    return jsonify({"status": "success"})

@app.route('/api/soundboard/file/settings', methods=['POST'])
async def soundboard_file_settings():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    file_path = data.get('file_path')
    volume = data.get('volume')
    loop = data.get('loop')

    if not file_path or volume is None or loop is None:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    # Security check
    if '..' in file_path:
        return jsonify({"status": "error", "message": "Invalid file path"}), 400

    try:
        vol_int = int(volume)
        if vol_int < 0 or vol_int > 100: raise ValueError
        loop_bool = bool(loop)
    except ValueError:
         return jsonify({"status": "error", "message": "Invalid volume or loop value"}), 400

    settings = await load_soundboard_settings()
    if 'files' not in settings:
        settings['files'] = {}

    # If defaults (100% vol, loop off), remove entry to save space
    if vol_int == 100 and not loop_bool:
        if file_path in settings['files']:
            del settings['files'][file_path]
    else:
        settings['files'][file_path] = {
            "volume": vol_int,
            "loop": loop_bool
        }

    # Clean up if files dict is empty (optional, but cleaner)
    if not settings['files']:
        del settings['files']

    await save_soundboard_settings(settings)

    return jsonify({"status": "success"})

@app.route('/api/soundboard/play', methods=['POST'])
async def soundboard_play():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    channel_id = data.get('channel_id')
    file_path = data.get('file_path')

    if not guild_id or not channel_id or not file_path:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    # Security check for file path
    if '..' in file_path:
        return jsonify({"status": "error", "message": "Invalid file path"}), 400

    full_path = os.path.join(SOUNDBOARD_FOLDER, file_path)
    if not os.path.exists(full_path):
        return jsonify({"status": "error", "message": "File not found"}), 404

    voice_client, error = await get_or_join_voice_channel(guild_id, channel_id)
    if error:
        return jsonify({"status": "error", "message": error}), 500

    # Get or create mixer
    mixer = guild_mixers.get(str(guild_id))
    if not mixer:
        mixer = MixingAudioSource()
        guild_mixers[str(guild_id)] = mixer

    # Check if we are playing the mixer
    is_playing_mixer = False
    if voice_client.is_playing() and isinstance(voice_client.source, discord.PCMVolumeTransformer):
         if voice_client.source.original == mixer:
             is_playing_mixer = True

    if not is_playing_mixer:
        if voice_client.is_playing():
            voice_client.stop()

        # Wait a moment for stop to propagate?
        # Usually fine.

        # Mixer handles volume per track now
        source = discord.PCMVolumeTransformer(mixer, volume=1.0)
        voice_client.play(source)

    # Add track
    loop_setting = data.get('loop', True)
    volume_modifier = data.get('volume_modifier', 1.0) # Individual file volume modifier

    try:
        volume_modifier = float(volume_modifier)
        volume_modifier = max(0.0, min(1.0, volume_modifier))
    except ValueError:
        volume_modifier = 1.0

    vol_data = server_volumes.get(str(guild_id), {'music': 1.0, 'soundboard': 0.5})
    sb_vol = vol_data.get('soundboard', 0.5)

    final_vol = sb_vol * volume_modifier

    mixer.add_track(
        full_path,
        volume=final_vol,
        loop=loop_setting,
        metadata={
            'type': 'soundboard',
            'volume_modifier': volume_modifier
        }
    )

    return jsonify({"status": "success"})

@app.route('/api/soundboard/join', methods=['POST'])
async def soundboard_join():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    channel_id = data.get('channel_id')

    if not guild_id or not channel_id:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    voice_client, error = await get_or_join_voice_channel(guild_id, channel_id)
    if error:
        return jsonify({"status": "error", "message": error}), 500

    return jsonify({"status": "success"})

@app.route('/api/soundboard/leave', methods=['POST'])
async def soundboard_leave():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')

    if not guild_id:
        return jsonify({"status": "error", "message": "Missing guild_id"}), 400

    guild = app.bot.get_guild(int(guild_id))
    if guild and guild.voice_client:
        await guild.voice_client.disconnect()
        # Clean up mixer
        mixer = guild_mixers.pop(str(guild_id), None)
        if mixer: mixer.cleanup()

    return jsonify({"status": "success"})

@app.route('/api/soundboard/stop', methods=['POST'])
async def soundboard_stop():
    """Stops all sounds but keeps connection."""
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')

    if not guild_id:
        return jsonify({"status": "error", "message": "Missing guild_id"}), 400

    # Just clear the tracks in the mixer
    mixer = guild_mixers.get(str(guild_id))
    if mixer:
        mixer.cleanup() # Clears tracks

    # We don't need to stop voice_client if it's playing mixer (it will just play silence)

    return jsonify({"status": "success"})

@app.route('/api/soundboard/volume', methods=['POST'])
async def soundboard_volume():
    """Master volume control"""
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    volume = data.get('volume') # 0-100

    if not guild_id or volume is None:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    try:
        vol_float = float(volume) / 100.0
        vol_float = max(0.0, min(1.0, vol_float))

        if str(guild_id) not in server_volumes:
            server_volumes[str(guild_id)] = {'music': 1.0, 'soundboard': 0.5}

        server_volumes[str(guild_id)]['soundboard'] = vol_float
        await save_server_volumes(server_volumes)

        # Update active soundboard tracks
        mixer = guild_mixers.get(str(guild_id))
        if mixer:
            with mixer.lock:
                for track in mixer.tracks:
                    if track.metadata.get('type') == 'soundboard':
                        mod = track.metadata.get('volume_modifier', 1.0)
                        track.volume = vol_float * mod

        # Note: We do NOT update the PCMVolumeTransformer volume anymore, as it stays at 1.0.

        return jsonify({"status": "success"})
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid volume"}), 400

# --- File Management Routes ---

@app.route('/api/soundboard/folder/create', methods=['POST'])
async def soundboard_create_folder():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    folder_name = data.get('folder_name')

    if not folder_name:
        return jsonify({"status": "error", "message": "Missing folder_name"}), 400

    safe_name = sanitize_filename(folder_name)
    target_path = os.path.join(SOUNDBOARD_FOLDER, safe_name)

    if os.path.exists(target_path):
        return jsonify({"status": "error", "message": "Folder already exists"}), 400

    success, error = await asyncio.to_thread(sync_create_directory, target_path)
    if success:
        return jsonify({"status": "success", "folder": safe_name})
    else:
        return jsonify({"status": "error", "message": error}), 500

@app.route('/api/soundboard/folder/delete', methods=['POST'])
async def soundboard_delete_folder():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    folder_name = data.get('folder_name')

    if not folder_name:
        return jsonify({"status": "error", "message": "Missing folder_name"}), 400

    safe_name = sanitize_filename(folder_name)
    target_path = os.path.join(SOUNDBOARD_FOLDER, safe_name)

    # Protect root
    if os.path.abspath(target_path) == os.path.abspath(SOUNDBOARD_FOLDER):
         return jsonify({"status": "error", "message": "Cannot delete root folder"}), 400

    if not os.path.exists(target_path):
        return jsonify({"status": "error", "message": "Folder not found"}), 404

    success, error = await asyncio.to_thread(sync_delete_path, target_path)
    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": error}), 500

@app.route('/api/soundboard/file/delete', methods=['POST'])
async def soundboard_delete_file():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    file_path = data.get('file_path')

    if not file_path:
        return jsonify({"status": "error", "message": "Missing file_path"}), 400

    # Basic path validation
    if '..' in file_path:
        return jsonify({"status": "error", "message": "Invalid path"}), 400

    full_path = os.path.join(SOUNDBOARD_FOLDER, file_path)

    # Ensure it is inside soundboard folder
    if not os.path.abspath(full_path).startswith(os.path.abspath(SOUNDBOARD_FOLDER)):
        return jsonify({"status": "error", "message": "Path traversal detected"}), 400

    if not os.path.exists(full_path):
        return jsonify({"status": "error", "message": "File not found"}), 404

    if not os.path.isfile(full_path):
        return jsonify({"status": "error", "message": "Not a file"}), 400

    success, error = await asyncio.to_thread(sync_delete_path, full_path)
    if success:
        # Clean up settings if any
        settings = await load_soundboard_settings()
        if 'files' in settings and file_path in settings['files']:
            del settings['files'][file_path]
            await save_soundboard_settings(settings)

        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": error}), 500

@app.route('/api/soundboard/file/rename', methods=['POST'])
async def soundboard_rename_file():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    file_path = data.get('file_path')
    new_name = data.get('new_name')

    if not file_path or not new_name:
        return jsonify({"status": "error", "message": "Missing file_path or new_name"}), 400

    # Basic path validation
    if '..' in file_path:
        return jsonify({"status": "error", "message": "Invalid path"}), 400

    full_old_path = os.path.join(SOUNDBOARD_FOLDER, file_path)

    # Ensure it is inside soundboard folder
    if not os.path.abspath(full_old_path).startswith(os.path.abspath(SOUNDBOARD_FOLDER)):
        return jsonify({"status": "error", "message": "Path traversal detected"}), 400

    if not os.path.exists(full_old_path):
        return jsonify({"status": "error", "message": "File not found"}), 404

    if not os.path.isfile(full_old_path):
        return jsonify({"status": "error", "message": "Target is not a file"}), 400

    # Sanitize new name and preserve extension
    safe_new_name = sanitize_filename(new_name)
    ext = os.path.splitext(file_path)[1]

    new_filename = f"{safe_new_name}{ext}"

    # Determine directory of the file (it might be in a subfolder)
    directory = os.path.dirname(full_old_path)
    full_new_path = os.path.join(directory, new_filename)

    # Relative path for settings
    rel_directory = os.path.dirname(file_path)

    if rel_directory:
        new_rel_path = os.path.join(rel_directory, new_filename)
    else:
        new_rel_path = new_filename

    # Fix potential path separator issues for settings key consistency
    new_rel_path = new_rel_path.replace('\\', '/')

    if os.path.exists(full_new_path):
        return jsonify({"status": "error", "message": "A file with that name already exists"}), 400

    success, error = await asyncio.to_thread(sync_rename_path, full_old_path, full_new_path)
    if success:
        # Migrate settings
        settings = await load_soundboard_settings()
        if 'files' in settings and file_path in settings['files']:
            settings['files'][new_rel_path] = settings['files'][file_path]
            del settings['files'][file_path]
            await save_soundboard_settings(settings)

        return jsonify({"status": "success", "new_path": new_rel_path})
    else:
        return jsonify({"status": "error", "message": error}), 500

@app.route('/api/soundboard/upload', methods=['POST'])
async def soundboard_upload():
    if not is_admin(): return "Unauthorized", 401

    form = await request.form
    files = await request.files
    folder = form.get('folder', '') # Optional subfolder (must exist, or be root)

    uploaded_files = files.getlist('files')
    if not uploaded_files:
        return jsonify({"status": "error", "message": "No files uploaded"}), 400

    results = []

    for file in uploaded_files:
        if not file.filename: continue

        filename = sanitize_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()

        if ext == '.zip':
            zip_folder_name = os.path.splitext(filename)[0]
            extract_dir = os.path.join(SOUNDBOARD_FOLDER, zip_folder_name)
            temp_zip_path = os.path.join(SOUNDBOARD_FOLDER, f"temp_{filename}")

            try:
                # Read content
                file_bytes = file.read()
                if asyncio.iscoroutine(file_bytes):
                    file_bytes = await file_bytes

                # Save zip
                success, error = await asyncio.to_thread(sync_save_bytes, file_bytes, temp_zip_path)
                if not success:
                    results.append(f"Error saving zip {filename}: {error}")
                    continue

                # Extract
                success, extract_results = await asyncio.to_thread(sync_extract_zip, temp_zip_path, extract_dir)
                if success:
                    results.append(f"Unzipped {filename} to {zip_folder_name}/")
                else:
                    results.append(f"Error unzipping {filename}: {extract_results[0]}")

                # Cleanup
                await asyncio.to_thread(sync_delete_path, temp_zip_path)
            except Exception as e:
                results.append(f"Error processing zip {filename}: {str(e)}")

        elif ext in ALLOWED_EXTENSIONS:
            # Determine target directory
            save_dir = SOUNDBOARD_FOLDER
            if folder and folder != 'Root':
                safe_folder = sanitize_filename(folder)
                potential_dir = os.path.join(SOUNDBOARD_FOLDER, safe_folder)
                if os.path.exists(potential_dir) and os.path.isdir(potential_dir):
                    save_dir = potential_dir

            target_path = os.path.join(save_dir, filename)

            try:
                # Read content
                file_bytes = file.read()
                if asyncio.iscoroutine(file_bytes):
                    file_bytes = await file_bytes

                success, error = await asyncio.to_thread(sync_save_bytes, file_bytes, target_path)
                if success:
                    results.append(f"Uploaded {filename}")
                else:
                    results.append(f"Error saving {filename}: {error}")
            except Exception as e:
                results.append(f"Error uploading {filename}: {str(e)}")
        else:
            results.append(f"Skipped {filename} (invalid type)")

    return jsonify({"status": "success", "results": results})

# --- Track Control Endpoints ---

@app.route('/api/soundboard/track/volume', methods=['POST'])
async def track_volume():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    track_id = data.get('track_id')
    volume = data.get('volume') # 0-100

    mixer = guild_mixers.get(str(guild_id))
    if not mixer:
        return jsonify({"status": "error", "message": "No active mixer"}), 404

    track = mixer.get_track(track_id)
    if not track:
        return jsonify({"status": "error", "message": "Track not found"}), 404

    try:
        vol_float = float(volume) / 100.0
        track.volume = max(0.0, min(1.0, vol_float))
        return jsonify({"status": "success"})
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid volume"}), 400

@app.route('/api/soundboard/track/loop', methods=['POST'])
async def track_loop():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    track_id = data.get('track_id')
    loop = data.get('loop') # boolean

    mixer = guild_mixers.get(str(guild_id))
    if not mixer: return jsonify({"status": "error", "message": "No active mixer"}), 404

    track = mixer.get_track(track_id)
    if not track: return jsonify({"status": "error", "message": "Track not found"}), 404

    track.loop = bool(loop)
    return jsonify({"status": "success"})

@app.route('/api/soundboard/track/pause', methods=['POST'])
async def track_pause():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    track_id = data.get('track_id')
    paused = data.get('paused') # boolean

    mixer = guild_mixers.get(str(guild_id))
    if not mixer: return jsonify({"status": "error", "message": "No active mixer"}), 404

    track = mixer.get_track(track_id)
    if not track: return jsonify({"status": "error", "message": "Track not found"}), 404

    track.paused = bool(paused)
    return jsonify({"status": "success"})

@app.route('/api/soundboard/track/remove', methods=['POST'])
async def track_remove():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    track_id = data.get('track_id')

    mixer = guild_mixers.get(str(guild_id))
    if not mixer: return jsonify({"status": "error", "message": "No active mixer"}), 404

    if mixer.remove_track(track_id):
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Track not found"}), 404

# --- Reaction Roles Routes ---

@app.route('/admin/reactionroles')
async def admin_reaction_roles():
    if not is_admin(): return redirect(url_for('login'))
    return await render_template('reaction_roles.html')

@app.route('/api/reactionroles/data')
async def reaction_roles_data():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"guilds": [], "rules": []})

    data = await load_reaction_roles()
    rules = []

    # Iterate through data to build the rules list
    for guild_id, messages in data.items():
        guild = None
        if app.bot:
            guild = app.bot.get_guild(int(guild_id))
        guild_name = guild.name if guild else f"Unknown Guild ({guild_id})"

        for message_id, message_data in messages.items():
            roles = {}
            if "roles" in message_data:
                roles = message_data["roles"]
            else:
                roles = message_data

            for emoji_str, role_id in roles.items():
                role_name = "Unknown Role"
                if guild:
                    role = guild.get_role(int(role_id))
                    if role:
                        role_name = role.name
                    else:
                         role_name = f"Deleted Role ({role_id})"

                rules.append({
                    "guild_id": guild_id,
                    "guild_name": guild_name,
                    "message_id": message_id,
                    "emoji": emoji_str,
                    "role_id": role_id,
                    "role_name": role_name
                })

    # Build Guilds list for the Add form
    guilds_data = []
    if app.bot:
        for guild in app.bot.guilds:
            roles = []
            for role in guild.roles:
                if not role.is_default() and not role.managed: # Filter out @everyone and bot integration roles if possible
                     roles.append({"id": str(role.id), "name": role.name})
            # Sort roles by name
            roles.sort(key=lambda x: x['name'])

            channels = []
            for channel in guild.text_channels:
                 channels.append({"id": str(channel.id), "name": channel.name})

            guilds_data.append({
                "id": str(guild.id),
                "name": guild.name,
                "roles": roles,
                "channels": channels
            })

    return jsonify({
        "guilds": guilds_data,
        "rules": rules
    })

@app.route('/api/reactionroles/add', methods=['POST'])
async def reaction_roles_add():
    if not is_admin(): return "Unauthorized", 401

    data_in = await request.get_json()
    guild_id = data_in.get('guild_id')
    message_id = data_in.get('message_id')
    role_id = data_in.get('role_id')
    emoji_str = data_in.get('emoji')
    channel_id = data_in.get('channel_id')

    if not all([guild_id, message_id, role_id, emoji_str]):
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    resolved_emoji = emoji_str
    emoji_to_react = emoji_str

    # Resolve Emoji
    # Check for custom ID format :12345: or just 12345
    custom_id_match = re.match(r'^:?(\d+):?$', emoji_str)
    if custom_id_match:
        emoji_id = int(custom_id_match.group(1))
        if app.bot:
            custom_emoji = app.bot.get_emoji(emoji_id)
            if custom_emoji:
                resolved_emoji = str(custom_emoji) # <:name:id>
                emoji_to_react = custom_emoji
            else:
                # If bot doesn't have it, we can't really verify it or use it easily
                pass

    # Validate Message Exists BEFORE saving
    message = None
    if app.bot and channel_id:
        guild = app.bot.get_guild(int(guild_id))
        if guild:
            channel = guild.get_channel(int(channel_id))
            if channel:
                try:
                    message = await channel.fetch_message(int(message_id))
                except discord.NotFound:
                    return jsonify({"status": "error", "message": f"Message {message_id} not found in channel {channel_id}"}), 400
                except discord.Forbidden:
                    return jsonify({"status": "error", "message": "Bot does not have permission to access that channel/message."}), 400
                except Exception as e:
                    return jsonify({"status": "error", "message": f"Error fetching message: {str(e)}"}), 500
            else:
                return jsonify({"status": "error", "message": "Channel not found"}), 400
        else:
            return jsonify({"status": "error", "message": "Guild not found"}), 400

    # Load, Update, Save
    data = await load_reaction_roles()

    if guild_id not in data:
        data[guild_id] = {}
    if message_id not in data[guild_id]:
        data[guild_id][message_id] = {}

    # Handle data structure (Old vs New)
    message_data = data[guild_id][message_id]
    if "roles" in message_data:
            # Already new format
            pass
    elif message_data and not any(k in ["roles", "channel_id"] for k in message_data):
            # Old format, migrate
            old_roles = message_data.copy()
            data[guild_id][message_id] = {"roles": old_roles}
            message_data = data[guild_id][message_id]
    elif not message_data:
            # New entry
            data[guild_id][message_id] = {"roles": {}}
            message_data = data[guild_id][message_id]

    # Save channel_id
    if channel_id:
        message_data["channel_id"] = str(channel_id)

    if "roles" in message_data:
            message_data["roles"][resolved_emoji] = str(role_id)
    else:
            # Fallback
            pass

    await save_reaction_roles(data)

    # Try to react to the message
    try:
        if message:
            await message.add_reaction(emoji_to_react)
    except Exception as e:
        print(f"Error in reaction role setup: {e}")

    return jsonify({"status": "success"})

@app.route('/api/reactionroles/delete', methods=['POST'])
async def reaction_roles_delete():
    if not is_admin(): return "Unauthorized", 401

    data_in = await request.get_json()
    guild_id = data_in.get('guild_id')
    message_id = data_in.get('message_id')
    emoji_str = data_in.get('emoji')

    if not all([guild_id, message_id, emoji_str]):
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    data = await load_reaction_roles()

    if guild_id in data and message_id in data[guild_id]:
        message_data = data[guild_id][message_id]
        roles = {}
        channel_id = None

        if "roles" in message_data:
            roles = message_data["roles"]
            channel_id = message_data.get("channel_id")
        else:
            roles = message_data

        if emoji_str in roles:
            # Remove reaction from Discord
            if app.bot:
                guild = app.bot.get_guild(int(guild_id))
                if guild:
                    message = None

                    if channel_id:
                        target_channel = guild.get_channel(int(channel_id))
                        if target_channel:
                            try:
                                message = await target_channel.fetch_message(int(message_id))
                            except:
                                pass

                    if not message:
                        # Fallback search if channel_id missing or incorrect
                        for chan in guild.text_channels:
                            try:
                                message = await chan.fetch_message(int(message_id))
                                break
                            except:
                                continue

                    if message:
                        try:
                            # Remove bot's reaction
                            await message.remove_reaction(emoji_str, app.bot.user)
                        except Exception as e:
                            print(f"Failed to remove reaction: {e}")

            del roles[emoji_str]

            # Cleanup empty dicts
            if not roles:
                del data[guild_id][message_id]
            if not data[guild_id]:
                del data[guild_id]

            await save_reaction_roles(data)
            return jsonify({"status": "success"})

    return jsonify({"status": "error", "message": "Rule not found"}), 404

# --- Music Routes ---

@app.route('/admin/music')
async def music_dashboard():
    if not is_admin(): return redirect(url_for('login'))
    return await render_template('music_dashboard.html')

@app.route('/api/music/data')
async def music_data():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot or not hasattr(app.bot, 'music_cog'):
        return jsonify({"guilds": {}})

    music_cog = app.bot.music_cog
    data = {}

    for guild in app.bot.guilds:
        guild_id = str(guild.id)

        # Current Track
        current_track_info = None
        if guild_id in music_cog.current_track:
            track = music_cog.current_track[guild_id]
            # Ensure track is not finished (prevents desync)
            if not track.finished:
                current_track_info = {
                    "title": track.metadata.get('title', 'Unknown'),
                    "url": track.metadata.get('original_url', ''),
                    "thumbnail": track.metadata.get('thumbnail', ''),
                    "volume": int(track.volume * 100),
                    "loop": track.loop,
                    "paused": track.paused
                }

        # Queue
        queue = []
        if guild_id in music_cog.queue:
            for song in music_cog.queue[guild_id]:
                queue.append({
                    "title": song['title'],
                    "url": song['original_url'],
                    "thumbnail": song.get('thumbnail', '')
                })

        data[guild_id] = {
            "name": guild.name,
            "current_track": current_track_info,
            "queue": queue
        }

    return jsonify({
        "guilds": data,
        "blacklist": music_cog.blacklist
    })

@app.route('/api/music/control', methods=['POST'])
async def music_control():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    action = data.get('action')
    guild_id = data.get('guild_id')

    if not app.bot or not hasattr(app.bot, 'music_cog'):
        return jsonify({"status": "error", "message": "Music system not ready"}), 500

    music_cog = app.bot.music_cog

    if action == 'skip':
        track = music_cog.current_track.get(guild_id)
        if track:
            track.finished = True
            await music_cog._process_queue(guild_id)
    elif action == 'loop':
        track = music_cog.current_track.get(guild_id)
        if track:
            track.loop = not track.loop
    elif action == 'volume':
        vol = data.get('volume')
        new_vol = max(0, min(100, int(vol))) / 100

        if str(guild_id) not in server_volumes:
            server_volumes[str(guild_id)] = {'music': 1.0, 'soundboard': 0.5}

        server_volumes[str(guild_id)]['music'] = new_vol
        await save_server_volumes(server_volumes)

        track = music_cog.current_track.get(guild_id)
        if track:
             track.volume = new_vol
    elif action == 'remove':
        # Remove from queue
        index = data.get('index')
        if guild_id in music_cog.queue and 0 <= index < len(music_cog.queue[guild_id]):
            music_cog.queue[guild_id].pop(index)

    return jsonify({"status": "success"})

@app.route('/api/music/ban', methods=['POST'])
async def music_ban():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({"status": "error", "message": "Missing URL"}), 400

    if not app.bot or not hasattr(app.bot, 'music_cog'):
        return jsonify({"status": "error", "message": "Music system not ready"}), 500

    music_cog = app.bot.music_cog

    if url not in music_cog.blacklist:
        music_cog.blacklist.append(url)
        await save_music_blacklist(music_cog.blacklist)

        # If currently playing, skip it
        for guild_id, track in music_cog.current_track.items():
            if track.metadata.get('original_url') == url or track.metadata.get('url') == url:
                 track.finished = True

    return jsonify({"status": "success"})

# --- RSS Routes ---

@app.route('/admin/rss')
async def admin_rss():
    if not is_admin(): return redirect(url_for('login'))
    return await render_template('rss_dashboard.html')

@app.route('/api/rss/data')
async def rss_data():
    if not is_admin(): return "Unauthorized", 401

    rss_data = await load_rss_data()
    feeds = []

    for guild_id, items in rss_data.items():
        guild = None
        if app.bot:
            guild = app.bot.get_guild(int(guild_id))

        guild_name = guild.name if guild else f"Unknown Guild ({guild_id})"

        for item in items:
            channel_id = item.get('channel_id')
            channel = None
            if guild:
                channel = guild.get_channel(channel_id)

            channel_name = channel.name if channel else f"Unknown Channel ({channel_id})"

            feeds.append({
                "guild_id": guild_id,
                "guild_name": guild_name,
                "channel_id": str(channel_id),
                "channel_name": channel_name,
                "link": item.get('link'),
                "last_message": item.get('last_message', 'N/A'),
                "color": item.get('color', '#2E8B57')
            })

    # Guilds for dropdown
    guilds_data = []
    if app.bot:
        for guild in app.bot.guilds:
            channels = []
            for channel in guild.text_channels:
                 channels.append({"id": str(channel.id), "name": channel.name})

            guilds_data.append({
                "id": str(guild.id),
                "name": guild.name,
                "channels": channels
            })

    return jsonify({
        "guilds": guilds_data,
        "feeds": feeds
    })

@app.route('/api/rss/add', methods=['POST'])
async def rss_add():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    channel_id = data.get('channel_id')
    link = data.get('link')
    color = data.get('color', '#2E8B57')

    if not all([guild_id, channel_id, link]):
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    # Check for YouTube RSS
    try:
        rss_link = await get_youtube_rss_url(link)
        if rss_link:
            link = rss_link
    except Exception as e:
        print(f"Error checking YouTube RSS: {e}")

    # Validate RSS
    try:
        # Run in executor to avoid blocking
        feed = await asyncio.get_event_loop().run_in_executor(None, feedparser.parse, link)
        if not feed.entries:
            return jsonify({"status": "error", "message": "No items found in RSS feed"}), 400

        latest_entry = feed.entries[0]
        # Use same logic as rss.py for ID
        entry_id = getattr(latest_entry, 'id', getattr(latest_entry, 'link', getattr(latest_entry, 'title', None)))
        latest_title = latest_entry.title

    except Exception as e:
         return jsonify({"status": "error", "message": f"Failed to parse RSS: {str(e)}"}), 400

    rss_data = await load_rss_data()

    if str(guild_id) not in rss_data:
        rss_data[str(guild_id)] = []

    # Check duplicate
    for sub in rss_data[str(guild_id)]:
        if sub['link'] == link:
             return jsonify({"status": "error", "message": "Feed already exists for this server"}), 400

    rss_data[str(guild_id)].append({
        "link": link,
        "channel_id": int(channel_id),
        "last_message": latest_title,
        "last_id": entry_id,
        "color": color
    })

    await save_rss_data(rss_data)

    # Notify in channel
    if app.bot:
        guild = app.bot.get_guild(int(guild_id))
        if guild:
            channel = guild.get_channel(int(channel_id))
            if channel:
                try:
                    feed_title = feed.feed.get('title', link)

                    rss_cog = app.bot.get_cog('rss')
                    if rss_cog:
                        embed = rss_cog._create_rss_embed(latest_entry, feed_title, color)
                        await channel.send(f"New feed added: {feed_title}", embed=embed)
                    else:
                        entry_link = getattr(latest_entry, 'link', link)
                        await channel.send(f"New feed added: {feed_title}\n"
                                           f"**Title:** {latest_title}\n"
                                           f"**Link:** {entry_link}")
                except Exception as e:
                    print(f"Failed to send test message: {e}")

    return jsonify({"status": "success"})

@app.route('/api/rss/update_color', methods=['POST'])
async def rss_update_color():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    link = data.get('link')
    color = data.get('color')

    if not all([guild_id, link, color]):
         return jsonify({"status": "error", "message": "Missing arguments"}), 400

    rss_data = await load_rss_data()

    if str(guild_id) in rss_data:
        for sub in rss_data[str(guild_id)]:
            if sub['link'] == link:
                sub['color'] = color
                await save_rss_data(rss_data)
                return jsonify({"status": "success"})

    return jsonify({"status": "error", "message": "Feed not found"}), 404

# --- Gamer Roles Routes ---

@app.route('/admin/gameroles')
async def admin_gameroles():
    if not is_admin(): return redirect(url_for('login'))
    return await render_template('gameroles.html')

@app.route('/api/gameroles/data')
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
                "ignored_activities": guild_settings.get("ignored_activities", ["Custom Status"])
            }
        })

    return jsonify({"guilds": guilds_data})

@app.route('/api/gameroles/save', methods=['POST'])
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

@app.route('/api/gameroles/ignore/add', methods=['POST'])
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

@app.route('/api/gameroles/ignore/remove', methods=['POST'])
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

# --- Auto Room Routes ---

@app.route('/admin/autorooms')
async def admin_autorooms():
    if not is_admin(): return redirect(url_for('login'))
    return await render_template('autoroom_dashboard.html')

@app.route('/api/autorooms/data')
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

@app.route('/api/autorooms/save', methods=['POST'])
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

@app.route('/api/rss/delete', methods=['POST'])
async def rss_delete():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    link = data.get('link')

    if not guild_id or not link:
         return jsonify({"status": "error", "message": "Missing arguments"}), 400

    rss_data = await load_rss_data()

    if str(guild_id) in rss_data:
        original_len = len(rss_data[str(guild_id)])
        rss_data[str(guild_id)] = [s for s in rss_data[str(guild_id)] if s['link'] != link]

        if len(rss_data[str(guild_id)]) < original_len:
            # Clean up empty
            if not rss_data[str(guild_id)]:
                del rss_data[str(guild_id)]

            await save_rss_data(rss_data)
            return jsonify({"status": "success"})

    return jsonify({"status": "error", "message": "Feed not found"}), 404

# --- Auto Deleter Routes ---

@app.route('/admin/deleter')
async def admin_deleter():
    if not is_admin(): return redirect(url_for('login'))
    return await render_template('deleter_dashboard.html')

@app.route('/api/deleter/data')
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

@app.route('/api/deleter/save', methods=['POST'])
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

@app.route('/api/deleter/delete', methods=['POST'])
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

@app.route('/api/deleter/bulk_delete', methods=['POST'])
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

# --- Backup Routes ---

@app.route('/admin/backup')
async def admin_backup():
    if not is_admin(): return redirect(url_for('login'))
    settings = load_settings()
    backup_time = settings.get('backup_time')
    return await render_template('backup_dashboard.html', backup_time=backup_time)

@app.route('/api/backup/save', methods=['POST'])
async def backup_save():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    backup_time = data.get('backup_time')

    # Validation
    if backup_time:
        if not re.match(r'^\d{2}:\d{2}$', backup_time):
             return jsonify({"status": "error", "message": "Invalid time format (HH:MM required)"}), 400

    settings = load_settings()
    settings['backup_time'] = backup_time
    await save_settings(settings)

    return jsonify({"status": "success"})

@app.route('/api/backup/run', methods=['POST'])
async def backup_run():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    cog = app.bot.get_cog("backup")
    if not cog:
        return jsonify({"status": "error", "message": "Backup cog not loaded"}), 500

    # Run backup
    success, result = await cog.perform_backup()

    if success:
        return jsonify({"status": "success", "filename": result})
    else:
        return jsonify({"status": "error", "message": result}), 500

# --- System Backups (Physical Files) ---

def get_system_backups():
    if not os.path.exists(BACKUP_FOLDER):
        return []

    files = []
    try:
        for f in os.listdir(BACKUP_FOLDER):
            if f.endswith('.zip'):
                full_path = os.path.join(BACKUP_FOLDER, f)
                stat = os.stat(full_path)
                files.append({
                    "name": f,
                    "size": stat.st_size,
                    "created": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
        # Sort by creation date desc
        files.sort(key=lambda x: x['created'], reverse=True)
    except Exception as e:
        print(f"Error scanning backups: {e}")

    return files

@app.route('/api/backup/files')
async def backup_files_list():
    if not is_admin(): return "Unauthorized", 401
    return jsonify(get_system_backups())

@app.route('/api/backup/delete', methods=['POST'])
async def backup_delete_file():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    filename = data.get('filename')

    if not filename:
        return jsonify({"status": "error", "message": "Missing filename"}), 400

    # Security checks
    if not filename.endswith('.zip'):
         return jsonify({"status": "error", "message": "Invalid file type"}), 400

    if '..' in filename or '/' in filename or '\\' in filename:
         return jsonify({"status": "error", "message": "Invalid filename"}), 400

    target_path = os.path.join(BACKUP_FOLDER, filename)

    if not os.path.exists(target_path):
        return jsonify({"status": "error", "message": "File not found"}), 404

    try:
        os.remove(target_path)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/admin/backup/download/<filename>')
async def backup_download_file(filename):
    if not is_admin(): return redirect(url_for('login'))

    # Security checks
    if '..' in filename or '/' in filename or '\\' in filename:
        return "Invalid filename", 400

    if not os.path.exists(os.path.join(BACKUP_FOLDER, filename)):
        return "File not found", 404

    return await send_from_directory(BACKUP_FOLDER, filename, as_attachment=True)

# --- Pokemon GO Routes ---

@app.route('/admin/pokemon')
async def admin_pokemon():
    if not is_admin(): return redirect(url_for('login'))
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
    if not is_admin(): return redirect(url_for('login'))
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
    if not is_admin(): return redirect(url_for('login'))
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
    if not is_admin(): return redirect(url_for('login'))
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
    if not is_admin(): return redirect(url_for('login'))
    return await render_template('enroll_dashboard.html')

@app.route('/admin/newspaper')
async def admin_newspaper():
    if not is_admin(): return redirect(url_for('login'))
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
