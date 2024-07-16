import os
import logging
import requests
from PIL import UnidentifiedImageError
from flask import Blueprint, request, jsonify, current_app
from utils import load_image_from_file, evaluate_beam_search, correct_caption, get_gemini_caption, VALID_IMAGE_FORMATS
from bs4 import BeautifulSoup

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
        
        try:
            corrected_caption = correct_caption(caption)
        except Exception as e:
            logger.error(f"Kesalahan saat mengoreksi caption: {str(e)}")
            corrected_caption = caption
        
        # Rewind the file pointer to the beginning of the file
        file.seek(0)
        files = {'file': (file.filename, file.stream, file.content_type)}
        response = requests.post('https://uploader.nyxs.pw/upload', files=files)

        img_url = None

        if response.status_code == 200:
            # Parsing HTML response to extract the URL
            soup = BeautifulSoup(response.content, 'html.parser')
            url_tag = soup.find('a')
            
            if url_tag and url_tag.get('href'):
                img_url = url_tag.get('href')
            else:
                logger.error("URL tidak ditemukan dalam respons")
        else:
            logger.error("Gagal mengunggah gambar ke uploader.nyxs.pw")
        
        # If upload is successful and img_url is not None, get the Gemini caption
        if img_url:
            gemini_caption = get_gemini_caption(img_url, corrected_caption)
            final_caption = gemini_caption if gemini_caption else corrected_caption
        else:
            final_caption = corrected_caption

        return jsonify({"caption": final_caption})
    except UnidentifiedImageError:
        return jsonify({"error": "File gambar tidak valid"}), 400
    except Exception as e:
        logger.error(f"Kesalahan: {str(e)}")
        return jsonify({"error": str(e)}), 500