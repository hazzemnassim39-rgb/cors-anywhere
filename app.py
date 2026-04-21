from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import json
import uuid
import threading
import subprocess
import signal
import time
import hashlib
import secrets
from database import Database
from bot_runner import BotRunner

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
socketio = SocketIO(app)

# إعدادات
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'py'}
ADMIN_USERNAME = "NASSIM"
ADMIN_PASSWORD = "NASSIM2024"  # غيرها

# ✅ كود ثابت للمشرف (للدخول السريع)
MASTER_CODE = "NASSIM2024"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

db = Database()
runner = BotRunner(db)

# ============== وظائف مساعدة ==============
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ✅ دالة التحقق من صلاحية المستخدم
def is_user_expired(user_id):
    """ترجع True إذا كان المستخدم منتهي الصلاحية"""
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

# ✅ دالة تنظيف المستخدمين منتهي الصلاحية (تعمل كل ساعة)
def cleanup_expired_users():
    """حذف جميع المستخدمين منتهي الصلاحية وبوتاتهم بشكل دوري"""
    while True:
        time.sleep(3600)  # كل ساعة
        users = db.get_all_users()
        for user in users:
            if not user.get('is_admin', False):
                if is_user_expired(user['id']):
                    try:
                        db.delete_user_with_bots(user['id'])
                    except:
                        pass

# بدء مهمة التنظيف الدورية
threading.Thread(target=cleanup_expired_users, daemon=True).start()

def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        # ✅ فحص صلاحية المستخدم
        if is_user_expired(session['user_id']):
            # حذف المستخدم تلقائياً
            db.delete_user_with_bots(session['user_id'])
            session.clear()
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def admin_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin', False):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# ============== صفحات الموقع ==============
@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('is_admin'):
            return redirect(url_for('admin_panel'))
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        activation_code = request.form.get('activation_code', '').strip().upper()
        
        # ✅ الكود الثابت للمشرف (NASSIM2024)
        if activation_code == MASTER_CODE:
            session['user_id'] = 1
            session['username'] = 'NASSIM'
            session['is_admin'] = True
            session['expires_at'] = '2099-12-31'
            return redirect(url_for('admin_panel'))
        
        # التحقق من الكود من قاعدة البيانات
        user = db.verify_activation_code(activation_code)
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user.get('is_admin', False)
            session['expires_at'] = user['expires_at']
            
            if user.get('is_admin'):
                return redirect(url_for('admin_panel'))
            return redirect(url_for('dashboard'))
        
        return render_template('login.html', error="❌ كود التفعيل غير صحيح أو منتهي الصلاحية")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if session.get('is_admin'):
        return redirect(url_for('admin_panel'))
    
    user_id = session['user_id']
    bots = db.get_user_bots(user_id)
    user_info = db.get_user(user_id)
    
    return render_template('dashboard.html', 
                         bots=bots, 
                         user=user_info,
                         username=session.get('username'))

@app.route('/admin')
@admin_required
def admin_panel():
    users = db.get_all_users()
    codes = db.get_all_codes()
    bots = db.get_all_bots()
    stats = db.get_stats()
    
    return render_template('admin.html',
                         users=users,
                         codes=codes,
                         bots=bots,
                         stats=stats,
                         admin_name=ADMIN_USERNAME)

# ============== API للمستخدمين ==============
@app.route('/api/upload_bot', methods=['POST'])
@login_required
def upload_bot():
    # ✅ منع الرفع إذا انتهت الصلاحية
    if is_user_expired(session['user_id']):
        return jsonify({'error': 'انتهت صلاحية حسابك. لا يمكن رفع البوتات.'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'لم يتم رفع ملف'}), 400
    
    file = request.files['file']
    bot_name = request.form.get('bot_name', '').strip()
    
    if file.filename == '':
        return jsonify({'error': 'الملف فارغ'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'فقط ملفات .py مسموحة'}), 400
    
    if not bot_name:
        bot_name = file.filename.replace('.py', '')
    
    # حفظ الملف
    filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    # إضافة البوت لقاعدة البيانات
    bot_id = db.add_bot(
        user_id=session['user_id'],
        bot_name=bot_name,
        file_path=filepath,
        original_name=file.filename
    )
    
    return jsonify({'success': True, 'bot_id': bot_id, 'message': 'تم رفع البوت بنجاح'})

@app.route('/api/start_bot/<bot_id>', methods=['POST'])
@login_required
def start_bot(bot_id):
    # ✅ منع التشغيل إذا انتهت الصلاحية
    if is_user_expired(session['user_id']):
        return jsonify({'error': 'انتهت صلاحية حسابك. لا يمكن تشغيل البوتات.'}), 403
    
    # التحقق من ملكية البوت
    bot = db.get_bot(bot_id)
    if not bot or bot['user_id'] != session['user_id']:
        return jsonify({'error': 'غير مصرح'}), 403
    
    # تشغيل البوت
    result = runner.start_bot(bot_id)
    
    if result['success']:
        db.update_bot_status(bot_id, 'running', result.get('bot_username'))
        # إرسال تحديث عبر WebSocket
        socketio.emit('bot_status_update', {
            'bot_id': bot_id,
            'status': 'running',
            'bot_username': result.get('bot_username')
        })
    
    return jsonify(result)

@app.route('/api/stop_bot/<bot_id>', methods=['POST'])
@login_required
def stop_bot(bot_id):
    bot = db.get_bot(bot_id)
    if not bot or bot['user_id'] != session['user_id']:
        return jsonify({'error': 'غير مصرح'}), 403
    
    result = runner.stop_bot(bot_id)
    
    if result['success']:
        db.update_bot_status(bot_id, 'stopped')
        socketio.emit('bot_status_update', {
            'bot_id': bot_id,
            'status': 'stopped'
        })
    
    return jsonify(result)

@app.route('/api/delete_bot/<bot_id>', methods=['DELETE'])
@login_required
def delete_bot(bot_id):
    bot = db.get_bot(bot_id)
    if not bot or bot['user_id'] != session['user_id']:
        return jsonify({'error': 'غير مصرح'}), 403
    
    # إيقاف البوت أولاً إذا كان يعمل
    if bot['status'] == 'running':
        runner.stop_bot(bot_id)
    
    # حذف الملف
    try:
        os.remove(bot['file_path'])
    except:
        pass
    
    db.delete_bot(bot_id)
    
    return jsonify({'success': True, 'message': 'تم حذف البوت'})

# ============== API للمشرف ==============
@app.route('/api/admin/create_code', methods=['POST'])
@admin_required
def create_code():
    data = request.json
    username = data.get('username', 'user')
    days = int(data.get('days', 30))
    is_admin = data.get('is_admin', False)
    
    code = db.create_activation_code(username, days, is_admin)
    
    return jsonify({
        'success': True,
        'code': code,
        'username': username,
        'expires_in_days': days
    })

@app.route('/api/admin/delete_user/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    db.delete_user(user_id)
    return jsonify({'success': True})

@app.route('/api/admin/extend_user/<user_id>', methods=['POST'])
@admin_required
def extend_user(user_id):
    days = request.json.get('days', 30)
    db.extend_user_expiry(user_id, days)
    return jsonify({'success': True})

@app.route('/api/admin/delete_code/<code>', methods=['DELETE'])
@admin_required
def delete_code(code):
    db.delete_code(code)
    return jsonify({'success': True})

@app.route('/api/stats')
@login_required
def get_stats():
    if session.get('is_admin'):
        stats = db.get_stats()
    else:
        stats = db.get_user_stats(session['user_id'])
    
    return jsonify(stats)

# ============== API للتحقق من المستخدم الحالي ==============
@app.route('/api/current_user')
def current_user():
    if 'user_id' in session:
        return jsonify({
            'authenticated': True,
            'username': session.get('username'),
            'is_admin': session.get('is_admin', False)
        })
    return jsonify({'authenticated': False})

# ============== تشغيل متكيف مع Hugging Face ==============
if __name__ == '__main__':
    import os
    
    # المنفذ المطلوب من Hugging Face Spaces هو 7860
    # استخدام متغير البيئة PORT هو أفضل الممارسات
    port = int(os.environ.get('PORT', 7860))
    
    print("\n" + "="*60)
    print("🚀 NASSIM HOSTING - تم تشغيل السيرفر")
    print("="*60)
    print(f"🎫 كود المشرف: {MASTER_CODE}")
    print("="*60 + "\n")
    
    # تشغيل Flask على المنفذ الصحيح
    app.run(host='0.0.0.0', port=port, debug=False)