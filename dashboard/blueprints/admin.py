import os
import shutil
import psutil
from quart import Blueprint, request, jsonify, redirect, url_for, render_template

from dashboard.app import is_admin
from dashboard.state import FONTS_FOLDER, BASIC_FONTS, console_log_buffer
from loadnsave import load_settings_async, save_settings

admin_bp = Blueprint('admin', __name__)


def _read_cpu_temp_c():
    """Read CPU temperature in Celsius on Linux / Raspberry Pi."""
    thermal_path = "/sys/class/thermal/thermal_zone0/temp"
    try:
        if os.path.exists(thermal_path):
            with open(thermal_path, "r", encoding="utf-8") as f:
                raw = float(f.read().strip())
                return round(raw / 1000.0 if raw > 200 else raw, 1)
    except Exception:
        pass
    try:
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures() or {}
            for entries in temps.values():
                for entry in entries:
                    if getattr(entry, "current", None) is not None:
                        return round(float(entry.current), 1)
    except Exception:
        pass
    return None


def _get_system_telemetry():
    """Collect CPU, RAM, Disk, and RPi temperature telemetry."""
    cpu_pct = 0.0
    try:
        cpu_pct = round(float(psutil.cpu_percent(interval=None)), 1)
    except Exception:
        pass

    ram_used_mb = 0
    ram_total_mb = 0
    ram_pct = 0.0
    try:
        vm = psutil.virtual_memory()
        ram_used_mb = round(vm.used / (1024 * 1024))
        ram_total_mb = round(vm.total / (1024 * 1024))
        ram_pct = round(float(vm.percent), 1)
    except Exception:
        pass

    bot_rss_mb = 0
    try:
        bot_rss_mb = round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 1)
    except Exception:
        pass

    disk_used_gb = 0.0
    disk_total_gb = 0.0
    disk_pct = 0.0
    try:
        du = shutil.disk_usage(".")
        disk_used_gb = round(du.used / (1024 ** 3), 1)
        disk_total_gb = round(du.total / (1024 ** 3), 1)
        disk_pct = round((du.used / du.total) * 100.0, 1) if du.total else 0.0
    except Exception:
        pass

    return {
        "cpu_percent": cpu_pct,
        "cpu_temp_c": _read_cpu_temp_c(),
        "ram_used_mb": ram_used_mb,
        "ram_total_mb": ram_total_mb,
        "ram_percent": ram_pct,
        "bot_rss_mb": bot_rss_mb,
        "disk_used_gb": disk_used_gb,
        "disk_total_gb": disk_total_gb,
        "disk_percent": disk_pct,
    }


@admin_bp.route('/api/admin/system')
async def admin_system_telemetry():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({
        "telemetry": _get_system_telemetry(),
        "console_logs": list(console_log_buffer),
    })


@admin_bp.route('/api/admin/console/clear', methods=['POST'])
async def admin_console_clear():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    console_log_buffer.clear()
    return jsonify({"status": "success"})


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
