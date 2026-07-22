import os
import re
import sys
import subprocess
import datetime
from quart import Blueprint, request, jsonify, redirect, url_for, render_template, send_from_directory

from dashboard.app import app, is_admin
from dashboard.state import BACKUP_FOLDER
from loadnsave import load_settings_async, save_settings
from backup_utils import get_system_backups

backup_bp = Blueprint('backup', __name__)

# --- Backup Routes ---

@backup_bp.route('/admin/backup')
async def admin_backup():
    if not is_admin(): return redirect(url_for('core.login'))
    settings = await load_settings_async()
    backup_time = settings.get('backup_time')
    return await render_template('backup_dashboard.html', backup_time=backup_time)

@backup_bp.route('/api/backup/save', methods=['POST'])
async def backup_save():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    backup_time = data.get('backup_time')

    # Validation
    if backup_time:
        if not re.match(r'^\d{2}:\d{2}$', backup_time):
             return jsonify({"status": "error", "message": "Invalid time format (HH:MM required)"}), 400

    settings = await load_settings_async()
    settings['backup_time'] = backup_time
    await save_settings(settings)

    return jsonify({"status": "success"})

@backup_bp.route('/api/backup/run', methods=['POST'])
async def backup_run():
    if not is_admin(): return "Unauthorized", 401

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    cog = app.bot.get_cog("backup")
    if not cog:
        return jsonify({"status": "error", "message": "Backup cog not loaded"}), 500

    # Run backup
    success, result = await cog.perform_backup()

    if success:
        return jsonify({"status": "success", "filename": result})
    else:
        return jsonify({"status": "error", "message": result}), 500

# --- System Backups (Physical Files) ---

@backup_bp.route('/api/backup/files')
async def backup_files_list():
    if not is_admin(): return "Unauthorized", 401
    return jsonify(get_system_backups(BACKUP_FOLDER))

@backup_bp.route('/api/backup/delete', methods=['POST'])
async def backup_delete_file():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    filename = data.get('filename')

    if not filename:
        return jsonify({"status": "error", "message": "Missing filename"}), 400

    # Security checks
    if not filename.endswith('.zip'):
         return jsonify({"status": "error", "message": "Invalid file type"}), 400

    if '..' in filename or '/' in filename or '\\' in filename:
         return jsonify({"status": "error", "message": "Invalid filename"}), 400

    target_path = os.path.join(BACKUP_FOLDER, filename)

    if not os.path.exists(target_path):
        return jsonify({"status": "error", "message": "File not found"}), 404

    try:
        os.remove(target_path)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@backup_bp.route('/api/backup/restore', methods=['POST'])
async def backup_restore():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    filename = data.get('filename')

    if not filename or not filename.endswith('.zip'):
        return jsonify({"status": "error", "message": "Invalid filename"}), 400
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({"status": "error", "message": "Invalid filename"}), 400

    target_path = os.path.join(BACKUP_FOLDER, filename)
    if not os.path.exists(target_path):
        return jsonify({"status": "error", "message": "File not found"}), 404

    if not app.bot:
        return jsonify({"status": "error", "message": "Bot not ready"}), 500

    pid = str(os.getpid())
    cmd = [sys.executable, "updater.py", pid, "--restore", filename]

    try:
        if os.name == 'nt':
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen(cmd)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to start restore: {e}"}), 500

    await app.bot.close()
    return jsonify({"status": "success"})

@backup_bp.route('/admin/backup/download/<filename>')
async def backup_download_file(filename):
    if not is_admin(): return redirect(url_for('core.login'))

    # Security checks
    try:
        full_path = os.path.abspath(os.path.join(BACKUP_FOLDER, filename))
        if os.path.commonpath([full_path, os.path.abspath(BACKUP_FOLDER)]) != os.path.abspath(BACKUP_FOLDER):
            return "Invalid file path", 400
    except ValueError:
        return "Invalid file path", 400

    if not os.path.exists(full_path):
        return "File not found", 404

    return await send_from_directory(BACKUP_FOLDER, filename, as_attachment=True)
