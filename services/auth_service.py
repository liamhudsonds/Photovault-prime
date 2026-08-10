from datetime import datetime, timedelta, UTC
import os, uuid, random, string, hashlib, hmac, re, json
from flask import session, current_app, url_for
from werkzeug.security import generate_password_hash
from flask_mail import Message
from PIL import Image, ImageDraw, ImageFont
import io

from database.db import db, mail
from models import *
from utils.constants import *
def get_setting(key, default=''):
    """Get a site setting by key."""
    s = SiteSettings.query.filter_by(key=key).first()
    return s.value if s else default

def set_setting(key, value):
    """Save or update a site setting."""
    s = SiteSettings.query.filter_by(key=key).first()
    if s:
        s.value = str(value)
    else:
        db.session.add(SiteSettings(key=key, value=str(value)))
    db.session.commit()
