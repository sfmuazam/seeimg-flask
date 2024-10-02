# SeeImgPbg: Image Captioning for Tourist Attractions in Purbalingga

A web-based application that utilizes a custom image captioning model to generate descriptive captions for images of tourist attractions in Purbalingga. The model is built using **ResNet50** for feature extraction and **Transformer algorithms** for generating captions. Integrated with a text-to-speech feature, the system also reads the captions aloud.

## Tech Stack

![Python](https://img.shields.io/badge/python-%2314354C.svg?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/flask-%23000.svg?style=for-the-badge&logo=flask&logoColor=white)
![MySQL](https://img.shields.io/badge/mysql-%2300000f.svg?style=for-the-badge&logo=mysql&logoColor=white)
![TensorFlow](https://img.shields.io/badge/tensorflow-%23FF6F00.svg?style=for-the-badge&logo=tensorflow&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/tailwindcss-%2338B2AC.svg?style=for-the-badge&logo=tailwind-css&logoColor=white)

## System Overview

### Key Features
- **Image Captioning**: Users can upload images of tourist attractions, and the system generates a descriptive caption using a combination of **ResNet50** and **Transformer** models.
- **Text-to-Speech**: Automatically converts the generated captions into speech, enhancing accessibility.
- **History Feature**: The system saves a history of uploaded images and their generated captions for users to view later.
- **Web Integration**: The captioning model is seamlessly integrated into a Flask-based web interface for easy image uploads and caption generation.
  
### Images
![SeeImgPbg System Overview](https://example.com/seeimgpbg-overview.png)

## Installation

### Prerequisites
Ensure you have the following installed on your machine:
- Python 3.8+
- Flask
- MySQL
- TensorFlow

### Steps

1. **Clone the Repository**
    ```bash
    git clone https://github.com/yourusername/seeimg-flask.git
    cd seeimg-flask
    ```

2. **Install Python Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3. **Environment Setup**
    Create a `.env` file by copying `.env.example`:
    ```bash
    cp .env.example .env
    ```
    Update your database credentials and other configurations in `.env`:
    ```bash
    SECRET_KEY=YOUR_SECRET_KEY
    DATABASE_URL=mysql+pymysql://username:password@host/db_name
    ```
    
4. **Import the Database**
    Use the `seeimg.sql` file to set up the database.

5. **Run the Application**
    Start the Flask development server:
    ```bash
    flask run
    ```
    The application will be accessible at `http://localhost:5000`.
