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
def resolve_creator_dashboard_profile(require_profile=True):
    """Resolve the active profile for creator-dashboard routes.
    Admin override has been removed — only creator managers can access these routes.
    """
    profile = Profile.query.filter_by(manager_id=session.get('user_id')).first()
    if require_profile and not profile:
        return None, False
    return profile, False

def upload_url(endpoint, profile_id=None, **kwargs):
    """Build creator-dashboard URLs."""
    return url_for(endpoint, **kwargs)

def is_admin_override():
    """Admin override is permanently disabled — admins no longer have creator access."""
    return False
