from quart import Blueprint, request, jsonify, redirect, url_for, render_template

from dashboard.app import app, is_admin
from loadnsave import load_enroll_settings, save_enroll_settings

enroll_bp = Blueprint('enroll', __name__)

# --- Enrollment Wizard Routes ---

@enroll_bp.route('/admin/enroll')
async def admin_enroll():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('enroll_dashboard.html')

@enroll_bp.route('/admin/newspaper')
async def admin_newspaper():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('newspaper_dashboard.html')

@enroll_bp.route('/api/enroll/data')
async def enroll_data():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"guilds": []})

    settings = await load_enroll_settings()
    guilds_data = []

    for guild in app.bot.guilds:
        guild_id_str = str(guild.id)

        # Roles for dropdown
        roles = []
        for role in guild.roles:
            if not role.is_default() and not role.managed:
                roles.append({"id": str(role.id), "name": role.name, "color": str(role.color)})
        roles.sort(key=lambda x: x['name'])

        guild_settings = settings.get(guild_id_str, {})

        # Ensure defaults structure
        config = {
            "enabled": guild_settings.get("enabled", False),
            "final_message": guild_settings.get("final_message", "You have successfully enrolled!"),
            "pages": guild_settings.get("pages", [])
        }

        guilds_data.append({
            "id": guild_id_str,
            "name": guild.name,
            "roles": roles,
            "config": config
        })

    return jsonify({"guilds": guilds_data})

@enroll_bp.route('/api/enroll/save', methods=['POST'])
async def enroll_save():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    guild_id = data.get('guild_id')

    if not guild_id:
        return jsonify({"status": "error", "message": "Missing guild_id"}), 400

    settings = await load_enroll_settings()

    # Update settings for this guild
    settings[str(guild_id)] = {
        "enabled": bool(data.get('enabled', False)),
        "final_message": data.get('final_message', ""),
        "pages": data.get('pages', [])
    }

    await save_enroll_settings(settings)
    return jsonify({"status": "success"})
