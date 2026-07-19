import os
from quart import Blueprint, request, jsonify, redirect, url_for, render_template

from dashboard.app import is_admin
from dashboard.state import FONTS_FOLDER, BASIC_FONTS
from loadnsave import load_settings_async, save_settings

admin_bp = Blueprint('admin', __name__)


# --- Admin Routes ---

@admin_bp.route('/admin')
async def admin_dashboard():
    if not is_admin(): return redirect(url_for('core.login'))
    return await render_template('admin_dashboard.html')

@admin_bp.route('/admin/design')
async def admin_design():
    if not is_admin(): return redirect(url_for('core.login'))
    settings = await load_settings_async()
    current_theme = settings.get('dashboard_theme', 'cthulhu')
    current_fonts = settings.get('dashboard_fonts', {})
    current_origin_fonts = settings.get('origin_fonts', {})

    # Load uploaded fonts
    uploaded_fonts = []
    if os.path.exists(FONTS_FOLDER):
        for f in os.listdir(FONTS_FOLDER):
            if f.lower().endswith(('.ttf', '.otf', '.woff', '.woff2')):
                uploaded_fonts.append(f)
    uploaded_fonts.sort()

    return await render_template('design_dashboard.html',
                               current_theme=current_theme,
                               basic_fonts=BASIC_FONTS,
                               uploaded_fonts=uploaded_fonts,
                               current_fonts=current_fonts,
                               current_origin_fonts=current_origin_fonts)

@admin_bp.route('/api/design/save_fonts', methods=['POST'])
async def save_fonts():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    headers_font = data.get('headers')
    body_font = data.get('body')
    special_font = data.get('special')

    settings = await load_settings_async()
    if 'dashboard_fonts' not in settings:
        settings['dashboard_fonts'] = {}

    settings['dashboard_fonts']['headers'] = headers_font
    settings['dashboard_fonts']['body'] = body_font
    settings['dashboard_fonts']['special'] = special_font

    await save_settings(settings)
    return jsonify({"status": "success"})

@admin_bp.route('/api/design/save_origin_fonts', methods=['POST'])
async def save_origin_fonts():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    headers_font = data.get('headers')
    body_font = data.get('body')
    special_font = data.get('special')

    settings = await load_settings_async()
    if 'origin_fonts' not in settings:
        settings['origin_fonts'] = {}

    settings['origin_fonts']['headers'] = headers_font
    settings['origin_fonts']['body'] = body_font
    settings['origin_fonts']['special'] = special_font

    await save_settings(settings)
    return jsonify({"status": "success"})

@admin_bp.route('/api/design/save', methods=['POST'])
async def save_design():
    if not is_admin(): return "Unauthorized", 401

    data = await request.get_json()
    theme = data.get('theme')

    if not theme:
        return jsonify({"status": "error", "message": "Missing theme"}), 400

    settings = await load_settings_async()
    settings['dashboard_theme'] = theme
    await save_settings(settings)

    return jsonify({"status": "success"})
