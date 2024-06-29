import os
import logging
import requests
from PIL import UnidentifiedImageError
from flask import Blueprint, request, jsonify, current_app
from utils import load_image_from_file, evaluate_beam_search, correct_caption, get_gemini_caption, VALID_IMAGE_FORMATS
from collections import Counter

captioning = Blueprint('captioning', __name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        image_tensor = load_image_from_file(file)
        caption, _, _ = evaluate_beam_search(image_tensor)
        caption = ' '.join([word for word in caption if word != "<unk>"])
        corrected_caption = correct_caption(caption)
        
        imgbb_api_key = current_app.config['IMGBB_API_KEY']
        file.seek(0)
        imgbb_response = requests.post(
            'https://api.imgbb.com/1/upload',
            params={
                'key': imgbb_api_key,
                'expiration': 75
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

        captions = []
        for _ in range(3):  
            result = get_gemini_caption(imgbb_url, corrected_caption)
            if result:
                captions.append(result)
        
        most_common_caption = Counter(captions).most_common(1)[0][0] if captions else corrected_caption

        requests.delete(delete_url)

        return jsonify({"caption": most_common_caption})
    except UnidentifiedImageError:
        return jsonify({"error": "File gambar tidak valid"}), 400
    except Exception as e:
        logger.error(f"Kesalahan: {str(e)}")
        return jsonify({"error": str(e)}), 500
