# -*- coding: utf-8 -*-
"""VaultX — Flask application entry point."""
import os
import errno
import stripe

from flask import Flask
from dotenv import load_dotenv

from config import Config
from database.db import init_extensions
from database.seed import create_admin
from routes import register_blueprints
from middleware.errors import register_error_handlers
from middleware.logging import register_logging
from middleware.auth import register_auth_context
from utils.helpers import safe_makedirs
from utils.constants import PROFILE_UPLOAD_FOLDER, POST_UPLOAD_FOLDER

load_dotenv()


def create_app(config_class=Config):
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Upload folders
    os.makedirs(PROFILE_UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(POST_UPLOAD_FOLDER, exist_ok=True)
    for sub in ('originals', 'previews', 'videos', 'video_thumbs', 'video_previews', 'profiles', 'profile_posts'):
        safe_makedirs(os.path.join(app.config['UPLOAD_FOLDER'], sub))

    init_extensions(app)

    # Payment providers
    stripe.api_key = app.config['STRIPE_SECRET_KEY']

    # Jinja2 globals
    app.jinja_env.globals['enumerate'] = enumerate
    app.jinja_env.globals['range'] = range
    app.jinja_env.globals['len'] = len
    app.jinja_env.globals['zip'] = zip

    register_blueprints(app)
    register_error_handlers(app)
    register_logging(app)
    register_auth_context(app)

    with app.app_context():
        create_admin()

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=4000)
