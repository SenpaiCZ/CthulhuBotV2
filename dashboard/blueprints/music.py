from quart import Blueprint, request, jsonify, redirect, url_for, render_template

from dashboard.app import app, is_admin
from dashboard.state import server_volumes
from loadnsave import save_server_volumes, save_music_blacklist
from commands.music import MusicLookupError

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

    return jsonify({"status": "success"})

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
