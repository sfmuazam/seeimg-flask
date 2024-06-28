import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY') or 'rahasia'
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or 'mysql+pymysql://root:@localhost/seeimg'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
