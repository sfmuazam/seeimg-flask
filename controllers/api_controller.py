from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from PIL import UnidentifiedImageError
import os
from utils import load_image_from_file, evaluate_beam_search, correct_caption, tokenizer, VALID_IMAGE_FORMATS

captioning = Blueprint('captioning', __name__)

@captioning.route('/captioning', methods=['POST'])
def caption_image():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file.content_type.split("/")[-1] not in VALID_IMAGE_FORMATS:
        return jsonify({"error": "Invalid image format"}), 400
    
    try:
        image_tensor = load_image_from_file(file)
        caption, _, _ = evaluate_beam_search(image_tensor)
        caption = ' '.join([word for word in caption if word != "<unk>"])
        corrected_caption = correct_caption(caption)
        return jsonify({"caption": corrected_caption})
    except UnidentifiedImageError:
        return jsonify({"error": "Invalid image file"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
