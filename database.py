import sqlite3
import secrets
import string
from datetime import datetime, timedelta
import json
import os

class Database:
    def __init__(self, db_path='nassim_hosting.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # جدول المستخدمين
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    activation_code TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    is_admin BOOLEAN DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            # جدول البوتات
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bots (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    bot_name TEXT NOT NULL,
                    bot_username TEXT,
                    file_path TEXT NOT NULL,
                    original_name TEXT,
                    status TEXT DEFAULT 'stopped',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_start TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # جدول أكواد التفعيل
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS activation_codes (
                    code TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    days INTEGER DEFAULT 30,
                    is_admin BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    used_by INTEGER,
                    used_at TIMESTAMP,
                    FOREIGN KEY (used_by) REFERENCES users (id)
                )
            ''')
            
            # إضافة المشرف الافتراضي
            cursor.execute('SELECT COUNT(*) FROM users WHERE is_admin = 1')
            if cursor.fetchone()[0] == 0:
                admin_code = self._generate_code()
                expires = (datetime.now() + timedelta(days=36500)).isoformat()  # 100 سنة
                cursor.execute('''
                    INSERT INTO users (username, activation_code, expires_at, is_admin)
                    VALUES (?, ?, ?, ?)
                ''', ('NASSIM', admin_code, expires, True))
                
                cursor.execute('''
                    INSERT INTO activation_codes (code, username, days, is_admin, used_by, used_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (admin_code, 'NASSIM', 36500, True, 1, datetime.now().isoformat()))
                
                print(f"\n{'='*50}")
                print(f"👑 كود المشرف: {admin_code}")
                print(f"👤 اسم المستخدم: NASSIM")
                print(f"{'='*50}\n")
    
    def _generate_code(self, length=10):
        alphabet = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def create_activation_code(self, username, days, is_admin=False):
        code = self._generate_code()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO activation_codes (code, username, days, is_admin)
                VALUES (?, ?, ?, ?)
            ''', (code, username, days, is_admin))
        
        return code
    
    def verify_activation_code(self, code):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # ✅ أولاً: البحث عن مستخدم موجود بهذا الكود
            cursor.execute('''
                SELECT * FROM users 
                WHERE activation_code = ?
            ''', (code,))
            
            existing_user = cursor.fetchone()
            
            if existing_user:
                # ✅ فحص صلاحية الحساب (تاريخ الانتهاء)
                expires_at = existing_user['expires_at']
                if expires_at:
                    expiry = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    if datetime.now() > expiry:
                        # انتهت الصلاحية - حذف المستخدم وبوتاته
                        self.delete_user_with_bots(existing_user['id'])
                        return None
                # المستخدم موجود وصلاحيته سارية
                return dict(existing_user)
            
            # ✅ ثانياً: البحث عن كود جديد في جدول الأكواد
            cursor.execute('''
                SELECT * FROM activation_codes 
                WHERE code = ?
            ''', (code,))
            
            code_data = cursor.fetchone()
            
            if not code_data:
                return None
            
            # ✅ إذا الكود مستخدم سابقاً، نبحث عن المستخدم المرتبط به
            if code_data['used_by']:
                cursor.execute('SELECT * FROM users WHERE id = ?', (code_data['used_by'],))
                existing = cursor.fetchone()
                if existing:
                    # فحص صلاحية المستخدم المرتبط
                    expires_at = existing['expires_at']
                    if expires_at:
                        expiry = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                        if datetime.now() > expiry:
                            self.delete_user_with_bots(existing['id'])
                            return None
                    return dict(existing)
            
            # ✅ إنشاء مستخدم جديد (للكود الجديد فقط)
            expires_at = (datetime.now() + timedelta(days=code_data['days'])).isoformat()
            
            cursor.execute('''
                INSERT INTO users (username, activation_code, expires_at, is_admin)
                VALUES (?, ?, ?, ?)
            ''', (code_data['username'], code, expires_at, code_data['is_admin']))
            
            user_id = cursor.lastrowid
            
            # تحديث الكود كمستخدم
            cursor.execute('''
                UPDATE activation_codes 
                SET used_by = ?, used_at = ?
                WHERE code = ?
            ''', (user_id, datetime.now().isoformat(), code))
            
            # جلب بيانات المستخدم
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            return dict(cursor.fetchone())
    
    def get_user(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_users(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_codes(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM activation_codes ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_user(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM users WHERE id = ? AND is_admin = 0', (user_id,))
    
    def extend_user_expiry(self, user_id, days):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET expires_at = datetime(expires_at, '+' || ? || ' days')
                WHERE id = ?
            ''', (days, user_id))
    
    def delete_code(self, code):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM activation_codes WHERE code = ? AND used_by IS NULL', (code,))
    
    def add_bot(self, user_id, bot_name, file_path, original_name):
        import uuid
        bot_id = str(uuid.uuid4())[:12]
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO bots (id, user_id, bot_name, file_path, original_name)
                VALUES (?, ?, ?, ?, ?)
            ''', (bot_id, user_id, bot_name, file_path, original_name))
        
        return bot_id
    
    def get_user_bots(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM bots 
                WHERE user_id = ? 
                ORDER BY created_at DESC
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_bots(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT b.*, u.username as owner_name 
                FROM bots b
                JOIN users u ON b.user_id = u.id
                ORDER BY b.created_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_bot(self, bot_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM bots WHERE id = ?', (bot_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_bot_status(self, bot_id, status, bot_username=None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if status == 'running':
                cursor.execute('''
                    UPDATE bots 
                    SET status = ?, bot_username = ?, last_start = ?
                    WHERE id = ?
                ''', (status, bot_username, datetime.now().isoformat(), bot_id))
            else:
                cursor.execute('UPDATE bots SET status = ? WHERE id = ?', (status, bot_id))
    
    def delete_bot(self, bot_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM bots WHERE id = ?', (bot_id,))
    
    def get_stats(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM users WHERE is_admin = 0')
            total_users = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM bots')
            total_bots = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM bots WHERE status = "running"')
            active_bots = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM activation_codes WHERE used_by IS NULL')
            unused_codes = cursor.fetchone()[0]
            
            return {
                'total_users': total_users,
                'total_bots': total_bots,
                'active_bots': active_bots,
                'unused_codes': unused_codes
            }
    
    def get_user_stats(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM bots WHERE user_id = ?', (user_id,))
            total_bots = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM bots WHERE user_id = ? AND status = "running"', (user_id,))
            active_bots = cursor.fetchone()[0]
            
            return {
                'total_bots': total_bots,
                'active_bots': active_bots
            }

    # ✅ دالة حذف المستخدم وجميع بوتاته مع ملفاتها
    def delete_user_with_bots(self, user_id):
        """حذف المستخدم وجميع البوتات المرتبطة به مع ملفاتها من القرص"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # جلب مسارات ملفات البوتات لحذفها من القرص
            cursor.execute('SELECT file_path FROM bots WHERE user_id = ?', (user_id,))
            bot_files = cursor.fetchall()
            for (file_path,) in bot_files:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print(f"فشل حذف ملف البوت: {file_path} - {e}")
            # حذف البوتات من قاعدة البيانات
            cursor.execute('DELETE FROM bots WHERE user_id = ?', (user_id,))
            # حذف المستخدم (مع استثناء المشرف)
            cursor.execute('DELETE FROM users WHERE id = ? AND is_admin = 0', (user_id,))