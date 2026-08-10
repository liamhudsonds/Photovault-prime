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
def generate_watermark_preview(original_path, preview_path, blur_strength=12):
    try:
        img = Image.open(original_path).convert('RGBA')
        img.thumbnail((800, 800), Image.LANCZOS)
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw    = ImageDraw.Draw(overlay)
        text    = '© VaultX — PREVIEW'
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 28)
        except Exception:
            font = ImageFont.load_default()
        for x in range(0, img.width, 250):
            for y in range(0, img.height, 150):
                draw.text((x, y), text, fill=(255, 255, 255, 80), font=font)
        watermarked = Image.alpha_composite(img, overlay).convert('RGB')
        watermarked.save(preview_path, 'JPEG', quality=75)
        return True
    except Exception as e:
        print('Watermark error: {}'.format(str(e)))
        return False

def get_blur_settings(profile_id):
    s = CreatorBlurSettings.query.filter_by(profile_id=profile_id).first()
    if not s:
        s = CreatorBlurSettings(profile_id=profile_id)
        db.session.add(s)
        db.session.commit()
    return s

def check_upload_allowed(profile, content_kind):
    """Returns (allowed: bool, message: str). content_kind is 'photo' or 'video'.

    Enforces the per-creator upload cap defined in UPLOAD_LIMITS unless the
    profile has an active Premium subscription, in which case uploads are
    unlimited. Premium revenue (100%) goes entirely to the platform.
    """
    if profile.is_premium:
        return True, ''

    limits = UPLOAD_LIMITS['basic']
    if content_kind == 'photo':
        count = Photo.query.filter_by(profile_id=profile.id, is_active=True).count()
        cap   = limits['photos']
    else:
        count = Video.query.filter_by(profile_id=profile.id, is_active=True).count()
        cap   = limits['videos']

    if cap is not None and count >= cap:
        return False, (
            'You have reached the basic plan limit of {} {}s. '
            'Upgrade to Premium for unlimited uploads, longer videos, '
            'higher-quality photos, and unlimited live hours.'
        ).format(cap, content_kind)
    return True, ''
