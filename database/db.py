"""Database and Flask extension initialization."""
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail

db = SQLAlchemy()
mail = Mail()
download_tokens = {}

# Reserved for future Flask-Login integration
login_manager = None


def init_extensions(app):
    db.init_app(app)
    mail.init_app(app)
    return db, mail
