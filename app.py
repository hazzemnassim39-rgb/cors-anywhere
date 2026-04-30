#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
موقع NASSIM - الإصدار الأسطوري 2026
جميع الحقوق محفوظة © 2026 NASSIM Hosting
للمساعدة: https://t.me/NH_8G
"""

import os, sys, time, uuid, json, re, subprocess, threading, sqlite3, secrets, datetime, signal, atexit
from datetime import timedelta
from functools import wraps
import logging
from logging import basicConfig, INFO, WARNING, error as log_error, Formatter, FileHandler

from flask import (Flask, render_template_string, request, redirect, url_for,
                   session, flash, abort, make_response)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
import psutil

# ===================== إعدادات السجلات =====================
basicConfig(level=INFO, format='%(asctime)s - %(levelname)s - %(message)s')

security_logger = logging.getLogger('security')
security_logger.setLevel(WARNING)
if not security_logger.handlers:
    fh = FileHandler('security.log')
    fh.setFormatter(Formatter('%(asctime)s - %(message)s'))
    security_logger.addHandler(fh)

bot_logger = logging.getLogger('bot_runner')
bot_logger.setLevel(INFO)
if not bot_logger.handlers:
    fh = FileHandler('bot_runner.log')
    fh.setFormatter(Formatter('%(asctime)s - %(message)s'))
    bot_logger.addHandler(fh)

app = Flask(__name__)
app.secret_key = 'nassim-2026-fixed-secret'  # ثابت لضمان استقرار الجلسات
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
HTML_FOLDER = os.path.join(BASE_DIR, 'html_sites')
PENDING_FOLDER = os.path.join(BASE_DIR, 'pending')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(HTML_FOLDER, exist_ok=True)
os.makedirs(PENDING_FOLDER, exist_ok=True)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["300 per day", "80 per hour"],
    storage_uri="memory://"
)
limiter.init_app(app)

# ===================== الإعدادات =====================
DEFAULT_RAM_MB = 200
DEFAULT_STORAGE_MB = 500
DEFAULT_HTML_FILES = 3
TRIAL_HOURS = 48
DEVELOPER_TG = 'NH_8G'
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'Admin@Nassim2024'  # غيّرها

# ===================== قاعدة البيانات =====================
def init_db():
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT,
        password_hash TEXT,
        google_id TEXT UNIQUE,
        first_name TEXT,
        is_admin INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        join_date TEXT DEFAULT CURRENT_TIMESTAMP,
        ram_limit_mb INTEGER DEFAULT 200,
        storage_limit_mb INTEGER DEFAULT 500,
        html_limit INTEGER DEFAULT 3,
        expiry_date TEXT
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS python_bots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        filename TEXT,
        filepath TEXT,
        status TEXT DEFAULT 'pending',
        upload_date TEXT,
        expiry_date TEXT,
        process_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS html_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        filename TEXT,
        filepath TEXT,
        subdomain TEXT,
        upload_date TEXT,
        expiry_date TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    cur.execute('SELECT id FROM users WHERE username=?', (ADMIN_USERNAME,))
    if not cur.fetchone():
        hash_pw = generate_password_hash(ADMIN_PASSWORD)
        cur.execute('''INSERT INTO users (username, password_hash, is_admin, first_name, expiry_date,
                      ram_limit_mb, storage_limit_mb, html_limit)
                      VALUES (?,?,?,?,?,?,?,?)''',
                    (ADMIN_USERNAME, hash_pw, 1, 'المطور', '2099-12-31 23:59:59', 999999, 999999, 9999))
    conn.commit()
    conn.close()

init_db()

# ===================== دوال مساعدة =====================
def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn, conn.cursor()

def get_user_by_id(user_id):
    conn, cur = get_db()
    cur.execute('SELECT * FROM users WHERE id=?', (user_id,))
    user = cur.fetchone()
    conn.close()
    return user

def get_user_by_username(username):
    conn, cur = get_db()
    cur.execute('SELECT * FROM users WHERE username=?', (username,))
    user = cur.fetchone()
    conn.close()
    return user

def get_quota(user_id):
    user = get_user_by_id(user_id)
    if not user: return {}
    ram_limit = user['ram_limit_mb']
    storage_limit = user['storage_limit_mb']
    html_limit = user['html_limit']
    conn, cur = get_db()
    cur.execute("SELECT COUNT(*) as cnt FROM python_bots WHERE user_id=? AND status='running'", (user_id,))
    running_bots = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) as cnt FROM html_files WHERE user_id=?", (user_id,))
    html_count = cur.fetchone()['cnt']
    conn.close()
    total_size = 0
    for folder in [UPLOAD_FOLDER, HTML_FOLDER, PENDING_FOLDER]:
        for root, dirs, files in os.walk(folder):
            for f in files:
                if str(user_id) in f or f.startswith(f"{user_id}_"):
                    try: total_size += os.path.getsize(os.path.join(root, f))
                    except: pass
    used_storage_mb = total_size // (1024 * 1024)
    return {
        'ram_limit': ram_limit,
        'running_bots': running_bots,
        'storage_limit': storage_limit,
        'used_storage': used_storage_mb,
        'html_limit': html_limit,
        'html_count': html_count
    }

def delete_user_data(user_id):
    conn, cur = get_db()
    cur.execute("SELECT filepath, process_id, status FROM python_bots WHERE user_id=?", (user_id,))
    bots = cur.fetchall()
    for bot in bots:
        if bot['process_id'] and bot['status'] == 'running':
            try: psutil.Process(bot['process_id']).terminate()
            except: pass
        if os.path.exists(bot['filepath']): os.remove(bot['filepath'])
    cur.execute("SELECT filepath FROM html_files WHERE user_id=?", (user_id,))
    for h in cur.fetchall():
        if os.path.exists(h['filepath']): os.remove(h['filepath'])
    cur.execute("DELETE FROM python_bots WHERE user_id=?", (user_id,))
    cur.execute("DELETE FROM html_files WHERE user_id=?", (user_id,))
    cur.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

# ===================== نظام المكتبات العملاق (كل ما يخطر على البال) =====================
LIBRARIES_CACHE = os.path.join(BASE_DIR, 'installed_libraries.json')

def load_installed_libs():
    if os.path.exists(LIBRARIES_CACHE):
        try:
            with open(LIBRARIES_CACHE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {}

def save_installed_lib(name):
    libs = load_installed_libs()
    libs[name] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LIBRARIES_CACHE, 'w', encoding='utf-8') as f:
        json.dump(libs, f, ensure_ascii=False, indent=2)

# المكتبات المضمنة في بايثون + أنواع telebot (لن يتم تثبيتها)
BUILTIN_LIBS = {
    'os','sys','time','datetime','re','json','random','math','io','collections',
    'functools','itertools','hashlib','base64','types','typing','threading',
    'subprocess','tempfile','pathlib','string','decimal','fractions','statistics',
    'copy','pprint','inspect','argparse','csv','pickle','sqlite3','uuid','html',
    'queue','ssl','socket','logging','signal','atexit','gc','weakref','abc',
    'bisect','codecs','contextlib','difflib','dis','doctest','enum','fileinput',
    'getopt','glob','gzip','importlib','keyword','linecache','locale','marshal',
    'mimetypes','operator','optparse','parser','pdb','pickletools','pkgutil',
    'platform','plistlib','posixpath','py_compile','pyclbr','pydoc','quopri',
    'reprlib','rlcompleter','runpy','sched','selectors','shelve','shlex','shutil',
    'site','smtplib','sndhdr','spwd','sqlite3','stat','stringprep','struct',
    'sunau','symbol','symtable','sysconfig','tabnanny','tarfile','telnetlib',
    'textwrap','this','timeit','token','tokenize','traceback','tty','turtle',
    'unicodedata','unittest','urllib','uu','warnings','wave','webbrowser','xml',
    'zipapp','zipfile','zlib','__future__','_thread','multiprocessing','select',
    'fcntl','msvcrt','winreg','winsound','asyncio','concurrent',
    'InlineKeyboardMarkup','InlineKeyboardButton','types','ReplyKeyboardMarkup',
    'KeyboardButton','ForceReply','ReplyKeyboardRemove','CallbackQuery','Message'
}

# خريطة أسماء المكتبات إلى أسماء التثبيت (ضخمة جداً)
LIB_MAP = {
    # بوتات
    'telebot': 'pyTelegramBotAPI',
    'pyTelegramBotAPI': 'pyTelegramBotAPI',
    'telegram': 'python-telegram-bot',
    'pyrogram': 'pyrogram',
    'telethon': 'telethon',
    'aiogram': 'aiogram',
    'discord': 'discord.py',
    'discord.py': 'discord.py',
    # ويب
    'requests': 'requests',
    'aiohttp': 'aiohttp',
    'httpx': 'httpx',
    'urllib3': 'urllib3',
    'flask': 'Flask',
    'django': 'Django',
    'fastapi': 'fastapi',
    'uvicorn': 'uvicorn',
    'tornado': 'tornado',
    'sanic': 'sanic',
    'starlette': 'starlette',
    'bottle': 'bottle',
    'cherrypy': 'cherrypy',
    # بيانات
    'numpy': 'numpy',
    'pandas': 'pandas',
    'scipy': 'scipy',
    'matplotlib': 'matplotlib',
    'seaborn': 'seaborn',
    'plotly': 'plotly',
    'bokeh': 'bokeh',
    'sklearn': 'scikit-learn',
    'scikit-learn': 'scikit-learn',
    'tensorflow': 'tensorflow',
    'torch': 'torch',
    'keras': 'keras',
    'xgboost': 'xgboost',
    'lightgbm': 'lightgbm',
    'statsmodels': 'statsmodels',
    'nltk': 'nltk',
    'spacy': 'spacy',
    'gensim': 'gensim',
    'transformers': 'transformers',
    'huggingface': 'transformers',
    # صور وفيديو
    'PIL': 'Pillow',
    'pillow': 'Pillow',
    'cv2': 'opencv-python',
    'opencv': 'opencv-python',
    'imageio': 'imageio',
    'scikit-image': 'scikit-image',
    'moviepy': 'moviepy',
    'pygame': 'pygame',
    'arcade': 'arcade',
    # قواعد بيانات
    'pymongo': 'pymongo',
    'redis': 'redis',
    'sqlalchemy': 'SQLAlchemy',
    'psycopg2': 'psycopg2-binary',
    'mysql': 'mysql-connector-python',
    'pymysql': 'pymysql',
    'asyncpg': 'asyncpg',
    'aiosqlite': 'aiosqlite',
    'sqlite3': 'sqlite3',  # مضمنة
    # خدمات سحابية
    'boto3': 'boto3',
    'google-cloud': 'google-cloud',
    'azure': 'azure-storage-blob',
    'digitalocean': 'python-digitalocean',
    # أدوات
    'bs4': 'beautifulsoup4',
    'selenium': 'selenium',
    'lxml': 'lxml',
    'pyquery': 'pyquery',
    'qrcode': 'qrcode[pil]',
    'pillow-qrcode': 'qrcode[pil]',
    'youtube_dl': 'youtube_dl',
    'yt_dlp': 'yt-dlp',
    'wget': 'wget',
    'pyautogui': 'pyautogui',
    'pyshorteners': 'pyshorteners',
    'pytz': 'pytz',
    'colorama': 'colorama',
    'pyfiglet': 'pyfiglet',
    'termcolor': 'termcolor',
    'tqdm': 'tqdm',
    'pyperclip': 'pyperclip',
    'cryptography': 'cryptography',
    'pycryptodome': 'pycryptodome',
    'psutil': 'psutil',
    'pyaes': 'pyaes',
    'rsa': 'rsa',
    'python-dotenv': 'python-dotenv',
    'click': 'click',
    'rich': 'rich',
    'prompt-toolkit': 'prompt-toolkit',
    'watchdog': 'watchdog',
    'schedule': 'schedule',
    'arrow': 'arrow',
    'pendulum': 'pendulum',
    'bcrypt': 'bcrypt',
    'paramiko': 'paramiko',
    'scp': 'scp',
    'netmiko': 'netmiko',
    'pynput': 'pynput',
    'keyboard': 'keyboard',
    'mouse': 'mouse',
    'openpyxl': 'openpyxl',
    'xlsxwriter': 'xlsxwriter',
    'reportlab': 'reportlab',
    'pdfkit': 'pdfkit',
    'playwright': 'playwright',
    'fake-useragent': 'fake-useragent',
    'cloudscraper': 'cloudscraper',
    'curl_cffi': 'curl_cffi',
    'pydantic': 'pydantic',
    'marshmallow': 'marshmallow',
    'cerberus': 'cerberus',
    'jsonschema': 'jsonschema',
    'pytest': 'pytest',
    'unittest2': 'unittest2',
    'coverage': 'coverage',
    'flake8': 'flake8',
    'black': 'black',
    'isort': 'isort',
    'pre-commit': 'pre-commit',
    'tox': 'tox',
    'twine': 'twine',
    'setuptools': 'setuptools',
    'wheel': 'wheel',
    'pip': 'pip',
    'virtualenv': 'virtualenv',
    'pipenv': 'pipenv',
    'poetry': 'poetry',
    'cython': 'cython',
    'numba': 'numba',
    'sympy': 'sympy',
    'mpmath': 'mpmath',
    'shapely': 'shapely',
    'geopy': 'geopy',
    'folium': 'folium',
    'geopandas': 'geopandas',
    'networkx': 'networkx',
    'igraph': 'igraph',
    'graphviz': 'graphviz',
    'pydot': 'pydot',
    'pygraphviz': 'pygraphviz',
    'wordcloud': 'wordcloud',
    'emoji': 'emoji',
    'python-emoji': 'emoji',
    'q': 'q',
    'icecream': 'icecream',
    'loguru': 'loguru',
    'structlog': 'structlog',
    'sentry-sdk': 'sentry-sdk',
    'opentelemetry': 'opentelemetry-api',
    'celery': 'celery',
    'redis': 'redis',
    'rabbitmq': 'pika',
    'kafka-python': 'kafka-python',
    'confluent-kafka': 'confluent-kafka',
    'boto3': 'boto3',
    'awscli': 'awscli',
    'gcloud': 'google-cloud-sdk',
    'azure-cli': 'azure-cli',
    'heroku3': 'heroku3',
    'python-consul': 'python-consul',
    'etcd3': 'etcd3',
    'pyvmomi': 'pyvmomi',
    'docker': 'docker',
    'docker-compose': 'docker-compose',
    'ansible': 'ansible',
    'fabric': 'fabric',
    'salt': 'salt',
    'puppet': 'puppet',
    'chef': 'chef',
    'splunk-sdk': 'splunk-sdk',
    'elasticsearch': 'elasticsearch',
    'opensearch-py': 'opensearch-py',
    'kibana': 'kibana',
    'airflow': 'apache-airflow',
    'prefect': 'prefect',
    'dagster': 'dagster',
    'luigi': 'luigi',
    'beam': 'apache-beam',
    'spark': 'pyspark',
    'hadoop': 'pydoop',
    'hive': 'pyhive',
    'impyla': 'impyla',
    'sqlparse': 'sqlparse',
    'sqlalchemy-utils': 'sqlalchemy-utils',
    'marshmallow-sqlalchemy': 'marshmallow-sqlalchemy',
    'graphene': 'graphene',
    'strawberry-graphql': 'strawberry-graphql',
    'ariadne': 'ariadne',
    'tartiflette': 'tartiflette',
    'sanic-graphql': 'sanic-graphql',
    'flask-graphql': 'flask-graphql',
    'django-graphql': 'django-graphql',
}

# أنماط إضافية للاكتشاف (content based)
COMMON_PATTERNS = {
    'telebot': 'pyTelegramBotAPI',
    'pyrogram': 'pyrogram',
    'telethon': 'telethon',
    'aiogram': 'aiogram',
    'discord': 'discord.py',
    'requests': 'requests',
    'aiohttp': 'aiohttp',
    'flask': 'Flask',
    'django': 'Django',
    'fastapi': 'fastapi',
    'numpy': 'numpy',
    'pandas': 'pandas',
    'matplotlib': 'matplotlib',
    'PIL': 'Pillow',
    'cv2': 'opencv-python',
    'bs4': 'beautifulsoup4',
    'selenium': 'selenium',
    'qrcode': 'qrcode[pil]',
    'yt_dlp': 'yt-dlp',
    'youtube_dl': 'youtube_dl',
    'wget': 'wget',
    'sqlalchemy': 'SQLAlchemy',
    'pymongo': 'pymongo',
    'redis': 'redis',
    'bcrypt': 'bcrypt',
    'cryptography': 'cryptography',
    'psutil': 'psutil',
    'tqdm': 'tqdm',
    'colorama': 'colorama',
    'pyfiglet': 'pyfiglet',
    'rich': 'rich',
    'openpyxl': 'openpyxl',
    'pygame': 'pygame',
    'moviepy': 'moviepy',
    'scipy': 'scipy',
    'sklearn': 'scikit-learn',
    'tensorflow': 'tensorflow',
    'torch': 'torch',
    'transformers': 'transformers',
    'spacy': 'spacy',
    'nltk': 'nltk',
    'playwright': 'playwright',
    'cloudscraper': 'cloudscraper',
    'pydantic': 'pydantic',
}

def detect_libs(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        libs = set()
        # البحث عن import / from
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'): continue
            # import xxx
            m = re.match(r'^import\s+([a-zA-Z_][a-zA-Z0-9_]*)', line)
            if m:
                lib = m.group(1)
                if lib not in BUILTIN_LIBS and len(lib) > 1:
                    mapped = LIB_MAP.get(lib)
                    if not mapped and lib.count('.') > 0:
                        # في حالة from xxx.yyy import zzz
                        first_part = lib.split('.')[0]
                        mapped = LIB_MAP.get(first_part)
                    if mapped:
                        libs.add(mapped)
            # from xxx import yyy
            m = re.match(r'^from\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s+import', line)
            if m:
                full_lib = m.group(1)
                first_part = full_lib.split('.')[0]
                if first_part not in BUILTIN_LIBS and len(first_part) > 1:
                    mapped = LIB_MAP.get(first_part)
                    if mapped:
                        libs.add(mapped)
                    elif full_lib not in BUILTIN_LIBS:
                        # ربما المكتبة نفسها مسماة بالأول
                        mapped2 = LIB_MAP.get(full_lib)
                        if mapped2:
                            libs.add(mapped2)
        # بحث إضافي في المحتوى (للمكتبات غير المباشرة)
        content_lower = content.lower()
        for keyword, pkg in COMMON_PATTERNS.items():
            if keyword in content_lower:
                libs.add(pkg)
        # إزالة أي مكتبات مضمنة
        libs.discard('asyncio')
        libs.discard('sqlite3')
        return list(libs)
    except Exception as e:
        bot_logger.error(f"خطأ في detect_libs: {e}")
        return []

def install_libraries(lib_list):
    installed = load_installed_libs()
    to_install = [lib for lib in lib_list if lib not in installed]
    if not to_install:
        return [], []
    bot_logger.info(f"تثبيت المكتبات: {to_install}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install"] + to_install + ["--quiet"],
            check=True, timeout=300, capture_output=True, text=True
        )
        for lib in to_install:
            save_installed_lib(lib)
        return to_install, []
    except subprocess.CalledProcessError as e:
        bot_logger.error(f"فشل تثبيت دفعة: {e.stderr}")
        ok, fail = [], []
        for lib in to_install:
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", lib, "--quiet"],
                               check=True, timeout=60, capture_output=True)
                ok.append(lib)
                save_installed_lib(lib)
            except Exception as e2:
                fail.append(lib)
                bot_logger.error(f"فشل تثبيت {lib}: {e2}")
        return ok, fail

# ===================== إدارة العمليات =====================
active_bots = {}

def launch_bot(filepath):
    return subprocess.Popen(
        [sys.executable, filepath],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.PIPE,
        start_new_session=True,
        cwd=os.path.dirname(filepath)
    )

def stop_process(proc):
    try:
        if os.name == 'posix':
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            time.sleep(1)
            try: os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except: pass
        else:
            proc.terminate()
            time.sleep(1)
            if proc.poll() is None: proc.kill()
        proc.wait(timeout=5)
        return True
    except: return False

def start_bot(bot_id, filepath, user_id):
    try:
        if PENDING_FOLDER in filepath:
            new_path = filepath.replace(PENDING_FOLDER, UPLOAD_FOLDER)
            os.rename(filepath, new_path)
            filepath = new_path
            conn, cur = get_db()
            cur.execute("UPDATE python_bots SET filepath=? WHERE id=?", (filepath, bot_id))
            conn.commit()
            conn.close()
        proc = launch_bot(filepath)
        pid = proc.pid
        conn, cur = get_db()
        cur.execute("UPDATE python_bots SET status='running', process_id=? WHERE id=?", (pid, bot_id))
        conn.commit()
        conn.close()
        active_bots[bot_id] = {'process': proc, 'user_id': user_id}
        bot_logger.info(f"تم تشغيل بوت ID={bot_id} PID={pid} للمستخدم {user_id}")
        def monitor():
            try: proc.wait()
            except: pass
            finally:
                conn2, cur2 = get_db()
                cur2.execute("UPDATE python_bots SET status='stopped', process_id=NULL WHERE id=?", (bot_id,))
                conn2.commit()
                conn2.close()
                active_bots.pop(bot_id, None)
                bot_logger.info(f"بوت {bot_id} توقف")
        threading.Thread(target=monitor, daemon=True).start()
        return True, pid
    except Exception as e:
        bot_logger.error(f"فشل تشغيل بوت ID={bot_id}: {e}")
        return False, str(e)

atexit.register(lambda: [stop_process(d['process']) for d in active_bots.values()])

# ===================== فحص أمني =====================
def security_scan(filepath):
    warnings = []
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
        patterns = [
            (b'os.system(', 'os.system'),
            (b'subprocess.call(', 'subprocess.call'),
            (b'eval(', 'eval'),
            (b'exec(', 'exec'),
            (b'shutil.rmtree(', 'shutil.rmtree')
        ]
        for pat, desc in patterns:
            if pat in data:
                warnings.append(desc)
        if warnings:
            security_logger.warning(f"تحذيرات في {filepath}: {', '.join(warnings)}")
    except: pass
    return warnings

# ===================== حماية =====================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('يرجى تسجيل الدخول', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            abort(403)
        return f(*args, **kwargs)
    return decorated

# ===================== القوالب =====================
STYLE_CSS = """
:root { --primary: #ff4500; --secondary: #8a2be2; --dark: #0a0a0a; --light: #f0f0f0; --gold: #ffd700; }
* { margin:0; padding:0; box-sizing:border-box; }
body { background: radial-gradient(circle at top, #1a0033 0%, #000 70%); color: var(--light); font-family: 'Segoe UI', Tahoma, sans-serif; min-height:100vh; direction:rtl; }
.container { max-width:1200px; margin:auto; padding:20px; }
.hero { text-align:center; padding:80px 20px; }
h1 { color:var(--gold); font-size:2.8em; }
.btn { display:inline-block; background:linear-gradient(45deg, var(--primary), var(--secondary)); color:#fff; padding:12px 30px; border-radius:30px; margin:10px; text-decoration:none; transition:0.3s; border:none; cursor:pointer; }
.btn:hover { transform:scale(1.05); box-shadow:0 0 20px var(--primary); }
.btn-outline { background:transparent; border:2px solid var(--primary); }
.glass-form { background:rgba(255,255,255,0.05); backdrop-filter:blur(15px); border-radius:20px; padding:40px; max-width:400px; margin:50px auto; }
input, button { width:100%; padding:12px; margin:10px 0; border:1px solid var(--secondary); border-radius:8px; background:rgba(255,255,255,0.1); color:#fff; font-size:16px; }
.alert { padding:15px; border-radius:10px; margin:10px 0; }
.alert-danger { background:rgba(255,0,0,0.2); border:1px solid red; }
.alert-success { background:rgba(0,255,0,0.2); border:1px solid green; }
.alert-warning { background:rgba(255,165,0,0.2); border:1px solid orange; }
.grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(300px,1fr)); gap:20px; }
.card { background:rgba(255,255,255,0.05); backdrop-filter:blur(10px); border-radius:15px; padding:20px; border:1px solid rgba(255,255,255,0.1); }
table { width:100%; border-collapse:collapse; margin:20px 0; }
th,td { padding:12px; border:1px solid rgba(255,255,255,0.2); text-align:center; }
th { background:rgba(255,255,255,0.1); }
.footer { text-align:center; padding:30px; color:#777; }
"""

BASE_LAYOUT = """<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>NASSIM</title><style>""" + STYLE_CSS + """</style></head>
<body><div class="container">
{% with messages = get_flashed_messages(with_categories=true) %}
{% if messages %}{% for cat, msg in messages %}<div class="alert alert-{{ cat }}">{{ msg }}</div>{% endfor %}{% endif %}
{% endwith %}
{{ content | safe }}
</div><div class="footer">© 2026 NASSIM | <a href="https://t.me/""" + DEVELOPER_TG + """">تواصل مع المطور</a></div></body></html>"""

INDEX_CONTENT = """<div class="hero"><h1>🚀 NASSIM</h1><h2 style="color:var(--primary)">استضافة بوتات و HTML</h2>
<p>💎 تجربة 48 ساعة | 200MB رام | 500MB تخزين | 3 مواقع</p>
<a href="/login" class="btn">دخول</a><a href="/register" class="btn btn-outline">حساب جديد</a>
<br><small><a href="https://t.me/""" + DEVELOPER_TG + """">@""" + DEVELOPER_TG + """</a></small></div>"""

LOGIN_CONTENT = """<form method="POST" class="glass-form" action="/login">
<h2 style="color:var(--gold)">تسجيل الدخول</h2>
<input type="text" name="username" placeholder="اسم المستخدم" required>
<input type="password" name="password" placeholder="كلمة المرور" required>
<button class="btn">دخول</button>
<p style="text-align:center">ليس لديك حساب؟ <a href="/register">إنشاء حساب</a></p>
</form>"""

REGISTER_CONTENT = """<form method="POST" class="glass-form" action="/register">
<h2 style="color:var(--gold)">إنشاء حساب تجريبي</h2>
<p style="text-align:center">48 ساعة مجانية</p>
<input type="text" name="username" placeholder="اسم المستخدم" required>
<input type="email" name="email" placeholder="البريد الإلكتروني">
<input type="password" name="password" placeholder="كلمة المرور" required>
<button class="btn">إنشاء ودخول</button>
<p style="text-align:center">لديك حساب؟ <a href="/login">دخول</a></p>
</form>"""

DASHBOARD_CONTENT = """
<h1 style="color:var(--gold)">لوحة التحكم</h1>
<p>مرحباً {{ user.first_name }} | <a href="/logout">خروج</a></p>
<div class="grid"><div class="card"><h3>📊 الموارد</h3>
<p>🧠 الرام: {{ quota.used_ram if quota.used_ram else 0 }} / {{ quota.ram_limit }} MB</p>
<p>💾 التخزين: {{ quota.used_storage }} / {{ quota.storage_limit }} MB</p>
<p>🤖 بوتات نشطة: {{ quota.running_bots }}</p>
<p>🌐 مواقع HTML: {{ quota.html_count }} / {{ quota.html_limit }}</p>
</div><div class="card"><h3>⚡ إجراءات</h3>
<a href="/upload-python" class="btn">رفع بوت Python</a>
<a href="/upload-html" class="btn btn-outline">رفع موقع HTML</a>
</div></div>
<h3>🤖 بوتاتك</h3>
<table><tr><th>الملف</th><th>الحالة</th><th>تاريخ</th><th>إجراءات</th></tr>
{% for bot in bots %}
<tr><td>{{ bot.filename }}</td><td>{{ bot.status }}</td><td>{{ bot.upload_date }}</td>
<td>{% if bot.status == 'running' %}<a href="/stop-bot/{{ bot.id }}" class="btn">إيقاف</a>
{% else %}<a href="/run-bot/{{ bot.id }}" class="btn">تشغيل</a>{% endif %}
<a href="/delete-bot/{{ bot.id }}" class="btn btn-outline" onclick="return confirm('حذف؟')">حذف</a></td></tr>
{% endfor %}</table>
<h3>🌐 مواقع HTML</h3>
<table><tr><th>الملف</th><th>معاينة</th><th>تاريخ</th><th>حذف</th></tr>
{% for h in htmls %}
<tr><td>{{ h.filename }}</td><td><a href="/view-html/{{ h.id }}" target="_blank">عرض</a></td><td>{{ h.upload_date }}</td>
<td><a href="/delete-html/{{ h.id }}" class="btn btn-outline" onclick="return confirm('حذف؟')">حذف</a></td></tr>
{% endfor %}</table>"""

UPLOAD_PYTHON_CONTENT = """<h2 style="color:var(--gold)">رفع بوت Python</h2>
<form method="POST" enctype="multipart/form-data" class="glass-form">
<input type="file" name="file" required><button class="btn">رفع وتشغيل</button>
<a href="/dashboard" class="btn btn-outline">رجوع</a></form>"""

UPLOAD_HTML_CONTENT = """<h2 style="color:var(--gold)">رفع موقع HTML</h2>
<form method="POST" enctype="multipart/form-data" class="glass-form">
<input type="file" name="file" required>
<input type="text" name="subdomain" placeholder="اسم النطاق الفرعي" required>
<button class="btn">رفع</button><a href="/dashboard" class="btn btn-outline">رجوع</a></form>"""

ADMIN_CONTENT = """
<h1 style="color:var(--gold)">👑 لوحة المطور</h1>
<div class="grid"><div class="card"><h3>إنشاء حساب مخصص</h3>
<form method="POST" action="/admin/create-user">
<input type="text" name="username" placeholder="اسم المستخدم" required>
<input type="password" name="password" placeholder="كلمة المرور" required>
<input type="email" name="email" placeholder="البريد">
<input type="number" name="ram" value="200" placeholder="الرام MB">
<input type="number" name="storage" value="500" placeholder="التخزين MB">
<input type="number" name="html_limit" value="3" placeholder="حد HTML">
<input type="number" name="expiry_days" value="2" placeholder="مدة بالأيام">
<button class="btn">إنشاء</button></form></div>
<div class="card"><h3>تحكم سريع</h3>
<a href="/admin" class="btn">تحديث</a>
<a href="/admin/stop-all-bots" class="btn btn-outline">إيقاف جميع البوتات</a>
</div></div>
<h3>المستخدمون</h3>
<table><tr><th>ID</th><th>الاسم</th><th>الرام</th><th>التخزين</th><th>الصلاحية</th><th>حالة</th><th>حذف</th></tr>
{% for u in users %}
<tr><td>{{ u.id }}</td><td>{{ u.username }}</td><td>{{ u.ram_limit_mb }}</td><td>{{ u.storage_limit_mb }}</td>
<td>{{ u.expiry_date }}</td><td>{{ 'محظور' if u.is_banned else 'نشط' }}</td>
<td><a href="/admin/delete-user/{{ u.id }}" class="btn btn-outline">حذف</a></td></tr>
{% endfor %}</table>"""

def render_page(content_template, **kwargs):
    content_html = render_template_string(content_template, **kwargs)
    return render_template_string(BASE_LAYOUT, content=content_html)

# ===================== المسارات =====================
@app.route('/')
def index():
    return render_page(INDEX_CONTENT)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = get_user_by_username(username)
        if user and check_password_hash(user['password_hash'], password):
            if user['is_banned']:
                flash('الحساب محظور', 'danger')
                return render_page(LOGIN_CONTENT)
            session.update(user_id=user['id'], username=user['username'], is_admin=bool(user['is_admin']))
            if user['expiry_date'] and datetime.datetime.now() > datetime.datetime.strptime(user['expiry_date'], '%Y-%m-%d %H:%M:%S'):
                delete_user_data(user['id'])
                session.clear()
                flash('انتهت صلاحية حسابك وتم حذف جميع الملفات', 'warning')
                return redirect(url_for('login'))
            return redirect(url_for('dashboard'))
        flash('بيانات خاطئة', 'danger')
    return render_page(LOGIN_CONTENT)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        email = request.form.get('email', '').strip()
        if not username or not password:
            flash('يرجى ملء جميع الحقول', 'danger')
            return render_page(REGISTER_CONTENT)
        if get_user_by_username(username):
            flash('اسم المستخدم موجود', 'danger')
            return render_page(REGISTER_CONTENT)
        expiry = (datetime.datetime.now() + timedelta(hours=TRIAL_HOURS)).strftime('%Y-%m-%d %H:%M:%S')
        hash_pw = generate_password_hash(password)
        conn, cur = get_db()
        try:
            cur.execute('''INSERT INTO users (username, email, password_hash, first_name, ram_limit_mb, storage_limit_mb, html_limit, expiry_date)
                          VALUES (?,?,?,?,?,?,?,?)''',
                        (username, email, hash_pw, username, DEFAULT_RAM_MB, DEFAULT_STORAGE_MB, DEFAULT_HTML_FILES, expiry))
            conn.commit()
            user_id = cur.lastrowid
            session.clear()
            session['user_id'] = user_id
            session['username'] = username
            session['is_admin'] = False
            flash('تم إنشاء الحساب وتفعيل التجربة', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'خطأ: {e}', 'danger')
        finally:
            conn.close()
    return render_page(REGISTER_CONTENT)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    user = get_user_by_id(user_id)
    if not user:
        session.clear()
        return redirect(url_for('login'))
    if user['expiry_date'] and datetime.datetime.now() > datetime.datetime.strptime(user['expiry_date'], '%Y-%m-%d %H:%M:%S'):
        delete_user_data(user_id)
        session.clear()
        flash('انتهت الصلاحية', 'warning')
        return redirect(url_for('login'))
    quota = get_quota(user_id)
    conn, cur = get_db()
    cur.execute("SELECT * FROM python_bots WHERE user_id=?", (user_id,))
    bots = cur.fetchall()
    cur.execute("SELECT * FROM html_files WHERE user_id=?", (user_id,))
    htmls = cur.fetchall()
    conn.close()
    return render_page(DASHBOARD_CONTENT, user=user, quota=quota, bots=bots, htmls=htmls)

@app.route('/upload-python', methods=['GET', 'POST'])
@login_required
@limiter.limit("15 per hour")
def upload_python():
    if request.method == 'POST':
        user_id = session['user_id']
        q = get_quota(user_id)
        if q['used_storage'] >= q['storage_limit']:
            flash('تجاوزت التخزين', 'danger')
            return redirect(url_for('dashboard'))
        file = request.files.get('file')
        if not file or not file.filename.endswith('.py'):
            flash('فقط .py', 'danger')
            return render_page(UPLOAD_PYTHON_CONTENT)
        safe_name = f"{user_id}_{uuid.uuid4().hex}_{file.filename}"
        save_path = os.path.join(PENDING_FOLDER, safe_name)
        file.save(save_path)

        # تثبيت المكتبات تلقائياً
        libs = detect_libs(save_path)
        if libs:
            ok, fail = install_libraries(libs)
            if ok: flash(f'تم تثبيت المكتبات: {", ".join(ok)}', 'success')
            if fail: flash(f'فشل تثبيت: {", ".join(fail)}', 'warning')

        warns = security_scan(save_path)
        if warns: flash(f'تحذيرات أمنية: {", ".join(warns)}', 'warning')

        expiry = get_user_by_id(user_id)['expiry_date']
        conn, cur = get_db()
        cur.execute('''INSERT INTO python_bots (user_id, filename, filepath, status, upload_date, expiry_date)
                      VALUES (?,?,?,?,?,?)''',
                    (user_id, file.filename, save_path, 'pending', datetime.datetime.now(), expiry))
        bot_id = cur.lastrowid
        conn.commit()
        conn.close()

        success, pid = start_bot(bot_id, save_path, user_id)
        if success:
            flash(f'تم تشغيل البوت! PID: {pid}', 'success')
        else:
            flash('فشل التشغيل، يمكنك المحاولة لاحقاً', 'warning')
        return redirect(url_for('dashboard'))
    return render_page(UPLOAD_PYTHON_CONTENT)

@app.route('/run-bot/<int:bot_id>')
@login_required
def run_bot_route(bot_id):
    user_id = session['user_id']
    conn, cur = get_db()
    cur.execute("SELECT * FROM python_bots WHERE id=? AND user_id=?", (bot_id, user_id))
    bot = cur.fetchone()
    if not bot:
        flash('بوت غير موجود', 'danger')
        return redirect(url_for('dashboard'))
    if bot['status'] == 'running':
        flash('البوت يعمل بالفعل', 'info')
        return redirect(url_for('dashboard'))
    libs = detect_libs(bot['filepath'])
    if libs: install_libraries(libs)
    success, pid = start_bot(bot_id, bot['filepath'], user_id)
    if success:
        flash(f'تم تشغيل البوت! PID: {pid}', 'success')
    else:
        flash('فشل التشغيل', 'danger')
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/stop-bot/<int:bot_id>')
@login_required
def stop_bot_route(bot_id):
    user_id = session['user_id']
    conn, cur = get_db()
    cur.execute("SELECT * FROM python_bots WHERE id=? AND user_id=?", (bot_id, user_id))
    bot = cur.fetchone()
    if bot and bot['process_id'] and bot['status'] == 'running':
        try: psutil.Process(bot['process_id']).terminate()
        except: pass
    cur.execute("UPDATE python_bots SET status='stopped', process_id=NULL WHERE id=?", (bot_id,))
    conn.commit()
    conn.close()
    flash('تم الإيقاف', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete-bot/<int:bot_id>')
@login_required
def delete_bot_route(bot_id):
    user_id = session['user_id']
    conn, cur = get_db()
    cur.execute("SELECT * FROM python_bots WHERE id=? AND user_id=?", (bot_id, user_id))
    bot = cur.fetchone()
    if bot:
        if bot['process_id'] and bot['status'] == 'running':
            try: psutil.Process(bot['process_id']).terminate()
            except: pass
        if os.path.exists(bot['filepath']): os.remove(bot['filepath'])
        cur.execute("DELETE FROM python_bots WHERE id=?", (bot_id,))
    conn.commit()
    conn.close()
    flash('تم الحذف', 'success')
    return redirect(url_for('dashboard'))
@app.route('/upload-html', methods=['GET', 'POST'])
@login_required
@limiter.limit("15 per hour")
def upload_html():
    if request.method == 'POST':
        user_id = session['user_id']
        q = get_quota(user_id)

        if q['html_count'] >= q['html_limit']:
            flash('وصلت حد HTML', 'danger')
            return redirect(url_for('dashboard'))

        file = request.files.get('file')
        subdomain = request.form.get('subdomain', '').lower().strip()

        if not file or not (file.filename.endswith('.html') or file.filename.endswith('.htm')):
            flash('فقط .html', 'danger')
            return render_page(UPLOAD_HTML_CONTENT)

        if not subdomain or not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', subdomain):
            flash('اسم نطاق غير صالح', 'danger')
            return render_page(UPLOAD_HTML_CONTENT)

        conn, cur = get_db()
        cur.execute('SELECT id FROM html_files WHERE subdomain=?', (subdomain,))

        if cur.fetchone():
            flash('النطاق مستعمل', 'danger')
            conn.close()
            return render_page(UPLOAD_HTML_CONTENT)

        safe_name = f"{user_id}_{subdomain}_{file.filename}"
        save_path = os.path.join(HTML_FOLDER, safe_name)
        file.save(save_path)

        expiry = get_user_by_id(user_id)['expiry_date']

        cur.execute('''INSERT INTO html_files 
        (user_id, filename, filepath, subdomain, upload_date, expiry_date)
        VALUES (?,?,?,?,?,?)''', (
            user_id,
            file.filename,
            save_path,
            subdomain,
            datetime.datetime.now(),
            expiry
        ))

        html_id = cur.lastrowid

        conn.commit()
        conn.close()

        flash(f'تم الرفع! رابط المعاينة: /view-html/{html_id}', 'success')
        return redirect(url_for('dashboard'))

    return render_page(UPLOAD_HTML_CONTENT)

@app.route('/view-html/<int:html_id>')
@login_required
def view_html(html_id):
    user_id = session['user_id']
    conn, cur = get_db()
    cur.execute("SELECT * FROM html_files WHERE id=? AND user_id=?", (html_id, user_id))
    html = cur.fetchone()
    conn.close()
    if not html or not os.path.exists(html['filepath']): abort(404)
    with open(html['filepath'], 'r', encoding='utf-8') as f:
        content = f.read()
    response = make_response(content)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

@app.route('/delete-html/<int:html_id>')
@login_required
def delete_html_route(html_id):
    user_id = session['user_id']
    conn, cur = get_db()
    cur.execute("SELECT * FROM html_files WHERE id=? AND user_id=?", (html_id, user_id))
    hl = cur.fetchone()
    if hl:
        if os.path.exists(hl['filepath']): os.remove(hl['filepath'])
        cur.execute("DELETE FROM html_files WHERE id=?", (html_id,))
    conn.commit()
    conn.close()
    flash('تم حذف موقع HTML', 'success')
    return redirect(url_for('dashboard'))

@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    conn, cur = get_db()
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()
    conn.close()
    return render_page(ADMIN_CONTENT, users=users)

@app.route('/admin/create-user', methods=['POST'])
@admin_required
def admin_create_user():
    username = request.form.get('username')
    password = request.form.get('password')
    email = request.form.get('email')
    ram = int(request.form.get('ram', DEFAULT_RAM_MB))
    storage = int(request.form.get('storage', DEFAULT_STORAGE_MB))
    html_limit = int(request.form.get('html_limit', DEFAULT_HTML_FILES))
    expiry_days = int(request.form.get('expiry_days', 2))
    expiry = (datetime.datetime.now() + timedelta(days=expiry_days)).strftime('%Y-%m-%d %H:%M:%S')
    hash_pw = generate_password_hash(password)
    conn, cur = get_db()
    try:
        cur.execute('''INSERT INTO users (username, password_hash, email, ram_limit_mb, storage_limit_mb, html_limit, expiry_date)
                      VALUES (?,?,?,?,?,?,?)''',
                    (username, hash_pw, email, ram, storage, html_limit, expiry))
        conn.commit()
        flash('تم إنشاء المستخدم', 'success')
    except Exception as e:
        flash(f'خطأ: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete-user/<int:user_id>')
@admin_required
def admin_delete_user(user_id):
    if user_id == session.get('user_id'):
        flash('لا يمكنك حذف نفسك', 'danger')
        return redirect(url_for('admin_panel'))
    delete_user_data(user_id)
    flash('تم حذف المستخدم نهائياً', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/stop-all-bots')
@admin_required
def admin_stop_all():
    conn, cur = get_db()
    cur.execute("SELECT process_id FROM python_bots WHERE status='running'")
    for p in cur.fetchall():
        try: psutil.Process(p['process_id']).terminate()
        except: pass
    cur.execute("UPDATE python_bots SET status='stopped', process_id=NULL")
    conn.commit()
    conn.close()
    flash('تم إيقاف جميع البوتات', 'success')
    return redirect(url_for('admin_panel'))

# ===================== الحماية =====================
@app.route('/uploads/<path:filename>')
@app.route('/pending/<path:filename>')
@app.route('/html_sites/<path:filename>')
def block_access(filename):
    abort(403)

# ===================== مهمة التنظيف =====================
def cleanup_loop():
    while True:
        try:
            conn, cur = get_db()
            cur.execute("SELECT id FROM users WHERE expiry_date <= ? AND is_admin=0",
                        (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
            for u in cur.fetchall():
                bot_logger.info(f"حذف المستخدم {u['id']} لانتهاء الصلاحية")
                delete_user_data(u['id'])
            conn.close()
        except Exception as e:
            log_error(f"خطأ تنظيف: {e}")
        time.sleep(3600)

# ===================== بدء التشغيل =====================
if __name__ == '__main__':
    t = threading.Thread(target=cleanup_loop, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=8000, debug=False)