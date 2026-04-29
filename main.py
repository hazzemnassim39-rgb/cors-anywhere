from flask import Flask, request, jsonify, make_response
import requests
import binascii
import jwt
import urllib3
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

try:
    import my_pb2
    import output_pb2
except ImportError:
    pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

FREEFIRE_VERSION = "OB53"

KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

BIO_HEADERS = {
    "Expect": "100-continue",
    "X-Unity-Version": "2018.4.11f1",
    "X-GA": "v1 1",
    "ReleaseVersion": FREEFIRE_VERSION,
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11; SM-A305F Build/RP1A.200720.012)",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
}

LOGIN_HEADERS = {
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
    "Content-Type": "application/octet-stream",
    "Expect": "100-continue",
    "X-Unity-Version": "2018.4.11f1",
    "X-GA": "v1 1",
    "ReleaseVersion": FREEFIRE_VERSION
}

# Region configuration
REGION_CONFIG = {
    "IND": {  # India
        "login": "https://loginbp.ggpolarbear.com",
        "server": "https://client.ind.freefiremobile.com"
    },
    "ME": {  # Middle East
        "login": "https://loginbp.ggpolarbear.com",
        "server": "https://clientbp.ggpolarbear.com"
    },
    "VN": {  # Vietnam
        "login": "https://loginbp.ggpolarbear.com",
        "server": "https://clientbp.ggpolarbear.com"
    },
    "BD": {  # Bangladesh
        "login": "https://loginbp.ggpolarbear.com",
        "server": "https://clientbp.ggwhitehawk.com"
    },
    "PK": {  # Pakistan
        "login": "https://loginbp.ggpolarbear.com",
        "server": "https://clientbp.ggblueshark.com"
    },
    "SG": {  # Singapore
        "login": "https://loginbp.ggpolarbear.com",
        "server": "https://clientbp.ggpolarbear.com"
    },
    "BR": {  # Brazil
        "login": "https://loginbp.ggpolarbear.com",
        "server": "https://client.us.freefiremobile.com"
    },
    "NA": {  # North America
        "login": "https://loginbp.ggpolarbear.com",
        "server": "https://client.us.freefiremobile.com"
    },
    "ID": {  # Indonesia
        "login": "https://loginbp.ggpolarbear.com",
        "server": "https://clientbp.ggpolarbear.com"
    },
    "RU": {  # Russia
        "login": "https://loginbp.ggpolarbear.com",
        "server": "https://clientbp.ggpolarbear.com"
    },
    "TH": {  # Thailand
        "login": "https://loginbp.ggpolarbear.com",
        "server": "https://clientbp.ggpolarbear.com"
    }
}

# Default region if not specified
DEFAULT_REGION = "ME"

_sym_db = _symbol_database.Default()
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\ndata.proto\"\xbb\x01\n\x04\x44\x61ta\x12\x0f\n\x07\x66ield_2\x18\x02 \x01(\x05\x12\x1e\n\x07\x66ield_5\x18\x05 \x01(\x0b\x32\r.EmptyMessage\x12\x1e\n\x07\x66ield_6\x18\x06 \x01(\x0b\x32\r.EmptyMessage\x12\x0f\n\x07\x66ield_8\x18\x08 \x01(\t\x12\x0f\n\x07\x66ield_9\x18\t \x01(\x05\x12\x1f\n\x08\x66ield_11\x18\x0b \x01(\x0b\x32\r.EmptyMessage\x12\x1f\n\x08\x66ield_12\x18\x0c \x01(\x0b\x32\r.EmptyMessage\"\x0e\n\x0c\x45mptyMessageb\x06proto3'
)
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'data1_pb2', _globals)
BioData = _sym_db.GetSymbol('Data')
EmptyMessage = _sym_db.GetSymbol('EmptyMessage')

def encrypt_data(data_bytes):
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    padded = pad(data_bytes, AES.block_size)
    return cipher.encrypt(padded)

def get_name_region_from_reward(access_token):
    try:
        uid_url = "https://prod-api.reward.ff.garena.com/redemption/api/auth/inspect_token/"
        uid_headers ={
            "authority": "prod-api.reward.ff.garena.com",
            "method": "GET",
            "path": "/redemption/api/auth/inspect_token/",
            "scheme": "https",
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "access-token": access_token,
            "cookie": "_gid=GA1.2.444482899.1724033242; _ga_XB5PSHEQB4=GS1.1.1724040177.1.1.1724040732.0.0.0; token_session=cb73a97aaef2f1c7fd138757dc28a08f92904b1062e66c; _ga_KE3SY7MRSD=GS1.1.1724041788.0.0.1724041788.0; _ga_RF9R6YT614=GS1.1.1724041788.0.0.1724041788.0; _ga=GA1.1.1843180339.1724033241; apple_state_key=817771465df611ef8ab00ac8aa985783; _ga_G8QGMJPWWV=GS1.1.1724049483.1.1.1724049880.0.0; datadome=HBTqAUPVsbBJaOLirZCUkN3rXjf4gRnrZcNlw2WXTg7bn083SPey8X~ffVwr7qhtg8154634Ee9qq4bCkizBuiMZ3Qtqyf3Isxmsz6GTH_b6LMCKWF4Uea_HSPk;",
            "origin": "https://reward.ff.garena.com",
            "referer": "https://reward.ff.garena.com/",
            "sec-ch-ua": '"Not.A/Brand";v="99", "Chromium";v="124"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        uid_res = requests.get(uid_url, headers=uid_headers, verify=False)
        uid_data = uid_res.json()
        
        return uid_data.get("uid"), uid_data.get("name"), uid_data.get("region")
    except Exception as e:
        return None, None, None

def get_openid_from_shop2game(uid):
    if not uid: return None
    try:
        openid_url = "https://topup.pk/api/auth/player_id_login"
        openid_headers = { 
            "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-MM,en-US;q=0.9,en;q=0.8",
        "Content-Type": "application/json",
        "Origin": "https://topup.pk",
        "Referer": "https://topup.pk/",
        "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Android WebView";v="138"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Linux; Android 15; RMX5070 Build/UKQ1.231108.001) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.157 Mobile Safari/537.36",
        "X-Requested-With": "mark.via.gp",
        "Cookie": "source=mb; region=PK; mspid2=13c49fb51ece78886ebf7108a4907756; _fbp=fb.1.1753985808817.794945392376454660; language=en; datadome=WQaG3HalUB3PsGoSXY3TdcrSQextsSFwkOp1cqZtJ7Ax4YkiERHUgkgHlEAIccQO~w8dzTGM70D9SzaH7vymmEqOrVeX5pIsPVE22Uf3TDu6W3WG7j36ulnTg2DltRO7; session_key=hq02g63z3zjcumm76mafcooitj7nc79y",
        }
        payload = {"app_id": 100067, "login_id": str(uid)}
        res = requests.post(openid_url, headers=openid_headers, json=payload, verify=False)
        data = res.json()
        return data.get("open_id")
    except Exception as e:
        return None

def decode_jwt_info(token):
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        name = decoded.get("nickname")
        region = decoded.get("lock_region") 
        uid = decoded.get("account_id")
        return str(uid), name, region
    except:
        return None, None, None

def perform_major_login(access_token, open_id, login_url):
    platforms = [8, 3, 4, 6]
    for platform_type in platforms:
        try:
            game_data = my_pb2.GameData()
            game_data.timestamp = "2024-12-05 18:15:32"
            game_data.game_name = "free fire"
            game_data.game_version = 1
            game_data.version_code = "1.123.4"
            game_data.os_info = "Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)"
            game_data.device_type = "Handheld"
            game_data.network_provider = "Verizon Wireless"
            game_data.connection_type = "WIFI"
            game_data.screen_width = 1280
            game_data.screen_height = 960
            game_data.dpi = "240"
            game_data.cpu_info = "ARMv7 VFPv3 NEON VMH | 2400 | 4"
            game_data.total_ram = 5951
            game_data.gpu_name = "Adreno (TM) 640"
            game_data.gpu_version = "OpenGL ES 3.0"
            game_data.user_id = "Google|74b585a9-0268-4ad3-8f36-ef41d2e53610"
            game_data.ip_address = "172.190.111.97"
            game_data.language = "en"
            game_data.open_id = open_id
            game_data.access_token = access_token
            game_data.platform_type = platform_type
            game_data.field_99 = str(platform_type)
            game_data.field_100 = str(platform_type)

            serialized_data = game_data.SerializeToString()
            encrypted = encrypt_data(serialized_data)
            hex_encrypted = binascii.hexlify(encrypted).decode('utf-8')
            
            edata = bytes.fromhex(hex_encrypted)
            major_login_url = f"{login_url}/MajorLogin"
            response = requests.post(major_login_url, data=edata, headers=LOGIN_HEADERS, verify=False, timeout=10)

            if response.status_code == 200:
                data_dict = None
                try:
                    example_msg = output_pb2.Garena_420()
                    example_msg.ParseFromString(response.content)
                    data_dict = {field.name: getattr(example_msg, field.name) 
                                 for field in example_msg.DESCRIPTOR.fields 
                                 if field.name == "token"}
                except Exception:
                    pass
                if data_dict and "token" in data_dict:
                    return data_dict["token"]
        except Exception:
            continue
    return None

def perform_guest_login(uid, password):
    payload = {
        'uid': uid,
        'password': password,
        'response_type': "token",
        'client_type': "2",
        'client_secret': "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        'client_id': "100067"
    }
    headers = {
        'User-Agent': "GarenaMSDK/4.0.19P9(SM-M526B ;Android 13;pt;BR;)",
        'Connection': "Keep-Alive"
    }
    oauth_url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    try:
        resp = requests.post(oauth_url, data=payload, headers=headers, timeout=10, verify=False)
        data = resp.json()
        if 'access_token' in data:
            return data['access_token'], data.get('open_id')
    except Exception as e:
        pass
    return None, None

def upload_bio_request(jwt_token, bio_text, server_url):
    try:
        data = BioData()
        data.field_2 = 17
        data.field_5.CopyFrom(EmptyMessage())
        data.field_6.CopyFrom(EmptyMessage())
        data.field_8 = bio_text
        data.field_9 = 1
        data.field_11.CopyFrom(EmptyMessage())
        data.field_12.CopyFrom(EmptyMessage())

        data_bytes = data.SerializeToString()
        encrypted = encrypt_data(data_bytes)

        headers = BIO_HEADERS.copy()
        headers["Authorization"] = f"Bearer {jwt_token}"

        update_url = f"{server_url}/UpdateSocialBasicInfo"
        resp = requests.post(update_url, headers=headers, data=encrypted, timeout=20, verify=False)

        status_text = "Unknown"
        if resp.status_code == 200: status_text = "✅ Success"
        elif resp.status_code == 401: status_text = "❌ Unauthorized (Invalid JWT)"
        else: status_text = f"⚠️ Status {resp.status_code}"

        raw_hex = binascii.hexlify(resp.content).decode('utf-8')

        return {
            "status": status_text,
            "code": resp.status_code,
            "bio": bio_text,
            "server_response": raw_hex
        }
    except Exception as e:
        return {"status": f"Error: {str(e)}", "code": 500, "bio": bio_text, "server_response": "N/A"}

@app.route("/bio_upload", methods=["GET", "POST"])
def combined_bio_upload():
    bio = request.args.get("bio") or request.form.get("bio")
    jwt_token = request.args.get("jwt") or request.form.get("jwt")
    uid = request.args.get("uid") or request.form.get("uid")
    password = request.args.get("pass") or request.form.get("pass")
    access_token = request.args.get("access") or request.form.get("access") or request.args.get("access_token")
    region = (request.args.get("region") or request.form.get("region") or DEFAULT_REGION).upper()

    if not bio:
        return jsonify({"status": "❌ Error", "code": 400, "error": "Missing 'bio' parameter"}), 400

    if region not in REGION_CONFIG:
        return jsonify({"status": "❌ Error", "code": 400, "error": f"Unsupported region '{region}'. Supported: {list(REGION_CONFIG.keys())}"}), 400

    login_url = REGION_CONFIG[region]["login"]
    server_url = REGION_CONFIG[region]["server"]

    final_jwt = None
    login_method = "Direct JWT"
    
    final_open_id = None
    final_access_token = None
    final_uid = None
    final_name = None
    final_region = None

    if jwt_token:
        final_jwt = jwt_token
        j_uid, j_name, j_region = decode_jwt_info(jwt_token)
        final_uid = j_uid
        final_name = j_name
        final_region = j_region
        
    elif uid and password:
        login_method = "UID/Pass Login"
        
        acc_token, login_openid = perform_guest_login(uid, password)
        
        if acc_token and login_openid:
            final_access_token = acc_token
            final_open_id = login_openid
            
            final_jwt = perform_major_login(final_access_token, final_open_id, login_url)
            
            if final_jwt:
                 j_uid, j_name, j_region = decode_jwt_info(final_jwt)
                 final_uid = j_uid
                 final_name = j_name
                 final_region = j_region
            else:
                 return jsonify({"status": "❌ JWT Generation Failed", "code": 500}), 500

        else:
            return jsonify({"status": "❌ Guest Login Failed (Check UID/Pass)", "code": 401}), 401

    elif access_token:
        login_method = "Access Token Login"
        final_access_token = access_token
        
        f_uid, f_name, f_region = get_name_region_from_reward(access_token)
        final_uid = f_uid
        final_name = f_name
        final_region = f_region

        if not final_uid:
            return jsonify({"status": "❌ Invalid Access Token", "code": 400}), 400

        final_open_id = get_openid_from_shop2game(final_uid)
        
        if final_open_id:
            final_jwt = perform_major_login(access_token, final_open_id, login_url)
        else:
            return jsonify({"status": "❌ Shop2Game OpenID Fetch Failed", "code": 400}), 400
    
    else:
        return jsonify({"status": "❌ Error", "code": 400, "error": "Provide JWT, or UID/Pass, or Access Token"}), 400

    if not final_jwt:
        return jsonify({"status": "❌ JWT Generation Failed", "code": 500}), 500

    result = upload_bio_request(final_jwt, bio, server_url)
    
    response_data = {
        "status": result["status"],
        "login_method": login_method,
        "code": result["code"],
        "bio": result["bio"],
        "uid": str(final_uid) if final_uid else None,
        "region": final_region,
        "selected_region": region,
        "open_id": final_open_id,
        "access_token": final_access_token,
        "server_response": result["server_response"],
        "generated_jwt": final_jwt
    }

    response = make_response(jsonify(response_data))
    response.headers["Content-Type"] = "application/json"
    return response

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)