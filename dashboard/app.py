import os
import json
import discord
import asyncio
from quart import Quart, render_template, request, redirect, url_for, session, jsonify, abort
from loadnsave import (
    load_player_stats, load_retired_characters_data, load_settings, save_settings,
    _load_json_file, _save_json_file, DATA_FOLDER, INFODATA_FOLDER
)

SOUNDBOARD_FOLDER = "soundboard"
ALLOWED_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.m4a', '.flac'}
guild_volumes = {}

app = Quart(__name__)
app.secret_key = os.urandom(24)
app.bot = None  # Placeholder for the Discord bot instance

# Helper to check login
def is_admin():
    return session.get('logged_in', False)

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
            if voice_client.channel.id != channel.id:
                await voice_client.move_to(channel)
        else:
            voice_client = await channel.connect()
    except Exception as e:
        return None, str(e)

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
    # stats is a dict, likely {user_id: {char_data...}}
    return await render_template('list_characters.html', title="Active Characters", data=stats, type="active")

@app.route('/retired')
async def retired():
    stats = await load_retired_characters_data()
    return await render_template('list_characters.html', title="Retired Characters", data=stats, type="retired")

# --- Admin Routes ---

@app.route('/admin')
async def admin_dashboard():
    if not is_admin(): return redirect(url_for('login'))
    return await render_template('admin_dashboard.html')

@app.route('/admin/settings')
async def admin_settings():
    if not is_admin(): return redirect(url_for('login'))
    # Direct to editing settings.json
    return redirect(url_for('edit_file', folder_name='data', filename='settings.json'))

@app.route('/admin/browse/<folder_name>')
async def browse_files(folder_name):
    if not is_admin(): return redirect(url_for('login'))

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

# --- Soundboard Routes ---

@app.route('/admin/soundboard')
async def soundboard_page():
    if not is_admin(): return redirect(url_for('login'))
    return await render_template('soundboard.html')

@app.route('/api/soundboard/data')
async def soundboard_data():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"guilds": [], "files": {}, "status": {}})

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
        status = {
            "is_connected": voice_client is not None,
            "channel_id": str(voice_client.channel.id) if voice_client else None,
            "is_playing": voice_client.is_playing() if voice_client else False,
            "volume": int(guild_volumes.get(str(guild.id), 0.5) * 100)
        }
        status_data[str(guild.id)] = status

    files = get_soundboard_files()

    return jsonify({
        "guilds": guilds_data,
        "files": files,
        "status": status_data
    })

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

    if voice_client.is_playing():
        voice_client.stop()

    try:
        source = discord.FFmpegPCMAudio(full_path)
        volume = guild_volumes.get(str(guild_id), 0.5)
        transform_source = discord.PCMVolumeTransformer(source, volume=volume)
        voice_client.play(transform_source)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/soundboard/stop', methods=['POST'])
async def soundboard_stop():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')

    if not guild_id:
        return jsonify({"status": "error", "message": "Missing guild_id"}), 400

    guild = app.bot.get_guild(int(guild_id))
    if guild and guild.voice_client and guild.voice_client.is_playing():
        guild.voice_client.stop()

    return jsonify({"status": "success"})

@app.route('/api/soundboard/volume', methods=['POST'])
async def soundboard_volume():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    volume = data.get('volume') # 0-100

    if not guild_id or volume is None:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    try:
        vol_float = float(volume) / 100.0
        vol_float = max(0.0, min(1.0, vol_float)) # Clamp between 0 and 1
        guild_volumes[str(guild_id)] = vol_float

        guild = app.bot.get_guild(int(guild_id))
        if guild and guild.voice_client and guild.voice_client.source:
             # Check if it's a PCMVolumeTransformer
             if isinstance(guild.voice_client.source, discord.PCMVolumeTransformer):
                 guild.voice_client.source.volume = vol_float

        return jsonify({"status": "success"})
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid volume"}), 400
