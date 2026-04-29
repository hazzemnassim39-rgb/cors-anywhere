from flask import Flask, request, jsonify, send_file
import requests
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=10)

def fetch_player_info(uid):
    player_info_url = f'https://privet-api-info-01.vercel.app/player-info?uid={uid}'
    response = requests.get(player_info_url)
    if response.status_code == 200:
        return response.json()
    return None

def fetch_and_process_image(image_url, size=None):
    response = requests.get(image_url)
    if response.status_code == 200:
        try:
            image = Image.open(BytesIO(response.content))
            if size:
                image = image.resize(size)
            return image
        except Exception:
            return None
    return None

@app.route('/outfit-image', methods=['GET'])
def outfit_image():
    uid = request.args.get('uid')
    key = request.args.get('key')

    if key != 'NASSIM':
        return jsonify({'error': 'Invalid or missing API key'}), 401

    player_data = fetch_player_info(uid)
    if player_data is None:
        return jsonify({'error': 'Failed to fetch player info'}), 500

    outfit_ids = player_data.get("AccountProfileInfo", {}).get("EquippedOutfit", [])
    required_starts = ["211", "214", "211", "203", "204", "205", "203"]
    fallback_ids = ["211000000", "214000000", "208000000", "203000000", "204000000", "205000000", "212000000"]

    used_ids = set()
    outfit_images = []

    def fetch_outfit_image(idx, code):
        matched = None
        for oid in outfit_ids:
            str_oid = str(oid)
            if str_oid.startswith(code) and oid not in used_ids:
                matched = oid
                used_ids.add(oid)
                break
        if matched is None:
            matched = fallback_ids[idx]
        image_url = f'https://iconapi.wasmer.app/{matched}'
        return fetch_and_process_image(image_url, size=(150, 150))

    for idx, code in enumerate(required_starts):
        outfit_images.append(executor.submit(fetch_outfit_image, idx, code))

    bg_url = 'https://iili.io/39iE4rF.jpg'
    background_image = fetch_and_process_image(bg_url)
    if not background_image:
        return jsonify({'error': 'Failed to fetch background image'}), 500

    positions = [
        {'x': 280, 'y': 20, 'height': 150, 'width': 150},
        {'x': 470, 'y': 95, 'height': 150, 'width': 150},
        {'x': 550, 'y': 280, 'height': 150, 'width': 150},
        {'x': 470, 'y': 455, 'height': 150, 'width': 150},
        {'x': 280, 'y': 535, 'height': 150, 'width': 150},
        {'x': 100, 'y': 455, 'height': 150, 'width': 150},
        {'x': 25, 'y': 280, 'height': 150, 'width': 150}
    ]

    for idx, future in enumerate(outfit_images):
        outfit_image = future.result()
        if outfit_image:
            pos = positions[idx]
            resized = outfit_image.resize((pos['width'], pos['height']))
            background_image.paste(resized, (pos['x'], pos['y']), resized.convert("RGBA"))

    output_image = BytesIO()
    background_image.save(output_image, format='PNG')
    output_image.seek(0)
    return send_file(output_image, mimetype='image/png')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
