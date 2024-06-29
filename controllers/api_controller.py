import os
import logging
import requests
from PIL import UnidentifiedImageError
from flask import Blueprint, request, jsonify, current_app
from utils import load_image_from_file, evaluate_beam_search, correct_caption, VALID_IMAGE_FORMATS
from collections import Counter

captioning = Blueprint('captioning', __name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_gemini_caption(imgbb_url, corrected_caption):
    gemini_response = requests.get(
        'https://api.nyxs.pw/ai/gemini-img',
        params={
            'url': imgbb_url,
            'text': f'Deskripsikan gambar ini tanpa menuliskan "Gambar ini menunjukkan" atau sejenisnya. Jika ini adalah salah satu dari lima tempat wisata berikut: Dlas, Owabong, Sanggaluri, Purbasari, atau Golaga (Goa Lawa), pertimbangkan deskripsi berikut: {corrected_caption}. Jika Iya, gunakan atau gabungkan dengan deskripsi yang dihasilkan. Jika ada yang tidak sesuai, abaikan. Jika bukan dari lima tempat tersebut, buat deskripsi sendiri tanpa mengikuti deskripsi yang diberikan model.'
        }
    )
    
    if gemini_response.status_code != 200:
        logger.error("Gagal mendapatkan deskripsi dari API Gemini")
        return None
    
    gemini_data = gemini_response.json()
    return gemini_data.get('result', corrected_caption)

@captioning.route('/captioning', methods=['POST'])
def caption_image():
    if 'file' not in request.files:
        return jsonify({"error": "Bagian file tidak ada"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Tidak ada file yang dipilih"}), 400
    if file.content_type.split("/")[-1] not in VALID_IMAGE_FORMATS:
        return jsonify({"error": "Format gambar tidak valid"}), 400
    
    try:
        # Generate local caption
        image_tensor = load_image_from_file(file)
        caption, _, _ = evaluate_beam_search(image_tensor)
        caption = ' '.join([word for word in caption if word != "<unk>"])
        corrected_caption = correct_caption(caption)
        
        # Upload the image to Imgbb
        imgbb_api_key = current_app.config['IMGBB_API_KEY']
        file.seek(0)
        imgbb_response = requests.post(
            'https://api.imgbb.com/1/upload',
            params={
                'key': imgbb_api_key,
                'expiration': 120
            },
            files={
                'image': file
            }
        )
        
        if imgbb_response.status_code != 200:
            logger.error("Gagal mengunggah gambar ke Imgbb")
            return jsonify({"error": "Gagal mengunggah gambar ke Imgbb"}), 500
        
        imgbb_data = imgbb_response.json()
        imgbb_url = imgbb_data['data']['url']
        delete_url = imgbb_data['data']['delete_url']

        # Rerun and Averaging
        captions = []
        for _ in range(3):  # Number of reruns
            result = get_gemini_caption(imgbb_url, corrected_caption)
            if result:
                captions.append(result)
        
        most_common_caption = Counter(captions).most_common(1)[0][0] if captions else corrected_caption

        # Delete the image from Imgbb
        requests.delete(delete_url)

        return jsonify({"caption": most_common_caption})
    except UnidentifiedImageError:
        return jsonify({"error": "File gambar tidak valid"}), 400
    except Exception as e:
        logger.error(f"Kesalahan: {str(e)}")
        return jsonify({"error": str(e)}), 500
