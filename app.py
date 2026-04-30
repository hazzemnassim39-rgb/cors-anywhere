from flask import Flask, request, Response
import requests
import json
import os

app = Flask(__name__)

def get_player_info(player_id):
    url = f"https://xza-get-region.vercel.app/region?uid={player_id}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {
                "nickname": data.get("nickname", "Not available"),
                "region": data.get("region", "Unknown")
            }
    except:
        pass

    return {
        "nickname": "Failed to fetch nickname",
        "region": "Failed to fetch region"
    }


# دالة فحص الحظر
def check_banned(player_id):
    url = f"https://banchack.vercel.app/bancheck?key=saeed&uid={player_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10)",
        "Accept": "application/json",
        "referer": "https://ff.garena.com/en/support/",
        "x-requested-with": "B6FksShzIgjfrYImLpTsadjS86sddhFH"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        player_info = get_player_info(player_id)

        if response.status_code == 200:
            data = response.json().get("data", {})
            is_banned = data.get("is_banned", 0)
            period = data.get("period", 0)

            result = {
                "status": "success",
                "uid": player_id,
                "nickname": player_info["nickname"],
                "region": player_info["region"],
                "account_status": "BANNED" if is_banned else "NOT BANNED",
                "ban_duration_days": period if is_banned else 0,
                "is_banned": bool(is_banned),
                "powered_by": "nassim"
            }

            return Response(
                json.dumps(result, indent=4, ensure_ascii=False),
                mimetype="application/json"
            )

        return Response(json.dumps({
            "status": "error",
            "message": "Failed to fetch ban status",
            "status_code": 500
        }, indent=4), mimetype="application/json")

    except Exception as e:
        return Response(json.dumps({
            "status": "exception",
            "error": str(e),
            "status_code": 500
        }, indent=4), mimetype="application/json")


@app.route("/check", methods=["GET"])
def check():
    player_id = request.args.get("uid", "")

    if not player_id:
        return Response(json.dumps({
            "status": "error",
            "message": "uid is required",
            "status_code": 400
        }, indent=4), mimetype="application/json")

    return check_banned(player_id)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))