import os
import asyncio
from quart import Blueprint, request, jsonify, redirect, url_for, render_template

from dashboard.app import is_admin
from dashboard.state import FONTS_FOLDER
from ..file_utils import sanitize_filename
from loadnsave import load_fonts_config, save_fonts_config

fonts_admin_bp = Blueprint('fonts_admin', __name__)


# --- Font Management Routes ---

@fonts_admin_bp.route('/admin/fonts')
async def admin_fonts():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('fonts_dashboard.html')

@fonts_admin_bp.route('/api/fonts/list')
async def fonts_list():
    if not is_admin(): return "Unauthorized", 401

    files = []
    config = await load_fonts_config()
    if os.path.exists(FONTS_FOLDER):
        for f in os.listdir(FONTS_FOLDER):
            if f.lower().endswith(('.ttf', '.otf', '.woff', '.woff2')):
                category = config.get(f, "Decorative")
                files.append({"filename": f, "category": category})
    files.sort(key=lambda x: x['filename'])
    return jsonify({"fonts": files})

@fonts_admin_bp.route('/api/fonts/upload', methods=['POST'])
async def fonts_upload():
    if not is_admin(): return "Unauthorized", 401

    files = await request.files
    uploaded_files = files.getlist('files')
    form = await request.form
    category = form.get('category', 'Decorative')

    if not uploaded_files:
        return jsonify({"status": "error", "message": "No files uploaded"}), 400

    results = []
    config = await load_fonts_config()

    for file in uploaded_files:
        if not file.filename: continue

        filename = sanitize_filename(file.filename)
        # Preserve extension properly (sanitize might strip dots if not careful, but usually file_utils preserves it or we assume it doesn't)
        # Let's check sanitize_filename in file_utils... assumed safe.
        # But wait, sanitize_filename often replaces '.'
        # I should probably split ext first.

        base, ext = os.path.splitext(file.filename)
        safe_base = sanitize_filename(base)
        ext = ext.lower()

        if ext not in ['.ttf', '.otf', '.woff', '.woff2']:
            results.append(f"Skipped {file.filename} (invalid type)")
            continue

        safe_filename = f"{safe_base}{ext}"
        target_path = os.path.join(FONTS_FOLDER, safe_filename)

        try:
            file_bytes = file.read()
            if asyncio.iscoroutine(file_bytes):
                file_bytes = await file_bytes

            with open(target_path, 'wb') as f:
                f.write(file_bytes)

            config[safe_filename] = category
            results.append(f"Uploaded {safe_filename} ({category})")
        except Exception as e:
            results.append(f"Error {file.filename}: {e}")

    await save_fonts_config(config)
    return jsonify({"status": "success", "results": results})

@fonts_admin_bp.route('/api/fonts/delete', methods=['POST'])
async def fonts_delete():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    filename = data.get('filename')

    if not filename:
        return jsonify({"status": "error", "message": "Missing filename"}), 400

    if '..' in filename or '/' in filename:
        return jsonify({"status": "error", "message": "Invalid filename"}), 400

    target_path = os.path.join(FONTS_FOLDER, filename)

    if os.path.exists(target_path):
        try:
            os.remove(target_path)

            # Remove from config
            config = await load_fonts_config()
            if filename in config:
                del config[filename]
                await save_fonts_config(config)

            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "error", "message": "File not found"}), 404

@fonts_admin_bp.route('/api/fonts/update_category', methods=['POST'])
async def fonts_update_category():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    filename = data.get('filename')
    category = data.get('category')

    if not filename or not category:
        return jsonify({"status": "error", "message": "Missing arguments"}), 400

    config = await load_fonts_config()
    config[filename] = category
    await save_fonts_config(config)

    return jsonify({"status": "success"})
