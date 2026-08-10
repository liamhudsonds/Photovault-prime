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
def get_session_token():
    if 'session_token' not in session:
        session['session_token'] = str(uuid.uuid4())
    return session['session_token']

def has_access(photo_id):
    # Admin always has full access without paying
    if session.get('is_admin'):
        return True
    tok = get_session_token()
    purchase = Purchase.query.filter_by(photo_id=photo_id, session_token=tok).first()
    if purchase:
        if purchase.is_permanent:
            return True
        if purchase.expires_at and purchase.expires_at > datetime.utcnow():
            return True
    return False

def has_video_access(video_id):
    # Admin always has access
    if session.get('is_admin'):
        return True
    # Creator manager can always view videos belonging to their assigned creator
    if session.get('is_manager'):
        user_id = session.get('user_id')
        video   = Video.query.get(video_id)
        if video:
            profile = Profile.query.filter_by(manager_id=user_id, id=video.profile_id).first()
            if profile:
                return True
    tok = get_session_token()
    purchase = Purchase.query.filter_by(photo_id=video_id, session_token=tok).first()
    if purchase:
        if purchase.is_permanent:
            return True
        if purchase.expires_at and purchase.expires_at > datetime.utcnow():
            return True
    return False

def has_post_access(post_id, session_token=None):
    """Returns True if the session has unlocked a paid post, or post is free."""
    post = ProfilePost.query.get(post_id)
    if not post:
        return False
    if post.blur_strength == 0:
        return True
    if session_token is None:
        session_token = session.get('session_token', '')
    return PostUnlock.query.filter_by(post_id=post_id, session_token=session_token).first() is not None

# ══════════════════════════════════════════════════════════════════════════════
# TRENDING FEED  (public page)
# ══════════════════════════════════════════════════════════════════════════════
