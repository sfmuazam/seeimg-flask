from flask import Flask, render_template, redirect, url_for
from config import Config
from extensions import db, login_manager
from models import Users
from flask_login import login_required, current_user

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

from controllers.auth_controller import auth as auth_blueprint
from controllers.image_controller import images as images_blueprint
from controllers.api_controller import captioning as captioning_blueprint

app.register_blueprint(auth_blueprint)
app.register_blueprint(images_blueprint)
app.register_blueprint(captioning_blueprint)

@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main'))
    return render_template('index.html')

@app.route('/main')
@login_required
def main():
    return render_template('main.html')

if __name__ == '__main__':
    app.run(debug=True)
