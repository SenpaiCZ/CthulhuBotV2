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
from quart import Quart, render_template, request, redirect, url_for, session, jsonify, abort
from markupsafe import escape
from loadnsave import (
    load_player_stats, load_retired_characters_data, load_settings, save_settings,
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
    load_gamerole_settings, save_gamerole_settings,
    load_monsters_data, load_deities_data, load_spells_data, load_weapons_data,
    load_archetype_data, load_pulp_talents_data, load_madness_insane_talent_data,
    load_manias_data, load_phobias_data, load_poisons_data, load_skills_data,
    load_inventions_data, load_years_data, load_occupations_data,
    _load_json_file, _save_json_file, DATA_FOLDER, INFODATA_FOLDER
)
from .audio_mixer import MixingAudioSource
from rss_utils import get_youtube_rss_url

SOUNDBOARD_FOLDER = "soundboard"
ALLOWED_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.m4a', '.flac'}
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

def sanitize_filename(filename):
    """Sanitizes a filename to ensure it is safe for the filesystem."""
    # Keep only alphanumeric, dot, dash, underscore
    clean = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
    # Remove leading/trailing dots/spaces
    clean = clean.strip('. ')
    return clean or 'unnamed'

def get_soundboard_files():
    structure = {}
    if not os.path.exists(SOUNDBOARD_FOLDER):
        return structure

    # Level 1: Root files
    root_files = []
    # Level 2: Subdirectories
    folders = {}

    try:
        for entry in os.listdir(SOUNDBOARD_FOLDER):
            entry_path = os.path.join(SOUNDBOARD_FOLDER, entry)

            if os.path.isfile(entry_path):
                 if os.path.splitext(entry)[1].lower() in ALLOWED_EXTENSIONS:
                    root_files.append({"name": entry, "path": entry})
            elif os.path.isdir(entry_path):
                folder_files = []
                for f in os.listdir(entry_path):
                    f_path = os.path.join(entry_path, f)
                    if os.path.isfile(f_path) and os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS:
                        folder_files.append({"name": f, "path": os.path.join(entry, f).replace('\\', '/')})
                if folder_files:
                    folder_files.sort(key=lambda x: x['name'])
                    folders[entry] = folder_files

        if root_files:
            root_files.sort(key=lambda x: x['name'])
            structure["Root"] = root_files

        # Sort folders by name and merge
        for k in sorted(folders.keys()):
            structure[k] = folders[k]
    except Exception as e:
        print(f"Error scanning soundboard: {e}")

    return structure

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

    return await render_template('render_monster.html', monster=target, emojis=emojis, emoji_lib=emoji)

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

    return await render_template('render_deity.html', deity=target, emojis=emojis, emoji_lib=emoji)

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

    return await render_template('render_spell.html', spell=target, emojis=emojis, emoji_lib=emoji)

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

    return await render_template('render_weapon.html', weapon=weapon, weapon_name=target_key)

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

    return await render_template('render_archetype.html', archetype=archetype, name=target_key, emojis=emojis, emoji_lib=emoji)

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

    return await render_template('render_pulp_talent.html', talent=target_talent, emojis=emojis, emoji_lib=emoji)

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

    return await render_template('render_simple_entry.html', title=target_key, description=data[target_key], type="Insane Talent", emojis=emojis, emoji_lib=emoji)

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

    return await render_template('render_simple_entry.html', title=target_key, description=data[target_key], type="Mania", emojis=emojis, emoji_lib=emoji)

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

    return await render_template('render_simple_entry.html', title=target_key, description=data[target_key], type="Phobia", emojis=emojis, emoji_lib=emoji)

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

    return await render_template('render_poison.html', title=target_key, poison=data[target_key], type="Poison", emojis=emojis, emoji_lib=emoji)

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

    return await render_template('render_simple_entry.html', title=target_key, description=data[target_key], type="Skill", emojis=emojis, emoji_lib=emoji)

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

    return await render_template('render_timeline.html', title=target_key, events=data[target_key], type="Inventions", emojis=emojis, emoji_lib=emoji)

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

    return await render_template('render_timeline.html', title=target_key, events=data[target_key], type="Timeline", emojis=emojis, emoji_lib=emoji)


# --- Admin Routes ---

@app.route('/admin')
async def admin_dashboard():
    if not is_admin(): return redirect(url_for('login'))
    return await render_template('admin_dashboard.html')

@app.route('/monsters')
async def admin_monsters():
    monsters_data = await _load_json_file(INFODATA_FOLDER, 'monsters.json')
    stat_emojis = {k: emoji.emojize(v, language='alias') for k, v in emojis.stat_emojis.items()}
    return await render_template('monsters.html', data=monsters_data, stat_emojis=stat_emojis)

@app.route('/deities')
async def admin_deities():
    deities_data = await _load_json_file(INFODATA_FOLDER, 'deities.json')
    stat_emojis = {k: emoji.emojize(v, language='alias') for k, v in emojis.stat_emojis.items()}
    return await render_template('deities.html', data=deities_data, stat_emojis=stat_emojis)

@app.route('/spells')
async def admin_spells():
    spells_data = await _load_json_file(INFODATA_FOLDER, 'spells.json')
    stat_emojis = {k: emoji.emojize(v, language='alias') for k, v in emojis.stat_emojis.items()}
    return await render_template('spells.html', data=spells_data, stat_emojis=stat_emojis)

@app.route('/weapons')
async def admin_weapons():
    weapons_data = await _load_json_file(INFODATA_FOLDER, 'weapons.json')
    if not weapons_data:
        print(f"Warning: Weapons data is empty or file not found. Path: {os.path.join(INFODATA_FOLDER, 'weapons.json')} CWD: {os.getcwd()}")
    return await render_template('weapons.html', data=weapons_data)

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
    return await render_template('archetypes.html', data=data)

@app.route('/pulp_talents')
async def admin_pulp_talents():
    data = await load_pulp_talents_data()
    return await render_template('pulp_talents.html', data=data)

@app.route('/insane_talents')
async def admin_insane_talents():
    data = await load_madness_insane_talent_data()
    return await render_template('generic_list.html', data=data, title="Insane Talents")

@app.route('/manias')
async def admin_manias():
    data = await load_manias_data()
    return await render_template('generic_list.html', data=data, title="Manias")

@app.route('/phobias')
async def admin_phobias():
    data = await load_phobias_data()
    return await render_template('generic_list.html', data=data, title="Phobias")

@app.route('/poisons')
async def admin_poisons():
    data = await load_poisons_data()
    return await render_template('poisons.html', data=data, title="Poisons")

@app.route('/skills')
async def admin_skills():
    data = await load_skills_data()
    # Process emojis in descriptions
    processed_data = {}
    for key, description in data.items():
        processed_data[key] = emoji.emojize(description, language='alias')
    return await render_template('generic_list.html', data=processed_data, title="Skills")

@app.route('/inventions')
async def admin_inventions():
    data = await load_inventions_data()
    return await render_template('timeline_list.html', data=data, title="Inventions")

@app.route('/years')
async def admin_years():
    data = await load_years_data()
    return await render_template('timeline_list.html', data=data, title="Years Timeline")

@app.route('/occupations')
async def admin_occupations():
    data = await load_occupations_data()
    return await render_template('occupations.html', data=data)

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

# --- Prefix Routes ---

@app.route('/admin/prefixes')
async def admin_prefixes():
    if not is_admin(): return redirect(url_for('login'))

    if not app.bot:
        return "Bot not initialized", 500

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

    return await render_template('prefixes.html', guilds=guilds_data)

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

    files = get_soundboard_files()
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

    try:
        os.makedirs(target_path)
        return jsonify({"status": "success", "folder": safe_name})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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

    try:
        shutil.rmtree(target_path)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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

    try:
        os.remove(full_path)
        # Clean up settings if any
        settings = await load_soundboard_settings()
        if 'files' in settings and file_path in settings['files']:
            del settings['files'][file_path]
            await save_soundboard_settings(settings)

        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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
            # Create folder from zip name
            zip_folder_name = os.path.splitext(filename)[0]
            extract_dir = os.path.join(SOUNDBOARD_FOLDER, zip_folder_name)

            if not os.path.exists(extract_dir):
                os.makedirs(extract_dir)

            try:
                # We need to save the file stream to disk temporarily
                file_bytes = file.read()
                # Check if async
                if asyncio.iscoroutine(file_bytes):
                    file_bytes = await file_bytes

                temp_zip_path = os.path.join(SOUNDBOARD_FOLDER, f"temp_{filename}")

                with open(temp_zip_path, 'wb') as f:
                    f.write(file_bytes)

                with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                    for member in zip_ref.namelist():
                        # Skip directories
                        if member.endswith('/'): continue

                        # Get basename to flatten structure
                        base_name = os.path.basename(member)
                        if not base_name: continue

                        m_ext = os.path.splitext(base_name)[1].lower()
                        if m_ext in ALLOWED_EXTENSIONS:
                            target_file = os.path.join(extract_dir, sanitize_filename(base_name))
                            with open(target_file, 'wb') as out_f:
                                out_f.write(zip_ref.read(member))

                os.remove(temp_zip_path)
                results.append(f"Unzipped {filename} to {zip_folder_name}/")
            except Exception as e:
                results.append(f"Error unzipping {filename}: {str(e)}")

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
                res = file.save(target_path)
                if asyncio.iscoroutine(res):
                    await res

                results.append(f"Uploaded {filename}")
            except Exception as e:
                results.append(f"Error saving {filename}: {str(e)}")
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
            await music_cog._process_queue()
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
                gw_copy = gw.copy()
                gw_copy['message_id'] = msg_id

                # Fetch participant count
                gw_copy['participant_count'] = len(gw.get('participants', []))

                # Resolve channel name
                chan = guild.get_channel(int(gw['channel_id']))
                gw_copy['channel_name'] = chan.name if chan else "Unknown Channel"

                # Resolve winner name
                if 'winner_id' in gw:
                    mem = guild.get_member(int(gw['winner_id']))
                    gw_copy['winner_name'] = mem.display_name if mem else f"User {gw['winner_id']}"

                guild_giveaways.append(gw_copy)

        # Sort by status (active first) then title
        guild_giveaways.sort(key=lambda x: (x['status'] == 'ended', x['title']))

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

        # Create Embed
        embed = discord.Embed(title=f"🎉 GIVEAWAY: {title}", description=description, color=discord.Color.gold())
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
            "participants": []
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

@app.route('/api/admin/update', methods=['POST'])
async def admin_update_bot():
    if not is_admin(): return "Unauthorized", 401

    updater_script = "updater.py"
    if not os.path.exists(updater_script):
        return jsonify({"status": "error", "message": "Updater script not found"}), 500

    pid = str(os.getpid())
    python_exe = sys.executable

    try:
        if os.name == 'nt':
            subprocess.Popen([python_exe, updater_script, pid],
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([python_exe, updater_script, pid],
                             start_new_session=True)
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
