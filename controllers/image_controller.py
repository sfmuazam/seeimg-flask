import os
import datetime
import logging
import uuid
import pytz
import requests
from PIL import UnidentifiedImageError
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from utils import load_image_from_file, evaluate_beam_search, correct_caption, VALID_IMAGE_FORMATS
from extensions import db
from models import Images
from collections import Counter

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

images = Blueprint('images', __name__)

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
        file_ext = secure_filename(file.filename).split('.')[-1]
        filename = f"{uuid.uuid4()}.{file_ext}"
        upload_folder = 'static/uploads'
        
        # Ensure the upload directory exists
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        # Generate local caption
        with open(file_path, 'rb') as f:
            image_tensor = load_image_from_file(f)
        
        caption, _, _ = evaluate_beam_search(image_tensor)
        caption = ' '.join([word for word in caption if word != "<unk>"])
        corrected_caption = correct_caption(caption)
        
        # Upload the image to Imgbb
        imgbb_api_key = current_app.config['IMGBB_API_KEY']
        with open(file_path, 'rb') as f:
            imgbb_response = requests.post(
                'https://api.imgbb.com/1/upload',
                params={
                    'key': imgbb_api_key,
                    'expiration': 120
                },
                files={
                    'image': f
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

        # Save image data to database
        wib = pytz.timezone('Asia/Jakarta')
        upload_date = datetime.datetime.now(wib)

        new_image = Images(
            user_id=current_user.id, 
            image_path=file_path, 
            predicted_caption=most_common_caption, 
            upload_date=upload_date
        )
        db.session.add(new_image)
        db.session.commit()

        return jsonify({"caption": most_common_caption})
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
        
        # Delete the image file from the system
        if os.path.exists(image.image_path):
            os.remove(image.image_path)
        
        # Delete the image record from the database
        db.session.delete(image)
        db.session.commit()

        return jsonify({"message": "Gambar berhasil dihapus"}), 200
    except Exception as e:
        logger.error(f"Kesalahan: {str(e)}")
        return jsonify({"error": str(e)}), 500
