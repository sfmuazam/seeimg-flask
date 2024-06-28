import os
import datetime
import logging
import uuid
import pytz
from PIL import UnidentifiedImageError
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from utils import load_image_from_file, evaluate_beam_search, correct_caption, VALID_IMAGE_FORMATS
from extensions import db
from models import Images

# Setup logging
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
        file_ext = secure_filename(file.filename).split('.')[-1]
        filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join('static/uploads', filename)
        file.save(file_path)
        
        with open(file_path, 'rb') as f:
            image_tensor = load_image_from_file(f)
        
        caption, _, _ = evaluate_beam_search(image_tensor)
        caption = ' '.join([word for word in caption if word != "<unk>"])
        corrected_caption = correct_caption(caption)

        # Set the timezone to WIB and get the current time
        wib = pytz.timezone('Asia/Jakarta')
        upload_date = datetime.datetime.now(wib)

        new_image = Images(user_id=current_user.id, image_path=file_path, predicted_caption=corrected_caption, upload_date=upload_date)
        db.session.add(new_image)
        db.session.commit()

        return jsonify({"caption": corrected_caption})
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
