import os
import json
from quart import Quart, render_template, request, redirect, url_for, session, jsonify, abort
from loadnsave import (
    load_player_stats, load_retired_characters_data, load_settings, save_settings,
    _load_json_file, _save_json_file, DATA_FOLDER, INFODATA_FOLDER
)

app = Quart(__name__)
app.secret_key = os.urandom(24)

# Helper to check login
def is_admin():
    return session.get('logged_in', False)

@app.context_processor
def inject_user():
    return dict(is_admin=is_admin())

@app.route('/')
async def index():
    return await render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        form = await request.form
        password = form.get('password')
        settings = load_settings()
        if password == settings.get('admin_password', 'changeme'):
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return await render_template('login.html', error="Invalid Password")
    return await render_template('login.html')

@app.route('/logout')
async def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/characters')
async def characters():
    stats = await load_player_stats()
    # stats is a dict, likely {user_id: {char_data...}}
    return await render_template('list_characters.html', title="Active Characters", data=stats, type="active")

@app.route('/retired')
async def retired():
    stats = await load_retired_characters_data()
    return await render_template('list_characters.html', title="Retired Characters", data=stats, type="retired")

# --- Admin Routes ---

@app.route('/admin')
async def admin_dashboard():
    if not is_admin(): return redirect(url_for('login'))
    return await render_template('admin_dashboard.html')

@app.route('/admin/settings')
async def admin_settings():
    if not is_admin(): return redirect(url_for('login'))
    # Direct to editing settings.json
    return redirect(url_for('edit_file', folder_name='data', filename='settings.json'))

@app.route('/admin/browse/<folder_name>')
async def browse_files(folder_name):
    if not is_admin(): return redirect(url_for('login'))

    if folder_name == 'infodata':
        target_dir = INFODATA_FOLDER
    elif folder_name == 'data':
        target_dir = DATA_FOLDER
    else:
        return "Invalid folder", 400

    if not os.path.exists(target_dir):
        files = []
    else:
        files = [f for f in os.listdir(target_dir) if f.endswith('.json')]

    files.sort()
    return await render_template('file_browser.html', folder=folder_name, files=files)

@app.route('/admin/edit/<folder_name>/<filename>')
async def edit_file(folder_name, filename):
    if not is_admin(): return redirect(url_for('login'))

    if folder_name == 'infodata':
        target_dir = INFODATA_FOLDER
    elif folder_name == 'data':
        target_dir = DATA_FOLDER
    else:
        return "Invalid folder", 400

    # Security check
    if '..' in filename or '/' in filename:
        return "Invalid filename", 400

    content = await _load_json_file(target_dir, filename)
    formatted_json = json.dumps(content, indent=4)
    return await render_template('json_editor.html', folder=folder_name, filename=filename, content=formatted_json)

@app.route('/api/save/<folder_name>/<filename>', methods=['POST'])
async def save_file(folder_name, filename):
    if not is_admin(): return "Unauthorized", 401

    if folder_name == 'infodata':
        target_dir = INFODATA_FOLDER
    elif folder_name == 'data':
        target_dir = DATA_FOLDER
    else:
        return "Invalid folder", 400

    if '..' in filename or '/' in filename:
        return "Invalid filename", 400

    try:
        data = await request.get_json()
        json_content = data.get('content')
        # Validate JSON
        parsed = json.loads(json_content)

        await _save_json_file(target_dir, filename, parsed)
        return jsonify({"status": "success"})
    except json.JSONDecodeError:
        return jsonify({"status": "error", "message": "Invalid JSON format"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
