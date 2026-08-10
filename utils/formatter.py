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
def dynamic_price(photo):
    if not photo.dynamic_pricing:
        return photo.unlock_price
    bump = (photo.view_count / 10) * 0.5
    return round(photo.unlock_price + bump, 2)

# Alias used in templates and routes for convenience

def get_current_price(photo):
    return dynamic_price(photo)

def make_slug(name):
    """Turn a category name into a URL slug."""
    import re
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug

def _time_ago(dt):
    diff = datetime.utcnow() - dt
    s = int(diff.total_seconds())
    if s < 60:   return 'just now'
    if s < 3600: return '{} min ago'.format(s // 60)
    if s < 86400:return '{} hr ago'.format(s // 3600)
    return '{} days ago'.format(s // 86400)


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS  API
# ══════════════════════════════════════════════════════════════════════════════
