from app import db
from flask_login import UserMixin
from datetime import datetime

class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class Images(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    predicted_caption = db.Column(db.String(1000))
    upload_date = db.Column(db.TIMESTAMP, default=datetime.utcnow)
