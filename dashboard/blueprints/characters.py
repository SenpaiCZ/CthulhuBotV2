from quart import Blueprint, request, jsonify, render_template
import emoji
import emojis
from dashboard.app import app, is_admin
from loadnsave import load_player_stats, save_player_stats, load_retired_characters_data, save_retired_characters_data

characters_bp = Blueprint('characters', __name__)


@characters_bp.route('/characters')
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

@characters_bp.route('/retired')
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

@characters_bp.route('/api/character/delete', methods=['POST'])
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
