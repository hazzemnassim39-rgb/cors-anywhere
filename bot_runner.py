import subprocess
import sys
import os
import signal
import time
import re
import requests
import threading

class BotRunner:
    def __init__(self, db):
        self.db = db
        self.active_processes = {}  # {bot_id: process}
        self.monitor_threads = {}
    
    def extract_token_from_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            patterns = [
                r'["\']?([0-9]{8,11}:[A-Za-z0-9_-]{34,36})["\']?',
                r'bot_token\s*=\s*["\']([^"\']+)["\']',
                r'BOT_TOKEN\s*=\s*["\']([^"\']+)["\']',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    token = matches[0].strip()
                    if len(token) > 30 and ':' in token:
                        return token
            return None
        except:
            return None
    
    def get_bot_username(self, token):
        try:
            url = f"https://api.telegram.org/bot{token}/getMe"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    return f"@{data['result']['username']}"
        except:
            pass
        return None
    
    def start_bot(self, bot_id):
        bot = self.db.get_bot(bot_id)
        if not bot:
            return {'success': False, 'error': 'البوت غير موجود'}
        
        if bot_id in self.active_processes:
            return {'success': False, 'error': 'البوت يعمل بالفعل'}
        
        file_path = bot['file_path']
        
        # استخراج يوزر البوت
        token = self.extract_token_from_file(file_path)
        bot_username = None
        if token:
            bot_username = self.get_bot_username(token)
        
        try:
            process = subprocess.Popen(
                [sys.executable, file_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.PIPE,
                start_new_session=True
            )
            
            self.active_processes[bot_id] = process
            
            # مراقبة العملية
            def monitor():
                try:
                    process.wait(timeout=86400)
                except:
                    pass
                
                if bot_id in self.active_processes:
                    del self.active_processes[bot_id]
                    self.db.update_bot_status(bot_id, 'stopped')
            
            thread = threading.Thread(target=monitor, daemon=True)
            thread.start()
            self.monitor_threads[bot_id] = thread
            
            return {
                'success': True,
                'bot_username': bot_username,
                'message': f'تم تشغيل البوت {bot_username or ""}'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def stop_bot(self, bot_id):
        if bot_id not in self.active_processes:
            return {'success': False, 'error': 'البوت لا يعمل'}
        
        process = self.active_processes[bot_id]
        
        try:
            if os.name == 'posix':
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                time.sleep(2)
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except:
                    pass
            else:
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    process.kill()
            
            process.wait(timeout=5)
            del self.active_processes[bot_id]
            
            return {'success': True, 'message': 'تم إيقاف البوت'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def stop_all_user_bots(self, user_id):
        bots = self.db.get_user_bots(user_id)
        for bot in bots:
            if bot['id'] in self.active_processes:
                self.stop_bot(bot['id'])
    
    def get_running_bots_count(self):
        return len(self.active_processes)