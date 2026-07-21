import re
from quart import Blueprint, request, jsonify, render_template, redirect, url_for
import discord

from dashboard.app import app, is_admin
from loadnsave import load_giveaway_data

giveaway_bp = Blueprint('giveaway', __name__)

# --- Giveaway Routes ---

@giveaway_bp.route('/admin/giveaway')
async def admin_giveaway():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('giveaway_dashboard.html')

@giveaway_bp.route('/api/giveaway/data')
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

@giveaway_bp.route('/api/giveaway/create', methods=['POST'])
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

@giveaway_bp.route('/api/giveaway/end', methods=['POST'])
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

@giveaway_bp.route('/api/giveaway/reroll', methods=['POST'])
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
