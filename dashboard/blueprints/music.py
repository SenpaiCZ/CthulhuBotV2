import asyncio
import os
import uuid
from quart import Blueprint, request, jsonify, redirect, url_for, render_template

from dashboard.app import app, is_admin
from dashboard.state import server_volumes, SOUNDBOARD_FOLDER, guild_mixers
from dashboard.file_utils import sync_get_soundboard_files
from loadnsave import (
    save_server_volumes,
    save_music_blacklist,
    load_ambience_scenes,
    save_ambience_scenes,
)
from commands.music import (
    MusicLookupError,
    _get_voice_env_diagnostics,
    _get_process_table_diagnostics,
    _voice_log_buffer,
)

music_bp = Blueprint('music', __name__)


@music_bp.route('/admin/music')
async def music_dashboard():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('music_dashboard.html')

@music_bp.route('/api/music/data')
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
                    "loop_mode": music_cog.loop_mode.get(guild_id, "off"),
                    "paused": track.paused,
                    "elapsed": round(track.elapsed, 1),
                    "duration": track.metadata.get('duration'),
                    "is_cached": bool(track.metadata.get('is_cached')),
                }

        # Queue
        queue = []
        if guild_id in music_cog.queue:
            for song in music_cog.queue[guild_id]:
                queue.append({
                    "title": song.get('title', 'Unknown'),
                    "original_url": song.get('original_url', ''),
                    "thumbnail": song.get('thumbnail', ''),
                    "duration": song.get('duration'),
                    "is_cached": bool(song.get('is_cached')),
                })

        # Voice channels
        voice_channels = [
            {
                "id": str(ch.id),
                "name": ch.name,
                "members": len([m for m in getattr(ch, "members", []) if not getattr(m, "bot", False)]),
            }
            for ch in getattr(guild, "voice_channels", [])
        ]
        vc = getattr(guild, "voice_client", None)
        connected_channel_id = (
            str(vc.channel.id)
            if vc and vc.is_connected() and getattr(vc, "channel", None)
            else None
        )

        # Active soundboard tracks in mixer
        mixer = guild_mixers.get(guild_id)
        active_sb = []
        if mixer:
            for t in getattr(mixer, "tracks", []):
                if not t.finished and (t.metadata or {}).get("type") == "soundboard":
                    bname = os.path.basename(t.file_path)
                    active_sb.append({
                        "id": t.id,
                        "name": bname,
                        "file": bname,
                        "loop": t.loop,
                        "volume": round((t.metadata or {}).get("volume_modifier", 1.0) * 100),
                    })

        data[guild_id] = {
            "name": guild.name,
            "current_track": current_track_info,
            "queue": queue,
            "voice_channels": voice_channels,
            "connected_channel_id": connected_channel_id,
            "active_soundboard": active_sb,
        }

    scenes_data = await load_ambience_scenes()
    sb_tree = await asyncio.to_thread(sync_get_soundboard_files, SOUNDBOARD_FOLDER)
    flat_sb_files = []
    if isinstance(sb_tree, dict):
        for folder, flist in sb_tree.items():
            if not isinstance(flist, list):
                continue
            for entry in flist:
                if isinstance(entry, dict):
                    fname = str(entry.get("name") or "")
                    rel = str(entry.get("path") or (fname if folder == "Root" else f"{folder}/{fname}"))
                else:
                    fname = str(entry)
                    rel = fname if folder == "Root" else f"{folder}/{fname}"
                if not fname:
                    continue
                flat_sb_files.append({
                    "file": rel,
                    "name": os.path.splitext(fname)[0],
                    "folder": "" if folder == "Root" else folder,
                })
    flat_sb_files.sort(key=lambda x: x["file"])

    ytdlp_status = getattr(music_cog, "last_ytdlp_status", "Auto-update active (24h)")
    ytdlp_checked_at = getattr(music_cog, "last_ytdlp_check", None)

    resp = {
        "guilds": data,
        "blacklist": music_cog.blacklist,
        "scenes": scenes_data.get("scenes", []),
        "soundboard_files": flat_sb_files,
        "ytdlp_status": ytdlp_status,
        "ytdlp_checked_at": ytdlp_checked_at,
        "diagnostics": {
            "env": _get_voice_env_diagnostics(),
            "processes": _get_process_table_diagnostics(),
            "voice_logs": _voice_log_buffer.get_recent(max_chars=1500),
            "last_bg_error": getattr(music_cog, "_last_bg_error", {}),
            "ytdlp_status": ytdlp_status,
            "ytdlp_checked_at": ytdlp_checked_at,
        },
    }
    if hasattr(music_cog, 'get_cache_status'):
        resp["cache"] = await music_cog.get_cache_status()

    return jsonify(resp)

@music_bp.route('/api/music/control', methods=['POST'])
async def music_control():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    action = data.get('action')
    guild_id = data.get('guild_id')

    if not app.bot or not hasattr(app.bot, 'music_cog'):
        return jsonify({"status": "error", "message": "Music system not ready"}), 500

    music_cog = app.bot.music_cog

    if action == 'pause':
        track = music_cog.current_track.get(guild_id)
        if track and not track.paused:
            track.paused = True
            guild = app.bot.get_guild(int(guild_id))
            if guild and guild.voice_client:
                guild.voice_client.pause()
    elif action == 'resume':
        track = music_cog.current_track.get(guild_id)
        if track and track.paused:
            track.paused = False
            guild = app.bot.get_guild(int(guild_id))
            if guild and guild.voice_client:
                guild.voice_client.resume()
    elif action == 'skip':
        track = music_cog.current_track.get(guild_id)
        if track:
            if hasattr(music_cog, '_fade_or_finish_track'):
                music_cog._fade_or_finish_track(track)
            else:
                track.finished = True
            await music_cog._process_queue(guild_id)
    elif action == 'loop':
        _cycle = {"off": "track", "track": "queue", "queue": "off"}
        current_mode = music_cog.loop_mode.get(guild_id, "off")
        new_mode = _cycle[current_mode]
        music_cog.loop_mode[guild_id] = new_mode
        track = music_cog.current_track.get(guild_id)
        if track and not track.finished:
            track.loop = (new_mode == "track")
    elif action == 'volume':
        vol = data.get('volume')
        clamped = max(0, min(100, int(vol)))
        new_vol = clamped / 100.0  # store linear (percent) in server_volumes

        if str(guild_id) not in server_volumes:
            server_volumes[str(guild_id)] = {'music': 1.0, 'soundboard': 0.5}

        server_volumes[str(guild_id)]['music'] = new_vol
        await save_server_volumes(server_volumes)

        track = music_cog.current_track.get(guild_id)
        if track:
            track.volume = (clamped / 100.0) ** 2  # log-scale amplitude for PCM
    elif action == 'seek':
        seconds = data.get('seconds')
        if seconds is not None:
            try:
                await music_cog._seek(guild_id, float(seconds))
            except MusicLookupError:
                pass  # track ended between page render and click; silently ignore like other stale-state actions
    elif action == 'remove':
        # Remove from queue
        index = data.get('index')
        if guild_id in music_cog.queue and 0 <= index < len(music_cog.queue[guild_id]):
            music_cog.queue[guild_id].pop(index)
    elif action == 'cache_settings':
        if hasattr(music_cog, 'update_cache_settings'):
            cache_status = await music_cog.update_cache_settings(
                enabled=data.get('enabled'),
                max_duration_minutes=data.get('max_duration_minutes'),
                max_size_gb=data.get('max_size_gb'),
            )
            return jsonify({"status": "success", "cache": cache_status})
    elif action == 'clear_cache':
        if hasattr(music_cog, 'clear_cache'):
            keep_favorites = bool(data.get('keep_favorites', True))
            removed, freed_bytes = await music_cog.clear_cache(keep_favorites=keep_favorites)
            return jsonify({
                "status": "success",
                "removed": removed,
                "freed_bytes": freed_bytes,
            })
    elif action == 'play':
        query = data.get('query', '')
        channel_id = data.get('channel_id')
        play_next = bool(data.get('play_next', False))
        replace_current = bool(data.get('replace_current', False))
        res = await music_cog.play_from_dashboard(
            guild_id=str(guild_id),
            query=query,
            channel_id=str(channel_id) if channel_id else None,
            play_next=play_next,
            replace_current=replace_current,
        )
        return jsonify(res), (200 if res.get("status") == "success" else 400)
    elif action == 'stop':
        music_cog._intentional_disconnects.add(str(guild_id))
        guild = app.bot.get_guild(int(guild_id)) if str(guild_id).isdigit() else None
        if guild and guild.voice_client and guild.voice_client.is_connected():
            guild.voice_client.stop()
            await guild.voice_client.disconnect(force=False)
        await music_cog._cleanup_guild(str(guild_id))
        await music_cog._update_dashboard_for_guild(str(guild_id))
    elif action == 'upgrade_ytdlp':
        if hasattr(music_cog, 'upgrade_ytdlp_now'):
            res = await music_cog.upgrade_ytdlp_now()
            return jsonify(res)

    return jsonify({"status": "success"})


@music_bp.route('/api/music/scenes', methods=['POST'])
async def music_scenes():
    if not is_admin():
        return "Unauthorized", 401

    if not app.bot or not hasattr(app.bot, 'music_cog'):
        return jsonify({"status": "error", "message": "Music system not ready"}), 500

    music_cog = app.bot.music_cog
    data = await request.get_json() or {}
    action = data.get('action')
    scenes_data = await load_ambience_scenes()
    scenes = scenes_data.setdefault("scenes", [])

    if action == 'save':
        payload = data.get('scene') if isinstance(data.get('scene'), dict) else data
        name = (payload.get('name') or '').strip()
        if not name:
            return jsonify({"status": "error", "message": "Scene name is required"}), 400

        scene_id = (payload.get('id') or payload.get('scene_id') or '').strip() or str(uuid.uuid4())[:8]
        sb_tracks = []
        raw_sb = payload.get('soundboard_tracks') or payload.get('soundboard') or []
        for item in raw_sb:
            fp = (item.get('file_path') or item.get('file') or '').strip()
            if not fp or '..' in fp:
                continue
            sb_tracks.append({
                "file": fp,
                "file_path": fp,
                "volume": max(0, min(100, int(item.get('volume', 80)))),
                "loop": bool(item.get('loop', True)),
            })

        music_q = (payload.get('music_query') or payload.get('music_url') or '').strip()
        scene_obj = {
            "id": scene_id,
            "name": name[:80],
            "icon": (payload.get('icon') or '🕯️').strip()[:8],
            "music_query": music_q,
            "music_url": music_q,
            "music_volume": max(0, min(100, int(payload.get('music_volume', 50)))),
            "music_loop": payload.get('music_loop') if payload.get('music_loop') in ('off', 'track', 'queue') else 'track',
            "soundboard_tracks": sb_tracks,
            "soundboard": sb_tracks,
        }

        replaced = False
        for idx, existing in enumerate(scenes):
            if existing.get("id") == scene_id:
                scenes[idx] = scene_obj
                replaced = True
                break
        if not replaced:
            scenes.append(scene_obj)

        await save_ambience_scenes(scenes_data)
        return jsonify({"status": "success", "scene": scene_obj, "scenes": scenes})

    elif action == 'delete':
        scene_id = (data.get('id') or data.get('scene_id') or '').strip()
        scenes[:] = [s for s in scenes if s.get("id") != scene_id]
        await save_ambience_scenes(scenes_data)
        return jsonify({"status": "success", "scenes": scenes})

    elif action == 'activate':
        scene_id = (data.get('id') or data.get('scene_id') or '').strip()
        guild_id = str(data.get('guild_id') or '')
        channel_id = data.get('channel_id')
        scene = next((s for s in scenes if s.get("id") == scene_id), None)
        if not scene:
            return jsonify({"status": "error", "message": "Scene not found"}), 404
        res = await music_cog.activate_ambience_scene(
            guild_id=guild_id,
            scene=scene,
            channel_id=str(channel_id) if channel_id else None,
        )
        return jsonify(res), (200 if res.get("status") == "success" else 400)

    elif action == 'stop_soundboard':
        guild_id = str(data.get('guild_id') or '')
        mixer = guild_mixers.get(guild_id)
        if mixer:
            with mixer.lock:
                sb_list = [
                    t for t in mixer.tracks
                    if not t.finished and (t.metadata or {}).get("type") == "soundboard"
                ]
            for t in sb_list:
                t.start_fade_out(0.8)
        return jsonify({"status": "success"})

    return jsonify({"status": "error", "message": "Unknown scene action"}), 400

@music_bp.route('/api/music/ban', methods=['POST'])
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
