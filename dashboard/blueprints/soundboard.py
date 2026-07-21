import os
import asyncio
import discord
from quart import Blueprint, request, jsonify, redirect, url_for, render_template

from dashboard.app import app, is_admin
from dashboard.state import SOUNDBOARD_FOLDER, server_volumes, guild_mixers
from ..audio_mixer import MixingAudioSource
from ..file_utils import (
    sanitize_filename, sync_get_soundboard_files, sync_save_bytes,
    sync_extract_zip, sync_delete_path, sync_rename_path, sync_create_directory,
    ALLOWED_AUDIO_EXTENSIONS as ALLOWED_EXTENSIONS,
)
from loadnsave import (
    load_soundboard_settings, save_soundboard_settings,
    save_server_volumes,
)

soundboard_bp = Blueprint('soundboard', __name__)


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
                try:
                    await voice_client.disconnect(force=True)
                except Exception as e:
                    print(f"[Dashboard] Error forcefully disconnecting stale voice client: {e}")
                voice_client = await channel.connect(timeout=60.0, reconnect=True)
            elif voice_client.channel.id != channel.id:
                await voice_client.move_to(channel)
        else:
            voice_client = await channel.connect(timeout=60.0, reconnect=True)
    except asyncio.TimeoutError:
        print(f"[Dashboard] Timeout connecting to voice channel in guild {guild_id}. UDP blocked?")
        return None, "Connection timed out. This may indicate a network issue (e.g. UDP ports blocked) on the server hosting the bot."
    except Exception as e:
        print(f"[Dashboard] Unexpected error connecting to voice in guild {guild_id}: {e}")
        return None, str(e)

    if voice_client is None or not voice_client.is_connected():
        return None, "Failed to establish a stable connection to the voice channel."

    return voice_client, None

# --- Soundboard Routes ---

@soundboard_bp.route('/admin/soundboard')
async def soundboard_page():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('soundboard.html')

@soundboard_bp.route('/api/soundboard/data')
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

@soundboard_bp.route('/api/soundboard/folder/color', methods=['POST'])
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

@soundboard_bp.route('/api/soundboard/file/settings', methods=['POST'])
async def soundboard_file_settings():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    file_path = data.get('file_path')
    volume = data.get('volume')
    loop = data.get('loop')

    if not file_path or volume is None or loop is None:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    # Security check
    try:
        full_path = os.path.abspath(os.path.join(SOUNDBOARD_FOLDER, file_path))
        if os.path.commonpath([full_path, os.path.abspath(SOUNDBOARD_FOLDER)]) != os.path.abspath(SOUNDBOARD_FOLDER):
            return jsonify({"status": "error", "message": "Invalid file path"}), 400
    except ValueError:
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

@soundboard_bp.route('/api/soundboard/file/favorite', methods=['POST'])
async def soundboard_file_favorite():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    file_path = data.get('file_path')
    favorited = data.get('favorited')

    if file_path is None or favorited is None:
        return jsonify({"status": "error", "message": "Missing file_path or favorited"}), 400

    settings = await load_soundboard_settings()
    if 'favorites' not in settings:
        settings['favorites'] = []

    if favorited and file_path not in settings['favorites']:
        settings['favorites'].append(file_path)
    elif not favorited and file_path in settings['favorites']:
        settings['favorites'].remove(file_path)

    await save_soundboard_settings(settings)
    return jsonify({"status": "success"})

@soundboard_bp.route('/api/soundboard/play', methods=['POST'])
async def soundboard_play():
    if not is_admin(): return "Unauthorized", 401
    try:
        return await _soundboard_play_inner()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Server error: {e}"}), 500

async def _soundboard_play_inner():
    data = await request.get_json()
    guild_id = data.get('guild_id')
    channel_id = data.get('channel_id')
    file_path = data.get('file_path')

    if not guild_id or not channel_id or not file_path:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    # Security check for file path
    try:
        full_path = os.path.abspath(os.path.join(SOUNDBOARD_FOLDER, file_path))
        if os.path.commonpath([full_path, os.path.abspath(SOUNDBOARD_FOLDER)]) != os.path.abspath(SOUNDBOARD_FOLDER):
            return jsonify({"status": "error", "message": "Invalid file path"}), 400
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid file path"}), 400

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

        try:
            if not voice_client.is_connected():
                print(f"[Dashboard] Bot disconnected right before play in guild {guild_id}. Attempting to forcefully disconnect...")
                try:
                    # Non-blocking forceful disconnect
                    if app.bot:
                        app.bot.loop.create_task(voice_client.disconnect(force=True))
                except Exception as ex:
                    print(f"[Dashboard] Error forcefully disconnecting voice client: {ex}")
                raise Exception("Bot is not connected to voice anymore.")
            voice_client.play(source)
        except Exception as e:
            print(f"[Dashboard] Playback error in guild {guild_id}: {e}")
            return jsonify({"status": "error", "message": f"Playback error: {e}"}), 500

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

@soundboard_bp.route('/api/soundboard/join', methods=['POST'])
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

@soundboard_bp.route('/api/soundboard/leave', methods=['POST'])
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

@soundboard_bp.route('/api/soundboard/stop', methods=['POST'])
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

@soundboard_bp.route('/api/soundboard/volume', methods=['POST'])
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

@soundboard_bp.route('/api/soundboard/folder/create', methods=['POST'])
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

@soundboard_bp.route('/api/soundboard/folder/delete', methods=['POST'])
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

@soundboard_bp.route('/api/soundboard/folder/rename', methods=['POST'])
async def soundboard_rename_folder():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    old_name = data.get('old_name')
    new_name = data.get('new_name')

    if not old_name or not new_name:
        return jsonify({"status": "error", "message": "Missing old_name or new_name"}), 400

    safe_old = sanitize_filename(old_name)
    safe_new = sanitize_filename(new_name)
    old_path = os.path.join(SOUNDBOARD_FOLDER, safe_old)
    new_path = os.path.join(SOUNDBOARD_FOLDER, safe_new)

    if not os.path.exists(old_path):
        return jsonify({"status": "error", "message": "Folder not found"}), 404

    if os.path.exists(new_path):
        return jsonify({"status": "error", "message": "A folder with that name already exists"}), 400

    success, error = await asyncio.to_thread(sync_rename_path, old_path, new_path)
    if success:
        settings = await load_soundboard_settings()
        old_prefix = safe_old + '/'
        new_prefix = safe_new + '/'

        if 'folder_colors' in settings and safe_old in settings['folder_colors']:
            settings['folder_colors'][safe_new] = settings['folder_colors'].pop(safe_old)

        if 'files' in settings:
            settings['files'] = {
                (new_prefix + k[len(old_prefix):] if k.startswith(old_prefix) else k): v
                for k, v in settings['files'].items()
            }

        if 'favorites' in settings:
            settings['favorites'] = [
                new_prefix + p[len(old_prefix):] if p.startswith(old_prefix) else p
                for p in settings['favorites']
            ]

        await save_soundboard_settings(settings)
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": error}), 500

@soundboard_bp.route('/api/soundboard/file/delete', methods=['POST'])
async def soundboard_delete_file():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    file_path = data.get('file_path')

    if not file_path:
        return jsonify({"status": "error", "message": "Missing file_path"}), 400

    # Basic path validation
    try:
        full_path = os.path.abspath(os.path.join(SOUNDBOARD_FOLDER, file_path))
        if os.path.commonpath([full_path, os.path.abspath(SOUNDBOARD_FOLDER)]) != os.path.abspath(SOUNDBOARD_FOLDER):
            return jsonify({"status": "error", "message": "Path traversal detected"}), 400
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid path"}), 400

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

@soundboard_bp.route('/api/soundboard/file/rename', methods=['POST'])
async def soundboard_rename_file():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    file_path = data.get('file_path')
    new_name = data.get('new_name')

    if not file_path or not new_name:
        return jsonify({"status": "error", "message": "Missing file_path or new_name"}), 400

    # Basic path validation
    try:
        full_old_path = os.path.abspath(os.path.join(SOUNDBOARD_FOLDER, file_path))
        if os.path.commonpath([full_old_path, os.path.abspath(SOUNDBOARD_FOLDER)]) != os.path.abspath(SOUNDBOARD_FOLDER):
            return jsonify({"status": "error", "message": "Path traversal detected"}), 400
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid path"}), 400

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
        settings = await load_soundboard_settings()
        changed = False
        if 'files' in settings and file_path in settings['files']:
            settings['files'][new_rel_path] = settings['files'].pop(file_path)
            changed = True
        if 'favorites' in settings and file_path in settings['favorites']:
            settings['favorites'].remove(file_path)
            settings['favorites'].append(new_rel_path)
            changed = True
        if changed:
            await save_soundboard_settings(settings)

        return jsonify({"status": "success", "new_path": new_rel_path})
    else:
        return jsonify({"status": "error", "message": error}), 500

@soundboard_bp.route('/api/soundboard/upload', methods=['POST'])
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

@soundboard_bp.route('/api/soundboard/track/volume', methods=['POST'])
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

@soundboard_bp.route('/api/soundboard/track/loop', methods=['POST'])
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

@soundboard_bp.route('/api/soundboard/track/pause', methods=['POST'])
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

@soundboard_bp.route('/api/soundboard/track/remove', methods=['POST'])
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
