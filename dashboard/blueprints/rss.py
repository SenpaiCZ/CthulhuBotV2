import asyncio
import feedparser
from quart import Blueprint, request, jsonify, redirect, url_for, render_template

from dashboard.app import app, is_admin
from loadnsave import load_rss_data, save_rss_data
from rss_utils import get_youtube_rss_url

rss_bp = Blueprint('rss', __name__)


@rss_bp.route('/admin/rss')
async def admin_rss():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('rss_dashboard.html')

@rss_bp.route('/api/rss/data')
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

@rss_bp.route('/api/rss/add', methods=['POST'])
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
        feed = await asyncio.get_running_loop().run_in_executor(None, feedparser.parse, link)
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
        if sub['link'] == link and str(sub.get('channel_id')) == str(channel_id):
             return jsonify({"status": "error", "message": "Feed already subscribed in this channel"}), 400

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

@rss_bp.route('/api/rss/update_color', methods=['POST'])
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

@rss_bp.route('/api/rss/delete', methods=['POST'])
async def rss_delete():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')
    link = data.get('link')

    if not all([guild_id, link]):
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    rss_data = await load_rss_data()

    if str(guild_id) not in rss_data:
        return jsonify({"status": "error", "message": "No feeds for this server"}), 404

    original_len = len(rss_data[str(guild_id)])
    rss_data[str(guild_id)] = [s for s in rss_data[str(guild_id)] if s['link'] != link]

    if len(rss_data[str(guild_id)]) == original_len:
        return jsonify({"status": "error", "message": "Feed not found"}), 404

    if not rss_data[str(guild_id)]:
        del rss_data[str(guild_id)]

    await save_rss_data(rss_data)
    return jsonify({"status": "success"})
