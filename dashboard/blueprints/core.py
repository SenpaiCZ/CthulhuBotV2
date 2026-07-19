import os
import time
import asyncio
import secrets
import psutil
from quart import Blueprint, request, jsonify, session, redirect, url_for, render_template, send_from_directory

from dashboard.state import _APP_START, _failed_login_attempts, IMAGES_FOLDER, FONTS_FOLDER
from dashboard.app import app, get_image_url, is_admin
from ..file_utils import sanitize_filename, ALLOWED_IMAGE_EXTENSIONS
from loadnsave import load_settings_async

core_bp = Blueprint('core', __name__)


def check_rate_limit(ip):
    """
    Sentinel: Check if IP is rate limited for login.
    Limit: 5 attempts per 60 seconds.
    """
    now = time.time()
    attempts = _failed_login_attempts.get(ip, [])
    # Filter out old attempts
    attempts = [t for t in attempts if now - t < 60]

    if not attempts:
        if ip in _failed_login_attempts:
            del _failed_login_attempts[ip]
    else:
        _failed_login_attempts[ip] = attempts

    if len(attempts) >= 5:
        return False
    return True

def record_login_failure(ip):
    """
    Sentinel: Record a failed login attempt.
    """
    now = time.time()
    if ip not in _failed_login_attempts:
        _failed_login_attempts[ip] = []
    _failed_login_attempts[ip].append(now)

@core_bp.route('/api/status')
async def bot_status():
    is_ready = app.bot is not None and app.bot.is_ready()
    secs = int(time.monotonic() - _APP_START)
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    uptime = (f"{d}d " if d else "") + f"{h:02d}h {m:02d}m"
    latency = round(app.bot.latency * 1000) if is_ready else 0
    guilds = len(app.bot.guilds) if is_ready else 0
    try:
        proc = psutil.Process()
        mem_mb = round(proc.memory_info().rss / 1024 / 1024)
    except Exception:
        mem_mb = 0
    return jsonify({
        "status": "online",
        "ready": is_ready,
        "uptime": uptime,
        "latency_ms": latency,
        "guilds": guilds,
        "memory_mb": mem_mb,
    })

@core_bp.route('/fonts/<path:filename>')
async def serve_fonts(filename):
    try:
        full_path = os.path.abspath(os.path.join(FONTS_FOLDER, filename))
        if os.path.commonpath([full_path, os.path.abspath(FONTS_FOLDER)]) != os.path.abspath(FONTS_FOLDER):
            return "Invalid file path", 400
    except ValueError:
        return "Invalid file path", 400

    return await send_from_directory(FONTS_FOLDER, filename)

@core_bp.route('/images/<path:filename>')
async def serve_image(filename):
    try:
        full_path = os.path.abspath(os.path.join(IMAGES_FOLDER, filename))
        if os.path.commonpath([full_path, os.path.abspath(IMAGES_FOLDER)]) != os.path.abspath(IMAGES_FOLDER):
            return "Invalid file path", 400
    except ValueError:
        return "Invalid file path", 400

    return await send_from_directory(IMAGES_FOLDER, filename)

@core_bp.route('/api/images/upload', methods=['POST'])
async def upload_image():
    if not is_admin(): return "Unauthorized", 401

    form = await request.form
    files = await request.files

    type_slug = form.get('type_slug')
    name = form.get('name')
    file = files.get('file')

    if not type_slug or not name or not file:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    if not file.filename:
        return jsonify({"status": "error", "message": "No file selected"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"status": "error", "message": "Invalid file type"}), 400

    # Ensure type directory exists
    safe_type = sanitize_filename(type_slug)
    target_dir = os.path.join(IMAGES_FOLDER, safe_type)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    # Sanitize name
    safe_name = sanitize_filename(name)
    filename = f"{safe_name}{ext}"
    target_path = os.path.join(target_dir, filename)

    # Remove any existing images with different extensions for this entry
    for other_ext in ALLOWED_IMAGE_EXTENSIONS:
        other_filename = f"{safe_name}{other_ext}"
        other_path = os.path.join(target_dir, other_filename)
        if os.path.exists(other_path):
            os.remove(other_path)

    try:
        # Save file
        file_bytes = file.read()
        if asyncio.iscoroutine(file_bytes):
            file_bytes = await file_bytes

        with open(target_path, 'wb') as f:
            f.write(file_bytes)

        return jsonify({"status": "success", "url": f"/images/{safe_type}/{filename}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@core_bp.route('/api/images/delete', methods=['POST'])
async def delete_image():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    type_slug = data.get('type_slug')
    name = data.get('name')

    if not type_slug or not name:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    safe_type = sanitize_filename(type_slug)
    safe_name = sanitize_filename(name)
    target_dir = os.path.join(IMAGES_FOLDER, safe_type)

    deleted = False

    if os.path.exists(target_dir):
        for ext in ALLOWED_IMAGE_EXTENSIONS:
            filename = f"{safe_name}{ext}"
            target_path = os.path.join(target_dir, filename)
            if os.path.exists(target_path):
                try:
                    os.remove(target_path)
                    deleted = True
                except Exception as e:
                    return jsonify({"status": "error", "message": str(e)}), 500

    if deleted:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Image not found"}), 404

@core_bp.route('/api/images/check', methods=['GET'])
async def check_image():
    type_slug = request.args.get('type_slug')
    name = request.args.get('name')

    if not type_slug or not name:
        return jsonify({"found": False}), 400

    url = get_image_url(type_slug, name)
    if url:
        return jsonify({"found": True, "url": url})
    else:
        return jsonify({"found": False})

@core_bp.route('/')
async def index():
    return await render_template('index.html')

@core_bp.route('/login', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        # Sentinel: Rate Limiting
        ip = request.remote_addr
        if not check_rate_limit(ip):
             return await render_template('login.html', error="Too many failed attempts. Please try again later."), 429

        form = await request.form
        password = form.get('password')
        settings = await load_settings_async()

        # Sentinel: Prevent timing attacks
        input_password = password or ""
        expected_password = settings.get('admin_password', 'changeme') or ""

        if secrets.compare_digest(input_password, expected_password):
            # Sentinel: Clear failed attempts on success
            if ip in _failed_login_attempts:
                del _failed_login_attempts[ip]
            session['logged_in'] = True
            return redirect(url_for('admin.admin_dashboard'))
        else:
            # Sentinel: Record failure
            record_login_failure(ip)
            return await render_template('login.html', error="Invalid Password")
    return await render_template('login.html')

@core_bp.route('/logout')
async def logout():
    session.pop('logged_in', None)
    return redirect(url_for('core.index'))
