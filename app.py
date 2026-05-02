from flask import Flask, request, Response
import requests
import json
import os

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False


# 🔹 جلب معلومات اللاعب
def get_player_info(player_id):
    url = f"https://xza-get-region.vercel.app/region?uid={player_id}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {
                "nickname": data.get("nickname", "غير متوفر"),
                "region": data.get("region", "غير معروف")
            }
    except:
        pass

    return {
        "nickname": "غير متوفر",
        "region": "غير معروف"
    }


# 🔥 تحويل قيمة الحظر بشكل آمن
def parse_bool(value):
    return str(value).lower() == "true"


# 🔹 فحص الحظر
def check_banned(player_id):
    url = f"https://banchack.vercel.app/bancheck?key=saeed&uid={player_id}"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)

        print("RAW RESPONSE:", response.text)

        player_info = get_player_info(player_id)

        if response.status_code != 200:
            raise Exception("API ERROR")

        # 🔥 مهم: لا تستخدم data.get("data")
        ban_data = response.json()

        is_banned = parse_bool(ban_data.get("is_banned", False))
        period = int(ban_data.get("ban_period", 0))

        result = {
            "status": "success",
            "uid": player_id,
            "nickname": player_info["nickname"],
            "region": player_info["region"],
            "account_status": "BANNED" if is_banned else "NOT BANNED",
            "ban_duration_days": period if is_banned else 0,
            "is_banned": is_banned,
            "powered_by": "nassim"
        }

        return Response(
            json.dumps(result, ensure_ascii=False, indent=4),
            mimetype="application/json"
        )

    except Exception as e:
        return Response(json.dumps({
            "status": "error",
            "message": str(e),
            "account_status": "UNKNOWN",
            "is_banned": None
        }, ensure_ascii=False, indent=4), mimetype="application/json")


# 🔹 endpoint
@app.route("/check", methods=["GET"])
def check():
    uid = request.args.get("uid", "").strip()

    if not uid:
        return Response(json.dumps({
            "status": "error",
            "message": "uid required"
        }, ensure_ascii=False, indent=4), mimetype="application/json")

    return check_banned(uid)


# 🔹 تشغيل السيرفر
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
