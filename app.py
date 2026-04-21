from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime
import os
import uuid
import threading
import time
import secrets

from database import Database
from bot_runner import BotRunner

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'py'}

ADMIN_USERNAME = "NASSIM"
ADMIN_PASSWORD = "NASSIM2024"
MASTER_CODE = "NASSIM2024"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = Database()
runner = BotRunner(db)

# ========== Helpers ==========
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_user_expired(user_id):
    user = db.get_user(user_id)
    if not user or not user.get('expires_at'):
        return True
    try:
        expires_at = user['expires_at']
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        return datetime.now() > expires_at
    except:
        return True

# تنظيف دوري
def cleanup_expired_users():
    while True:
        time.sleep(3600)
        users = db.get_all_users()
        for user in users:
            try:
                if not user.get('is_admin') and is_user_expired(user['id']):
                    db.delete_user_with_bots(user['id'])
            except:
                pass

threading.Thread(target=cleanup_expired_users, daemon=True).start()

# ========== Auth ==========
def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def admin_required(f):
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# ========== Routes ==========
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('admin_panel') if session.get('is_admin') else url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        code = request.form.get('activation_code', '').strip().upper()

        if code == MASTER_CODE:
            session['user_id'] = 1
            session['username'] = 'NASSIM'
            session['is_admin'] = True
            return redirect(url_for('admin_panel'))

        user = db.verify_activation_code(code)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user.get('is_admin', False)
            return redirect(url_for('dashboard'))

        return render_template('login.html', error="Invalid code")

    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/admin')
@admin_required
def admin_panel():
    return render_template('admin.html')

# ========== API ==========
@app.route('/api/upload_bot', methods=['POST'])
@login_required
def upload_bot():
    if 'file' not in request.files:
        return jsonify({'error': 'no file'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'empty file'}), 400

    filename = f"{uuid.uuid4().hex}.py"
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    bot_id = db.add_bot(session['user_id'], filename, path, file.filename)

    return jsonify({'success': True, 'bot_id': bot_id})

@app.route('/api/start_bot/<bot_id>', methods=['POST'])
@login_required
def start_bot(bot_id):
    bot = db.get_bot(bot_id)

    if not bot:
        return jsonify({'error': 'not found'}), 404

    if bot['user_id'] != session['user_id']:
        return jsonify({'error': 'unauthorized'}), 403

    result = runner.start_bot(bot_id)
    return jsonify(result)

@app.route('/api/stop_bot/<bot_id>', methods=['POST'])
@login_required
def stop_bot(bot_id):
    result = runner.stop_bot(bot_id)
    return jsonify(result)

@app.route('/api/delete_bot/<bot_id>', methods=['DELETE'])
@login_required
def delete_bot(bot_id):
    bot = db.get_bot(bot_id)

    if bot and bot['user_id'] == session['user_id']:
        try:
            os.remove(bot['file_path'])
        except:
            pass

        db.delete_bot(bot_id)

    return jsonify({'success': True})

# ========== Render RUN ==========
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)