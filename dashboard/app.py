import os
import json
import discord
import asyncio
from quart import Quart, render_template, request, redirect, url_for, session, jsonify, abort
from loadnsave import (
    load_player_stats, load_retired_characters_data, load_settings, save_settings,
    load_soundboard_settings, save_soundboard_settings, load_music_blacklist, save_music_blacklist,
    load_server_stats, save_server_stats, load_karma_settings, save_karma_settings,
    load_reaction_roles, save_reaction_roles,
    _load_json_file, _save_json_file, DATA_FOLDER, INFODATA_FOLDER
)
from .audio_mixer import MixingAudioSource

SOUNDBOARD_FOLDER = "soundboard"
ALLOWED_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.m4a', '.flac'}
guild_volumes = {}
guild_mixers = {} # guild_id (str) -> MixingAudioSource

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
    # Direct to editing config.json
    return redirect(url_for('edit_file', folder_name='root', filename='config.json'))

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

        guild_id_str = str(guild.id)
        current_settings = karma_settings.get(guild_id_str, {})

        guilds_data.append({
            "id": guild_id_str,
            "name": guild.name,
            "channels": channels,
            "settings": current_settings
        })

    return await render_template('karma_settings.html', guilds=guilds_data)

@app.route('/api/karma/save', methods=['POST'])
async def save_karma():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    channel_id = data.get('channel_id')
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
        karma_settings[str(guild_id)] = {
            "channel_id": int(channel_id),
            "upvote_emoji": upvote_emoji if upvote_emoji else "👌",
            "downvote_emoji": downvote_emoji if downvote_emoji else "🤏"
        }

    await save_karma_settings(karma_settings)

    return jsonify({"status": "success"})

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

        status = {
            "is_connected": voice_client is not None,
            "channel_id": str(voice_client.channel.id) if voice_client else None,
            "is_playing": voice_client.is_playing() if voice_client else False,
            "volume": int(guild_volumes.get(str(guild.id), 0.5) * 100),
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

        master_vol = guild_volumes.get(str(guild_id), 0.5)
        source = discord.PCMVolumeTransformer(mixer, volume=master_vol)
        voice_client.play(source)

    # Add track
    loop_setting = data.get('loop', True)
    mixer.add_track(full_path, volume=0.5, loop=loop_setting)

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
        guild_volumes[str(guild_id)] = vol_float

        guild = app.bot.get_guild(int(guild_id))
        if guild and guild.voice_client and guild.voice_client.source:
             if isinstance(guild.voice_client.source, discord.PCMVolumeTransformer):
                 guild.voice_client.source.volume = vol_float

        return jsonify({"status": "success"})
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid volume"}), 400

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
        guild = app.bot.get_guild(int(guild_id))
        guild_name = guild.name if guild else f"Unknown Guild ({guild_id})"

        for message_id, emojis in messages.items():
            for emoji_str, role_id in emojis.items():
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
    for guild in app.bot.guilds:
        roles = []
        for role in guild.roles:
            if not role.is_default() and not role.managed: # Filter out @everyone and bot integration roles if possible
                 roles.append({"id": str(role.id), "name": role.name})
        # Sort roles by name
        roles.sort(key=lambda x: x['name'])

        guilds_data.append({
            "id": str(guild.id),
            "name": guild.name,
            "roles": roles
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

    if not all([guild_id, message_id, role_id, emoji_str]):
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    # Load, Update, Save
    data = await load_reaction_roles()

    if guild_id not in data:
        data[guild_id] = {}
    if message_id not in data[guild_id]:
        data[guild_id][message_id] = {}

    data[guild_id][message_id][emoji_str] = str(role_id)

    await save_reaction_roles(data)

    # Optional: Try to react to the message if the bot can find it
    # We do this asynchronously without waiting or failing the request
    try:
        if app.bot:
            guild = app.bot.get_guild(int(guild_id))
            if guild:
                # We don't know the channel, so we can't easily fetch the message to react.
                # We would need to search all channels or store channel_id.
                # For now, we skip the auto-react from dashboard add, user must react themselves or ensure bot reacts.
                pass
    except Exception:
        pass

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
        if emoji_str in data[guild_id][message_id]:
            del data[guild_id][message_id][emoji_str]

            # Cleanup empty dicts
            if not data[guild_id][message_id]:
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
        track = music_cog.current_track.get(guild_id)
        if track:
             track.volume = max(0, min(100, int(vol))) / 100
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
