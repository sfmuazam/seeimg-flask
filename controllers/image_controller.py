import os
import datetime
import logging
import uuid
import pytz
import requests
from PIL import Image, UnidentifiedImageError
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from utils import load_image_from_file, evaluate_beam_search, correct_caption, get_gemini_caption, VALID_IMAGE_FORMATS
from extensions import db
from models import Images
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

images = Blueprint('images', __name__)

@images.route('/images', methods=['POST'])
@login_required
def upload_image():
    if 'file' not in request.files:
        logger.error("Bagian file tidak ada")
        return jsonify({"error": "Bagian file tidak ada"}), 400
    file = request.files['file']
    if file.filename == '':
        logger.error("Tidak ada file yang dipilih")
        return jsonify({"error": "Tidak ada file yang dipilih"}), 400
    if file.content_type.split("/")[-1] not in VALID_IMAGE_FORMATS:
        logger.error("Format gambar tidak valid")
        return jsonify({"error": "Format gambar tidak valid"}), 400
    
    try:
        # Simpan file asli untuk analisis model
        file_ext = secure_filename(file.filename).split('.')[-1]
        original_filename = f"{uuid.uuid4()}.{file_ext}"
        upload_folder = 'static/uploads'
        
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        original_file_path = os.path.join(upload_folder, original_filename)
        file.save(original_file_path)
        
        # Load image for model analysis using the original file path
        with open(original_file_path, 'rb') as f:
            image_tensor = load_image_from_file(f)
        
        caption, _, _ = evaluate_beam_search(image_tensor)
        caption = ' '.join([word for word in caption if word != "<unk>"])
        
        corrected_caption = correct_caption(caption)
        
        # Konversi gambar ke format WebP dengan kompresi dan simpan untuk penyimpanan yang efisien
        webp_filename = f"{uuid.uuid4()}.webp"
        webp_file_path = os.path.join(upload_folder, webp_filename)
        
        with Image.open(original_file_path) as img:
            img = img.convert('RGB')
            img.save(webp_file_path, format="webp", quality=65, method=6)
        
        # Upload the image to Nyxs Uploader
        with open(original_file_path, 'rb') as f:
            files = {'file': (file.filename, f, file.content_type)}
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

        wib = pytz.timezone('Asia/Jakarta')
        upload_date = datetime.datetime.now(wib)

        new_image = Images(
            user_id=current_user.id, 
            image_path=webp_file_path, 
            predicted_caption=final_caption, 
            upload_date=upload_date
        )
        db.session.add(new_image)
        db.session.commit()

        return jsonify({"caption": final_caption})
    except UnidentifiedImageError:
        logger.error("File gambar tidak valid")
        return jsonify({"error": "File gambar tidak valid"}), 400
    except ValueError as ve:
        logger.error(f"Kesalahan nilai: {str(ve)}")
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Kesalahan: {str(e)}")
        return jsonify({"error": str(e)}), 500

@images.route('/images', methods=['GET'])
@login_required
def get_images():
    try:
        images = Images.query.filter_by(user_id=current_user.id).order_by(Images.upload_date.desc()).all()
        images_data = [
            {
                "id": image.id,
                "image_path": image.image_path,
                "upload_date": image.upload_date,
                "predicted_caption": image.predicted_caption
            } 
            for image in images
        ]
        return jsonify(images_data)
    except Exception as e:
        logger.error(f"Kesalahan: {str(e)}")
        return jsonify({"error": str(e)}), 500

@images.route('/images/<int:image_id>', methods=['DELETE'])
@login_required
def delete_image(image_id):
    try:
        image = Images.query.get(image_id)
        if image is None or image.user_id != current_user.id:
            logger.error("Gambar tidak ditemukan atau pengguna tidak diizinkan")
            return jsonify({"error": "Gambar tidak ditemukan atau pengguna tidak diizinkan"}), 404
        
        if os.path.exists(image.image_path):
            os.remove(image.image_path)
        
        db.session.delete(image)
        db.session.commit()

        return jsonify({"message": "Gambar berhasil dihapus"}), 200
    except Exception as e:
        logger.error(f"Kesalahan: {str(e)}")
        return jsonify({"error": str(e)}), 500
