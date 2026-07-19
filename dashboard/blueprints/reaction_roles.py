import re
from quart import Blueprint, request, jsonify, render_template, redirect, url_for
import discord

from dashboard.app import app, is_admin
from loadnsave import load_reaction_roles, save_reaction_roles

reaction_roles_bp = Blueprint('reaction_roles', __name__)

# --- Reaction Roles Routes ---

@reaction_roles_bp.route('/admin/reactionroles')
async def admin_reaction_roles():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('reaction_roles.html')

@reaction_roles_bp.route('/api/reactionroles/data')
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

@reaction_roles_bp.route('/api/reactionroles/add', methods=['POST'])
async def reaction_roles_add():
    if not is_admin(): return "Unauthorized", 401

    data_in = await request.get_json()
    guild_id = data_in.get('guild_id')
    message_id = data_in.get('message_id')
    role_id = data_in.get('role_id')
    emoji_str = data_in.get('emoji')
    channel_id = data_in.get('channel_id')

    if not all([guild_id, message_id, role_id, emoji_str, channel_id]):
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

@reaction_roles_bp.route('/api/reactionroles/delete', methods=['POST'])
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
                        # 1. Check bot's message cache first
                        cached_msgs = getattr(app.bot, 'cached_messages', [])
                        for msg in cached_msgs:
                            if msg.id == int(message_id) and msg.guild and msg.guild.id == int(guild_id):
                                message = msg
                                break

                    if not message:
                        # Fallback search if channel_id missing or incorrect
                        for chan in guild.text_channels:
                            try:
                                message = await chan.fetch_message(int(message_id))
                                # Update channel_id in data to avoid future N+1 searches
                                if "roles" in message_data:
                                    message_data["channel_id"] = str(chan.id)
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
