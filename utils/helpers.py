from datetime import datetime, timedelta, UTC
import os, uuid, random, string, hashlib, hmac, re, json, errno
from flask import session, current_app, url_for
from werkzeug.security import generate_password_hash
from flask_mail import Message
from PIL import Image, ImageDraw, ImageFont
import io

from database.db import db, mail
from models import *
from utils.constants import *
def safe_makedirs(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

# Create all upload folders
"""
safe_makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'originals'))
safe_makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'previews'))
safe_makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'videos'))
safe_makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'video_thumbs'))
safe_makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'video_previews'))
safe_makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profiles'))       # NEW
safe_makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profile_posts'))  # NEW
"""

def upload_url(endpoint, profile_id=None, **kwargs):
    """Build creator-dashboard URLs."""
    return url_for(endpoint, **kwargs)

def is_admin_override():
    """Admin override is permanently disabled — admins no longer have creator access."""
    return False

def resolve_creator_dashboard_profile(require_profile=True):
    """Resolve the active profile for creator-dashboard routes.
    Admin override has been removed — only creator managers can access these routes.
    """
    profile = Profile.query.filter_by(manager_id=session.get('user_id')).first()
    if require_profile and not profile:
        return None, False
    return profile, False

def calculate_age(dob):
    """Returns age in whole years given a date object."""
    if not dob:
        return None
    today = datetime.utcnow().date()
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return years
