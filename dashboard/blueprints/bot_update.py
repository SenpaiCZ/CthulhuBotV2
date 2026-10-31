import os
import sys
import subprocess
import asyncio
from quart import Blueprint, request, jsonify

from dashboard.app import app, is_admin

bot_update_bp = Blueprint('bot_update', __name__)

@bot_update_bp.route('/api/admin/update', methods=['POST'])
async def admin_update_bot():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json(silent=True)
    update_infodata = False
    if data:
        update_infodata = data.get('update_infodata', False)

    updater_script = "updater.py"
    if not os.path.exists(updater_script):
        return jsonify({"status": "error", "message": "Updater script not found"}), 500

    pid = str(os.getpid())
    python_exe = sys.executable

    # Pre-apply update while bot.py is still alive so systemd KillMode=control-group
    # cannot SIGKILL the updater mid-download when bot.py exits.
    if os.name != 'nt':
        prep_cmd = [python_exe, updater_script, "--no-restart"]
        if update_infodata:
            prep_cmd.append("--update-infodata")
        try:
            proc = await asyncio.create_subprocess_exec(*prep_cmd)
            await asyncio.wait_for(proc.wait(), timeout=180)
        except Exception as e:
            print(f"[DashboardUpdate] Pre-apply warning: {e}")

    cmd = [python_exe, updater_script, pid]
    if update_infodata:
        cmd.append("--update-infodata")

    try:
        if os.name == 'nt':
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen(cmd, start_new_session=True)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    # We need to shut down the bot/app.
    # Since this is running in Hypercorn via bot.py (which imports app),
    # we can try to close the bot if available, or just exit.

    if app.bot:
        await app.bot.close()

    # We schedule a sys.exit shortly to allow the response to return
    app.add_background_task(shutdown_process)

    return jsonify({"status": "success", "message": "Update started. Bot is restarting..."})

async def shutdown_process():
    await asyncio.sleep(1)
    sys.exit(0)
