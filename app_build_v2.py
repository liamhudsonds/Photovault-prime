# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, flash, jsonify, session, redirect, url_for, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime, timedelta, UTC
import os, uuid, stripe, hashlib, hmac, time, json, requests, errno
from PIL import Image, ImageDraw, ImageFont
import io
import random
import string

from dotenv import load_dotenv
from flask import render_template, request, abort, send_from_directory
import os

load_dotenv()

app = Flask(__name__)
download_tokens = {}

# ── Mail ───────────────────────────────────────────────────────────────────────
app.config['MAIL_SERVER']         = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT']           = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS']        = os.getenv('MAIL_USE_TLS') == 'True'
app.config['MAIL_USE_SSL']        = os.getenv('MAIL_USE_SSL') == 'True'
app.config['MAIL_USERNAME']       = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD']       = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = ('VaultX', os.getenv('MAIL_DEFAULT_SENDER'))
mail = Mail(app)

# ── Configuration ──────────────────────────────────────────────────────────────
app.config['SECRET_KEY']                     = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI']        = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER']                  = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH']             = 500 * 1024 * 1024   # 500 MB (supports video)
app.config['TEMPLATES_AUTO_RELOAD']          = True
app.config['SEND_FILE_MAX_AGE_DEFAULT']      = 0

PROFILE_UPLOAD_FOLDER = 'static/uploads/profiles'
POST_UPLOAD_FOLDER = 'static/uploads/posts'

app.config['PROFILE_UPLOAD_FOLDER'] = PROFILE_UPLOAD_FOLDER
app.config['POST_UPLOAD_FOLDER'] = POST_UPLOAD_FOLDER

os.makedirs(PROFILE_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(POST_UPLOAD_FOLDER, exist_ok=True)

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


# ── Payment Keys ───────────────────────────────────────────────────────────────
PAYSTACK_SECRET_KEY      = os.getenv("PAYSTACK_SECRET_KEY")
PAYSTACK_PUBLISHABLE_KEY = os.getenv("PAYSTACK_PUBLISHABLE_KEY")
PAYSTACK_INITIALIZE_URL  = os.getenv("PAYSTACK_INITIALIZE_URL")

stripe.api_key            = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_YOUR_STRIPE_SECRET')
STRIPE_WEBHOOK_SECRET     = os.environ.get('STRIPE_WEBHOOK_SECRET', 'whsec_YOUR_WEBHOOK_SECRET')
STRIPE_PUBLISHABLE_KEY    = os.environ.get('STRIPE_PUBLISHABLE_KEY', 'pk_test_YOUR_STRIPE_PK')

BINANCE_API_KEY  = os.environ.get('BINANCE_API_KEY', '')
BINANCE_SECRET_KEY = os.environ.get('BINANCE_SECRET_KEY', '')
BINANCE_BASE_URL = 'https://bpay.binanceapi.com'

ADMIN_EMAIL    = os.getenv('ADMIN_EMAIL')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

ALLOWED_EXTENSIONS = set(['jpg', 'jpeg', 'png', 'webp'])
ALLOWED_VIDEO_EXT  = set(['mp4', 'mov', 'webm', 'avi'])

db = SQLAlchemy(app)

# ══════════════════════════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════════════════════════

class User(db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    username      = db.Column(db.String(60), unique=True, nullable=True)  # used for creator-manager login alongside email
    password_hash = db.Column(db.String(256))
    is_admin      = db.Column(db.Boolean, default=False)
    is_blocked    = db.Column(db.Boolean, default=False)
    # Role: 'admin', 'ops_manager', 'junior_creator', 'creator', 'subscriber'
    # Legacy: 'creator_manager' retained for backward compat (existing manager accounts)
    role          = db.Column(db.String(30), nullable=False, default='subscriber')
    date_of_birth = db.Column(db.Date, nullable=True)
    is_age_verified = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    purchases     = db.relationship('Purchase', backref='user', lazy=True)
    # Profiles managed by this user (if creator_manager)
    managed_profiles = db.relationship('Profile', foreign_keys='Profile.manager_id', backref='manager', lazy=True)


class Photo(db.Model):
    __tablename__    = 'photos'
    id               = db.Column(db.Integer, primary_key=True)

    profile_id = db.Column(
        db.Integer,
        db.ForeignKey('profiles.id'),
        nullable=False
    )
    title            = db.Column(db.String(200), nullable=False)
    description      = db.Column(db.Text)
    category         = db.Column(db.String(100))
    tier             = db.Column(db.String(20), default='basic')
    preview_filename = db.Column(db.String(300))
    original_filename= db.Column(db.String(300))
    unlock_price     = db.Column(db.Float, default=2.0)
    unlock_duration  = db.Column(db.Integer, default=24)
    view_count       = db.Column(db.Integer, default=0)
    downloads        = db.Column(db.Integer, default=0)
    dynamic_pricing  = db.Column(db.Boolean, default=False)
    is_active        = db.Column(db.Boolean, default=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)


# ── NEW: Video Model ───────────────────────────────────────────────────────────
class Video(db.Model):
    __tablename__ = 'videos'

    id = db.Column(db.Integer, primary_key=True)

    profile_id = db.Column(
        db.Integer,
        db.ForeignKey('profiles.id'),
        nullable=False
    )

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100))
    tier = db.Column(db.String(20), default='basic')
    thumbnail_filename = db.Column(db.String(300))
    video_filename = db.Column(db.String(300))
    preview_filename = db.Column(db.String(300))
    duration_seconds = db.Column(db.Integer, default=0)
    # Which second of the video the hover/preview clip starts at — chosen by
    # the creator so they can pick the most attention-grabbing moment.
    preview_start_seconds = db.Column(db.Integer, default=0)
    # How long (seconds) the hover preview plays before pausing — creator-controlled.
    preview_duration_seconds = db.Column(db.Integer, default=4)
    # Blur strength applied to the hover preview (locked/unpurchased state).
    blur_strength = db.Column(db.Integer, default=8)
    unlock_price = db.Column(db.Float, default=5.0)
    unlock_duration = db.Column(db.Integer, default=24)
    view_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Order(db.Model):
    __tablename__   = 'orders'
    id              = db.Column(db.Integer, primary_key=True)
    order_id        = db.Column(db.String(100), unique=True, nullable=False)
    customer_name   = db.Column(db.String(255), nullable=False)
    customer_email  = db.Column(db.String(255), nullable=False)
    total_price     = db.Column(db.Float, default=0)
    total_items     = db.Column(db.Integer, default=0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    delivery_status = db.Column(db.String(20), default='pending')
    downloads       = db.Column(db.Integer, default=0)
    items           = db.relationship('OrderItem', backref='order', lazy=True)


class VideoLike(db.Model):
    __tablename__ = 'video_likes'
    id            = db.Column(db.Integer, primary_key=True)
    video_id      = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    session_token = db.Column(db.String(100), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('video_id', 'session_token', name='_video_like_uc'),)
 
 
class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id            = db.Column(db.Integer, primary_key=True)
    order_id      = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id    = db.Column(db.Integer, db.ForeignKey('photos.id'), nullable=False)
    product_name  = db.Column(db.String(255))
    quantity      = db.Column(db.Integer, default=1)
    unit_price    = db.Column(db.Float, nullable=False)
    total_price   = db.Column(db.Float, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)


class Purchase(db.Model):
    __tablename__   = 'purchases'
    id              = db.Column(db.Integer, primary_key=True)
    session_token   = db.Column(db.String(100), nullable=False)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    photo_id        = db.Column(db.Integer, db.ForeignKey('photos.id'), nullable=False)
    payment_method  = db.Column(db.String(50))
    amount          = db.Column(db.Float)
    expires_at      = db.Column(db.DateTime)
    is_permanent    = db.Column(db.Boolean, default=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)


class Payment(db.Model):
    __tablename__  = 'payments'
    id             = db.Column(db.Integer, primary_key=True)
    order_id       = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    session_token  = db.Column(db.String(100))
    gateway        = db.Column(db.String(50))
    transaction_id = db.Column(db.String(200))
    amount         = db.Column(db.Float)
    status         = db.Column(db.String(50), default='pending')
    photo_id       = db.Column(db.Integer, db.ForeignKey('photos.id'))
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

class SiteSettings(db.Model):
    __tablename__ = 'site_settings'
    id    = db.Column(db.Integer, primary_key=True)
    key   = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(500), default='')
 
 
# ── MODEL: Category ────────────────────────────────────────────────────────────
class Category(db.Model):
    __tablename__ = 'categories'
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(100), unique=True, nullable=False)
    slug         = db.Column(db.String(100), unique=True, nullable=False)
    description  = db.Column(db.String(300), default='')
    icon         = db.Column(db.String(10), default='📁')     # emoji icon
    cover_photo_id  = db.Column(db.Integer, nullable=True)    # optional cover photo
    content_type = db.Column(db.String(10), default='both')   # 'photo','video','both'
    sort_order   = db.Column(db.Integer, default=0)
    is_active    = db.Column(db.Boolean, default=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)


class Profile(db.Model):

    __tablename__  = 'profiles'

    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(100), nullable=False)
    username       = db.Column(db.String(60), unique=True, nullable=False)

    tagline        = db.Column(db.String(200), default='')
    bio            = db.Column(db.Text, default='')

    avatar_filename= db.Column(db.String(300), nullable=True)
    cover_filename = db.Column(db.String(300), nullable=True)

    category       = db.Column(db.String(100), default='')

    accent_color   = db.Column(db.String(20), default='#C9A84C')

    membership_tier = db.Column(db.String(20), default='standard')
    country_code    = db.Column(db.String(10), default='')

    is_active      = db.Column(db.Boolean, default=True)

    sort_order     = db.Column(db.Integer, default=0)

    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    is_verified    = db.Column(db.Boolean, default=False)
    is_featured    = db.Column(db.Boolean, default=False)
    is_trending    = db.Column(db.Boolean, default=False)
    is_online      = db.Column(db.Boolean, default=False)
    last_seen      = db.Column(db.DateTime, default=datetime.utcnow)

    # Creator Manager assignment: which User manages this profile
    manager_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    # Which OPS manager assigned the creator manager to this profile (for OPS revenue cut)
    assigned_by_ops_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # ── Account lifecycle tracking ──────────────────────────────────────────
    # 'junior_creator' = newly onboarded creator on probation — uploads themselves; 55% split until 4+4 sales
    # 'manager_trial'  = profile is being run by an assigned creator manager (55% split)
    # 'sole_creator'   = profile is independently owned by a promoted creator (70% split)
    account_type        = db.Column(db.String(40), default='junior_creator')
    manager_assigned_at = db.Column(db.DateTime, nullable=True)
    is_premium           = db.Column(db.Boolean, default=False)
    premium_started_at   = db.Column(db.DateTime, nullable=True)

    videos = db.relationship(
        'Video',
        backref='profile',
        lazy=True,
        cascade='all, delete-orphan'
    )
 
 
class ProfilePost(db.Model):
    """A post (photo or video) linked to a profile, with its own like/comment."""
    __tablename__  = 'profile_posts'
    id             = db.Column(db.Integer, primary_key=True)
    profile_id     = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    title          = db.Column(db.String(200), default='')
    caption        = db.Column(db.Text, default='')
    post_type      = db.Column(db.String(10), default='photo')   # 'photo' or 'video'
    # Link to existing Photo or Video record (optional – post can be standalone)
    photo_id       = db.Column(db.Integer, db.ForeignKey('photos.id'), nullable=True)
    video_id       = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=True)
    # Standalone media (not in main gallery)
    media_filename = db.Column(db.String(300), nullable=True)
    blur_strength  = db.Column(db.Integer, default=0)   # 0 = no blur (profile posts are free previews)
    view_count     = db.Column(db.Integer, default=0)
    is_active      = db.Column(db.Boolean, default=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    profile        = db.relationship('Profile', backref='posts')
 
 
class CreatorProfile(db.Model):
    __tablename__  = 'creator_profiles'
    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(100), nullable=False)
    username       = db.Column(db.String(60), unique=True, nullable=False)
    bio            = db.Column(db.Text, default='')
    tagline        = db.Column(db.String(200), default='')
    avatar_filename= db.Column(db.String(300), nullable=True)
    cover_filename = db.Column(db.String(300), nullable=True)
    category       = db.Column(db.String(100), default='')   # e.g. "Nature", "Fashion"
    accent_color   = db.Column(db.String(20), default='#C9A84C')  # hex for profile theme
    is_active      = db.Column(db.Boolean, default=True)
    sort_order     = db.Column(db.Integer, default=0)
    is_verified    = db.Column(db.Boolean, default=False)  # for a verified badge
    is_featured    = db.Column(db.Boolean, default=False)  # for homepage spotlight
    last_seen      = db.Column(db.DateTime, default=datetime.utcnow)
    is_online      = db.Column(db.Boolean, default=False)
    admin_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    profile_id     = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)


class ProfilePostLike(db.Model):
    __tablename__  = 'profile_post_likes'
    id             = db.Column(db.Integer, primary_key=True)
    post_id        = db.Column(db.Integer, db.ForeignKey('profile_posts.id'), nullable=False)
    session_token  = db.Column(db.String(100), nullable=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('post_id', 'session_token', name='_ppl_uc'),)
 
 
class ProfilePostComment(db.Model):
    __tablename__  = 'profile_post_comments'
    id             = db.Column(db.Integer, primary_key=True)
    post_id        = db.Column(db.Integer, db.ForeignKey('profile_posts.id'), nullable=False)
    session_token  = db.Column(db.String(100), nullable=False)
    author_name    = db.Column(db.String(80), default='Anonymous')
    body           = db.Column(db.Text, nullable=False)
    emoji_reaction = db.Column(db.String(10), default='')   # quick emoji reaction
    is_approved    = db.Column(db.Boolean, default=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

class PhotoLike(db.Model):
    __tablename__ = 'photo_likes'
    id            = db.Column(db.Integer, primary_key=True)
    photo_id      = db.Column(db.Integer, db.ForeignKey('photos.id'), nullable=False)
    # We use session_token so guests can also like (no login required)
    session_token = db.Column(db.String(100), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('photo_id', 'session_token', name='_photo_like_uc'),)


# ── MODEL Comment ───────────────────────────────────────────────────────────
class Comment(db.Model):
    __tablename__  = 'comments'
    id             = db.Column(db.Integer, primary_key=True)
    content_type   = db.Column(db.String(10), nullable=False, default='photo')
    content_id     = db.Column(db.Integer, nullable=False)
    session_token  = db.Column(db.String(100), nullable=False)
    author_name    = db.Column(db.String(80), default='Anonymous')
    body           = db.Column(db.Text, nullable=False)
    is_approved    = db.Column(db.Boolean, default=True)
    is_pinned      = db.Column(db.Boolean, default=False)
    is_highlighted = db.Column(db.Boolean, default=False)
    reply_to_id    = db.Column(db.Integer, nullable=True)
    reply_to_name  = db.Column(db.String(80), default='')
    tagged_user    = db.Column(db.String(80), default='')
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)


class CreatorApplication(db.Model):
    """Application to become a creator manager or verified creator."""
    __tablename__ = 'creator_applications'
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    applicant_name  = db.Column(db.String(100), nullable=False)
    applicant_email = db.Column(db.String(200), nullable=False)
    application_type= db.Column(db.String(30), default='junior_creator')  # 'junior_creator' or 'verified_creator'
    motivation      = db.Column(db.Text, default='')
    content_type    = db.Column(db.String(100), default='')  # what kind of content they plan to share
    social_links    = db.Column(db.Text, default='')  # comma separated
    id_document     = db.Column(db.String(300), nullable=True)  # filename for ID upload (verified creator)
    selfie_document = db.Column(db.String(300), nullable=True)  # filename for selfie (age/identity match)
    legal_name      = db.Column(db.String(200), default='')  # as on ID (verified creator)
    date_of_birth   = db.Column(db.Date, nullable=True)       # parsed/declared DOB for age check
    status          = db.Column(db.String(30), default='pending')  # pending/under_review/approved/rejected
    stage           = db.Column(db.Integer, default=1)  # 1-7 progress stage
    rejection_reason= db.Column(db.Text, default='')
    reviewed_by     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    # Linked profile once an account has been issued for this application
    issued_profile_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow)
    user            = db.relationship('User', foreign_keys=[user_id])
    reviewer        = db.relationship('User', foreign_keys=[reviewed_by])
    issued_profile  = db.relationship('Profile', foreign_keys=[issued_profile_id])


class SocialLink(db.Model):
    """Creator-managed social links — NOT hard-coded in templates.
    Platform is freeform so a creator can add Instagram, TikTok, Twitter,
    LinkedIn (for education-purpose creators), YouTube, website, etc."""
    __tablename__ = 'social_links'
    id          = db.Column(db.Integer, primary_key=True)
    profile_id  = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    platform    = db.Column(db.String(40), nullable=False)   # 'instagram','tiktok','twitter','linkedin','youtube','website',...
    label       = db.Column(db.String(60), default='')       # optional custom display label
    url         = db.Column(db.String(500), nullable=False)
    sort_order  = db.Column(db.Integer, default=0)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    profile     = db.relationship('Profile', backref=db.backref('social_links', cascade='all, delete-orphan'))


class CreatorBlurSettings(db.Model):
    """Per-profile default blur strength for locked content, adjustable by the
    creator themselves from their own dashboard (not admin-only)."""
    __tablename__ = 'creator_blur_settings'
    id              = db.Column(db.Integer, primary_key=True)
    profile_id      = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False, unique=True)
    photo_blur      = db.Column(db.Integer, default=12)
    video_blur      = db.Column(db.Integer, default=12)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow)
    profile         = db.relationship('Profile', backref=db.backref('blur_settings', uselist=False))


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_video(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXT

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

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


def manager_required(f):
    """Allows both admins and creator_managers through."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin') and not session.get('is_manager'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def ops_manager_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin') and session.get('user_role') not in ('ops_manager',):
            return redirect(url_for('ops_login'))
        return f(*args, **kwargs)
    return decorated


def creator_only_required(f):
    """Allows ONLY creator_managers/creators through — admins are blocked.

    Content creation (photo/video uploads) is exclusively a creator
    responsibility. Admins manage the platform and users, but no longer
    have direct upload access.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_manager'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


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


def upload_url(endpoint, profile_id=None, **kwargs):
    """Build creator-dashboard URLs."""
    return url_for(endpoint, **kwargs)


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

def dynamic_price(photo):
    if not photo.dynamic_pricing:
        return photo.unlock_price
    bump = (photo.view_count / 10) * 0.5
    return round(photo.unlock_price + bump, 2)

# Alias used in templates and routes for convenience

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'jpg','jpeg','png','webp'}
 
def allowed_video_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'mp4','mov','webm','avi'}
 
def get_current_price(photo):
    return dynamic_price(photo)


def create_binance_signature(timestamp, nonce, body):
    payload   = '{}\n{}\n{}\n'.format(timestamp, nonce, body)
    signature = hmac.new(BINANCE_SECRET_KEY.encode(), payload.encode(), hashlib.sha512).hexdigest().upper()
    return signature


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
 
 
def make_slug(name):
    """Turn a category name into a URL slug."""
    import re
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug


# Jinja2 globals
app.jinja_env.globals['enumerate'] = enumerate
app.jinja_env.globals['range'] = range
app.jinja_env.globals['len'] = len
app.jinja_env.globals['zip'] = zip


@app.context_processor
def inject_upload_context():
    return {
        'is_admin_override': is_admin_override(),
        'upload_url': upload_url,
    }

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — add these before create_admin()
# ═══════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC ROUTES — PHOTOS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    photos = Photo.query.filter_by(is_active=True).order_by(Photo.created_at.desc()).limit(9).all()
    for p in photos:
        p.unlocked      = has_access(p.id)
        p.current_price = get_current_price(p)

    videos = Video.query.filter_by(is_active=True).order_by(Video.created_at.desc()).limit(6).all()

    total_photos = Photo.query.filter_by(is_active=True).count()
    total_videos = Video.query.filter_by(is_active=True).count()
    total_buyers = Purchase.query.distinct(Purchase.session_token).count()
    total_creators = Profile.query.filter_by(is_active=True).count()

    return render_template('index.html',
                           photos=photos,
                           videos=videos,
                           total_photos=total_photos,
                           total_videos=total_videos,
                           total_buyers=total_buyers,
                           total_creators=total_creators)


@app.route('/gallery')
def gallery():
    selected_tier = request.args.get('tier')
    selected_cat  = request.args.get('category')
    search_query  = request.args.get('q', '').strip()
    sort_by       = request.args.get('sort', 'newest')

    q = Photo.query.filter_by(is_active=True)
    if selected_tier:
        q = q.filter_by(tier=selected_tier)
    if selected_cat:
        q = q.filter_by(category=selected_cat)
    if search_query:
        q = q.filter(db.or_(
            Photo.title.ilike('%{}%'.format(search_query)),
            Photo.description.ilike('%{}%'.format(search_query)),
            Photo.category.ilike('%{}%'.format(search_query))
        ))

    if sort_by == 'popular':
        q = q.order_by(Photo.view_count.desc())
    elif sort_by == 'price_asc':
        q = q.order_by(Photo.unlock_price.asc())
    elif sort_by == 'price_desc':
        q = q.order_by(Photo.unlock_price.desc())
    else:
        q = q.order_by(Photo.created_at.desc())

    photos     = q.all()
    categories = [r[0] for r in db.session.query(Photo.category).filter(Photo.is_active==True).distinct().all() if r[0]]

    for p in photos:
        p.unlocked      = has_access(p.id)
        p.current_price = get_current_price(p)

    return render_template('gallery.html',
                           photos=photos,
                           categories=categories,
                           selected_tier=selected_tier,
                           selected_cat=selected_cat,
                           search_query=search_query,
                           sort=sort_by)


@app.route('/premium')
def premium_page():
    """Dedicated premium page — shows both premium photos AND premium videos."""
    photos = Photo.query.filter_by(is_active=True, tier='premium')\
                        .order_by(Photo.created_at.desc()).all()
    videos = Video.query.filter_by(is_active=True, tier='premium')\
                        .order_by(Video.created_at.desc()).all()
    for p in photos:
        p.unlocked      = has_access(p.id)
        p.current_price = get_current_price(p)
    for v in videos:
        v.unlocked = has_video_access(v.id)
    total = len(photos) + len(videos)
    return render_template('premium_page.html',
                           photos=photos, videos=videos, total=total)


@app.route('/photo/<int:photo_id>')
def photo_detail(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    photo.view_count   += 1
    db.session.commit()
    photo.current_price = dynamic_price(photo)
    photo.unlocked      = has_access(photo.id)
    return render_template('photo_detail.html', photo=photo, stripe_pk=STRIPE_PUBLISHABLE_KEY)


# ── Serve images ───────────────────────────────────────────────────────────────
@app.route('/img/preview/<int:photo_id>')
def serve_preview(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    if not photo.preview_filename:
        abort(404)
    path = os.path.join(app.config['UPLOAD_FOLDER'], 'previews', photo.preview_filename)
    return send_file(path)


@app.route('/img/original/<int:photo_id>')
def serve_original(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    if not has_access(photo_id):
        abort(403)
    path = os.path.join(app.config['UPLOAD_FOLDER'], 'originals', photo.original_filename)
    return send_file(path)


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC ROUTES — VIDEOS  ★ NEW ★
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/videos')
def video_gallery():
    selected_tier    = request.args.get('tier')
    selected_cat     = request.args.get('category')
    selected_creator = request.args.get('creator')

    q = Video.query.filter_by(is_active=True)
    if selected_tier:
        q = q.filter_by(tier=selected_tier)
    if selected_cat:
        q = q.filter_by(category=selected_cat)

    videos = q.order_by(Video.created_at.desc()).all()

    # Mark unlocked for each video
    for v in videos:
        v.unlocked = has_video_access(v.id)

    # Categories from DB (admin-defined)
    categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order, Category.name).all()
    creators   = Profile.query.filter_by(is_active=True).order_by(Profile.name).all()

    return render_template('video_gallery.html',
                           videos=videos,
                           categories=categories,
                           creators=creators,
                           selected_tier=selected_tier,
                           selected_cat=selected_cat,
                           selected_creator=selected_creator)


@app.route('/video/<int:video_id>')
def video_detail(video_id):
    video    = Video.query.get_or_404(video_id)
    unlocked = has_video_access(video_id)
    video.view_count += 1
    db.session.commit()
    return render_template('video_detail.html', video=video, unlocked=unlocked)


@app.route('/video/thumb/<int:video_id>')
def serve_video_thumb(video_id):
    video = Video.query.get_or_404(video_id)
    if video.thumbnail_filename:
        path = os.path.join(app.config['UPLOAD_FOLDER'], 'video_thumbs', video.thumbnail_filename)
        if os.path.exists(path):
            return send_file(path, mimetype='image/jpeg')
    # No thumbnail: try to extract first frame from video using ffmpeg
    if video.video_filename:
        # Check multiple locations
        for vdir in [
            os.path.join(app.config['UPLOAD_FOLDER'], 'videos'),
            app.config['POST_UPLOAD_FOLDER'],
        ]:
            vpath = os.path.join(vdir, video.video_filename)
            if os.path.exists(vpath):
                try:
                    import subprocess, tempfile
                    tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
                    tmp.close()
                    result = subprocess.run(
                        ['ffmpeg', '-i', vpath, '-ss', '00:00:01', '-vframes', '1',
                         '-vf', 'scale=640:-1', '-y', tmp.name],
                        capture_output=True, timeout=15
                    )
                    if os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 0:
                        return send_file(tmp.name, mimetype='image/jpeg')
                except Exception:
                    pass
    # Fallback: generate a simple placeholder image using Pillow
    try:
        from PIL import Image, ImageDraw
        import io
        img  = Image.new('RGB', (640, 360), color=(20, 20, 30))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 639, 359], outline=(60, 60, 80), width=2)
        draw.text((290, 165), '▶', fill=(100, 100, 120))
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=70)
        buf.seek(0)
        from flask import Response
        return Response(buf.getvalue(), mimetype='image/jpeg')
    except Exception:
        abort(404)


@app.route('/video/preview/<int:video_id>')
def serve_video_preview(video_id):
    video = Video.query.get_or_404(video_id)
    if not video.preview_filename:
        abort(404)
    path = os.path.join(app.config['UPLOAD_FOLDER'], 'video_previews', video.preview_filename)
    return send_file(path, mimetype='video/mp4')

# ══════════════════════════════════════════════════════════════════════════════
# CHECKOUT
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/checkout/<int:photo_id>')
def checkout(photo_id):
    # Try photo first, then video
    content_type = 'photo'
    photo = db.session.get(Photo, photo_id)
    if not photo:
        # It's a video
        video = Video.query.get(photo_id)
        if not video:
            abort(404)
        # Build a pseudo-photo object for the template
        class _VideoProxy:
            pass
        photo = _VideoProxy()
        photo.id = video.id
        photo.title = video.title
        photo.description = video.description or ''
        photo.tier = video.tier
        photo.unlock_price = video.unlock_price
        photo.unlock_duration = video.unlock_duration
        photo.current_price = video.unlock_price
        photo.preview_filename = video.thumbnail_filename
        content_type = 'video'
    else:
        photo.current_price = dynamic_price(photo)

    tok = get_session_token()
    user_name = "Guest"
    user_email = "guest@example.com"
    if session.get('user_id'):
        user = User.query.get(session['user_id'])
        if user:
            user_email = user.email
            user_name = user.email.split('@')[0]

    return render_template(
        'checkout.html',
        photo=photo,
        session_token=tok,
        stripe_pk=STRIPE_PUBLISHABLE_KEY,
        user_name=user_name,
        user_email=user_email,
        content_type=content_type
    )



# ══════════════════════════════════════════════════════════════════════════════
# STRIPE
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/payments/stripe/create-session', methods=['POST'])
def stripe_create_session():
    try:
        data = request.get_json()

        # Current browser session token
        tok = get_session_token()

        # Request data
        photo_id = data.get("photo_id")
        user_name = data.get("customer_name")
        user_email = data.get("customer_email")

        # Validation
        if not photo_id:
            return jsonify({
                "error": "photo_id is required"
            }), 400

        if not user_name or not user_email:
            return jsonify({
                "error": "Customer details required"
            }), 400

        # Get photo
        photo = Photo.query.get_or_404(photo_id)
        price = dynamic_price(photo)

        # Create order
        order = Order(
            order_id=str(uuid.uuid4()),
            customer_name=user_name,
            customer_email=user_email,
            total_price=price,
            total_items=1
        )

        db.session.add(order)
        db.session.flush()

        # Create order item
        item = OrderItem(
            order_id=order.id,
            product_id=photo.id,
            product_name=photo.title,
            quantity=1,
            unit_price=price,
            total_price=price
        )

        db.session.add(item)
        db.session.commit()

        # Create Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],

            line_items=[{
                'price_data': {
                    'currency': 'usd',

                    'product_data': {
                        'name': photo.title,
                        'description': "{} tier access".format(photo.tier)
                    },

                    'unit_amount': int(price * 100),
                },

                'quantity': 1,
            }],

            mode='payment',

            success_url=url_for(
                'payment_success',
                _external=True
            ) + "?order_id={}&photo_id={}".format(
                order.order_id,
                photo_id
            ),

            cancel_url=url_for(
                'photo_detail',
                photo_id=photo_id,
                _external=True
            ),

            metadata={
                "order_id": order.order_id,
                "photo_id": str(photo_id),
                "customer_email": user_email,
                "session_token": tok
            }
        )

        return jsonify({
            'url': checkout_session.url
        })

    except Exception as e:
        print("🔥 ERROR:", str(e))

        return jsonify({
            'error': str(e)
        }), 500



@app.route('/payments/stripe/webhook', methods=['POST'])
def stripe_webhook():
    print("🔥 STRIPE WEBHOOK HIT")

    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            STRIPE_WEBHOOK_SECRET
        )

        print("✅ Event verified:", event['type'])

    except ValueError:
        print("❌ Invalid payload")
        return 'Invalid payload', 400

    except stripe.error.SignatureVerificationError:
        print("❌ Invalid signature")
        return 'Invalid signature', 400

    # Only handle successful checkout
    if event['type'] != 'checkout.session.completed':
        print("⚠️ Ignored event:", event['type'])
        return '', 200

    try:
        session_data = event['data']['object']

        metadata = session_data.get('metadata', {})

        # ── VaultX: DM-unlock completions ────────────────────────────────
        # These use a separate metadata schema (vaultx_type/vault_ref) from
        # the photo/video Order flow below, so handle them first and return.
        if metadata.get('vaultx_type') == 'dm_unlock':
            vault_ref = metadata.get('vault_ref')
            tx = VaultTransaction.query.filter_by(reference=vault_ref).first()
            if not tx:
                print('❌ VaultX dm_unlock: transaction reference not found:', vault_ref)
                return '', 200
            if tx.status == 'completed':
                print('⚠️ VaultX dm_unlock already processed:', vault_ref)
                return '', 200
            msg_row = DMMessage.query.get(tx.content_id)
            if not msg_row:
                print('❌ VaultX dm_unlock: message not found for tx', vault_ref)
                return '', 200
            tx.status = 'completed'
            db.session.flush()
            split_revenue(tx)
            msg_row.is_unlocked = True
            db.session.commit()
            print('✅ VaultX dm_unlock completed:', vault_ref)
            return '', 200

        order_uuid = metadata.get('order_id')
        photo_id = metadata.get('photo_id')
        customer_email = metadata.get('customer_email')
        session_token = metadata.get('session_token')

        payment_intent = session_data.get('payment_intent')

        print("📦 ORDER UUID:", order_uuid)

        if not order_uuid:
            print("❌ Missing order_id")
            return '', 200

        # =========================================
        # FIND ORDER
        # =========================================
        order = Order.query.filter_by(
            order_id=order_uuid
        ).first()

        if not order:
            print("❌ Order not found")
            return '', 200

        # Prevent duplicate processing
        existing_payment = Payment.query.filter_by(
            transaction_id=payment_intent
        ).first()

        if existing_payment and existing_payment.status == 'completed':
            print("⚠️ Payment already processed")
            return '', 200

        # =========================================
        # UPDATE ORDER STATUS
        # =========================================
        order.delivery_status = 'successful'

        # =========================================
        # GET ORDER ITEMS
        # =========================================
        order_items = OrderItem.query.filter_by(
            order_id=order.id
        ).all()

        if not order_items:
            print("❌ No order items found")
            return '', 200

        # =========================================
        # CREATE PURCHASE + PAYMENT RECORDS
        # =========================================
        email_images = []

        for item in order_items:

            photo = Photo.query.get(item.product_id)

            if not photo:
                continue

            # Save purchase
            purchase = Purchase(
                session_token=session_token,
                photo_id=photo.id,
                payment_method='stripe',
                amount=item.total_price,
                expires_at=datetime.utcnow() + timedelta(
                    hours=photo.unlock_duration
                ),
                is_permanent=False
            )

            db.session.add(purchase)

            # Save payment
            payment = Payment(
                session_token=session_token,
                gateway='stripe',
                transaction_id=payment_intent,
                amount=item.total_price,
                status='completed',
                photo_id=photo.id
            )

            db.session.add(payment)

            # Store image path for email
            image_path = os.path.join(
                app.config['UPLOAD_FOLDER'],
                photo.original_filename
            )

            if os.path.exists(image_path):
                email_images.append({
                    "title": photo.title,
                    "path": image_path,
                    "filename": photo.original_filename
                })

    # Commit DB changes
        db.session.commit()

        print("✅ Order updated successfully")

        # =========================================
        # SEND EMAIL WITH IMAGES
        # =========================================

        try:

            msg = Message(
                subject="Your PhotoVault Purchase",
                sender=app.config['MAIL_USERNAME'],
                recipients=[order.customer_email]
            )

            premium_link = "https://mitchellkaori.top/premiums?order_id={}".format(
                order.order_id
            )

            msg.html = """
            <h2>Thank You For Your Purchase</h2>

            <p>Hello {}</p>

            <p>Your payment was successful.</p>

            <p>Your purchased images are ready.</p>

            <p>
                <strong>Order ID:</strong> {}
            </p>

            <p>
                <a href="{}">
                    Click Here To Download Your Images
                </a>
            </p>
            """.format(
                order.customer_name,
                order.order_id,
                premium_link
            )

            for img in email_images:

                with app.open_resource(img["path"]) as fp:

                    msg.attach(
                        img["filename"],
                        "image/jpeg",
                        fp.read()
                    )

            mail.send(msg)

            print("📧 Email sent successfully")

        except Exception as email_error:

            print("❌ Email sending failed:", str(email_error))

        return '', 200
        
        
    except Exception as e:
        db.session.rollback()

        print("🔥 WEBHOOK ERROR:", str(e))

        return 'Webhook error', 500


@app.route('/checkout/paystack/paymentsuccessful')
def payment_successful_paystack():

    return render_template(
        'payment_successful.html'
    )
    

# ══════════════════════════════════════════════════════════════════════════════
# PAYSTACK
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/payments/paystack/initialize', methods=['POST'])
def paystack_initialize():
    try:
        data = request.get_json()

        # Current browser session token
        tok = get_session_token()

        # Request data
        photo_id = data.get("photo_id")
        user_name = data.get("customer_name")
        user_email = data.get("customer_email")

        # Validation
        if not photo_id:
            return jsonify({
                "error": "photo_id is required"
            }), 400

        if not user_name or not user_email:
            return jsonify({
                "error": "Customer details required"
            }), 400

        # Get photo
        photo = Photo.query.get_or_404(photo_id)

        # Dynamic pricing
        price = dynamic_price(photo)

        # =========================
        # CREATE ORDER
        # =========================
        order = Order(
            order_id=str(uuid.uuid4()),
            customer_name=user_name,
            customer_email=user_email,
            total_price=price,
            total_items=1
        )

        db.session.add(order)
        db.session.flush()

        # =========================
        # CREATE ORDER ITEM
        # =========================
        item = OrderItem(
            order_id=order.id,
            product_id=photo.id,
            product_name=photo.title,
            quantity=1,
            unit_price=price,
            total_price=price
        )

        db.session.add(item)
        db.session.commit()

        # =========================
        # PAYSTACK AMOUNT
        # Paystack expects smallest currency unit
        # KES -> cents
        # NGN -> kobo
        # USD -> cents
        # =========================
        paystack_amount = int(float(price) * 100)

        # =========================
        # CALLBACK URL
        # =========================
        callback_url = "https://mitchellkaori.top/checkout/paystack/paymentsuccessful"

        # =========================
        # PAYSTACK PAYLOAD
        # =========================
        payload = {
            "email": user_email,
            "amount": paystack_amount,
            "currency": "USD",

            # Unique transaction reference
            "reference": order.order_id,
            

            "callback_url": callback_url,

            "metadata": {
                "order_id": order.order_id,
                "photo_id": str(photo.id),
                "customer_email": user_email,
                "customer_name": user_name,
                "session_token": tok
            }
        }

        headers = {
            "Authorization": "Bearer {}".format(
                PAYSTACK_SECRET_KEY
            ),
            "Content-Type": "application/json"
        }

        # =========================
        # INITIALIZE PAYMENT
        # =========================
        response = requests.post(
            PAYSTACK_INITIALIZE_URL,
            json=payload,
            headers=headers
        )

        response_data = response.json()

        print("PAYSTACK RESPONSE:", response_data)

        # =========================
        # ERROR CHECKING
        # =========================
        if not response_data.get("status"):
            return jsonify({
                "error": response_data.get("message", "Paystack initialization failed")
            }), 400

        # =========================
        # AUTHORIZATION URL
        # =========================
        authorization_url = response_data["data"]["authorization_url"]

        return jsonify({
            "status": True,
            "message": "Payment initialized successfully",
            "payment": "paystack",
            "url": authorization_url,
            "reference": order.order_id
        })

    except Exception as e:
        print("🔥 PAYSTACK ERROR:", str(e))

        db.session.rollback()

        return jsonify({
            "error": str(e)
        }), 500

    
@app.route('/test-email')
def test_email():

    try:

        msg = Message(

            subject='TEST EMAIL',

            sender=(
                'PhotoVault',
                app.config['MAIL_USERNAME']
            ),

            recipients=['@gmail.com']
        )

        msg.body = 'Email test successful'

        mail.send(msg)

        return 'EMAIL SENT'

    except Exception as e:

        traceback.print_exc()

        return str(e)


@app.route('/payments/paystack/verify/<reference>', methods=['GET'])
def verify_paystack_payment(reference):

    try:

        # =========================
        # VERIFY WITH PAYSTACK
        # =========================
        verify_url = (
            "https://api.paystack.co/transaction/verify/{}"
        ).format(reference)

        headers = {
            "Authorization": "Bearer {}".format(
                PAYSTACK_SECRET_KEY
            ),
        }

        response = requests.get(
            verify_url,
            headers=headers
        )

        response_data = response.json()

        print("PAYSTACK VERIFY RESPONSE:", response_data)

        # =========================
        # VERIFY RESPONSE STATUS
        # =========================
        if not response_data.get("status"):

            return jsonify({
                "error": "Unable to verify payment"
            }), 400

        payment_data = response_data.get("data")

        # =========================
        # PAYMENT MUST BE SUCCESS
        # =========================
        if payment_data.get("status") != "success":

            return jsonify({
                "error": "Payment not successful"
            }), 400

        # =========================
        # GET METADATA
        # =========================
        metadata = payment_data.get("metadata", {})

        order_id = metadata.get("order_id")
        photo_id = metadata.get("photo_id")
        customer_email = metadata.get("customer_email")
        session_token = metadata.get("session_token")

        # =========================
        # VALIDATION
        # =========================
        if not order_id or not photo_id:

            return jsonify({
                "error": "Invalid payment metadata"
            }), 400

        # =========================
        # FIND ORDER
        # =========================
        order = Order.query.filter_by(
            order_id=order_id
        ).first()

        if not order:

            return jsonify({
                "error": "Order not found"
            }), 404

        # =========================
        # PREVENT DUPLICATES
        # =========================
        existing_purchase = Purchase.query.filter_by(
            session_token=session_token
        ).first()

        if existing_purchase:

            print("Purchase already exists")

            return redirect(
                url_for(
                    'photo_detail',
                    photo_id=photo_id
                )
            )

        # =========================
        # GET PHOTO
        # =========================
        photo = db.session.get(Photo, photo_id)

        if not photo:

            return jsonify({
                "error": "Photo not found"
            }), 404

        # =========================
        # ACCESS EXPIRY
        # =========================
        expires_at = datetime.utcnow() + timedelta(
            hours=photo.unlock_duration
        )

        # =========================
        # CREATE PURCHASE
        # =========================
        purchase = Purchase(

            session_token=session_token,

            user_id=None,

            photo_id=photo.id,

            payment_method="paystack",

            amount=payment_data.get("amount", 0) / 100,

            expires_at=expires_at,

            is_permanent=False,

            created_at=datetime.utcnow()
        )

        db.session.add(purchase)

        # =========================
        # UPDATE ORDER STATUS
        # =========================
        order.delivery_status = "completed"

        # =========================
        # INCREMENT DOWNLOADS
        # =========================
        order.downloads = (order.downloads or 0) + 1

        # =========================
        # OPTIONAL:
        # INCREMENT VIEW COUNT
        # =========================
        photo.view_count = (photo.view_count or 0) + 1

        # =========================
        # SAVE
        # =========================
        db.session.commit()



        # =========================
        # REDIRECT USER
        # =========================
        return redirect(
            url_for(
                'photo_detail',
                photo_id=photo.id,
                payment="success"
            )
        )

    except Exception as e:

        print("🔥 PAYSTACK VERIFY ERROR:", str(e))

        db.session.rollback()

        return jsonify({
            "error": str(e)
        }), 500



@app.route('/payments/paystack/webhook', methods=['POST'])
def paystack_webhook():
    print("🔥 PAYSTACK WEBHOOK HIT")

    try:
        # =====================================
        # RAW PAYLOAD & SIGNATURE VERIFICATION
        # =====================================
        payload = request.data
        if not payload:
            print("❌ EMPTY PAYLOAD")
            return '', 400

        paystack_signature = request.headers.get('x-paystack-signature')
        computed_signature = hmac.new(
            PAYSTACK_SECRET_KEY.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()

        if paystack_signature != computed_signature:
            print("❌ INVALID SIGNATURE")
            return 'Invalid signature', 400

        print("✅ SIGNATURE VERIFIED")

        # =====================================
        # PARSE INCOMING EVENT
        # =====================================
        event = request.get_json()
        if not event:
            print("❌ INVALID JSON")
            return '', 400

        event_type = event.get('event')
        print("✅ EVENT:", event_type)

        if event_type != 'charge.success':
            print("⚠️ EVENT IGNORED:", event_type)
            return '', 200

        # =====================================
        # LOCAL DATA EXTRACTION
        # =====================================
        payment_data = event.get('data', {}) or {}
        metadata = payment_data.get('metadata', {}) or {}

        order_uuid = metadata.get('order_id')
        session_token = metadata.get('session_token')
        transaction_reference = payment_data.get('reference')
        total_amount = payment_data.get('amount', 0) / 100.0

        print("📦 ORDER UUID FROM PAYSTACK METADATA: {}".format(order_uuid))

        if not order_uuid:
            print("❌ Missing order_id inside payload metadata")
            return '', 200

        # =========================================
        # FIND AND VERIFY ORDER (Following Stripe approach)
        # =========================================
        order = Order.query.filter_by(order_id=order_uuid).first()
        if not order:
            print("❌ Order not found in database for UUID: {}".format(order_uuid))
            return '', 200

        # Save recipient details out immediately before session modification
        recipient_email = order.customer_email
        recipient_name = order.customer_name or "Valued Customer"

        # Prevent duplicate fulfillment handling
        existing_payment = Payment.query.filter_by(transaction_id=transaction_reference).first()
        if existing_payment and existing_payment.status == 'completed':
            print("⚠️ Payment reference already successfully processed")
            return '', 200

        # =========================================
        # UPDATE ORDERS & RELATED ENTITIES
        # =========================================
        # Directly updates 'delivery_status' inside 'public.orders' table
        order.delivery_status = 'successful'
        if order.downloads is None:
            order.downloads = 0

        # Fetch matching items purchased under this order context
        order_items = OrderItem.query.filter_by(order_id=order.id).all()
        if not order_items:
            print("❌ No order items linked to order ID: {}".format(order.id))
            return '', 200

        # Loop items to create unlock accesses & logs (matches your Stripe pattern)
        for item in order_items:
            photo = Photo.query.get(item.product_id)
            if not photo:
                continue

            # Provision purchase download right allowances
            existing_purchase = Purchase.query.filter_by(
                session_token=session_token,
                photo_id=photo.id
            ).first()

            if not existing_purchase:
                purchase = Purchase(
                    session_token=session_token,
                    photo_id=photo.id,
                    payment_method='paystack',
                    amount=item.total_price,
                    expires_at=datetime.utcnow() + timedelta(hours=photo.unlock_duration),
                    is_permanent=False
                )
                db.session.add(purchase)

            # Record audit logs for payment tracking
            payment = Payment(
                order_id=order.id,
                session_token=session_token,
                gateway='paystack',
                transaction_id=transaction_reference,
                amount=item.total_price,
                status='completed',
                photo_id=photo.id
            )
            db.session.add(payment)

        # =========================================
        # COMMIT TRANSACTION TO DATABASE
        # =========================================
        db.session.commit()
        print("✅ ORDERS AND PURCHASES TABLES SUCCESSFULLY REFRESHED ON DISK")

        # =========================================
        # TEXT-ONLY OUTBOUND EMAIL ROUTING ZONE
        # =========================================
        if not recipient_email:
            print("❌ Cancelled mail routing: Destination email field is empty.")
            return '', 200

        try:
            msg = Message(
                subject="Your PhotoVault Purchase",
                sender=app.config['MAIL_DEFAULT_SENDER'],
                recipients=[recipient_email]
            )

            premium_link = "https://mitchellkaori.top/premiums?order_id={}".format(order_uuid)

            msg.html = """
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eeeeee;">
                <h2 style="color: #333333;">Thank You For Your Purchase</h2>
                <p>Hello {},</p>
                <p>Your payment via Paystack was processed successfully.</p>
                <p>Your purchased images are now unlocked and available for download.</p>
                
                <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Order ID:</strong> {}</p>
                    <p style="margin: 5px 0;"><strong>Transaction Ref:</strong> {}</p>
                </div>
                
                <p style="margin-top: 30px; margin-bottom: 30px;">
                    <a href="{}" style="padding: 12px 25px; background-color: #007bff; color: #ffffff; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">Click Here To Download Your Images</a>
                </p>
                <p style="color: #777777; font-size: 12px;">If the button above does not work, copy and paste this link into your browser:<br>{}</p>
            </div>
            """.format(
                recipient_name,
                order_uuid,
                transaction_reference,
                premium_link,
                premium_link
            )

            print("📧 Dispatching text email route to: {}...".format(recipient_email))
            mail.send(msg)
            print("📧 Email delivered successfully.")

        except Exception as email_send_error:
            print("❌ Outbound mail generation dropped: {}".format(str(email_send_error)))

        return '', 200

    except Exception as general_error:
        db.session.rollback()
        print("🔥 CRITICAL RUNTIME SYSTEM WEBHOOK ERROR: {}".format(str(general_error)))
        return 'Webhook handling failure', 500
    finally:
        # Prevent thread session leakage or locking across previews
        db.session.remove()

        
# ============================================
# PAYSTACK WEBHOOK ABOVE
# ============================================

@app.route('/checkout/paymentsuccessful')
def payment_successful():

    return """
    <!DOCTYPE html>
    <html>

    <head>

        <title>
            Payment Successful
        </title>

        <style>

            body{

                margin:0;
                padding:0;
                background:#f5f5f5;
                font-family:Arial;
            }

            .box{

                width:90%;
                max-width:600px;

                background:white;

                margin:80px auto;

                padding:40px;

                border-radius:10px;

                text-align:center;

                box-shadow:0 0 20px rgba(0,0,0,0.1);
            }

            h1{

                color:green;
            }

            p{

                color:#555;
                line-height:1.8;
            }

            a{

                display:inline-block;

                margin-top:20px;

                padding:12px 25px;

                background:black;

                color:white;

                text-decoration:none;

                border-radius:6px;
            }

        </style>

    </head>

    <body>

        <div class="box">

            <h1>
                Payment Successful
            </h1>

            <p>
                Your payment has been received successfully.
            </p>

            <p>
                Please check your email for your order details
                and premium access link.
            </p>

            <a href="/">
                Go Back Home
            </a>

        </div>

    </body>

    </html>
    """

# ══════════════════════════════════════════════════════════════════════════════
# BINANCE PAY
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/payments/binance/create', methods=['POST'])
def binance_create():
    data     = request.get_json()
    photo_id = data.get('photo_id')
    tok      = get_session_token()
    photo    = Photo.query.get_or_404(photo_id)
    price    = dynamic_price(photo)

    nonce     = uuid.uuid4().hex[:32]
    timestamp = str(int(time.time() * 1000))

    body_dict = {"env": {"terminalType": "WEB"}, "merchantTradeNo": nonce,
                 "orderAmount": str(price), "currency": "USDT",
                 "goods": {"goodsType": "01", "goodsCategory": "D000",
                            "goodsName": photo.title, "referenceGoodsId": str(photo_id)},
                 "returnUrl": url_for('payment_success', _external=True) + '?photo_id={}&session_token={}'.format(photo_id, tok),
                 "cancelUrl": url_for('photo_detail', photo_id=photo_id, _external=True)}

    body      = json.dumps(body_dict)
    signature = create_binance_signature(timestamp, nonce, body)

    headers = {"Content-Type": "application/json", "BinancePay-Timestamp": timestamp,
               "BinancePay-Nonce": nonce, "BinancePay-Certificate-SN": BINANCE_API_KEY,
               "BinancePay-Signature": signature}

    try:
        response = requests.post("{}/binancepay/openapi/v2/order".format(BINANCE_BASE_URL), headers=headers, data=body)
        resp = response.json()
        if resp.get("status") == "SUCCESS":
            checkout_url = resp["data"]["checkoutUrl"]
            payment = Payment(session_token=tok, gateway="binance", transaction_id=nonce,
                              amount=price, status="pending", photo_id=photo_id)
            db.session.add(payment)
            db.session.commit()
            return jsonify({"url": checkout_url})
        return jsonify({"error": resp.get("errorMessage", "Binance error")}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/payments/binance/webhook', methods=['POST'])
def binance_webhook():
    data = request.get_json()
    if data.get("bizStatus") != "PAY_SUCCESS":
        return jsonify({"returnCode": "SUCCESS"}), 200
    try:
        biz_content      = json.loads(data.get("bizContent", "{}"))
        merchant_trade_no = biz_content.get("merchantTradeNo")
        payment = Payment.query.filter_by(transaction_id=merchant_trade_no).first()
        if not payment or payment.status == "completed":
            return jsonify({"returnCode": "SUCCESS"}), 200
        photo = Photo.query.get(payment.photo_id)
        if not photo:
            return jsonify({"returnCode": "FAIL"}), 400
        purchase = Purchase(session_token=payment.session_token, photo_id=photo.id,
                            payment_method="binance", amount=payment.amount,
                            expires_at=datetime.utcnow() + timedelta(hours=photo.unlock_duration),
                            is_permanent=False)
        db.session.add(purchase)
        payment.status = "completed"
        db.session.commit()
        return jsonify({"returnCode": "SUCCESS"}), 200
    except Exception as e:
        print("Binance webhook error:", e)
        return jsonify({"returnCode": "FAIL"}), 400


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT SUCCESS & DOWNLOADS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/payment/success')
def payment_success():
    photo_id   = request.args.get('photo_id', type=int)
    order_uuid = request.args.get('order_id')
    reference  = request.args.get('reference')
    photo      = db.session.get(Photo, photo_id) if photo_id else None
    has_paid   = False
    download_link = None

    if photo and order_uuid:
        try:
            order = Order.query.filter_by(order_id=order_uuid).first()
            if reference and order:
                headers       = {"Authorization": "Bearer {}".format(PAYSTACK_SECRET_KEY)}
                response      = requests.get("https://api.paystack.co/transaction/verify/{}".format(reference), headers=headers)
                response_data = response.json()
                if response_data.get("status") and response_data["data"]["status"] == "success":
                    if order.delivery_status != "successful":
                        metadata      = response_data["data"].get("metadata", {})
                        session_token = metadata.get("session_token")
                        existing      = Purchase.query.filter_by(session_token=session_token).first()
                        if not existing:
                            purchase = Purchase(session_token=session_token, user_id=None, photo_id=photo.id,
                                                payment_method="paystack",
                                                amount=response_data["data"]["amount"] / 100,
                                                expires_at=datetime.utcnow() + timedelta(hours=photo.unlock_duration),
                                                is_permanent=False, created_at=datetime.utcnow())
                            db.session.add(purchase)
                        order.delivery_status = "successful"
                        photo.downloads       = (photo.downloads or 0) + 1
                        photo.view_count      = (photo.view_count or 0) + 1
                        db.session.commit()
            if order and order.delivery_status == 'successful':
                has_paid = True
                download_link = url_for('download_photo', order_uuid=order.order_id, photo_id=photo.id, _external=True)
        except Exception as e:
            db.session.rollback()
            print("Payment success error:", str(e))

    return render_template('payment_success.html', photo=photo, has_paid=has_paid, download_link=download_link)


@app.route('/premiums', methods=['GET', 'POST'])
def premiums():

    photos = []
    order = None
    error = None

    order_uuid = None

    # =========================================
    # GET METHOD
    # /premiums?order_id=XXXX
    # =========================================

    if request.method == 'GET':

        order_uuid = request.args.get('order_id')

    # =========================================
    # POST METHOD
    # FORM SUBMISSION
    # =========================================

    elif request.method == 'POST':

        order_uuid = request.form.get('order_id')

    # =========================================
    # PROCESS ORDER
    # =========================================

    if order_uuid:

        order = Order.query.filter_by(
            order_id=order_uuid
        ).first()

        if not order:

            error = "Invalid Order ID"

        elif order.delivery_status != 'successful':

            error = "Payment not completed yet"

        else:

            order_items = OrderItem.query.filter_by(
                order_id=order.id
            ).all()

            for item in order_items:

                photo = Photo.query.get(item.product_id)

                if photo:

                    photos.append(photo)

    return render_template(
        'premiums.html',
        photos=photos,
        order=order,
        error=error
    )


@app.route('/download/<order_uuid>/<int:photo_id>')
def download_photo(order_uuid, photo_id):
    order = Order.query.filter_by(order_id=order_uuid).first()
    if not order:
        abort(403)
    if order.delivery_status != 'successful':
        return "Payment not completed"
    if order.downloads is None:
        order.downloads = 0
    if int(order.downloads) >= 1:
        return "Already downloaded"
    order_item = OrderItem.query.filter_by(order_id=order.id, product_id=photo_id).first()
    if not order_item:
        abort(403)
    photo = db.session.get(Photo, photo_id)
    if not photo:
        abort(404)
    originals_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'originals')
    file_path     = os.path.join(originals_dir, photo.original_filename)
    if not os.path.exists(file_path):
        abort(404)
    order.downloads = int(order.downloads) + 1
    db.session.commit()
    return send_from_directory(originals_dir, photo.original_filename, as_attachment=True)


@app.route('/photo-original/<filename>')
def photo_original(filename):
    originals_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'originals')
    return send_from_directory(originals_dir, filename)


@app.route('/charge', methods=['POST'])
def charge():
    return jsonify({"status": "success"}), 200


# ══════════════════════════════════════════════════════════════════════════════
# USER AUTH
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user     = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            if user.is_blocked:
                return render_template('login.html', error='Account blocked.')
            session['user_id']    = user.id
            session['is_admin']   = user.is_admin
            session['is_manager'] = (user.role in ('creator_manager', 'ops_manager'))
            session['user_role']  = user.role
            # Smart redirect based on role
            if user.is_admin or user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'ops_manager':
                return redirect(url_for('ops_dashboard'))
            elif user.role == 'creator_manager':
                return redirect(url_for('manager_vx_dashboard'))
            elif user.role in ('junior_creator', 'creator'):
                # check if they have a CreatorAccount
                ca = CreatorAccount.query.filter_by(user_id=user.id).first()
                if ca:
                    session['creator_account_id'] = ca.id
                    session['creator_user_id'] = user.id
                    session['creator_profile_id'] = ca.profile_id
                    return redirect(url_for('creator_home'))
                return redirect(url_for('index'))
            else:
                return redirect(url_for('index'))
        return render_template('login.html', error='Invalid credentials.')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error='Email already registered.')
        hashed = generate_password_hash(password, method='pbkdf2:sha256')
        user   = User(email=email, password_hash=hashed, role='subscriber')
        db.session.add(user)
        db.session.commit()
        session['user_id']  = user.id
        session['is_admin'] = False
        session['is_manager'] = False
        session['user_role'] = 'subscriber'
        return redirect(url_for('index'))
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# ══════════════════════════════════════════════════════════════════════════════
# CREATOR APPLICATION ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/apply-to-be-creator', methods=['GET', 'POST'])
def apply_to_be_creator():
    """Public page to apply to become a creator manager or verified creator."""
    if request.method == 'POST':
        app_type    = request.form.get('application_type', 'junior_creator')
        name        = request.form.get('applicant_name', '').strip()
        email       = request.form.get('applicant_email', '').strip().lower()
        motivation  = request.form.get('motivation', '').strip()
        content_type= request.form.get('content_type', '').strip()
        social_links= request.form.get('social_links', '').strip()
        legal_name  = request.form.get('legal_name', '').strip()

        if not name or not email:
            flash('Name and email are required.', 'error')
            return redirect(url_for('apply_to_be_creator'))

        # Handle ID document upload for verified creator applicants
        id_filename = None
        if app_type == 'verified_creator':
            id_file = request.files.get('id_document')
            if id_file and id_file.filename and allowed_image(id_file.filename):
                ext = id_file.filename.rsplit('.', 1)[1].lower()
                id_filename = 'id_doc_{}_{}.{}'.format(email.replace('@','_'), int(time.time()), ext)
                save_path = os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], id_filename)
                id_file.save(save_path)

        user_id = session.get('user_id')
        app_record = CreatorApplication(
            user_id=user_id,
            applicant_name=name,
            applicant_email=email,
            application_type=app_type,
            motivation=motivation,
            content_type=content_type,
            social_links=social_links,
            legal_name=legal_name,
            id_document=id_filename,
            status='pending',
            stage=1
        )
        db.session.add(app_record)
        db.session.commit()
        # Notify admin
        try:
            send_application_notification_email(app_record)
        except Exception:
            pass
        flash('Application submitted! We will review and get back to you.', 'success')
        return redirect(url_for('application_status', app_id=app_record.id))

    preselect = request.args.get('type', 'junior_creator')
    return render_template('apply_creator.html', preselect=preselect)


@app.route('/application-status/<int:app_id>')
def application_status(app_id):
    """Show application progress to the applicant."""
    app_record = CreatorApplication.query.get_or_404(app_id)
    stage_labels = [
        'Application Submitted',
        'Documents Uploaded',
        'Under Review',
        'Manager Assignment',
        'Performance Evaluation',
        'Verification Approved',
        'Creator Account Issued',
    ]
    return render_template('application_status.html',
                           app_record=app_record,
                           stage_labels=stage_labels)


# ══════════════════════════════════════════════════════════════════════════════
# OPS — CREATOR APPLICATIONS MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/ops/applications')
@ops_manager_required
def ops_applications():
    """Ops Manager views and manages Junior Creator applications."""
    applications = CreatorApplication.query.order_by(CreatorApplication.created_at.desc()).all()
    pending_count = CreatorApplication.query.filter_by(status='pending').count()
    profiles = Profile.query.filter_by(is_active=True).all()
    # Pass available (unassigned) profiles for issuing demo accounts
    linked_profile_ids = [p.manager_id for p in Profile.query.filter(Profile.manager_id.isnot(None)).all()]
    available_profiles = Profile.query.filter(
        Profile.manager_id.is_(None),
        Profile.is_active == True
    ).all()
    return render_template('ops_applications.html', applications=applications,
                           pending_count=pending_count, profiles=profiles,
                           available_profiles=available_profiles)


@app.route('/ops/application/<int:app_id>/issue-account', methods=['POST'])
@ops_manager_required
def ops_issue_creator_manager(app_id):
    """OPS manager issues a creator manager (demo) account from an application."""
    app_record  = CreatorApplication.query.get_or_404(app_id)
    password    = request.form.get('password', '').strip()
    profile_id  = request.form.get('profile_id', type=int)

    if not password or len(password) < 6:
        flash('Password must be at least 6 characters.', 'error')
        return redirect(url_for('ops_applications'))

    email = app_record.applicant_email

    if User.query.filter_by(email=email).first():
        flash('An account already exists for this email.', 'error')
        return redirect(url_for('ops_applications'))

    # Create user with junior_creator role
    user = User(
        email=email,
        password_hash=generate_password_hash(password),
        role='junior_creator'
    )
    db.session.add(user)
    db.session.flush()

    # Determine which OPS manager is issuing
    ops_user_id = session.get('ops_user_id') or session.get('user_id')
    om = OperationsManager.query.filter_by(user_id=ops_user_id).first()

    if profile_id:
        profile = db.session.get(Profile, profile_id)
        if profile:
            profile.account_type = 'junior_creator'
            if om and hasattr(profile, 'assigned_by_ops_id'):
                profile.assigned_by_ops_id = om.user_id
            # Junior creator logs in at /creator/login via CreatorAccount
            existing_ca = CreatorAccount.query.filter_by(profile_id=profile.id).first()
            if not existing_ca:
                new_ca = CreatorAccount(
                    user_id=user.id,
                    profile_id=profile.id,
                    terms_accepted=False
                )
                db.session.add(new_ca)

    # Update application status
    app_record.status     = 'approved'
    app_record.updated_at = datetime.utcnow()
    app_record.reviewed_by = ops_user_id
    if profile_id:
        app_record.issued_profile_id = profile_id

    db.session.commit()

    # Email the applicant their credentials
    send_account_grant_email(email, app_record.applicant_name or email.split('@')[0], password, role='junior_creator')

    flash('Junior Creator account issued to {}. They log in at /creator/login and will be auto-promoted after {} photo + {} video sales.'.format(
        email, GRADUATION_MIN_PHOTOS, GRADUATION_MIN_VIDEOS), 'success')
    return redirect(url_for('ops_applications'))


@app.route('/ops/application/<int:app_id>/update', methods=['POST'])
@ops_manager_required
def ops_update_application(app_id):
    """Ops Manager updates application status and stage."""
    app_record = CreatorApplication.query.get_or_404(app_id)
    new_status = request.form.get('status', app_record.status)
    new_stage  = int(request.form.get('stage', app_record.stage))
    rejection_reason = request.form.get('rejection_reason', '').strip()

    app_record.status = new_status
    app_record.stage  = new_stage
    app_record.rejection_reason = rejection_reason
    app_record.updated_at = datetime.utcnow()
    app_record.reviewed_by = session.get('user_id')
    db.session.commit()
    flash('Application updated.', 'success')
    return redirect(url_for('ops_applications'))




@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user     = User.query.filter_by(email=email, is_admin=True).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id']  = user.id
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        return render_template('admin_login.html', error='Invalid admin credentials.')
    return render_template('admin_login.html')


@app.route('/admin')
@admin_required
def admin_dashboard():
    total_photos    = Photo.query.count()
    total_videos    = Video.query.count()
    total_users     = User.query.filter_by(is_admin=False).count()
    total_revenue   = db.session.query(db.func.sum(Payment.amount)).filter_by(status='completed').scalar() or 0
    total_purchases = Purchase.query.count()

    recent_payments = Payment.query.order_by(Payment.created_at.desc()).limit(10).all()
    photos          = Photo.query.order_by(Photo.created_at.desc()).all()
    videos          = Video.query.order_by(Video.created_at.desc()).all()
    users           = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).all()

    return render_template(
        'admin_dashboard.html',
        total_photos=total_photos,
        total_videos=total_videos,
        total_users=total_users,
        total_revenue=total_revenue,
        total_purchases=total_purchases,
        recent_payments=recent_payments,
        photos=photos,
        videos=videos,
        users=users,
        admin=session.get('admin')
    )


@app.route('/admin/photo/<int:photo_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    if request.method == 'POST':
        photo.title           = request.form.get('title', photo.title)
        photo.description     = request.form.get('description', photo.description)
        photo.category        = request.form.get('category', photo.category)
        photo.tier            = request.form.get('tier', photo.tier)
        photo.unlock_price    = float(request.form.get('price', photo.unlock_price))
        photo.unlock_duration = int(request.form.get('duration', photo.unlock_duration))
        photo.dynamic_pricing = request.form.get('dynamic_pricing') == 'on'
        photo.is_active       = request.form.get('is_active') == 'on'
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_edit_photo.html', photo=photo)


@app.route('/admin/photo/<int:photo_id>/delete', methods=['POST'])
@admin_required
def admin_delete_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    photo.is_active = False
    db.session.commit()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/user/<int:user_id>/block', methods=['POST'])
@admin_required
def admin_block_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_blocked = not user.is_blocked
    db.session.commit()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/revenue')
@admin_required
def admin_revenue():
    payments   = Payment.query.filter_by(status='completed').order_by(Payment.created_at.desc()).all()
    by_gateway = {}
    for p in payments:
        by_gateway[p.gateway] = by_gateway.get(p.gateway, 0) + p.amount
    return render_template('admin_revenue.html', payments=payments, by_gateway=by_gateway)


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN — VIDEOS  ★ NEW ★
# ══════════════════════════════════════════════════════════════════════════════


@app.route('/admin/video/<int:video_id>/delete', methods=['POST'])
@admin_required
def admin_delete_video(video_id):
    video = Video.query.get_or_404(video_id)
    for folder, attr in [('videos', 'video_filename'), ('video_thumbs', 'thumbnail_filename'),
                         ('video_previews', 'preview_filename')]:
        fn = getattr(video, attr)
        if fn:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], folder, fn))
            except OSError:
                pass
    db.session.delete(video)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))


# ── API ────────────────────────────────────────────────────────────────────────
@app.route('/api/access/<int:photo_id>')
def api_check_access(photo_id):
    return jsonify({'access': has_access(photo_id)})


# =====================================
# 1. THE ACTUAL CLEANUP FUNCTION
# =====================================
@app.teardown_request
def cleanup(exception=None):
    if exception:
        db.session.rollback()
    db.session.remove()  # Safely close the database worker connection


# (duplicate api_post_comment removed)


# ── Public: Category browsing page ────────────────────────────────────────────
@app.route('/categories')
def categories_page():
    cats = Category.query.filter_by(is_active=True).order_by(Category.sort_order, Category.name).all()
    # Attach counts
    for cat in cats:
        cat.photo_count = Photo.query.filter_by(category=cat.name, is_active=True).count()
        cat.video_count = Video.query.filter_by(category=cat.name, is_active=True).count()
    return render_template('categories_page.html', categories=cats)
 
 
@app.route('/category/<slug>')
def category_detail(slug):
    cat    = Category.query.filter_by(slug=slug, is_active=True).first_or_404()
    photos = Photo.query.filter_by(category=cat.name, is_active=True).order_by(Photo.created_at.desc()).all()
    videos = Video.query.filter_by(category=cat.name, is_active=True).order_by(Video.created_at.desc()).all()
    blur_photo = int(get_setting('blur_photo', 12))
    blur_video = int(get_setting('blur_video', 16))
 
    for p in photos:
        p.unlocked      = has_access(p.id)
        p.current_price = get_current_price(p)
 
    return render_template('category_detail.html',
                           cat=cat,
                           photos=photos,
                           videos=videos,
                           blur_photo=blur_photo,
                           blur_video=blur_video)
 
 
# ── Admin: Settings (blur control + site config) ───────────────────────────────
@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    if request.method == 'POST':
        # Blur levels
        blur_photo = request.form.get('blur_photo', '12')
        blur_video = request.form.get('blur_video', '16')
        blur_checkout = request.form.get('blur_checkout', '6')
        blur_detail   = request.form.get('blur_detail', '18')
        blur_tint_color = request.form.get('blur_tint_color', 'purple-gold')
 
        set_setting('blur_photo',     blur_photo)
        set_setting('blur_video',     blur_video)
        set_setting('blur_checkout',  blur_checkout)
        set_setting('blur_detail',    blur_detail)
        set_setting('blur_tint_color', blur_tint_color)
 
        # Site config
        set_setting('site_name',        request.form.get('site_name', 'PhotoVault'))
        set_setting('site_tagline',     request.form.get('site_tagline', ''))
        set_setting('allow_comments',   '1' if request.form.get('allow_comments') else '0')
        set_setting('allow_likes',      '1' if request.form.get('allow_likes') else '0')
        set_setting('show_view_counts', '1' if request.form.get('show_view_counts') else '0')
 
        return redirect(url_for('admin_settings'))
 
    settings = {
        'blur_photo':      get_setting('blur_photo', '12'),
        'blur_video':      get_setting('blur_video', '16'),
        'blur_checkout':   get_setting('blur_checkout', '6'),
        'blur_detail':     get_setting('blur_detail', '18'),
        'blur_tint_color': get_setting('blur_tint_color', 'purple-gold'),
        'site_name':       get_setting('site_name', 'PhotoVault'),
        'site_tagline':    get_setting('site_tagline', ''),
        'allow_comments':  get_setting('allow_comments', '1'),
        'allow_likes':     get_setting('allow_likes', '1'),
        'show_view_counts':get_setting('show_view_counts', '1'),
    }
    return render_template('admin_settings.html', settings=settings)
 
 
# ── Admin: Settings API (live preview) ────────────────────────────────────────
@app.route('/api/settings/blur')
def api_blur_settings():
    return jsonify({
        'blur_photo':    int(get_setting('blur_photo', 12)),
        'blur_video':    int(get_setting('blur_video', 16)),
        'blur_checkout': int(get_setting('blur_checkout', 6)),
        'blur_detail':   int(get_setting('blur_detail', 18)),
        'tint':          get_setting('blur_tint_color', 'purple-gold'),
    })
 
 
# ── Admin: Category list ───────────────────────────────────────────────────────
@app.route('/admin/categories')
@admin_required
def admin_categories():
    cats = Category.query.order_by(Category.sort_order, Category.name).all()
    for cat in cats:
        cat.photo_count = Photo.query.filter_by(category=cat.name).count()
        cat.video_count = Video.query.filter_by(category=cat.name).count()
    return render_template('admin_categories.html', categories=cats)
 
 
# ── Admin: Create category ─────────────────────────────────────────────────────
@app.route('/admin/categories/create', methods=['POST'])
@admin_required
def admin_create_category():
    name         = request.form.get('name', '').strip()
    description  = request.form.get('description', '').strip()
    icon         = request.form.get('icon', '📁').strip() or '📁'
    content_type = request.form.get('content_type', 'both')
    sort_order   = int(request.form.get('sort_order', 0))
 
    if not name:
        return redirect(url_for('admin_categories'))
 
    slug = make_slug(name)
    # Ensure unique slug
    base_slug = slug
    counter   = 1
    while Category.query.filter_by(slug=slug).first():
        slug = '{}-{}'.format(base_slug, counter)
        counter += 1
 
    cat = Category(name=name, slug=slug, description=description,
                   icon=icon, content_type=content_type, sort_order=sort_order)
    db.session.add(cat)
    db.session.commit()
    return redirect(url_for('admin_categories'))
 
 
# ── Admin: Edit category ───────────────────────────────────────────────────────
@app.route('/admin/categories/<int:cat_id>/edit', methods=['POST'])
@admin_required
def admin_edit_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    cat.name         = request.form.get('name', cat.name).strip()
    cat.description  = request.form.get('description', '').strip()
    cat.icon         = request.form.get('icon', cat.icon).strip() or cat.icon
    cat.content_type = request.form.get('content_type', cat.content_type)
    cat.sort_order   = int(request.form.get('sort_order', cat.sort_order))
    cat.is_active    = bool(request.form.get('is_active'))
    db.session.commit()
    return redirect(url_for('admin_categories'))
 
 
# ── Admin: Delete category ─────────────────────────────────────────────────────
@app.route('/admin/categories/<int:cat_id>/delete', methods=['POST'])
@admin_required
def admin_delete_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    db.session.delete(cat)
    db.session.commit()
    return redirect(url_for('admin_categories'))
 
 
# ── Admin: Bulk assign category to photos ─────────────────────────────────────
@app.route('/admin/categories/assign', methods=['POST'])
@admin_required
def admin_assign_category():
    photo_ids    = request.form.getlist('photo_ids')
    category_name = request.form.get('category_name', '').strip()
    for pid in photo_ids:
        photo = Photo.query.get(int(pid))
        if photo:
            photo.category = category_name
    db.session.commit()
    return redirect(url_for('admin_categories'))
 
@app.route('/profiles')
def public_profiles():
    profiles = Profile.query.filter_by(is_active=True).order_by(Profile.sort_order, Profile.name).all()
    for p in profiles:
        p.post_count = ProfilePost.query.filter_by(profile_id=p.id, is_active=True).count()
        # Total likes across all posts
        p.total_likes = db.session.query(db.func.count(ProfilePostLike.id))\
            .join(ProfilePost, ProfilePost.id == ProfilePostLike.post_id)\
            .filter(ProfilePost.profile_id == p.id).scalar() or 0
    return render_template('public_profiles.html', profiles=profiles,
                           COUNTRY_FLAGS=COUNTRY_FLAGS, COUNTRY_NAMES=COUNTRY_NAMES)
 
 
COUNTRY_FLAGS = {
    'KE':'🇰🇪','US':'🇺🇸','GB':'🇬🇧','NG':'🇳🇬','ZA':'🇿🇦','GH':'🇬🇭','TZ':'🇹🇿','UG':'🇺🇬',
    'RW':'🇷🇼','ET':'🇪🇹','EG':'🇪🇬','MA':'🇲🇦','TN':'🇹🇳','SN':'🇸🇳','CI':'🇨🇮','CM':'🇨🇲',
    'IN':'🇮🇳','CN':'🇨🇳','JP':'🇯🇵','KR':'🇰🇷','PH':'🇵🇭','ID':'🇮🇩','MY':'🇲🇾','TH':'🇹🇭',
    'FR':'🇫🇷','DE':'🇩🇪','IT':'🇮🇹','ES':'🇪🇸','PT':'🇵🇹','NL':'🇳🇱','SE':'🇸🇪','NO':'🇳🇴',
    'BR':'🇧🇷','MX':'🇲🇽','AR':'🇦🇷','CO':'🇨🇴','CA':'🇨🇦','AU':'🇦🇺','NZ':'🇳🇿','AE':'🇦🇪',
    'SA':'🇸🇦','TR':'🇹🇷','PK':'🇵🇰','BD':'🇧🇩','RU':'🇷🇺','UA':'🇺🇦','PL':'🇵🇱',
}
COUNTRY_NAMES = {
    'KE':'Kenya','US':'United States','GB':'United Kingdom','NG':'Nigeria','ZA':'South Africa',
    'GH':'Ghana','TZ':'Tanzania','UG':'Uganda','RW':'Rwanda','ET':'Ethiopia','EG':'Egypt',
    'MA':'Morocco','TN':'Tunisia','SN':'Senegal','CI':'Côte d\'Ivoire','CM':'Cameroon',
    'IN':'India','CN':'China','JP':'Japan','KR':'South Korea','PH':'Philippines','ID':'Indonesia',
    'MY':'Malaysia','TH':'Thailand','FR':'France','DE':'Germany','IT':'Italy','ES':'Spain',
    'PT':'Portugal','NL':'Netherlands','SE':'Sweden','NO':'Norway','BR':'Brazil','MX':'Mexico',
    'AR':'Argentina','CO':'Colombia','CA':'Canada','AU':'Australia','NZ':'New Zealand',
    'AE':'UAE','SA':'Saudi Arabia','TR':'Turkey','PK':'Pakistan','BD':'Bangladesh',
    'RU':'Russia','UA':'Ukraine','PL':'Poland',
}

@app.route('/creator/<username>')
def creator_page(username):
    """Alias for /profile/<username> so trending links work."""
    return profile_page(username)

@app.route('/profile/<username>')
def profile_page(username):
    profile = Profile.query.filter_by(username=username, is_active=True).first_or_404()
    # Determine if the current session is the creator's manager or admin
    is_owner = False
    if session.get('is_admin'):
        is_owner = True
    elif session.get('is_manager'):
        user_id = session.get('user_id')
        if profile.manager_id and profile.manager_id == user_id:
            is_owner = True

    # Admin is a platform moderator, not a creator/subscriber. is_owner unlocks
    # content for moderation review, but admin must never see or use creator
    # engagement actions (Follow / Like / Subscribe / Message). This flag is
    # used purely to hide those controls; it does not affect content access.
    is_admin_viewer = bool(session.get('is_admin'))

    posts   = ProfilePost.query.filter_by(profile_id=profile.id, is_active=True)\
                               .order_by(ProfilePost.created_at.desc()).all()
    # Also load photos and videos so they appear in Photos/Videos tabs AND on profile
    photos  = Photo.query.filter_by(profile_id=profile.id, is_active=True)\
                         .order_by(Photo.created_at.desc()).all()
    videos  = Video.query.filter_by(profile_id=profile.id, is_active=True)\
                         .order_by(Video.created_at.desc()).all()

    tok = get_session_token()
    for post in posts:
        post.view_count += 1
        post.like_count    = ProfilePostLike.query.filter_by(post_id=post.id).count()
        post.comment_count = ProfilePostComment.query.filter_by(post_id=post.id, is_approved=True).count()
        post.i_liked       = ProfilePostLike.query.filter_by(post_id=post.id, session_token=tok).first() is not None
        # Owner always sees content unlocked
        post.is_owner_view = is_owner
        # Attach linked photo/video if any
        if post.photo_id:
            post.linked_photo = Photo.query.get(post.photo_id)
        if post.video_id:
            post.linked_video = Video.query.get(post.video_id)

    # Mark access for photos and videos
    for p in photos:
        p.unlocked = is_owner or has_access(p.id)
        p.current_price = dynamic_price(p)
    for v in videos:
        v.unlocked = is_owner or has_video_access(v.id)

    db.session.commit()
    # Other profiles to suggest
    others = Profile.query.filter(Profile.id != profile.id, Profile.is_active==True).limit(4).all()
    # Follower / subscriber counts
    follower_count    = CreatorFollow.query.filter_by(profile_id=profile.id).count()
    subscriber_count  = CreatorSubscription.query.filter_by(profile_id=profile.id).count()
    like_count        = CreatorLike.query.filter_by(profile_id=profile.id).count()
    return render_template('profile_page.html', profile=profile, posts=posts, others=others,
                           photos=photos, videos=videos,
                           is_owner=is_owner,
                           is_admin_viewer=is_admin_viewer,
                           follower_count=follower_count,
                           subscriber_count=subscriber_count,
                           like_count=like_count,
                           COUNTRY_FLAGS=COUNTRY_FLAGS, COUNTRY_NAMES=COUNTRY_NAMES)
 
 
# ── API: like a profile post ───────────────────────────────────────────────────
@app.route('/api/post/<int:post_id>/like', methods=['POST'])
def toggle_post_like(post_id):
    tok      = get_session_token()
    existing = ProfilePostLike.query.filter_by(post_id=post_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(ProfilePostLike(post_id=post_id, session_token=tok))
        liked = True
    db.session.commit()
    count = ProfilePostLike.query.filter_by(post_id=post_id).count()
    return jsonify({'liked': liked, 'count': count})
 
 
# ── API: comment on a profile post ────────────────────────────────────────────
@app.route('/api/post/<int:post_id>/comment', methods=['POST'])
def post_profile_comment(post_id):
    data        = request.get_json()
    body        = (data.get('body') or '').strip()
    author_name = (data.get('author_name') or 'Anonymous').strip()[:80]
    emoji       = (data.get('emoji') or '').strip()[:5]
    tok         = get_session_token()
 
    if not body or len(body) < 1:
        return jsonify({'error': 'Comment cannot be empty'}), 400
    if len(body) > 500:
        return jsonify({'error': 'Too long (max 500 chars)'}), 400
 
    # Rate limit: 10 comments per session per post
    if ProfilePostComment.query.filter_by(post_id=post_id, session_token=tok).count() >= 10:
        return jsonify({'error': 'Comment limit reached'}), 429
 
    comment = ProfilePostComment(post_id=post_id, session_token=tok,
                                  author_name=author_name, body=body, emoji_reaction=emoji)
    db.session.add(comment)
    db.session.commit()
    # Log activity + update engagement score
    post = ProfilePost.query.get(post_id)
    if post:
        try:
            log_activity('comment', author_name, profile_id=post.profile_id,
                         post_id=post_id, meta=post.title or 'a post')
            recalculate_engagement(post_id)
        except Exception:
            pass
    return jsonify({
        'id':           comment.id,
        'author_name':  comment.author_name,
        'body':         comment.body,
        'emoji':        comment.emoji_reaction,
        'created_at':   comment.created_at.strftime('%b %d, %Y'),
        'is_mine':      True
    })
 
 
# ── API: get comments for a post ──────────────────────────────────────────────
@app.route('/api/post/<int:post_id>/comments')
def get_post_comments(post_id):
    tok      = get_session_token()
    comments = ProfilePostComment.query.filter_by(post_id=post_id, is_approved=True)\
                                       .order_by(ProfilePostComment.created_at.asc()).limit(100).all()
    return jsonify([{
        'id':          c.id,
        'author_name': c.author_name,
        'body':        c.body,
        'emoji':       c.emoji_reaction,
        'created_at':  c.created_at.strftime('%b %d'),
        'is_mine':     c.session_token == tok
    } for c in comments])
 
 
# ══════════════════════════════════════════════════════════════════════════════
# ADMIN PROFILE ROUTES
# ══════════════════════════════════════════════════════════════════════════════
 
@app.route('/media/profile/<filename>')
def serve_profile_media(filename):
    # Check uploads/profiles first, then static/uploads/profiles
    path1 = os.path.join(app.config['UPLOAD_FOLDER'], 'profiles', filename)
    path2 = os.path.join(PROFILE_UPLOAD_FOLDER, filename)
    if os.path.exists(path1):
        return send_file(path1)
    if os.path.exists(path2):
        return send_file(path2)
    abort(404)

@app.route('/media/post/<filename>')
def serve_post_media(filename):
    # Check uploads/profile_posts first, then static/uploads/posts
    path1 = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_posts', filename)
    path2 = os.path.join(POST_UPLOAD_FOLDER, filename)
    if os.path.exists(path1):
        return send_file(path1)
    if os.path.exists(path2):
        return send_file(path2)
    abort(404)

# ── Like / Unlike a Photo ──────────────────────────────────────────────────────
@app.route('/api/photo/<int:photo_id>/like', methods=['POST'])
def toggle_photo_like(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    tok   = get_session_token()
    existing = PhotoLike.query.filter_by(photo_id=photo_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(PhotoLike(photo_id=photo_id, session_token=tok))
        liked = True
    db.session.commit()
    count = PhotoLike.query.filter_by(photo_id=photo_id).count()
    return jsonify({'liked': liked, 'count': count})


# ── Like / Unlike a Video ──────────────────────────────────────────────────────
@app.route('/api/video/<int:video_id>/like', methods=['POST'])
def toggle_video_like(video_id):
    video = Video.query.get_or_404(video_id)
    tok   = get_session_token()
    existing = VideoLike.query.filter_by(video_id=video_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(VideoLike(video_id=video_id, session_token=tok))
        liked = True
    db.session.commit()
    count = VideoLike.query.filter_by(video_id=video_id).count()
    return jsonify({'liked': liked, 'count': count})


# ── Post a Comment ─────────────────────────────────────────────────────────────
@app.route('/api/comment', methods=['POST'])
def post_comment():
    data         = request.get_json()
    content_type = data.get('content_type', 'photo')
    content_id   = data.get('content_id')
    body         = (data.get('body') or '').strip()
    author_name  = (data.get('author_name') or 'Anonymous').strip()[:80]
    tok          = get_session_token()

    if not body or len(body) < 2:
        return jsonify({'error': 'Comment too short'}), 400
    if len(body) > 1000:
        return jsonify({'error': 'Comment too long (max 1000 chars)'}), 400
    if not content_id:
        return jsonify({'error': 'Missing content_id'}), 400

    # Basic spam guard: max 5 comments per session per content item
    existing_count = Comment.query.filter_by(
        session_token=tok, content_type=content_type, content_id=content_id
    ).count()
    if existing_count >= 5:
        return jsonify({'error': 'Comment limit reached for this item'}), 429

    comment = Comment(content_type=content_type, content_id=content_id,
                      session_token=tok, author_name=author_name, body=body)
    db.session.add(comment)
    db.session.commit()

    return jsonify({
        'id':          comment.id,
        'author_name': comment.author_name,
        'body':        comment.body,
        'created_at':  comment.created_at.strftime('%b %d, %Y')
    })


# ── Get Comments ───────────────────────────────────────────────────────────────
# (duplicate get_comments removed)


# ── Delete own comment ─────────────────────────────────────────────────────────
@app.route('/api/comment/<int:comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    tok     = get_session_token()
    if comment.session_token != tok and not session.get('is_admin'):
        return jsonify({'error': 'Not allowed'}), 403
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'deleted': True})


# ── Engagement stats for a photo (for cards) ──────────────────────────────────
@app.route('/api/stats/photo/<int:photo_id>')
def photo_stats(photo_id):
    tok      = get_session_token()
    likes    = PhotoLike.query.filter_by(photo_id=photo_id).count()
    comments = Comment.query.filter_by(content_type='photo', content_id=photo_id, is_approved=True).count()
    i_liked  = PhotoLike.query.filter_by(photo_id=photo_id, session_token=tok).first() is not None
    photo    = Photo.query.get_or_404(photo_id)
    return jsonify({'likes': likes, 'comments': comments, 'views': photo.view_count, 'liked': i_liked})


# ── Engagement stats for a video ──────────────────────────────────────────────
@app.route('/api/stats/video/<int:video_id>')
def video_stats(video_id):
    tok      = get_session_token()
    likes    = VideoLike.query.filter_by(video_id=video_id).count()
    comments = Comment.query.filter_by(content_type='video', content_id=video_id, is_approved=True).count()
    i_liked  = VideoLike.query.filter_by(video_id=video_id, session_token=tok).first() is not None
    video    = Video.query.get_or_404(video_id)
    return jsonify({'likes': likes, 'comments': comments, 'views': video.view_count, 'liked': i_liked})


# ── Trending: most viewed + liked in last 7 days ──────────────────────────────
@app.route('/api/trending')
def trending():
    week_ago = datetime.utcnow() - timedelta(days=7)
    photos   = Photo.query.filter_by(is_active=True).order_by(Photo.view_count.desc()).limit(6).all()
    result   = []
    for p in photos:
        likes = PhotoLike.query.filter_by(photo_id=p.id).count()
        result.append({'id': p.id, 'title': p.title, 'views': p.view_count,
                       'likes': likes, 'tier': p.tier, 'type': 'photo'})
    return jsonify(result)


# ── Admin: moderate comments ───────────────────────────────────────────────────
@app.route('/admin/comments')
@admin_required
def admin_comments():
    comments = Comment.query.order_by(Comment.created_at.desc()).all()
    return render_template('admin_comments.html', comments=comments)


@app.route('/admin/comment/<int:comment_id>/approve', methods=['POST'])
@admin_required
def admin_approve_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    comment.is_approved = not comment.is_approved
    db.session.commit()
    return redirect(url_for('admin_comments'))


@app.route('/admin/comment/<int:comment_id>/delete', methods=['POST'])
@admin_required
def admin_delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for('admin_comments'))


@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    # ── Revenue by gateway ──────────────────────────────────────────────────
    gateways   = db.session.query(Payment.gateway, db.func.sum(Payment.amount))\
                           .filter_by(status='completed').group_by(Payment.gateway).all()
    by_gateway = {g: float(a or 0) for g, a in gateways}
 
    # ── Revenue: photos vs videos (videos stored with different photo_id range)
    total_revenue  = sum(by_gateway.values())
    # ── Top selling photos ──────────────────────────────────────────────────
    top_photos = db.session.query(Photo, db.func.count(Purchase.id).label('sales'))\
        .join(Purchase, Purchase.photo_id == Photo.id)\
        .group_by(Photo.id).order_by(db.text('sales DESC')).limit(8).all()
    # ── Sales by tier ────────────────────────────────────────────────────────
    tier_sales = db.session.query(Photo.tier, db.func.count(Purchase.id))\
        .join(Purchase, Purchase.photo_id == Photo.id)\
        .group_by(Photo.tier).all()
    by_tier = {t: int(c) for t, c in tier_sales}
 
    # ── Revenue by category ──────────────────────────────────────────────────
    cat_rev = db.session.query(Photo.category, db.func.sum(Payment.amount))\
        .join(Payment, Payment.photo_id == Photo.id)\
        .filter(Payment.status=='completed')\
        .group_by(Photo.category).order_by(db.text('sum(payments.amount) DESC')).limit(8).all()
    by_category = [(c or 'Uncategorized', float(a or 0)) for c, a in cat_rev]
 
    # ── Profile performance ──────────────────────────────────────────────────
    profiles = Profile.query.filter_by(is_active=True).all()
    profile_stats = []
    for prf in profiles:
        posts = ProfilePost.query.filter_by(profile_id=prf.id, is_active=True).all()
        total_views = sum(p.view_count for p in posts)
        total_likes = ProfilePostLike.query.join(ProfilePost)\
            .filter(ProfilePost.profile_id == prf.id).count()
        post_count  = len(posts)
        profile_stats.append({
            'id': prf.id, 'name': prf.name, 'username': prf.username,
            'avatar': prf.avatar_filename, 'accent': prf.accent_color,
            'views': total_views, 'likes': total_likes, 'posts': post_count
        })
    profile_stats.sort(key=lambda x: x['views'], reverse=True)
 
    # ── Monthly revenue (last 6 months) ─────────────────────────────────────
    monthly = []
    for i in range(5, -1, -1):
        d     = datetime.utcnow() - timedelta(days=30*i)
        label = d.strftime('%b %Y')
        rev   = db.session.query(db.func.sum(Payment.amount))\
            .filter(Payment.status=='completed',
                    db.extract('month', Payment.created_at)==d.month,
                    db.extract('year',  Payment.created_at)==d.year).scalar() or 0
        monthly.append({'label': label, 'revenue': float(rev)})
 
    # ── Views over time (last 7 days) ────────────────────────────────────────
    daily_views = []
    for i in range(6, -1, -1):
        d = datetime.now(UTC) - timedelta(days=i)
        daily_views.append({'label': d.strftime('%a'), 'day': d.strftime('%Y-%m-%d')})
 
    return render_template('admin_analytics.html',
        by_gateway=by_gateway, total_revenue=total_revenue,
        top_photos=top_photos, by_tier=by_tier,
        by_category=by_category, profile_stats=profile_stats,
        monthly=monthly, daily_views=daily_views)


@app.route('/api/comments/<content_type>/<int:content_id>')
def api_get_comments(content_type, content_id):
    """Return comments for a photo or video, pinned first."""
    comments = Comment.query.filter_by(
        content_type=content_type, content_id=content_id,
        is_approved=True, reply_to_id=None
    ).order_by(Comment.is_pinned.desc(), Comment.created_at.asc()).all()

    out = []
    for c in comments:
        out.append({
            'id': c.id,
            'author_name': c.author_name,
            'body': c.body,
            'tagged_user': c.tagged_user or '',
            'is_pinned': c.is_pinned,
            'is_highlighted': c.is_highlighted,
            'created_at': c.created_at.strftime('%H:%M · %b %d'),
            'replies': [{
                'id': r.id,
                'author_name': r.author_name,
                'body': r.body,
                'tagged_user': r.tagged_user or '',
                'reply_to_name': r.reply_to_name or '',
                'created_at': r.created_at.strftime('%H:%M · %b %d'),
            } for r in Comment.query.filter_by(
                reply_to_id=c.id, is_approved=True
            ).order_by(Comment.created_at.asc()).all()]
        })
    return jsonify(out)


@app.route('/api/comments/post', methods=['POST'])
def api_post_comment_v2():
    """Post a comment with optional reply_to and tag."""
    data         = request.get_json() or {}
    body         = (data.get('body') or '').strip()
    content_type = data.get('content_type', 'video')
    content_id   = data.get('content_id')
    author_name  = (data.get('author_name') or 'Anonymous').strip()[:80]
    reply_to_id  = data.get('reply_to_id')
    reply_to_name= (data.get('reply_to_name') or '').strip()[:80]
    tagged_user  = (data.get('tagged_user') or '').strip()[:80]
    tok          = get_session_token()

    if not body or len(body) < 1: return jsonify({'error': 'Empty comment'}), 400
    if len(body) > 1000: return jsonify({'error': 'Too long'}), 400
    if not content_id: return jsonify({'error': 'Missing content_id'}), 400

    existing = Comment.query.filter_by(session_token=tok, content_type=content_type,
                                        content_id=content_id).count()
    if existing >= 10:
        return jsonify({'error': 'Comment limit reached'}), 429

    c = Comment(content_type=content_type, content_id=int(content_id),
                session_token=tok, author_name=author_name, body=body,
                reply_to_id=int(reply_to_id) if reply_to_id else None,
                reply_to_name=reply_to_name,
                tagged_user=tagged_user)
    db.session.add(c)
    db.session.commit()
    return jsonify({
        'id': c.id, 'author_name': c.author_name, 'body': c.body,
        'tagged_user': c.tagged_user, 'reply_to_name': c.reply_to_name,
        'is_pinned': False, 'is_highlighted': False,
        'created_at': c.created_at.strftime('%H:%M · %b %d'),
        'replies': []
    })


@app.route('/api/comments/<int:comment_id>/pin', methods=['POST'])
def api_pin_comment(comment_id):
    c = Comment.query.get_or_404(comment_id)
    # Allow admin OR creator who owns the content
    if not session.get('is_admin'):
        # Check if logged-in creator owns the content
        creator_authed = False
        if session.get('creator_account_id'):
            ca = CreatorAccount.query.get(session['creator_account_id'])
            if ca:
                if c.content_type == 'photo':
                    item = Photo.query.get(c.content_id)
                    creator_authed = item and item.profile_id == ca.profile_id
                elif c.content_type == 'video':
                    item = Video.query.get(c.content_id)
                    creator_authed = item and item.profile_id == ca.profile_id
        # Also allow manager
        if not creator_authed and session.get('is_manager'):
            user_id = session.get('user_id')
            profile = Profile.query.filter_by(manager_id=user_id).first()
            if profile:
                if c.content_type == 'photo':
                    item = Photo.query.get(c.content_id)
                    creator_authed = item and item.profile_id == profile.id
                elif c.content_type == 'video':
                    item = Video.query.get(c.content_id)
                    creator_authed = item and item.profile_id == profile.id
        if not creator_authed:
            return jsonify({'error': 'Unauthorized'}), 403
    c.is_pinned = not c.is_pinned
    db.session.commit()
    return jsonify({'pinned': c.is_pinned})


@app.route('/api/comments/<int:comment_id>/highlight', methods=['POST'])
def api_highlight_comment(comment_id):
    c = Comment.query.get_or_404(comment_id)
    if not session.get('is_admin'):
        creator_authed = False
        if session.get('creator_account_id'):
            ca = CreatorAccount.query.get(session['creator_account_id'])
            if ca:
                if c.content_type == 'photo':
                    item = Photo.query.get(c.content_id)
                    creator_authed = item and item.profile_id == ca.profile_id
                elif c.content_type == 'video':
                    item = Video.query.get(c.content_id)
                    creator_authed = item and item.profile_id == ca.profile_id
        if not creator_authed and session.get('is_manager'):
            user_id = session.get('user_id')
            profile = Profile.query.filter_by(manager_id=user_id).first()
            if profile:
                if c.content_type == 'photo':
                    item = Photo.query.get(c.content_id)
                    creator_authed = item and item.profile_id == profile.id
                elif c.content_type == 'video':
                    item = Video.query.get(c.content_id)
                    creator_authed = item and item.profile_id == profile.id
        if not creator_authed:
            return jsonify({'error': 'Unauthorized'}), 403
    c.is_highlighted = not c.is_highlighted
    db.session.commit()
    return jsonify({'highlighted': c.is_highlighted})


@app.route('/api/comments/<int:comment_id>/delete', methods=['POST'])
def api_delete_comment(comment_id):
    c = Comment.query.get_or_404(comment_id)
    if not session.get('is_admin'):
        creator_authed = False
        if session.get('creator_account_id'):
            ca = CreatorAccount.query.get(session['creator_account_id'])
            if ca:
                if c.content_type == 'photo':
                    item = Photo.query.get(c.content_id)
                    creator_authed = item and item.profile_id == ca.profile_id
                elif c.content_type == 'video':
                    item = Video.query.get(c.content_id)
                    creator_authed = item and item.profile_id == ca.profile_id
        if not creator_authed and session.get('is_manager'):
            user_id = session.get('user_id')
            profile = Profile.query.filter_by(manager_id=user_id).first()
            if profile:
                if c.content_type == 'photo':
                    item = Photo.query.get(c.content_id)
                    creator_authed = item and item.profile_id == profile.id
                elif c.content_type == 'video':
                    item = Video.query.get(c.content_id)
                    creator_authed = item and item.profile_id == profile.id
        if not creator_authed:
            return jsonify({'error': 'Unauthorized'}), 403
    content_type = c.content_type
    content_id   = c.content_id
    Comment.query.filter_by(reply_to_id=comment_id).delete()
    db.session.delete(c)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/video/<int:video_id>/view', methods=['POST'])
def api_video_view(video_id):
    """Count a view only once per session."""
    tok     = get_session_token()
    key     = 'viewed_video_{}'.format(video_id)
    already = session.get(key, False)
    if not already:
        video = Video.query.get(video_id)
        if video:
            video.view_count = (video.view_count or 0) + 1
            db.session.commit()
        session[key] = True
    video = Video.query.get(video_id)
    return jsonify({'view_count': video.view_count if video else 0, 'already': already})


@app.route('/api/photo/<int:photo_id>/view', methods=['POST'])
def api_photo_view(photo_id):
    """Count a photo view only once per session."""
    tok     = get_session_token()
    key     = 'viewed_photo_{}'.format(photo_id)
    already = session.get(key, False)
    if not already:
        photo = db.session.get(Photo, photo_id)
        if photo:
            photo.view_count = (photo.view_count or 0) + 1
            db.session.commit()
        session[key] = True
    photo = db.session.get(Photo, photo_id)
    return jsonify({'view_count': photo.view_count if photo else 0, 'already': already})

# ══════════════════════════════════════════════════════════════════════════════
# REPOST ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/repost', methods=['POST'])
def api_repost():
    """Toggle a repost for a photo or video."""
    data         = request.get_json() or {}
    content_type = data.get('content_type', 'photo')  # 'photo' or 'video'
    content_id   = int(data.get('content_id', 0))
    name         = (data.get('name') or 'Anonymous').strip()[:100]
    caption      = (data.get('caption') or '').strip()[:300]
    tok          = get_session_token()

    if not content_id:
        return jsonify({'error': 'Missing content_id'}), 400

    # Validate content exists
    if content_type == 'photo':
        item = Photo.query.get(content_id)
    else:
        item = Video.query.get(content_id)
    if not item:
        return jsonify({'error': 'Content not found'}), 404

    # Toggle repost
    existing = Repost.query.filter_by(
        session_token=tok, content_type=content_type, content_id=content_id
    ).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        reposted = False
    else:
        rp = Repost(session_token=tok, reposter_name=name,
                    content_type=content_type, content_id=content_id,
                    caption=caption)
        db.session.add(rp)
        db.session.commit()
        reposted = True
        # Log activity
        try:
            log_activity('repost', name, meta=item.title or 'content')
        except Exception:
            pass

    count = Repost.query.filter_by(content_type=content_type, content_id=content_id).count()
    return jsonify({'reposted': reposted, 'count': count})


@app.route('/api/repost/status')
def api_repost_status():
    """Check if current session has reposted a specific item."""
    content_type = request.args.get('type', 'photo')
    content_id   = int(request.args.get('id', 0))
    tok          = get_session_token()
    existing = Repost.query.filter_by(
        session_token=tok, content_type=content_type, content_id=content_id
    ).first()
    count = Repost.query.filter_by(content_type=content_type, content_id=content_id).count()
    return jsonify({'reposted': existing is not None, 'count': count})


@app.route('/api/reposts/feed')
def api_reposts_feed():
    """Public feed of recent reposts with content details."""
    limit  = min(int(request.args.get('limit', 20)), 50)
    reposts = Repost.query.order_by(Repost.created_at.desc()).limit(limit).all()
    result  = []
    for rp in reposts:
        entry = {
            'id':            rp.id,
            'reposter_name': rp.reposter_name,
            'content_type':  rp.content_type,
            'content_id':    rp.content_id,
            'caption':       rp.caption,
            'created_at':    _time_ago(rp.created_at),
        }
        if rp.content_type == 'photo':
            item = Photo.query.get(rp.content_id)
            if item:
                entry['title']        = item.title
                entry['preview_url']  = '/img/preview/{}'.format(item.id)
                entry['detail_url']   = '/photo/{}'.format(item.id)
                entry['price']        = item.unlock_price
                entry['tier']         = item.tier
        else:
            item = Video.query.get(rp.content_id)
            if item:
                entry['title']        = item.title
                entry['preview_url']  = '/video/thumb/{}'.format(item.id) if item.thumbnail_filename else ''
                entry['detail_url']   = '/video/{}'.format(item.id)
                entry['price']        = item.unlock_price
                entry['tier']         = item.tier
        if 'title' in entry:
            result.append(entry)
    return jsonify(result)


@app.route('/reposts')
def reposts_feed_page():
    """Public repost feed page."""
    return render_template('reposts_feed.html')

class CreatorMessage(db.Model):
    __tablename__ = 'creator_messages'
    id           = db.Column(db.Integer, primary_key=True)
    profile_id   = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    sender_name  = db.Column(db.String(100), default='Anonymous')
    sender_email = db.Column(db.String(200), default='')
    subject      = db.Column(db.String(300), default='New Message')
    body         = db.Column(db.Text, nullable=False)
    is_read      = db.Column(db.Boolean, default=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

class CreatorFollow(db.Model):
    __tablename__ = 'creator_follows'
    id           = db.Column(db.Integer, primary_key=True)
    profile_id   = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    session_token= db.Column(db.String(100), nullable=False)
    follower_name= db.Column(db.String(100), default='Visitor')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('profile_id', 'session_token', name='_follow_uc'),)

class CreatorSubscription(db.Model):
    __tablename__ = 'creator_subscriptions'
    id           = db.Column(db.Integer, primary_key=True)
    profile_id   = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    session_token= db.Column(db.String(100), nullable=False)
    name         = db.Column(db.String(100), default='Visitor')
    email        = db.Column(db.String(200), default='')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('profile_id', 'session_token', name='_sub_uc'),)

class CreatorLike(db.Model):
    __tablename__ = 'creator_likes'
    id           = db.Column(db.Integer, primary_key=True)
    profile_id   = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    session_token= db.Column(db.String(100), nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('profile_id', 'session_token', name='_clk_uc'),)

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1-2 UPGRADE: Engagement, Trending, Activity Feed, Notifications,
#                    Email Verification, Post Unlocking
# ══════════════════════════════════════════════════════════════════════════════

# ── MODEL: PostEngagement — tracks per-post engagement score ─────────────────
class PostEngagement(db.Model):
    """Stores a rolling engagement score for each ProfilePost."""
    __tablename__ = 'post_engagements'
    id           = db.Column(db.Integer, primary_key=True)
    post_id      = db.Column(db.Integer, db.ForeignKey('profile_posts.id'), nullable=False, unique=True)
    score        = db.Column(db.Float, default=0.0)   # computed score
    view_count   = db.Column(db.Integer, default=0)
    like_count   = db.Column(db.Integer, default=0)
    comment_count= db.Column(db.Integer, default=0)
    unlock_count = db.Column(db.Integer, default=0)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow)

# ── MODEL: PostUnlock — paid unlock for a locked ProfilePost ─────────────────
class PostUnlock(db.Model):
    __tablename__  = 'post_unlocks'
    id             = db.Column(db.Integer, primary_key=True)
    post_id        = db.Column(db.Integer, db.ForeignKey('profile_posts.id'), nullable=False)
    session_token  = db.Column(db.String(100), nullable=False)
    amount         = db.Column(db.Float, default=0.0)
    payment_ref    = db.Column(db.String(200), default='')
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('post_id', 'session_token', name='_unlock_uc'),)

# ── MODEL: ActivityFeed — platform activity log ───────────────────────────────
class ActivityFeed(db.Model):
    __tablename__ = 'activity_feed'
    id            = db.Column(db.Integer, primary_key=True)
    event_type    = db.Column(db.String(50), nullable=False)
    # e.g. 'follow','like','comment','unlock','new_post','trending'
    actor_name    = db.Column(db.String(100), default='Someone')
    profile_id    = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=True)
    post_id       = db.Column(db.Integer, db.ForeignKey('profile_posts.id'), nullable=True)
    meta          = db.Column(db.String(300), default='')   # extra info e.g. post title
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

# ── MODEL: Notification — per-session notification queue ─────────────────────
class Notification(db.Model):
    __tablename__  = 'notifications'
    id             = db.Column(db.Integer, primary_key=True)
    session_token  = db.Column(db.String(100), nullable=False)
    notif_type     = db.Column(db.String(50), nullable=False)
    # 'new_post','trending','like','comment','follow','recommended'
    title          = db.Column(db.String(200), default='')
    body           = db.Column(db.String(500), default='')
    link           = db.Column(db.String(300), default='')
    is_read        = db.Column(db.Boolean, default=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

# ── MODEL: EmailVerification ──────────────────────────────────────────────────
class EmailVerification(db.Model):
    __tablename__  = 'email_verifications'
    id             = db.Column(db.Integer, primary_key=True)
    session_token  = db.Column(db.String(100), nullable=False)
    email          = db.Column(db.String(200), nullable=False)
    token          = db.Column(db.String(100), unique=True, nullable=False)
    is_verified    = db.Column(db.Boolean, default=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    verified_at    = db.Column(db.DateTime, nullable=True)

# ── MODEL: Repost ─────────────────────────────────────────────────────────────
class Repost(db.Model):
    """Tracks when a user reposts a photo or video to their feed/activity."""
    __tablename__ = 'reposts'
    id             = db.Column(db.Integer, primary_key=True)
    session_token  = db.Column(db.String(100), nullable=False)
    reposter_name  = db.Column(db.String(100), default='Anonymous')
    content_type   = db.Column(db.String(10), nullable=False)  # 'photo' or 'video'
    content_id     = db.Column(db.Integer, nullable=False)
    caption        = db.Column(db.Text, default='')
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    # Unique: one repost per session per item
    __table_args__ = (db.UniqueConstraint('session_token', 'content_type', 'content_id', name='_repost_uc'),)

# ── Ensure new tables exist ─────────────────────────────────────────────────
with app.app_context():
    db.create_all()

# ══════════════════════════════════════════════════════════════════════════════
# ENGAGEMENT HELPERS
# ══════════════════════════════════════════════════════════════════════════════

SCORE_VIEW    = 1
SCORE_LIKE    = 2
SCORE_COMMENT = 3
SCORE_UNLOCK  = 5

def recalculate_engagement(post_id):
    """Recompute engagement score for a post and update PostEngagement row."""
    post   = ProfilePost.query.get(post_id)
    if not post:
        return
    views    = post.view_count or 0
    likes    = ProfilePostLike.query.filter_by(post_id=post_id).count()
    comments = ProfilePostComment.query.filter_by(post_id=post_id, is_approved=True).count()
    unlocks  = PostUnlock.query.filter_by(post_id=post_id).count()
    score    = (views * SCORE_VIEW) + (likes * SCORE_LIKE) + \
               (comments * SCORE_COMMENT) + (unlocks * SCORE_UNLOCK)
    eng = PostEngagement.query.filter_by(post_id=post_id).first()
    if eng:
        eng.score = score; eng.view_count = views; eng.like_count = likes
        eng.comment_count = comments; eng.unlock_count = unlocks
        eng.updated_at = datetime.utcnow()
    else:
        db.session.add(PostEngagement(post_id=post_id, score=score,
            view_count=views, like_count=likes,
            comment_count=comments, unlock_count=unlocks))
    db.session.commit()

def log_activity(event_type, actor_name='Someone', profile_id=None, post_id=None, meta=''):
    """Append an event to the activity feed (cap at 200 rows)."""
    db.session.add(ActivityFeed(event_type=event_type, actor_name=actor_name,
                                 profile_id=profile_id, post_id=post_id, meta=meta))
    db.session.commit()
    # Trim to latest 200
    oldest_ids = db.session.query(ActivityFeed.id).order_by(ActivityFeed.id.desc())\
                            .offset(200).all()
    if oldest_ids:
        ActivityFeed.query.filter(ActivityFeed.id.in_([r[0] for r in oldest_ids])).delete(synchronize_session=False)
        db.session.commit()

def push_notification(session_token, notif_type, title, body, link=''):
    """Push a notification to a specific session."""
    db.session.add(Notification(session_token=session_token,
        notif_type=notif_type, title=title, body=body, link=link))
    db.session.commit()

def broadcast_notification(notif_type, title, body, link='', exclude_token=None):
    """Send notification to all distinct sessions that have at least one notification (i.e. opted in).
    For new-post broadcasts, send to followers of the relevant profile.
    """
    pass   # Used for specific follow-based broadcasts — see below

def notify_followers(profile_id, notif_type, title, body, link='', exclude_token=None):
    """Push a notification to all followers of a profile."""
    follows = CreatorFollow.query.filter_by(profile_id=profile_id).all()
    for f in follows:
        if f.session_token != exclude_token:
            push_notification(f.session_token, notif_type, title, body, link)

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

@app.route('/trending')
def trending_page():
    """Public trending feed — top scored posts + trending creators."""
    # Top scored posts (join PostEngagement)
    top_posts = db.session.query(ProfilePost, PostEngagement, Profile)\
        .join(PostEngagement, PostEngagement.post_id == ProfilePost.id)\
        .join(Profile, Profile.id == ProfilePost.profile_id)\
        .filter(ProfilePost.is_active == True, Profile.is_active == True)\
        .order_by(PostEngagement.score.desc()).limit(20).all()

    # Trending creators by total post score
    creator_scores = db.session.query(
        Profile,
        db.func.sum(PostEngagement.score).label('total_score')
    ).join(ProfilePost, ProfilePost.profile_id == Profile.id)\
     .join(PostEngagement, PostEngagement.post_id == ProfilePost.id)\
     .filter(Profile.is_active == True)\
     .group_by(Profile.id)\
     .order_by(db.text('total_score DESC')).limit(8).all()

    # Recent new uploads (last 48 hrs)
    cutoff = datetime.utcnow() - timedelta(hours=48)
    new_posts = db.session.query(ProfilePost, Profile)\
        .join(Profile, Profile.id == ProfilePost.profile_id)\
        .filter(ProfilePost.is_active == True, ProfilePost.created_at >= cutoff,
                Profile.is_active == True)\
        .order_by(ProfilePost.created_at.desc()).limit(12).all()

    # Activity feed
    activity = ActivityFeed.query.order_by(ActivityFeed.created_at.desc()).limit(15).all()

    return render_template('trending.html',
        top_posts=top_posts, creator_scores=creator_scores,
        new_posts=new_posts, activity=activity)


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVITY FEED  (public JSON — for live widget)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/activity')
def api_activity():
    rows = ActivityFeed.query.order_by(ActivityFeed.created_at.desc()).limit(15).all()
    result = []
    for r in rows:
        result.append({
            'type':       r.event_type,
            'actor':      r.actor_name,
            'meta':       r.meta,
            'profile_id': r.profile_id,
            'post_id':    r.post_id,
            'ago':        _time_ago(r.created_at),
        })
    return jsonify(result)

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

@app.route('/api/notifications')
def api_notifications():
    tok = get_session_token()
    notes = Notification.query.filter_by(session_token=tok)\
                .order_by(Notification.created_at.desc()).limit(30).all()
    unread = sum(1 for n in notes if not n.is_read)
    result = [{'id': n.id, 'type': n.notif_type, 'title': n.title,
               'body': n.body, 'link': n.link,
               'read': n.is_read, 'ago': _time_ago(n.created_at)} for n in notes]
    return jsonify({'notifications': result, 'unread': unread})

@app.route('/api/notifications/read', methods=['POST'])
def api_mark_notifications_read():
    tok = get_session_token()
    notif_id = (request.get_json() or {}).get('id')
    if notif_id:
        n = Notification.query.filter_by(id=notif_id, session_token=tok).first()
        if n: n.is_read = True
    else:
        Notification.query.filter_by(session_token=tok).update({'is_read': True})
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/api/notifications/clear', methods=['POST'])
def api_clear_notifications():
    tok = get_session_token()
    Notification.query.filter_by(session_token=tok).delete()
    db.session.commit()
    return jsonify({'ok': True})


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL VERIFICATION
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/verify-email', methods=['GET', 'POST'])
def verify_email_page():
    tok = get_session_token()
    ev  = EmailVerification.query.filter_by(session_token=tok).first()
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        if not email:
            flash('Please enter an email address.', 'error')
            return redirect(url_for('verify_email_page'))
        # Generate verification token
        verify_token = ''.join(random.choices(string.ascii_letters + string.digits, k=48))
        if ev:
            ev.email = email; ev.token = verify_token
            ev.is_verified = False; ev.verified_at = None
        else:
            ev = EmailVerification(session_token=tok, email=email, token=verify_token)
            db.session.add(ev)
        db.session.commit()
        # Send verification email
        verify_url = url_for('verify_email_confirm', token=verify_token, _external=True)
        try:
            msg = Message(
                subject='Verify your email — PhotoVault',
                recipients=[email],
                html='''<div style="font-family:sans-serif;max-width:480px;margin:auto">
                    <h2 style="color:#C9A84C">PhotoVault</h2>
                    <p>Click the button below to verify your email and receive notifications.</p>
                    <a href="{url}" style="display:inline-block;background:#C9A84C;color:#000;
                       padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold">
                       Verify Email</a>
                    <p style="color:#888;font-size:12px;margin-top:16px">
                    Link expires in 24 hours. If you did not request this, ignore it.</p>
                    </div>'''.format(url=verify_url)
            )
            mail.send(msg)
            flash('Verification email sent! Check your inbox.', 'success')
        except Exception as e:
            flash('Could not send email — please check your mail config.', 'error')
            print('Mail error:', e)
        return redirect(url_for('verify_email_page'))

    verified = ev.is_verified if ev else False
    email    = ev.email if ev else ''
    return render_template('verify_email.html', verified=verified, email=email)

@app.route('/verify-email/confirm/<token>')
def verify_email_confirm(token):
    ev = EmailVerification.query.filter_by(token=token).first()
    if not ev:
        flash('Invalid or expired verification link.', 'error')
        return redirect(url_for('verify_email_page'))
    ev.is_verified = True
    ev.verified_at = datetime.utcnow()
    # Set session to match
    session['session_token'] = ev.session_token
    db.session.commit()
    push_notification(ev.session_token, 'verified',
        'Email Verified ✓', 'You\'ll now receive notifications from PhotoVault.', '/')
    flash('Email verified successfully! You\'ll now receive notifications.', 'success')
    return redirect(url_for('index'))

@app.route('/api/email-status')
def api_email_status():
    tok = get_session_token()
    ev  = EmailVerification.query.filter_by(session_token=tok).first()
    return jsonify({'verified': ev.is_verified if ev else False,
                    'email': ev.email if ev else ''})


# ══════════════════════════════════════════════════════════════════════════════
# POST UNLOCK (pay-per-view for locked ProfilePosts)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/post/<int:post_id>/unlock', methods=['POST'])
def api_unlock_post(post_id):
    """Mark a post as unlocked for this session (after payment verification).
    For now records unlock and updates engagement; payment integration hooks in here.
    """
    tok  = get_session_token()
    post = ProfilePost.query.get_or_404(post_id)
    existing = PostUnlock.query.filter_by(post_id=post_id, session_token=tok).first()
    if existing:
        return jsonify({'ok': True, 'already_unlocked': True})
    data = request.get_json() or {}
    db.session.add(PostUnlock(post_id=post_id, session_token=tok,
        amount=data.get('amount', 0), payment_ref=data.get('ref', '')))
    db.session.commit()
    recalculate_engagement(post_id)
    log_activity('unlock', 'Someone', profile_id=post.profile_id, post_id=post_id,
                 meta=post.title or 'a post')
    return jsonify({'ok': True, 'unlocked': True})

@app.route('/api/post/<int:post_id>/access')
def api_post_access(post_id):
    tok = get_session_token()
    return jsonify({'access': has_post_access(post_id, tok)})


# ══════════════════════════════════════════════════════════════════════════════
# HOOK EXISTING ENDPOINTS: patch follow/like/comment to also log activity
# and update engagement scores
# ══════════════════════════════════════════════════════════════════════════════

# Override toggle_post_like to log activity
_orig_toggle_post_like = app.view_functions.get('toggle_post_like')

@app.route('/api/post/<int:post_id>/like-v2', methods=['POST'])
def toggle_post_like_v2(post_id):
    """Enhanced like toggle that logs activity and recalculates engagement."""
    tok  = get_session_token()
    post = ProfilePost.query.get_or_404(post_id)
    existing = ProfilePostLike.query.filter_by(post_id=post_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(ProfilePostLike(post_id=post_id, session_token=tok))
        liked = True
        log_activity('like', 'Someone', profile_id=post.profile_id,
                     post_id=post_id, meta=post.title or 'a post')
        # Notify followers when post gets liked (threshold: every 10 likes)
        like_count = ProfilePostLike.query.filter_by(post_id=post_id).count()
        if like_count % 10 == 0:
            notify_followers(post.profile_id, 'like',
                '🔥 Post trending!',
                '"{}" just hit {} likes!'.format(post.title or 'A post', like_count),
                '/profile/{}'.format(Profile.query.get(post.profile_id).username if post.profile_id else ''))
    db.session.commit()
    recalculate_engagement(post_id)
    count = ProfilePostLike.query.filter_by(post_id=post_id).count()
    return jsonify({'liked': liked, 'count': count})

# Enhanced follow that logs activity and sends notifications
@app.route('/api/creator/<int:profile_id>/follow-v2', methods=['POST'])
def api_creator_follow_v2(profile_id):
    if session.get('is_admin'):
        return jsonify({'error': 'Admin accounts cannot follow creators.'}), 403
    tok     = get_session_token()
    profile = Profile.query.get_or_404(profile_id)
    data    = request.get_json() or {}
    name    = data.get('name', 'Visitor')[:100]
    existing = CreatorFollow.query.filter_by(profile_id=profile_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        followed = False
    else:
        db.session.add(CreatorFollow(profile_id=profile_id, session_token=tok, follower_name=name))
        followed = True
        log_activity('follow', name, profile_id=profile_id, meta=profile.name)
        push_notification(tok, 'follow',
            'You\'re now following {}!'.format(profile.name),
            'You\'ll be notified when they post new content.',
            '/creator/{}'.format(profile.username))
    db.session.commit()
    count = CreatorFollow.query.filter_by(profile_id=profile_id).count()
    return jsonify({'followed': followed, 'count': count})

# Enhanced view tracking for profile posts
@app.route('/api/post/<int:post_id>/view', methods=['POST'])
def api_post_view(post_id):
    post = ProfilePost.query.get(post_id)
    if not post:
        return jsonify({'ok': False}), 404
    post.view_count = (post.view_count or 0) + 1
    db.session.commit()
    recalculate_engagement(post_id)
    return jsonify({'ok': True, 'views': post.view_count})


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN: ENGAGEMENT & TRENDING DASHBOARD EXTRAS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/trending')
@admin_required
def admin_trending():
    """Admin view of trending posts + engagement scores."""
    rows = db.session.query(ProfilePost, PostEngagement, Profile)\
        .join(PostEngagement, PostEngagement.post_id == ProfilePost.id)\
        .join(Profile, Profile.id == ProfilePost.profile_id)\
        .filter(ProfilePost.is_active == True)\
        .order_by(PostEngagement.score.desc()).limit(50).all()

    # Creator leaderboard
    creator_scores = db.session.query(
        Profile,
        db.func.sum(PostEngagement.score).label('total_score'),
        db.func.count(ProfilePost.id).label('post_count')
    ).join(ProfilePost, ProfilePost.profile_id == Profile.id)\
     .join(PostEngagement, PostEngagement.post_id == ProfilePost.id)\
     .group_by(Profile.id)\
     .order_by(db.text('total_score DESC')).limit(20).all()

    return render_template('admin_trending.html',
        rows=rows, creator_scores=creator_scores)

@app.route('/admin/post/<int:post_id>/recalculate', methods=['POST'])
@admin_required
def admin_recalculate_engagement(post_id):
    recalculate_engagement(post_id)
    flash('Engagement score recalculated.', 'success')
    return redirect(request.referrer or url_for('admin_trending'))

@app.route('/admin/engagement/recalculate-all', methods=['POST'])
@admin_required
def admin_recalculate_all():
    posts = ProfilePost.query.filter_by(is_active=True).all()
    for p in posts:
        recalculate_engagement(p.id)
    flash('All engagement scores recalculated ({} posts).'.format(len(posts)), 'success')
    return redirect(url_for('admin_trending'))

# ── API: leaderboard for homepage widget ────────────────────────────────────
@app.route('/api/leaderboard')
def api_leaderboard():
    """Top creators by total engagement score."""
    rows = db.session.query(
        Profile,
        db.func.sum(PostEngagement.score).label('total_score')
    ).join(ProfilePost, ProfilePost.profile_id == Profile.id)\
     .join(PostEngagement, PostEngagement.post_id == ProfilePost.id)\
     .filter(Profile.is_active == True)\
     .group_by(Profile.id)\
     .order_by(db.text('total_score DESC')).limit(10).all()

    result = [{'id': p.id, 'name': p.name, 'username': p.username,
               'avatar': p.avatar_filename, 'score': float(s or 0),
               'accent': p.accent_color} for p, s in rows]
    return jsonify(result)

# ── API: trending posts (public) ─────────────────────────────────────────────
@app.route('/api/trending-posts')
def api_trending_posts():
    limit = min(int(request.args.get('limit', 10)), 50)
    rows  = db.session.query(ProfilePost, PostEngagement, Profile)\
        .join(PostEngagement, PostEngagement.post_id == ProfilePost.id)\
        .join(Profile, Profile.id == ProfilePost.profile_id)\
        .filter(ProfilePost.is_active == True, Profile.is_active == True)\
        .order_by(PostEngagement.score.desc()).limit(limit).all()
    result = []
    for post, eng, profile in rows:
        result.append({
            'post_id':    post.id,
            'title':      post.title,
            'media':      post.media_filename,
            'post_type':  post.post_type,
            'profile':    profile.name,
            'username':   profile.username,
            'avatar':     profile.avatar_filename,
            'score':      eng.score,
            'views':      eng.view_count,
            'likes':      eng.like_count,
            'comments':   eng.comment_count,
            'unlocks':    eng.unlock_count,
        })
    return jsonify(result)

# ── Creator Stats API ────────────────────────────────────────────────────────
@app.route('/api/creator/<int:profile_id>/stats')
def api_creator_stats(profile_id):
    tok = get_session_token()
    followers   = CreatorFollow.query.filter_by(profile_id=profile_id).count()
    subscribers = CreatorSubscription.query.filter_by(profile_id=profile_id).count()
    likes       = CreatorLike.query.filter_by(profile_id=profile_id).count()
    i_follow    = CreatorFollow.query.filter_by(profile_id=profile_id, session_token=tok).first() is not None
    i_like      = CreatorLike.query.filter_by(profile_id=profile_id, session_token=tok).first() is not None
    i_sub       = CreatorSubscription.query.filter_by(profile_id=profile_id, session_token=tok).first() is not None
    return jsonify({'followers': followers, 'subscribers': subscribers, 'likes': likes,
                    'i_follow': i_follow, 'i_like': i_like, 'i_sub': i_sub})

# ── Creator Online Status API ─────────────────────────────────────────────────
@app.route('/api/creator/<int:profile_id>/online-status')
def api_creator_online_status(profile_id):
    profile = Profile.query.get_or_404(profile_id)
    last_seen_str = ''
    if not profile.is_online and profile.last_seen:
        try:
            diff = datetime.utcnow() - profile.last_seen
            s = int(diff.total_seconds())
            if s < 60:       last_seen_str = 'just now'
            elif s < 3600:   last_seen_str = '{} min ago'.format(s // 60)
            elif s < 86400:  last_seen_str = '{} hr ago'.format(s // 3600)
            else:            last_seen_str = '{} days ago'.format(s // 86400)
        except Exception:
            last_seen_str = ''
    return jsonify({'online': profile.is_online, 'last_seen': last_seen_str,
                    'username': profile.username,
                    'url': '/creator/{}'.format(profile.username)})

# ── Online creators for popup notifications ───────────────────────────────────
@app.route('/api/online-creators')
def api_online_creators():
    profiles = Profile.query.filter_by(is_active=True).order_by(Profile.name).all()
    result = []
    for p in profiles:
        last_seen_str = ''
        if p.last_seen:
            try:
                diff = datetime.utcnow() - p.last_seen
                s = int(diff.total_seconds())
                if s < 60:       last_seen_str = 'just now'
                elif s < 3600:   last_seen_str = '{} min ago'.format(s // 60)
                elif s < 86400:  last_seen_str = '{} hr ago'.format(s // 3600)
                else:            last_seen_str = '{} days ago'.format(s // 86400)
            except Exception:
                last_seen_str = ''
        result.append({
            'id':        p.id,
            'name':      p.name,
            'username':  p.username,
            # 'url' is the canonical profile link — used by the popup JS
            'url':       '/creator/{}'.format(p.username),
            'avatar':    p.avatar_filename,
            'online':    p.is_online,
            'last_seen': last_seen_str
        })
    return jsonify(result)

# ── Admin: toggle creator online status ──────────────────────────────────────
@app.route('/admin/creator/<int:profile_id>/toggle-online', methods=['POST'])
@admin_required
def admin_toggle_online(profile_id):
    profile = Profile.query.get_or_404(profile_id)
    profile.is_online = not profile.is_online
    if not profile.is_online:
        profile.last_seen = datetime.utcnow()
    db.session.commit()
    # Also update CreatorProfile if it exists
    cp = CreatorProfile.query.filter_by(profile_id=profile_id).first()
    if cp:
        cp.is_online = profile.is_online
        if not profile.is_online:
            cp.last_seen = datetime.utcnow()
        db.session.commit()
    if profile.is_online:
        notify_followers(profile_id, 'online',
            '🟢 {} is online!'.format(profile.name),
            'Tap to visit their profile now.',
            '/creator/{}'.format(profile.username))
    return jsonify({'online': profile.is_online})

# ── Follow/Unfollow ──────────────────────────────────────────────────────────
@app.route('/api/creator/<int:profile_id>/follow', methods=['POST'])
def api_creator_follow(profile_id):
    if session.get('is_admin'):
        return jsonify({'error': 'Admin accounts cannot follow creators.'}), 403
    tok  = get_session_token()
    data = request.get_json() or {}
    name = data.get('name', 'Visitor')[:100]
    existing = CreatorFollow.query.filter_by(profile_id=profile_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        followed = False
    else:
        db.session.add(CreatorFollow(profile_id=profile_id, session_token=tok, follower_name=name))
        followed = True
    db.session.commit()
    count = CreatorFollow.query.filter_by(profile_id=profile_id).count()
    return jsonify({'followed': followed, 'count': count})

# ── Like/Unlike Profile ──────────────────────────────────────────────────────
@app.route('/api/creator/<int:profile_id>/like', methods=['POST'])
def api_creator_like(profile_id):
    if session.get('is_admin'):
        return jsonify({'error': 'Admin accounts cannot like creators.'}), 403
    tok = get_session_token()
    existing = CreatorLike.query.filter_by(profile_id=profile_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(CreatorLike(profile_id=profile_id, session_token=tok))
        liked = True
    db.session.commit()
    count = CreatorLike.query.filter_by(profile_id=profile_id).count()
    return jsonify({'liked': liked, 'count': count})

# ── Subscribe ────────────────────────────────────────────────────────────────
@app.route('/api/creator/<int:profile_id>/subscribe', methods=['POST'])
def api_creator_subscribe(profile_id):
    if session.get('is_admin'):
        return jsonify({'error': 'Admin accounts cannot subscribe to creators.'}), 403
    tok  = get_session_token()
    data = request.get_json() or {}
    existing = CreatorSubscription.query.filter_by(profile_id=profile_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        subscribed = False
    else:
        db.session.add(CreatorSubscription(profile_id=profile_id, session_token=tok,
                        name=data.get('name','Visitor'), email=data.get('email','')))
        subscribed = True
    db.session.commit()
    count = CreatorSubscription.query.filter_by(profile_id=profile_id).count()
    return jsonify({'subscribed': subscribed, 'count': count})

# ── Send Message to Creator ──────────────────────────────────────────────────
@app.route('/api/creator/<int:profile_id>/message', methods=['POST'])
def api_creator_message(profile_id):
    if session.get('is_admin'):
        return jsonify({'error': 'Admin accounts cannot send creator messages.'}), 403
    profile = Profile.query.get_or_404(profile_id)
    data    = request.get_json() or {}
    body    = (data.get('body') or '').strip()
    if not body:
        return jsonify({'error': 'Message cannot be empty'}), 400
    msg = CreatorMessage(
        profile_id   = profile_id,
        sender_name  = (data.get('sender_name') or 'Anonymous').strip()[:100],
        sender_email = (data.get('sender_email') or '').strip()[:200],
        subject      = (data.get('subject') or 'New Message').strip()[:300],
        body         = body[:2000]
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({'ok': True, 'id': msg.id})

# ── Admin: Global inbox (all DM messages across all creators) ────────────────
@app.route('/admin/inbox')
@admin_required
def admin_inbox():
    messages = db.session.query(CreatorMessage, Profile)\
        .join(Profile, Profile.id == CreatorMessage.profile_id)\
        .order_by(CreatorMessage.created_at.desc()).all()
    unread_count = CreatorMessage.query.filter_by(is_read=False).count()
    return render_template('admin_inbox.html', messages=messages, unread_count=unread_count)

# ── Serve video stream (supports range requests for seek) ────────────────────
@app.route('/video/stream/<int:video_id>')
def serve_video_stream(video_id):
    video = Video.query.get_or_404(video_id)
    if not video.video_filename:
        abort(404)
    # Check if creator owns it (admin) or has purchased
    is_admin_user = session.get('is_admin', False)
    if not is_admin_user and not has_video_access(video_id):
        abort(403)
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], 'videos', video.video_filename)
    if not os.path.exists(video_path):
        # Try alternate locations
        for loc in ['static/uploads/posts', 'static/uploads']:
            alt = os.path.join(os.path.dirname(__file__), loc, video.video_filename)
            if os.path.exists(alt):
                video_path = alt
                break
        else:
            abort(404)

    file_size = os.path.getsize(video_path)
    range_header = request.headers.get('Range')
    if range_header:
        byte_start, byte_end = 0, file_size - 1
        match = __import__('re').search(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            byte_start = int(match.group(1))
            if match.group(2):
                byte_end = int(match.group(2))
        length = byte_end - byte_start + 1
        def generate():
            with open(video_path, 'rb') as f:
                f.seek(byte_start)
                remaining = length
                while remaining:
                    chunk = f.read(min(8192, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        from flask import Response
        headers = {
            'Content-Range': 'bytes {}-{}/{}'.format(byte_start, byte_end, file_size),
            'Accept-Ranges': 'bytes',
            'Content-Length': str(length),
            'Content-Type': 'video/mp4',
        }
        return Response(generate(), 206, headers)
    return send_file(video_path, mimetype='video/mp4')


# ══════════════════════════════════════════════════════════════════════════════
# SEARCH API — searches photos, videos, creators
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/search')
def api_search():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({'photos': [], 'videos': [], 'creators': []})

    like = '%{}%'.format(q)

    photos = Photo.query.filter(
        Photo.is_active == True,
        db.or_(Photo.title.ilike(like), Photo.description.ilike(like), Photo.category.ilike(like))
    ).order_by(Photo.view_count.desc()).limit(8).all()

    videos = Video.query.filter(
        Video.is_active == True,
        db.or_(Video.title.ilike(like), Video.description.ilike(like), Video.category.ilike(like))
    ).order_by(Video.view_count.desc()).limit(8).all()

    creators = Profile.query.filter(
        Profile.is_active == True,
        db.or_(Profile.name.ilike(like), Profile.username.ilike(like),
               Profile.tagline.ilike(like), Profile.category.ilike(like))
    ).limit(6).all()

    return jsonify({
        'photos': [{'id': p.id, 'title': p.title, 'tier': p.tier,
                    'price': p.unlock_price, 'views': p.view_count} for p in photos],
        'videos': [{'id': v.id, 'title': v.title, 'tier': v.tier,
                    'price': v.unlock_price, 'views': v.view_count,
                    'thumb': v.thumbnail_filename} for v in videos],
        'creators': [{'id': c.id, 'name': c.name, 'username': c.username,
                      'tagline': c.tagline, 'avatar': c.avatar_filename} for c in creators]
    })


@app.route('/search')
def search_page():
    q = request.args.get('q', '').strip()
    like = '%{}%'.format(q) if q else None
    photos, videos, creators = [], [], []
    if q and len(q) >= 2:
        photos = Photo.query.filter(
            Photo.is_active == True,
            db.or_(Photo.title.ilike(like), Photo.description.ilike(like), Photo.category.ilike(like))
        ).order_by(Photo.view_count.desc()).all()
        for p in photos:
            p.unlocked = has_access(p.id)
            p.current_price = dynamic_price(p)

        videos = Video.query.filter(
            Video.is_active == True,
            db.or_(Video.title.ilike(like), Video.description.ilike(like), Video.category.ilike(like))
        ).order_by(Video.view_count.desc()).all()
        for v in videos:
            v.unlocked = has_video_access(v.id)

        creators = Profile.query.filter(
            Profile.is_active == True,
            db.or_(Profile.name.ilike(like), Profile.username.ilike(like),
                   Profile.tagline.ilike(like))
        ).all()

    return render_template('search.html', q=q, photos=photos, videos=videos, creators=creators)


# ── Comment Likes / Reactions ─────────────────────────────────────────────────
@app.route('/api/comment/<int:comment_id>/like', methods=['POST'])
def api_comment_like(comment_id):
    tok = get_session_token()
    comment = Comment.query.get_or_404(comment_id)
    # Use a simple site setting key to track comment likes
    key = 'clike_{}_{}'.format(comment_id, tok[:16])
    existing = get_setting(key)
    if existing:
        set_setting(key, '')
        # Decrement like count stored in setting
        count_key = 'clike_count_{}'.format(comment_id)
        count = max(0, int(get_setting(count_key, '0')) - 1)
        set_setting(count_key, str(count))
        return jsonify({'liked': False, 'count': count})
    else:
        set_setting(key, '1')
        count_key = 'clike_count_{}'.format(comment_id)
        count = int(get_setting(count_key, '0')) + 1
        set_setting(count_key, str(count))
        return jsonify({'liked': True, 'count': count})


@app.route('/api/comment/<int:comment_id>/likes')
def api_comment_likes(comment_id):
    tok = get_session_token()
    count_key = 'clike_count_{}'.format(comment_id)
    key = 'clike_{}_{}'.format(comment_id, tok[:16])
    count = int(get_setting(count_key, '0'))
    liked = bool(get_setting(key))
    return jsonify({'count': count, 'liked': liked})


# ══════════════════════════════════════════════════════════════════════════════
# CREATOR MANAGER DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/creator-dashboard')
@manager_required
def creator_dashboard():
    """Main dashboard for creator managers — shows only their assigned creator."""
    profile, _ = resolve_creator_dashboard_profile(require_profile=False)

    user_id = session.get('user_id')

    if not profile:
        return render_template('creator_dashboard.html',
                               profile=None,
                               COUNTRY_FLAGS=COUNTRY_FLAGS,
                               COUNTRY_NAMES=COUNTRY_NAMES)

    # Gather stats
    photos    = Photo.query.filter_by(profile_id=profile.id).order_by(Photo.created_at.desc()).all()
    videos    = Video.query.filter_by(profile_id=profile.id).order_by(Video.created_at.desc()).all()
    posts     = ProfilePost.query.filter_by(profile_id=profile.id).order_by(ProfilePost.created_at.desc()).all()

    total_views = sum(p.view_count or 0 for p in posts)
    total_likes = ProfilePostLike.query.join(ProfilePost)\
        .filter(ProfilePost.profile_id == profile.id).count()

    # Earnings for this manager/creator
    earnings_user_id = user_id
    vx_pending, vx_available, vx_lifetime = get_user_balances(earnings_user_id)

    # Sold content counts (for graduation progress)
    sold_photos = db.session.query(db.func.count(db.distinct(VaultTransaction.content_id)))\
        .filter(VaultTransaction.profile_id==profile.id,
                VaultTransaction.content_type=='photo',
                VaultTransaction.status=='completed').scalar() or 0
    sold_videos = db.session.query(db.func.count(db.distinct(VaultTransaction.content_id)))\
        .filter(VaultTransaction.profile_id==profile.id,
                VaultTransaction.content_type=='video',
                VaultTransaction.status=='completed').scalar() or 0

    # Revenue split info
    split = get_revenue_split()
    if profile.account_type == 'sole_creator':
        creator_pct = split.creator_pct
        split_label = 'Creator'
    elif profile.account_type == 'junior_creator':
        creator_pct = split.manager_pct
        split_label = 'Junior Creator (Probation)'
    else:
        creator_pct = split.manager_pct
        split_label = 'Manager Trial'

    return render_template(
        'creator_dashboard.html',
        profile=profile,
        photos=photos,
        videos=videos,
        posts=posts,
        total_views=total_views,
        total_likes=total_likes,
        vx_pending=vx_pending,
        vx_available=vx_available,
        vx_lifetime=vx_lifetime,
        sold_photos=sold_photos,
        sold_videos=sold_videos,
        creator_pct=creator_pct,
        split_label=split_label,
        GRAD_MIN_PHOTOS=GRADUATION_MIN_PHOTOS,
        GRAD_MIN_VIDEOS=GRADUATION_MIN_VIDEOS,
        COUNTRY_FLAGS=COUNTRY_FLAGS,
        COUNTRY_NAMES=COUNTRY_NAMES,
        dm_settings=DMSettings.query.filter_by(profile_id=profile.id).first(),
    )


@app.route('/creator-dashboard/videos')
@manager_required
def creator_dashboard_videos():
    """Video management page for the assigned creator."""
    profile, _ = resolve_creator_dashboard_profile()

    videos = Video.query.filter_by(profile_id=profile.id).order_by(Video.created_at.desc()).all()
    return render_template(
        'creator_dashboard_videos.html',
        profile=profile,
        videos=videos,
        COUNTRY_FLAGS=COUNTRY_FLAGS,
        COUNTRY_NAMES=COUNTRY_NAMES,
    )


@app.route('/creator-dashboard/upload-photo', methods=['GET', 'POST'])
@creator_only_required
def creator_upload_photo():
    """Creator manager uploads a photo for their assigned creator."""
    profile, _ = resolve_creator_dashboard_profile()

    if request.method == 'POST':
        allowed, limit_msg = check_upload_allowed(profile, 'photo')
        if not allowed:
            flash(limit_msg, 'error')
            return redirect(upload_url('vx_become_creator_premium', profile.id))

        title       = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category    = request.form.get('category', '').strip()
        tier        = request.form.get('tier', 'basic').strip()
        unlock_price= float(request.form.get('unlock_price', 2.0) or 2.0)
        blur_strength= int(request.form.get('blur_strength', 12) or 12)
        photo_file  = request.files.get('photo_file')

        # Premium-only: high-res / premium tier requires active Premium subscription
        if tier == 'premium' and not profile.is_premium:
            flash('Uploading to the Premium tier requires a Premium subscription.', 'error')
            return redirect(url_for('vx_become_creator_premium'))

        if not title:
            flash('Title is required.', 'error')
            return redirect(upload_url('creator_upload_photo', profile.id))
        if not photo_file or not photo_file.filename:
            flash('Please select a photo to upload.', 'error')
            return redirect(upload_url('creator_upload_photo', profile.id))
        if not allowed_file(photo_file.filename):
            flash('Invalid file type. Use JPG, PNG, or WEBP.', 'error')
            return redirect(upload_url('creator_upload_photo', profile.id))

        ext = photo_file.filename.rsplit('.', 1)[1].lower()
        uid = str(uuid.uuid4())
        orig_filename    = '{}.{}'.format(uid, ext)
        preview_filename = 'prev_{}.jpg'.format(uid)

        orig_dir    = os.path.join(app.config['UPLOAD_FOLDER'], 'originals')
        preview_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'previews')
        os.makedirs(orig_dir, exist_ok=True)
        os.makedirs(preview_dir, exist_ok=True)

        orig_path    = os.path.join(orig_dir, orig_filename)
        preview_path = os.path.join(preview_dir, preview_filename)

        photo_file.save(orig_path)
        ok = generate_watermark_preview(orig_path, preview_path, blur_strength)
        if not ok:
            import shutil
            shutil.copy(orig_path, preview_path)

        photo = Photo(
            profile_id=profile.id,
            title=title,
            description=description,
            category=category,
            tier=tier,
            original_filename=orig_filename,
            preview_filename=preview_filename,
            unlock_price=unlock_price,
            unlock_duration=int(request.form.get('unlock_duration', 24) or 24),
            is_active=True,
        )
        db.session.add(photo)
        db.session.flush()

        # Also create ProfilePost so it appears on creator profile
        profile_post = ProfilePost(
            profile_id=profile.id,
            title=title,
            caption=description,
            post_type='photo',
            photo_id=photo.id,
            blur_strength=blur_strength,
            is_active=True,
        )
        db.session.add(profile_post)
        db.session.commit()

        flash('Photo uploaded successfully!', 'success')
        return redirect(upload_url('creator_dashboard', profile.id))

    categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order, Category.name).all()
    return render_template(
        'creator_upload_photo.html',
        profile=profile,
        categories=categories,
        COUNTRY_FLAGS=COUNTRY_FLAGS,
        COUNTRY_NAMES=COUNTRY_NAMES,
    )


@app.route('/creator-dashboard/upload-video', methods=['GET', 'POST'])
@creator_only_required
def creator_upload_video():
    """Creator manager uploads a video for their assigned creator."""
    profile, _ = resolve_creator_dashboard_profile()

    if request.method == 'POST':
        allowed, limit_msg = check_upload_allowed(profile, 'video')
        if not allowed:
            flash(limit_msg, 'error')
            return redirect(upload_url('vx_become_creator_premium', profile.id))

        title       = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category    = request.form.get('category', '').strip()
        tier        = request.form.get('tier', 'basic').strip()
        unlock_price = float(request.form.get('unlock_price', 5.0) or 5.0)
        # Creator chooses which part of the video plays as the hover/preview clip
        preview_start_seconds    = int(request.form.get('preview_start_seconds', 0) or 0)
        preview_duration_seconds = max(3, min(5, int(request.form.get('preview_duration_seconds', 4) or 4)))
        blur_strength             = max(0, min(40, int(request.form.get('blur_strength', 8) or 8)))

        # Premium-only tier (longer length / higher quality / no price ceiling)
        if tier == 'premium' and not profile.is_premium:
            flash('Uploading to the Premium tier requires a Premium subscription.', 'error')
            return redirect(url_for('vx_become_creator_premium'))
        if not profile.is_premium and unlock_price > 50:
            flash('Basic plan videos are capped at $50. Upgrade to Premium to set a higher price.', 'error')
            return redirect(url_for('creator_upload_video'))

        video_file = request.files.get('video_file')

        if not title:
            flash('Title is required.', 'error')
            return redirect(upload_url('creator_upload_video', profile.id))

        video_filename = None
        if video_file and video_file.filename and allowed_video(video_file.filename):
            ext = video_file.filename.rsplit('.', 1)[1].lower()
            video_filename = 'vid_{}_{}.{}'.format(profile.username, str(uuid.uuid4())[:8], ext)
            videos_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
            os.makedirs(videos_dir, exist_ok=True)
            video_file.save(os.path.join(videos_dir, video_filename))

        # No manual thumbnail upload — the hover-preview clip IS the thumbnail.
        # The frontend plays preview_duration_seconds of video starting at
        # preview_start_seconds on hover, blurred at blur_strength.
        video = Video(
            profile_id=profile.id,
            title=title,
            description=description,
            category=category,
            tier=tier,
            video_filename=video_filename,
            thumbnail_filename=None,
            unlock_price=unlock_price,
            unlock_duration=int(request.form.get('unlock_duration', 24) or 24),
            preview_start_seconds=preview_start_seconds,
            preview_duration_seconds=preview_duration_seconds,
            blur_strength=blur_strength,
            is_active=True,
        )
        db.session.add(video)
        db.session.flush()

        # Create ProfilePost so video appears on creator profile
        profile_post = ProfilePost(
            profile_id=profile.id,
            title=title,
            caption=description,
            post_type='video',
            video_id=video.id,
            blur_strength=blur_strength,
            is_active=True,
        )
        db.session.add(profile_post)
        db.session.commit()
        flash('Video uploaded successfully!', 'success')
        return redirect(upload_url('creator_dashboard_videos', profile.id))

    categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order, Category.name).all()
    return render_template(
        'creator_upload_video.html',
        profile=profile,
        categories=categories,
        COUNTRY_FLAGS=COUNTRY_FLAGS,
        COUNTRY_NAMES=COUNTRY_NAMES,
    )


@app.route('/creator-dashboard/video/<int:video_id>/delete', methods=['POST'])
@manager_required
def creator_delete_video(video_id):
    """Creator manager deletes one of their creator's videos."""
    video = Video.query.get_or_404(video_id)
    # Access control — only the assigned manager can delete
    profile = Profile.query.filter_by(manager_id=session.get('user_id')).first()
    if not profile or profile.id != video.profile_id:
        abort(403)
    profile_id = profile.id

    db.session.delete(video)
    db.session.commit()
    flash('Video deleted.', 'success')
    return redirect(upload_url('creator_dashboard_videos', profile_id))


# ══════════════════════════════════════════════════════════════════════════════
# CREATOR PREMIUM SUBSCRIPTION — 100% platform revenue, unlimited uploads/live
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/creator-dashboard/premium', methods=['GET', 'POST'])
@manager_required
def vx_become_creator_premium():
    """Either role (sole creator's manager OR admin-managed account) can
    subscribe their profile to Premium. 100% of this revenue goes to the
    platform — it never appears in the creator/manager/ops split."""
    user_id  = session.get('user_id')
    is_admin = session.get('is_admin', False)

    profile_id = request.args.get('profile_id', type=int) or request.form.get('profile_id', type=int)
    if is_admin and profile_id:
        profile = Profile.query.get_or_404(profile_id)
    elif profile_id and Profile.query.filter_by(id=profile_id, manager_id=user_id).first():
        profile = Profile.query.get_or_404(profile_id)
    else:
        profile = Profile.query.filter_by(manager_id=user_id).first()
        if not profile:
            # Maybe they are a sole creator instead of a manager
            ca = CreatorAccount.query.filter_by(user_id=user_id).first()
            profile = ca.profile if ca else None
    if not profile:
        return redirect(url_for('creator_dashboard'))

    if request.method == 'POST':
        # Simulate successful payment confirmation (Stripe/Paystack/Binance hookup point)
        profile.is_premium         = True
        profile.premium_started_at = datetime.utcnow()

        # Record this as a pure-platform transaction — no creator/manager/ops split
        txn = VaultTransaction(
            reference=make_transaction_ref(),
            session_token=get_session_token(),
            profile_id=profile.id,
            content_type='premium_subscription',
            gross_amount=PREMIUM_MONTHLY_PRICE,
            gateway=request.form.get('gateway', 'stripe'),
            status='completed'
        )
        db.session.add(txn)
        db.session.flush()
        db.session.add(EarningsRecord(
            transaction_id=txn.id,
            beneficiary_type='platform',
            beneficiary_user_id=None,
            profile_id=profile.id,
            amount=PREMIUM_MONTHLY_PRICE,
            content_type='premium_subscription',
            is_available=True
        ))
        db.session.commit()
        flash('🌟 Premium activated! Unlimited uploads and live hours are now unlocked.', 'success')
        return redirect(url_for('creator_dashboard'))

    return render_template('vx_creator_premium.html', profile=profile, price=PREMIUM_MONTHLY_PRICE)


# ══════════════════════════════════════════════════════════════════════════════
# ONLINE STATUS DB MIGRATION — adds is_online column to profiles if missing
# ══════════════════════════════════════════════════════════════════════════════
def ensure_online_column():
    """Add is_online to profiles table if it doesn't exist yet."""
    try:
        from sqlalchemy import text, inspect as sa_inspect
        with app.app_context():
            inspector = sa_inspect(db.engine)
            cols = [c['name'] for c in inspector.get_columns('profiles')]
            if 'is_online' not in cols:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE profiles ADD COLUMN is_online BOOLEAN DEFAULT 0'))
                    conn.commit()
    except Exception as e:
        print('ensure_online_column warning: {}'.format(e))


# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# VAULTX PAYMENT & REVENUE ENGINE — Append this block to the end of app.py
# (BEFORE the create_admin() and if __name__ == '__main__' lines)
# ══════════════════════════════════════════════════════════════════════════════
# Place these MODEL definitions alongside (or after) your existing models,
# then place all the ROUTE definitions before create_admin().
# ══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# NEW MODELS
# ─────────────────────────────────────────────────────────────────────────────

class OperationsManager(db.Model):
    __tablename__ = 'operations_managers'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    name        = db.Column(db.String(100), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    user        = db.relationship('User', foreign_keys=[user_id])


class CreatorManagerProfile(db.Model):
    """Tracks which ops manager a creator_manager user belongs to,
    and which creators they manage.  A creator_manager User must have
    one row here before they can log into the manager portal."""
    __tablename__  = 'creator_manager_profiles'
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    name           = db.Column(db.String(100), nullable=False)
    ops_manager_id = db.Column(db.Integer, db.ForeignKey('operations_managers.id'), nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    user           = db.relationship('User', foreign_keys=[user_id])
    ops_manager    = db.relationship('OperationsManager', backref='managed_creator_managers')


class CreatorAccount(db.Model):
    """Links a sole verified Creator (Profile) to a User account for login.

    NOTE: manager-run accounts do NOT get a CreatorAccount — they are tracked
    purely via Profile.manager_id + Profile.assigned_by_ops_id. A CreatorAccount
    is only created once a profile graduates to account_type == 'sole_creator'
    (or is issued directly as a sole account by admin).
    """
    __tablename__ = 'creator_accounts'
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    profile_id      = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False, unique=True)
    # Optional: link a CreatorManagerProfile so manager can see this creator
    # in their portal. NULL = no manager assigned (sole independent creator).
    creator_manager_id = db.Column(db.Integer, db.ForeignKey('creator_manager_profiles.id'), nullable=True)
    terms_accepted  = db.Column(db.Boolean, default=False)
    terms_accepted_at = db.Column(db.DateTime, nullable=True)
    telegram_creator_channel = db.Column(db.String(200), default='')
    telegram_subscriber_channel = db.Column(db.String(200), default='')
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    user            = db.relationship('User', foreign_keys=[user_id])
    profile         = db.relationship('Profile', foreign_keys=[profile_id])
    creator_manager = db.relationship('CreatorManagerProfile', backref='assigned_creators', foreign_keys=[creator_manager_id])


class RevenueSplit(db.Model):
    """Platform-wide revenue split configuration (stored in DB, editable by admin).

    Two distinct splits:
    - Sole verified creator: creator_pct (max 70%) / platform takes the rest
    - Manager-run (admin-issued, unmanaged-by-self) creator account:
        manager_pct (creator manager keeps this, e.g. 55%) +
        ops_manager_pct (the OPS manager who assigned them, e.g. 15%) +
        remaining goes to platform
    """
    __tablename__ = 'revenue_splits'
    id              = db.Column(db.Integer, primary_key=True)
    creator_pct     = db.Column(db.Float, default=70.0)   # sole verified creator share (hard cap 70)
    manager_pct     = db.Column(db.Float, default=55.0)   # creator-manager share of a manager-run account
    ops_manager_pct = db.Column(db.Float, default=15.0)   # ops manager override cut on manager-run accounts
    platform_pct    = db.Column(db.Float, default=30.0)   # platform share on sole-creator sales (informational)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow)


class VaultTransaction(db.Model):
    """Every purchase creates one transaction record."""
    __tablename__ = 'vault_transactions'
    id              = db.Column(db.Integer, primary_key=True)
    reference       = db.Column(db.String(120), unique=True, nullable=False)
    subscriber_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_token   = db.Column(db.String(100), nullable=False)
    profile_id      = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=True)
    content_type    = db.Column(db.String(30), default='photo')  # photo/video/subscription/dm/tip/voice
    content_id      = db.Column(db.Integer, nullable=True)
    gateway         = db.Column(db.String(30), default='stripe')
    gross_amount    = db.Column(db.Float, nullable=False)
    currency        = db.Column(db.String(10), default='USD')
    status          = db.Column(db.String(20), default='pending')  # pending/completed/failed/refunded
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    subscriber      = db.relationship('User', foreign_keys=[subscriber_user_id])
    profile         = db.relationship('Profile', foreign_keys=[profile_id])


class EarningsRecord(db.Model):
    """One record per beneficiary per transaction."""
    __tablename__ = 'earnings_records'
    id              = db.Column(db.Integer, primary_key=True)
    transaction_id  = db.Column(db.Integer, db.ForeignKey('vault_transactions.id'), nullable=False)
    beneficiary_type= db.Column(db.String(30), nullable=False)  # creator/creator_manager/ops_manager/platform
    beneficiary_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    profile_id      = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=True)
    amount          = db.Column(db.Float, nullable=False)
    content_type    = db.Column(db.String(30), default='photo')
    is_available    = db.Column(db.Boolean, default=False)  # True after payout window
    # Once a withdrawal request is created against this record, it gets locked
    # here so it can never be double-counted into a second withdrawal request.
    withdrawal_request_id = db.Column(db.Integer, db.ForeignKey('withdrawal_requests.id'), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    transaction     = db.relationship('VaultTransaction', backref='earnings')
    beneficiary     = db.relationship('User', foreign_keys=[beneficiary_user_id])


class PayoutMethod(db.Model):
    """Each user stores their preferred payout method."""
    __tablename__ = 'payout_methods'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    method_type = db.Column(db.String(20), nullable=False)  # mpesa/bank/paypal/crypto
    mpesa_number= db.Column(db.String(20), default='')
    bank_name   = db.Column(db.String(100), default='')
    bank_account= db.Column(db.String(100), default='')
    paypal_email= db.Column(db.String(200), default='')
    crypto_wallet = db.Column(db.String(200), default='')
    crypto_type = db.Column(db.String(20), default='USDT')
    is_default  = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    user        = db.relationship('User', backref='payout_methods')


class WithdrawalRequest(db.Model):
    """Creator / Manager withdrawal requests (only Wed & Sat)."""
    __tablename__ = 'withdrawal_requests'
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount          = db.Column(db.Float, nullable=False)
    payout_method_id= db.Column(db.Integer, db.ForeignKey('payout_methods.id'), nullable=True)
    method_snapshot = db.Column(db.Text, default='{}')  # JSON snapshot of method at request time
    status          = db.Column(db.String(20), default='pending')  # pending/approved/rejected/paid
    admin_note      = db.Column(db.Text, default='')
    requested_at    = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at    = db.Column(db.DateTime, nullable=True)
    user            = db.relationship('User', backref='withdrawal_requests')
    payout_method   = db.relationship('PayoutMethod')


class TermsAcceptance(db.Model):
    __tablename__ = 'terms_acceptances'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    accepted_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address  = db.Column(db.String(50), default='')
    user        = db.relationship('User', backref='terms_acceptances')


class DMThread(db.Model):
    """A conversation thread between a subscriber and a creator profile."""
    __tablename__ = 'dm_threads'
    id              = db.Column(db.Integer, primary_key=True)
    subscriber_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    profile_id      = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow)
    subscriber      = db.relationship('User', foreign_keys=[subscriber_user_id])
    profile         = db.relationship('Profile', foreign_keys=[profile_id])
    messages        = db.relationship('DMMessage', backref='thread', lazy=True, order_by='DMMessage.created_at')
    __table_args__ = (db.UniqueConstraint('subscriber_user_id', 'profile_id', name='_dm_thread_uc'),)


class DMMessage(db.Model):
    """Individual messages inside a DM thread."""
    __tablename__ = 'dm_messages'
    id              = db.Column(db.Integer, primary_key=True)
    thread_id       = db.Column(db.Integer, db.ForeignKey('dm_threads.id'), nullable=False)
    sender_type     = db.Column(db.String(20), nullable=False)  # subscriber/creator/admin
    sender_user_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    body            = db.Column(db.Text, default='')
    # Locked media
    media_url       = db.Column(db.String(500), default='')  # stored URL (cloud storage / CDN)
    media_type      = db.Column(db.String(20), default='')   # photo/video/voice/text
    lock_price      = db.Column(db.Float, default=0.0)       # 0 = free
    is_unlocked     = db.Column(db.Boolean, default=False)
    # Pricing toggle
    charge_enabled  = db.Column(db.Boolean, default=False)
    message_price   = db.Column(db.Float, default=0.0)
    is_read         = db.Column(db.Boolean, default=False)
    # Admin styled
    is_admin_notice = db.Column(db.Boolean, default=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    sender          = db.relationship('User', foreign_keys=[sender_user_id])


class DMSettings(db.Model):
    """Per-profile DM monetization settings — controlled by creator/manager."""
    __tablename__ = 'dm_settings'
    id              = db.Column(db.Integer, primary_key=True)
    profile_id      = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False, unique=True)
    # DM inbox enabled/disabled
    dm_enabled      = db.Column(db.Boolean, default=True)
    # Charge per message sent (subscriber pays to send)
    charge_per_msg  = db.Column(db.Boolean, default=False)
    msg_price       = db.Column(db.Float, default=1.0)   # price per inbound message
    # Auto-reply message when offline
    auto_reply_text = db.Column(db.String(500), default='')
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow)
    profile         = db.relationship('Profile', backref=db.backref('dm_settings_obj', uselist=False))


class Subscription(db.Model):
    """Monthly subscriptions from subscriber to creator profile."""
    __tablename__ = 'subscriptions'
    id              = db.Column(db.Integer, primary_key=True)
    subscriber_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    profile_id      = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    monthly_price   = db.Column(db.Float, nullable=False)
    status          = db.Column(db.String(20), default='active')  # active/cancelled/expired
    started_at      = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at      = db.Column(db.DateTime, nullable=True)
    gateway         = db.Column(db.String(30), default='stripe')
    subscriber      = db.relationship('User', foreign_keys=[subscriber_user_id])
    profile         = db.relationship('Profile', foreign_keys=[profile_id])


class Tip(db.Model):
    """Tips sent by subscribers to creators."""
    __tablename__ = 'tips'
    id              = db.Column(db.Integer, primary_key=True)
    subscriber_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_token   = db.Column(db.String(100), default='')
    profile_id      = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    amount          = db.Column(db.Float, nullable=False)
    message         = db.Column(db.String(300), default='')
    transaction_id  = db.Column(db.Integer, db.ForeignKey('vault_transactions.id'), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)


class TelegramChannel(db.Model):
    """Platform-level Telegram channel links set by Admin."""
    __tablename__ = 'telegram_channels'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    channel_url = db.Column(db.String(300), nullable=False)
    channel_type= db.Column(db.String(30), default='subscriber')  # subscriber/creator/admin
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


class SubscriberProfile(db.Model):
    """Extended profile data for subscribers."""
    __tablename__ = 'subscriber_profiles'
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    display_name    = db.Column(db.String(100), default='')
    avatar_url      = db.Column(db.String(500), default='')
    total_spent     = db.Column(db.Float, default=0.0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    user            = db.relationship('User', backref='subscriber_profile', uselist=False)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_revenue_split():
    split = RevenueSplit.query.first()
    if not split:
        split = RevenueSplit()
        db.session.add(split)
        db.session.commit()
    return split

# Hard ceiling — no sole creator (no matter what admin configures) earns more than this
MAX_CREATOR_PCT = 70.0

# Upload limits before a creator must subscribe to Premium for unlimited uploads/live hours
UPLOAD_LIMITS = {
    'basic':   {'photos': 15,  'videos': 8,    'live_hours_per_month': 4},
    'premium': {'photos': None,'videos': None, 'live_hours_per_month': None},  # None = unlimited
}
PREMIUM_MONTHLY_PRICE = 29.99  # 100% platform revenue

def is_withdrawal_day():
    """Returns True if today is Wednesday (2) or Saturday (5)."""
    return datetime.utcnow().weekday() in (2, 5)

def next_withdrawal_day():
    """Returns the name of the next withdrawal window."""
    today = datetime.utcnow().weekday()
    # Wednesday=2, Saturday=5
    if today < 2:
        return 'Wednesday'
    elif today < 5:
        return 'Saturday'
    else:
        return 'Wednesday'

def calculate_age(dob):
    """Returns age in whole years given a date object."""
    if not dob:
        return None
    today = datetime.utcnow().date()
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return years


def junior_creator_sales_count(user_id):
    """Count of completed transactions on a profile for a junior creator —
    used to display progress toward the 4+4 qualification threshold."""
    ca = CreatorAccount.query.filter_by(user_id=user_id).first()
    if not ca:
        return {'photos': 0, 'videos': 0}
    photo_sales = VaultTransaction.query.filter_by(
        profile_id=ca.profile_id, content_type='photo', status='completed'
    ).count()
    video_sales = VaultTransaction.query.filter_by(
        profile_id=ca.profile_id, content_type='video', status='completed'
    ).count()
    return {'photos': photo_sales, 'videos': video_sales}


def junior_creator_is_eligible_for_promotion(user_id):
    """Check if a junior_creator has met the 4+4 sales qualification for
    automatic promotion to full Creator. Returns (bool, message)."""
    min_sales = GRADUATION_MIN_PHOTOS
    ca = CreatorAccount.query.filter_by(user_id=user_id).first()
    if not ca:
        return False, 'No creator profile linked to this account.'
    profile = ca.profile
    sales = junior_creator_sales_count(user_id)
    if sales['photos'] < min_sales or sales['videos'] < min_sales:
        return False, 'You need {} photo sales and {} video sales (currently {} photos, {} videos).'.format(
            min_sales, min_sales, sales['photos'], sales['videos'])
    return True, 'Eligible'


def split_revenue(transaction: VaultTransaction):
    """Create EarningsRecord rows for each beneficiary.

    Revenue rules (hard caps enforced regardless of admin config):
    - Sole verified creator (account_type == 'sole_creator', self-applied + approved):
        creator gets up to 70% (hard cap), platform gets the remainder.
    - Sole creator account that was ISSUED by admin directly (never went through
      the manager-trial/application flow) earns slightly less than a self-applied
      verified creator — 65% instead of 70% — platform gets the remainder.
    - Manager-run account (account_type == 'manager_trial', Profile.manager_id set):
        creator manager earns manager_pct (e.g. 55%) — this is the ENTIRETY of what
        the manager earns; they hold no other stake.
        The OPS manager who assigned them earns ops_manager_pct (e.g. 15%).
        Platform absorbs whatever remains.
        NOTE: the underlying creator/profile itself earns nothing extra here —
        the manager IS the one "being" the creator for revenue purposes during trial.
    """
    gross   = transaction.gross_amount
    profile = transaction.profile
    if not profile:
        return

    split = get_revenue_split()
    records = []

    if profile.manager_id and profile.account_type != 'sole_creator':
        # ── Manager-run account ──────────────────────────────────────────
        manager_pct = min(split.manager_pct, 55.0)  # never exceeds configured/default cap
        ops_pct     = max(split.ops_manager_pct, 0.0)
        if manager_pct + ops_pct > 100:
            ops_pct = max(0.0, 100 - manager_pct)
        platform_pct = max(0.0, 100 - manager_pct - ops_pct)

        records.append(EarningsRecord(
            transaction_id=transaction.id,
            beneficiary_type='creator_manager',
            beneficiary_user_id=profile.manager_id,
            profile_id=profile.id,
            amount=round(gross * manager_pct / 100, 2),
            content_type=transaction.content_type
        ))
        if ops_pct > 0 and profile.assigned_by_ops_id:
            records.append(EarningsRecord(
                transaction_id=transaction.id,
                beneficiary_type='ops_manager',
                beneficiary_user_id=profile.assigned_by_ops_id,
                profile_id=profile.id,
                amount=round(gross * ops_pct / 100, 2),
                content_type=transaction.content_type
            ))
            platform_amount = round(gross * platform_pct / 100, 2)
        else:
            # No OPS manager attached — their cut rolls into platform
            platform_amount = round(gross * (platform_pct + ops_pct) / 100, 2)

        records.append(EarningsRecord(
            transaction_id=transaction.id,
            beneficiary_type='platform',
            beneficiary_user_id=None,
            profile_id=profile.id,
            amount=platform_amount,
            content_type=transaction.content_type
        ))

    else:
        # ── Sole verified creator account ────────────────────────────────
        creator_account = CreatorAccount.query.filter_by(profile_id=profile.id).first()
        creator_user_id = creator_account.user_id if creator_account else None

        # Hard cap: no sole creator ever earns more than MAX_CREATOR_PCT (70%)
        if profile.account_type == 'sole_creator_admin_issued':
            creator_pct = min(split.creator_pct, 65.0)
        else:
            creator_pct = min(split.creator_pct, MAX_CREATOR_PCT)
        platform_pct = max(0.0, 100 - creator_pct)

        records.append(EarningsRecord(
            transaction_id=transaction.id,
            beneficiary_type='creator',
            beneficiary_user_id=creator_user_id,
            profile_id=profile.id,
            amount=round(gross * creator_pct / 100, 2),
            content_type=transaction.content_type
        ))
        records.append(EarningsRecord(
            transaction_id=transaction.id,
            beneficiary_type='platform',
            beneficiary_user_id=None,
            profile_id=profile.id,
            amount=round(gross * platform_pct / 100, 2),
            content_type=transaction.content_type
        ))

    for r in records:
        db.session.add(r)
    db.session.commit()

    # Check if this profile qualifies for automatic graduation
    try:
        check_graduation(profile.id)
    except Exception as e:
        print('Graduation check error: {}'.format(e))

def get_user_balances(user_id):
    """Returns (pending, available, lifetime) for a user.

    'available' EXCLUDES any earnings already locked against a pending/approved/paid
    withdrawal request — this is what prevents double-withdrawal / conflicting payouts.
    """
    records = EarningsRecord.query.filter_by(beneficiary_user_id=user_id).all()
    pending   = sum(r.amount for r in records if not r.is_available and not r.withdrawal_request_id)
    available = sum(r.amount for r in records if r.is_available and not r.withdrawal_request_id)
    lifetime  = sum(r.amount for r in records)
    return pending, available, lifetime

def get_user_revenue_breakdown(user_id):
    """Returns dict of revenue by content_type for a user."""
    records = EarningsRecord.query.filter_by(beneficiary_user_id=user_id).all()
    breakdown = {}
    for r in records:
        breakdown[r.content_type] = breakdown.get(r.content_type, 0) + r.amount
    return breakdown


def lock_earnings_for_withdrawal(user_id, amount, withdrawal_request):
    """Lock exactly `amount` worth of available, unlocked EarningsRecord rows
    against this withdrawal request so they can never be claimed again by a
    second withdrawal. Returns True if the full amount could be locked.

    This is the fix for the double-withdrawal/conflict bug: without this,
    'available' balance was never actually deducted when a request was made.
    """
    remaining = amount
    records = EarningsRecord.query.filter_by(
        beneficiary_user_id=user_id, is_available=True, withdrawal_request_id=None
    ).order_by(EarningsRecord.created_at.asc()).all()

    locked_records = []
    for r in records:
        if remaining <= 0:
            break
        # Lock the whole record (simplest, avoids needing partial-amount splitting)
        locked_records.append(r)
        remaining -= r.amount

    if remaining > 0.009:  # not enough available earnings to cover the request
        return False

    for r in locked_records:
        r.withdrawal_request_id = withdrawal_request.id
    db.session.commit()
    return True


def release_locked_earnings(withdrawal_request):
    """If a withdrawal is rejected, unlock its earnings so they become available again."""
    EarningsRecord.query.filter_by(withdrawal_request_id=withdrawal_request.id)\
        .update({'withdrawal_request_id': None})
    db.session.commit()


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

def creator_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('creator_account_id'):
            return redirect(url_for('creator_login'))
        ca = CreatorAccount.query.get(session['creator_account_id'])
        if not ca:
            return redirect(url_for('creator_login'))
        if not ca.terms_accepted:
            return redirect(url_for('creator_terms'))
        return f(*args, **kwargs)
    return decorated

def make_transaction_ref():
    return 'VX-' + str(uuid.uuid4()).replace('-', '').upper()[:16]


# ─────────────────────────────────────────────────────────────────────────────
# CREATOR AUTH ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/creator/login', methods=['GET', 'POST'])
def creator_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        # Look up user by email
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            # ── CREATOR MANAGER acting as their assigned creator ──────────────
            if user.role == 'creator_manager':
                # Find the profile assigned to this manager
                profile = Profile.query.filter_by(manager_id=user.id).first()
                if profile:
                    # Log them in as "manager acting as creator"
                    session['user_id']    = user.id
                    session['is_admin']   = False
                    session['is_manager'] = True
                    session['user_role']  = 'creator_manager'
                    session['manager_profile_id'] = profile.id
                    flash('Logged in as Junior Creator managing {}'.format(profile.name), 'success')
                    return redirect(url_for('creator_dashboard'))
                else:
                    flash('You have no creator profile assigned yet. Contact admin.', 'error')
                    return render_template('vx_creator_login.html')

            # ── SOLE CREATOR with a CreatorAccount ────────────────────────────
            ca = CreatorAccount.query.filter_by(user_id=user.id).first()
            if not ca:
                flash('No creator profile is linked to this account.', 'error')
                return render_template('vx_creator_login.html')

            if user.role not in ('creator', 'junior_creator'):
                user.role = 'junior_creator'
                db.session.commit()

            session['creator_account_id']  = ca.id
            session['creator_user_id']     = user.id
            session['creator_profile_id']  = ca.profile_id
            if not ca.terms_accepted:
                return redirect(url_for('creator_terms'))
            telegram_channels = TelegramChannel.query.filter_by(channel_type='creator', is_active=True).all()
            if telegram_channels:
                session['show_creator_telegram'] = True
            return redirect(url_for('creator_home'))

        if user:
            flash('Incorrect password. Please try again.', 'error')
        else:
            flash('No account found with that email.', 'error')
    return render_template('vx_creator_login.html')


@app.route('/creator/terms', methods=['GET', 'POST'])
def creator_terms():
    ca_id = session.get('creator_account_id')
    if not ca_id:
        return redirect(url_for('creator_login'))
    ca = CreatorAccount.query.get(ca_id)
    if request.method == 'POST':
        ca.terms_accepted = True
        ca.terms_accepted_at = datetime.utcnow()
        ta = TermsAcceptance(user_id=ca.user_id, ip_address=request.remote_addr)
        db.session.add(ta)
        db.session.commit()
        return redirect(url_for('creator_home'))
    return render_template('vx_creator_terms.html')


@app.route('/creator/logout')
def creator_logout():
    session.pop('creator_account_id', None)
    session.pop('creator_user_id', None)
    session.pop('creator_profile_id', None)
    return redirect(url_for('creator_login'))


@app.route('/creator/home')
@creator_required
def creator_home():
    ca = CreatorAccount.query.get(session['creator_account_id'])
    profile = ca.profile
    user_id = ca.user_id
    pending, available, lifetime = get_user_balances(user_id)
    breakdown = get_user_revenue_breakdown(user_id)

    # Revenue by period
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start  = today_start - timedelta(days=now.weekday())
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def period_earnings(start):
        return db.session.query(db.func.sum(EarningsRecord.amount))\
            .filter(EarningsRecord.beneficiary_user_id==user_id,
                    EarningsRecord.created_at>=start).scalar() or 0.0

    today_rev   = period_earnings(today_start)
    weekly_rev  = period_earnings(week_start)
    monthly_rev = period_earnings(month_start)

    # Subscriber count
    subscriber_count = Subscription.query.filter_by(profile_id=profile.id, status='active').count()

    # Show telegram channels popup
    show_telegram = session.pop('show_creator_telegram', False)
    creator_channels = TelegramChannel.query.filter_by(channel_type='creator', is_active=True).all()

    withdrawal_open = is_withdrawal_day()
    next_window = next_withdrawal_day()

    return render_template('vx_creator_home.html',
        ca=ca, profile=profile,
        pending=pending, available=available, lifetime=lifetime,
        breakdown=breakdown,
        today_rev=today_rev, weekly_rev=weekly_rev, monthly_rev=monthly_rev,
        subscriber_count=subscriber_count,
        show_telegram=show_telegram,
        creator_channels=creator_channels,
        withdrawal_open=withdrawal_open,
        next_window=next_window
    )


@app.route('/manager/edit-profile', methods=['GET', 'POST'])
@manager_required
def manager_edit_profile():
    """Creator manager edits the profile they manage."""
    user_id = session.get('user_id')
    profile = Profile.query.filter_by(manager_id=user_id).first_or_404()

    categories = Category.query.filter_by(is_active=True).all()
    blur = get_blur_settings(profile.id)

    if request.method == 'POST':
        profile.name        = request.form.get('name', profile.name).strip()
        profile.bio          = request.form.get('bio', profile.bio).strip()
        profile.tagline      = request.form.get('tagline', profile.tagline).strip()
        profile.category     = request.form.get('category', profile.category).strip()
        profile.accent_color = request.form.get('accent_color', profile.accent_color).strip()
        profile.country_code = request.form.get('country_code', profile.country_code).strip()

        # ── Blur strength — the creator/manager controls this, not admin ────
        blur.photo_blur = max(0, min(40, int(request.form.get('photo_blur', blur.photo_blur) or blur.photo_blur)))
        blur.video_blur = max(0, min(40, int(request.form.get('video_blur', blur.video_blur) or blur.video_blur)))
        blur.updated_at = datetime.utcnow()

        # ── Manager account credentials (manager = account owner) ──────────
        if not is_admin:
            manager_user = User.query.get(user_id)
            if manager_user:
                new_email = request.form.get('email', '').strip().lower()
                if new_email and new_email != manager_user.email and not User.query.filter_by(email=new_email).first():
                    manager_user.email = new_email
                new_pass = request.form.get('new_password', '').strip()
                if new_pass and len(new_pass) >= 6:
                    manager_user.password_hash = generate_password_hash(new_pass)

        # ── Social links — fully dynamic, no fixed platform list ────────────
        SocialLink.query.filter_by(profile_id=profile.id).delete()
        platforms = request.form.getlist('social_platform[]')
        urls      = request.form.getlist('social_url[]')
        for i, (plat, url) in enumerate(zip(platforms, urls)):
            plat = plat.strip().lower()
            url  = url.strip()
            if plat and url:
                db.session.add(SocialLink(
                    profile_id=profile.id, platform=plat, url=url, sort_order=i
                ))

        # Avatar upload from device (file takes priority, no URL fallback required)
        avatar_file = request.files.get('avatar')
        if avatar_file and avatar_file.filename and allowed_image(avatar_file.filename):
            ext = avatar_file.filename.rsplit('.', 1)[1].lower()
            fname = 'avatar_{}_{}.{}'.format(profile.id, int(time.time()), ext)
            save_path = os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], fname)
            avatar_file.save(save_path)
            profile.avatar_filename = fname

        # Cover upload from device
        cover_file = request.files.get('cover')
        if cover_file and cover_file.filename and allowed_image(cover_file.filename):
            ext = cover_file.filename.rsplit('.', 1)[1].lower()
            fname = 'cover_{}_{}.{}'.format(profile.id, int(time.time()), ext)
            save_path = os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], fname)
            cover_file.save(save_path)
            profile.cover_filename = fname

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('creator_dashboard'))

    social_links = SocialLink.query.filter_by(profile_id=profile.id).order_by(SocialLink.sort_order).all()
    manager_user = User.query.get(user_id) if not is_admin else None
    return render_template('creator_edit_profile.html',
                           profile=profile,
                           categories=categories,
                           blur=blur,
                           social_links=social_links,
                           manager_user=manager_user,
                           COUNTRY_FLAGS=COUNTRY_FLAGS,
                           COUNTRY_NAMES=COUNTRY_NAMES)


@app.route('/creator/edit-profile', methods=['GET', 'POST'])
@creator_required
def creator_edit_profile():
    ca = CreatorAccount.query.get(session['creator_account_id'])
    profile = ca.profile
    user = ca.user
    blur = get_blur_settings(profile.id)

    if request.method == 'POST':
        profile.name        = request.form.get('name', profile.name).strip()
        profile.username    = request.form.get('username', profile.username).strip().lower()
        profile.bio         = request.form.get('bio', profile.bio).strip()
        profile.country_code= request.form.get('country_code', profile.country_code).strip()
        profile.category    = request.form.get('category', profile.category).strip()

        # Avatar — file upload takes priority over URL
        avatar_file = request.files.get('avatar_file')
        if avatar_file and avatar_file.filename and allowed_image(avatar_file.filename):
            ext = avatar_file.filename.rsplit('.', 1)[1].lower()
            fname = 'avatar_{}_{}.{}'.format(profile.id, int(time.time()), ext)
            save_path = os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], fname)
            avatar_file.save(save_path)
            profile.avatar_filename = fname
        else:
            avatar_url = request.form.get('avatar_url', '').strip()
            if avatar_url:
                profile.avatar_filename = avatar_url

        # Cover — file upload takes priority over URL
        cover_file = request.files.get('cover_file')
        if cover_file and cover_file.filename and allowed_image(cover_file.filename):
            ext = cover_file.filename.rsplit('.', 1)[1].lower()
            fname = 'cover_{}_{}.{}'.format(profile.id, int(time.time()), ext)
            save_path = os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], fname)
            cover_file.save(save_path)
            profile.cover_filename = fname
        else:
            cover_url = request.form.get('cover_url', '').strip()
            if cover_url:
                profile.cover_filename = cover_url

        # Password change
        new_pass = request.form.get('new_password', '').strip()
        if new_pass and len(new_pass) >= 6:
            user.password_hash = generate_password_hash(new_pass)

        # Email change
        new_email = request.form.get('email', '').strip()
        if new_email and new_email != user.email:
            user.email = new_email

        # ── Blur strength — creator-controlled, not admin-only ──────────────
        blur.photo_blur = max(0, min(40, int(request.form.get('photo_blur', blur.photo_blur) or blur.photo_blur)))
        blur.video_blur = max(0, min(40, int(request.form.get('video_blur', blur.video_blur) or blur.video_blur)))
        blur.updated_at = datetime.utcnow()

        # ── Social links — fully dynamic, creator adds as many as they want ──
        SocialLink.query.filter_by(profile_id=profile.id).delete()
        platforms = request.form.getlist('social_platform[]')
        urls      = request.form.getlist('social_url[]')
        for i, (plat, url) in enumerate(zip(platforms, urls)):
            plat = plat.strip().lower()
            url  = url.strip()
            if plat and url:
                db.session.add(SocialLink(
                    profile_id=profile.id, platform=plat, url=url, sort_order=i
                ))

        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('creator_home'))

    categories   = Category.query.filter_by(is_active=True).all()
    social_links = SocialLink.query.filter_by(profile_id=profile.id).order_by(SocialLink.sort_order).all()
    return render_template('vx_creator_edit_profile.html', ca=ca, profile=profile, user=user,
                           categories=categories, blur=blur, social_links=social_links,
                           COUNTRY_FLAGS=COUNTRY_FLAGS, COUNTRY_NAMES=COUNTRY_NAMES)


# ─────────────────────────────────────────────────────────────────────────────
# CREATOR WITHDRAWAL
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_creator_context():
    """Returns (user_id, profile, ca_or_None) for either a sole creator or an assigned manager."""
    if session.get('creator_account_id'):
        ca = CreatorAccount.query.get(session['creator_account_id'])
        if ca:
            return ca.user_id, ca.profile, ca
    if session.get('is_manager'):
        uid = session.get('user_id')
        profile = Profile.query.filter_by(manager_id=uid).first()
        if profile:
            return uid, profile, None
    return None, None, None


@app.route('/creator/payout-methods', methods=['GET', 'POST'])
def creator_payout_methods():
    user_id, profile, ca = _resolve_creator_context()
    if not user_id:
        return redirect(url_for('creator_login'))
    if request.method == 'POST':
        method_type = request.form.get('method_type', 'mpesa')
        pm = PayoutMethod(
            user_id     = user_id,
            method_type = method_type,
            mpesa_number= request.form.get('mpesa_number','').strip(),
            bank_name   = request.form.get('bank_name','').strip(),
            bank_account= request.form.get('bank_account','').strip(),
            paypal_email= request.form.get('paypal_email','').strip(),
            crypto_wallet=request.form.get('crypto_wallet','').strip(),
            crypto_type = request.form.get('crypto_type','USDT').strip(),
            is_default  = True
        )
        PayoutMethod.query.filter_by(user_id=user_id, is_default=True).update({'is_default': False})
        db.session.add(pm)
        db.session.commit()
        flash('Payout method saved!', 'success')
        return redirect(url_for('creator_payout_methods'))
    methods = PayoutMethod.query.filter_by(user_id=user_id).all()
    return render_template('vx_payout_methods.html', ca=ca, profile=profile, methods=methods)


@app.route('/creator/withdraw', methods=['GET', 'POST'])
def creator_withdraw():
    user_id, profile, ca = _resolve_creator_context()
    if not user_id:
        return redirect(url_for('creator_login'))

    if not is_withdrawal_day():
        next_win = next_withdrawal_day()
        return render_template('vx_withdrawal_closed.html', next_window=next_win, ca=ca)

    pending, available, lifetime = get_user_balances(user_id)
    methods = PayoutMethod.query.filter_by(user_id=user_id).all()

    if request.method == 'POST':
        amount = float(request.form.get('amount', 0))
        method_id = request.form.get('payout_method_id')

        if amount <= 0 or amount > available:
            flash('Invalid amount. You can only withdraw available balance.', 'error')
            return redirect(url_for('creator_withdraw'))

        if not method_id:
            flash('Please select a payout method.', 'error')
            return redirect(url_for('creator_withdraw'))

        pm = PayoutMethod.query.get(method_id)
        if not pm or pm.user_id != user_id:
            flash('Invalid payout method.', 'error')
            return redirect(url_for('creator_withdraw'))

        snapshot = json.dumps({
            'type': pm.method_type,
            'mpesa': pm.mpesa_number,
            'bank': pm.bank_name,
            'account': pm.bank_account,
            'paypal': pm.paypal_email,
            'crypto': pm.crypto_wallet,
            'crypto_type': pm.crypto_type
        })

        wr = WithdrawalRequest(
            user_id=user_id,
            amount=amount,
            payout_method_id=pm.id,
            method_snapshot=snapshot,
            status='pending'
        )
        db.session.add(wr)
        db.session.commit()

        if not lock_earnings_for_withdrawal(user_id, amount, wr):
            db.session.delete(wr)
            db.session.commit()
            flash('Could not lock funds — please refresh and try again.', 'error')
            return redirect(url_for('creator_withdraw'))

        flash('Withdrawal request submitted! Admin will process it soon.', 'success')
        if ca:
            return redirect(url_for('creator_home'))
        return redirect(url_for('creator_dashboard'))

    return render_template('vx_withdraw.html',
        ca=ca, profile=profile, available=available, pending=pending, lifetime=lifetime, methods=methods)


@app.route('/creator/withdrawal-history')
def creator_withdrawal_history():
    user_id, profile, ca = _resolve_creator_context()
    if not user_id:
        return redirect(url_for('creator_login'))
    requests_list = WithdrawalRequest.query.filter_by(user_id=user_id)\
        .order_by(WithdrawalRequest.requested_at.desc()).all()
    return render_template('vx_withdrawal_history.html', ca=ca, profile=profile, requests=requests_list)


# ─────────────────────────────────────────────────────────────────────────────
# DM SYSTEM
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/dm/<username>')
def dm_thread(username):
    """Subscriber opens DM with a creator."""
    if not session.get('user_id'):
        return redirect(url_for('login'))
    profile = Profile.query.filter_by(username=username, is_active=True).first_or_404()
    user_id = session['user_id']
    thread = DMThread.query.filter_by(subscriber_user_id=user_id, profile_id=profile.id).first()
    if not thread:
        thread = DMThread(subscriber_user_id=user_id, profile_id=profile.id)
        db.session.add(thread)
        db.session.commit()
    messages = DMMessage.query.filter_by(thread_id=thread.id).order_by(DMMessage.created_at).all()
    return render_template('vx_dm_thread.html', thread=thread, profile=profile, messages=messages)


@app.route('/dm/<username>/send', methods=['POST'])
def dm_send(username):
    if not session.get('user_id'):
        return jsonify({'error': 'Login required'}), 401
    profile = Profile.query.filter_by(username=username, is_active=True).first_or_404()

    # Check DM settings
    dm_cfg = DMSettings.query.filter_by(profile_id=profile.id).first()
    if dm_cfg and not dm_cfg.dm_enabled:
        return jsonify({'error': 'DMs are disabled for this creator.'}), 403

    user_id = session['user_id']
    thread = DMThread.query.filter_by(subscriber_user_id=user_id, profile_id=profile.id).first()
    if not thread:
        thread = DMThread(subscriber_user_id=user_id, profile_id=profile.id)
        db.session.add(thread)
        db.session.flush()

    body = (request.form.get('body') or request.get_json(silent=True, force=True) or {}).get('body', '') if request.is_json else request.form.get('body', '')
    if not body and not request.is_json:
        body = request.form.get('body', '')

    # If creator charges per message, record a transaction
    charge = dm_cfg.msg_price if (dm_cfg and dm_cfg.charge_per_msg and dm_cfg.msg_price > 0) else 0
    if charge > 0:
        tok = get_session_token()
        tx = VaultTransaction(
            reference=make_transaction_ref(),
            subscriber_user_id=user_id,
            session_token=tok,
            profile_id=profile.id,
            content_type='dm',
            gateway='stripe',
            gross_amount=charge,
            status='completed'
        )
        db.session.add(tx)
        db.session.flush()
        split_revenue(tx)

    msg = DMMessage(
        thread_id=thread.id,
        sender_type='subscriber',
        sender_user_id=user_id,
        body=body.strip()[:2000],
        charge_enabled=(dm_cfg.charge_per_msg if dm_cfg else False),
        message_price=charge
    )
    db.session.add(msg)
    thread.last_message_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True, 'id': msg.id, 'charge': charge})


@app.route('/creator/application-status')
def creator_application_status():
    """Creator manager can see their own application status."""
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('creator_login'))
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('creator_login'))
    # Find their application by email
    app_record = CreatorApplication.query.filter_by(
        applicant_email=user.email
    ).order_by(CreatorApplication.created_at.desc()).first()
    profile = Profile.query.filter_by(manager_id=user_id).first()
    return render_template('creator_application_status.html',
                           app_record=app_record, user=user, profile=profile)


@app.route('/creator/dm-settings', methods=['GET', 'POST'])
def creator_dm_settings():
    """Creator/Manager controls DM inbox monetization."""
    user_id, profile, ca = _resolve_creator_context()
    if not user_id or not profile:
        return redirect(url_for('creator_login'))

    settings = DMSettings.query.filter_by(profile_id=profile.id).first()
    if not settings:
        settings = DMSettings(profile_id=profile.id)
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        settings.dm_enabled     = request.form.get('dm_enabled') == 'on'
        settings.charge_per_msg = request.form.get('charge_per_msg') == 'on'
        settings.msg_price      = max(0.0, float(request.form.get('msg_price', 1.0) or 1.0))
        settings.auto_reply_text= request.form.get('auto_reply_text', '').strip()[:500]
        settings.updated_at     = datetime.utcnow()
        db.session.commit()
        flash('DM settings updated!', 'success')
        if ca:
            return redirect(url_for('creator_home'))
        return redirect(url_for('creator_dashboard'))

    return render_template('creator_dm_settings.html', ca=ca, profile=profile, settings=settings)


@app.route('/creator/dm-inbox')
def creator_dm_inbox():
    # Allow both sole creators and assigned managers
    if session.get('creator_account_id'):
        ca = CreatorAccount.query.get(session['creator_account_id'])
        if not ca:
            return redirect(url_for('creator_login'))
        profile_id = ca.profile_id
        threads = DMThread.query.filter_by(profile_id=profile_id)\
            .order_by(DMThread.last_message_at.desc()).all()
        return render_template('vx_creator_dm_inbox.html', ca=ca, threads=threads)
    elif session.get('is_manager'):
        user_id = session.get('user_id')
        profile = Profile.query.filter_by(manager_id=user_id).first()
        if not profile:
            flash('No creator profile assigned to your account.', 'error')
            return redirect(url_for('creator_dashboard'))
        threads = DMThread.query.filter_by(profile_id=profile.id)\
            .order_by(DMThread.last_message_at.desc()).all()
        return render_template('vx_creator_dm_inbox.html', ca=None, profile=profile, threads=threads)
    return redirect(url_for('creator_login'))


@app.route('/creator/dm-thread/<int:thread_id>', methods=['GET', 'POST'])
def creator_dm_reply(thread_id):
    # Resolve who is replying — sole creator or manager
    ca = None
    profile = None
    sender_user_id = None

    if session.get('creator_account_id'):
        ca = CreatorAccount.query.get(session['creator_account_id'])
        if not ca:
            return redirect(url_for('creator_login'))
        profile_id = ca.profile_id
        sender_user_id = ca.user_id
    elif session.get('is_manager'):
        user_id = session.get('user_id')
        profile = Profile.query.filter_by(manager_id=user_id).first()
        if not profile:
            return redirect(url_for('creator_dashboard'))
        profile_id = profile.id
        sender_user_id = user_id
    else:
        return redirect(url_for('creator_login'))

    thread = DMThread.query.filter_by(id=thread_id, profile_id=profile_id).first_or_404()

    if request.method == 'POST':
        body        = request.form.get('body', '').strip()
        lock_price  = float(request.form.get('lock_price', 0) or 0)
        media_url   = request.form.get('media_url', '').strip()
        media_type  = request.form.get('media_type', '').strip()

        msg = DMMessage(
            thread_id=thread.id,
            sender_type='creator',
            sender_user_id=sender_user_id,
            body=body[:2000],
            media_url=media_url,
            media_type=media_type,
            lock_price=lock_price,
            is_unlocked=(lock_price == 0)
        )
        db.session.add(msg)
        thread.last_message_at = datetime.utcnow()
        db.session.commit()
        flash('Message sent!', 'success')
        return redirect(url_for('creator_dm_reply', thread_id=thread_id))

    messages = DMMessage.query.filter_by(thread_id=thread.id).order_by(DMMessage.created_at).all()
    return render_template('vx_creator_dm_reply.html', ca=ca, profile=profile, thread=thread, messages=messages)


@app.route('/dm/unlock/<int:msg_id>', methods=['POST'])
def dm_unlock_message(msg_id):
    """Subscriber pays to unlock a locked DM via a real Stripe Checkout session.

    The transaction is only marked 'completed' by the /payments/stripe/webhook
    handler once Stripe confirms the payment actually happened — this route
    never grants access on its own.
    """
    if not session.get('user_id'):
        return jsonify({'error': 'Login required'}), 401
    msg = DMMessage.query.get_or_404(msg_id)
    if msg.is_unlocked or msg.lock_price <= 0:
        return jsonify({'ok': True, 'already_unlocked': True})

    thread  = msg.thread
    profile = thread.profile
    user_id = session['user_id']
    tok     = get_session_token()

    # Reuse an existing pending transaction for this message+user so that
    # re-clicking "unlock" doesn't spawn duplicate Stripe sessions/records.
    tx = VaultTransaction.query.filter_by(
        content_type='dm', content_id=msg.id,
        subscriber_user_id=user_id, status='pending'
    ).first()
    if not tx:
        tx = VaultTransaction(
            reference=make_transaction_ref(),
            subscriber_user_id=user_id,
            session_token=tok,
            profile_id=profile.id,
            content_type='dm',
            content_id=msg.id,
            gateway='stripe',
            gross_amount=msg.lock_price,
            status='pending'
        )
        db.session.add(tx)
        db.session.commit()

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Unlock message from {}'.format(profile.name),
                    },
                    'unit_amount': int(round(msg.lock_price * 100)),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('dm_thread', username=profile.username, _external=True) + '?unlocked=1',
            cancel_url=url_for('dm_thread', username=profile.username, _external=True) + '?unlock_cancelled=1',
            metadata={
                'vaultx_type': 'dm_unlock',
                'vault_ref': tx.reference,
                'session_token': tok,
            }
        )
    except Exception as e:
        print('🔥 DM unlock Stripe error:', str(e))
        return jsonify({'error': 'Could not start payment. Please try again.'}), 500

    return jsonify({'ok': True, 'checkout_url': checkout_session.url})


# ─────────────────────────────────────────────────────────────────────────────
# SUBSCRIPTION
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/subscribe/<username>', methods=['POST'])
def subscribe_to_creator(username):
    if not session.get('user_id'):
        return jsonify({'error': 'Login required'}), 401
    profile = Profile.query.filter_by(username=username, is_active=True).first_or_404()
    user_id = session['user_id']
    price   = float(request.form.get('price', 15.0))

    existing = Subscription.query.filter_by(subscriber_user_id=user_id, profile_id=profile.id, status='active').first()
    if existing:
        return jsonify({'ok': True, 'already_subscribed': True})

    tok = get_session_token()
    tx = VaultTransaction(
        reference=make_transaction_ref(),
        subscriber_user_id=user_id,
        session_token=tok,
        profile_id=profile.id,
        content_type='subscription',
        gateway='stripe',
        gross_amount=price,
        status='completed'
    )
    db.session.add(tx)
    db.session.flush()
    split_revenue(tx)

    sub = Subscription(
        subscriber_user_id=user_id,
        profile_id=profile.id,
        monthly_price=price,
        expires_at=datetime.utcnow() + timedelta(days=30),
        gateway='stripe'
    )
    db.session.add(sub)

    # Update subscriber spend
    sp = SubscriberProfile.query.filter_by(user_id=user_id).first()
    if sp:
        sp.total_spent += price
    db.session.commit()

    # After purchase → show Telegram channel
    subscriber_channels = TelegramChannel.query.filter_by(channel_type='subscriber', is_active=True).all()
    telegram_links = [c.channel_url for c in subscriber_channels]
    return jsonify({'ok': True, 'telegram_channels': telegram_links})


# ─────────────────────────────────────────────────────────────────────────────
# TIPPING
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/tip/<username>', methods=['POST'])
def send_tip(username):
    if not session.get('user_id'):
        return jsonify({'error': 'Login required'}), 401
    profile = Profile.query.filter_by(username=username, is_active=True).first_or_404()
    amount  = float(request.get_json(force=True, silent=True).get('amount', 0) or request.form.get('amount', 0))
    message = (request.get_json(force=True, silent=True) or {}).get('message', request.form.get('message', ''))
    if amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400
    tok = get_session_token()
    tx = VaultTransaction(
        reference=make_transaction_ref(),
        subscriber_user_id=session['user_id'],
        session_token=tok,
        profile_id=profile.id,
        content_type='tip',
        gateway='stripe',
        gross_amount=amount,
        status='completed'
    )
    db.session.add(tx)
    db.session.flush()
    split_revenue(tx)
    tip = Tip(
        subscriber_user_id=session['user_id'],
        session_token=tok,
        profile_id=profile.id,
        amount=amount,
        message=message[:300],
        transaction_id=tx.id
    )
    db.session.add(tip)
    db.session.commit()
    return jsonify({'ok': True})


# ─────────────────────────────────────────────────────────────────────────────
# SUBSCRIBER DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/my/dashboard')
def subscriber_dashboard():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    user_id = session['user_id']
    user = db.session.get(User, user_id)

    sp = SubscriberProfile.query.filter_by(user_id=user_id).first()
    if not sp:
        sp = SubscriberProfile(user_id=user_id)
        db.session.add(sp)
        db.session.commit()

    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Spending stats
    txs = VaultTransaction.query.filter_by(subscriber_user_id=user_id, status='completed').all()
    total_spent  = sum(t.gross_amount for t in txs)
    this_month   = sum(t.gross_amount for t in txs if t.created_at >= month_start)
    photos_bought  = sum(1 for t in txs if t.content_type == 'photo')
    videos_bought  = sum(1 for t in txs if t.content_type == 'video')
    dm_purchases   = sum(1 for t in txs if t.content_type == 'dm')
    subs_count     = Subscription.query.filter_by(subscriber_user_id=user_id, status='active').count()
    tips_sent      = Tip.query.filter_by(subscriber_user_id=user_id).count()

    # Favorite creators (most transacted)
    from sqlalchemy import func
    fav_creators = db.session.query(Profile, func.count(VaultTransaction.id).label('cnt'))\
        .join(VaultTransaction, VaultTransaction.profile_id == Profile.id)\
        .filter(VaultTransaction.subscriber_user_id == user_id)\
        .group_by(Profile.id).order_by(func.count(VaultTransaction.id).desc()).limit(5).all()

    # Active subscriptions
    active_subs = Subscription.query.filter_by(subscriber_user_id=user_id, status='active').all()

    # Recent purchases
    recent_txs = VaultTransaction.query.filter_by(subscriber_user_id=user_id, status='completed')\
        .order_by(VaultTransaction.created_at.desc()).limit(20).all()

    # DM threads
    threads = DMThread.query.filter_by(subscriber_user_id=user_id)\
        .order_by(DMThread.last_message_at.desc()).limit(10).all()

    return render_template('vx_subscriber_dashboard.html',
        user=user, sp=sp,
        total_spent=total_spent, this_month=this_month,
        photos_bought=photos_bought, videos_bought=videos_bought,
        dm_purchases=dm_purchases, subs_count=subs_count, tips_sent=tips_sent,
        fav_creators=fav_creators,
        active_subs=active_subs,
        recent_txs=recent_txs,
        threads=threads
    )


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — VAULTX MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/admin/vaultx')
@admin_required
def admin_vaultx_dashboard():
    """VaultX main admin hub."""
    # Revenue totals
    total_revenue = db.session.query(db.func.sum(VaultTransaction.gross_amount))\
        .filter(VaultTransaction.status=='completed').scalar() or 0.0
    platform_earnings = db.session.query(db.func.sum(EarningsRecord.amount))\
        .filter(EarningsRecord.beneficiary_type=='platform').scalar() or 0.0
    pending_withdrawals = WithdrawalRequest.query.filter_by(status='pending').count()
    total_subscribers = User.query.filter_by(role='subscriber').count()
    total_creators    = User.query.filter_by(role='creator').count()
    total_managers    = User.query.filter_by(role='creator_manager').count()
    total_ops         = User.query.filter_by(role='ops_manager').count()

    # Recent transactions
    recent_txs = VaultTransaction.query.order_by(VaultTransaction.created_at.desc()).limit(15).all()

    split = get_revenue_split()

    return render_template('vx_admin_dashboard.html',
        total_revenue=total_revenue,
        platform_earnings=platform_earnings,
        pending_withdrawals=pending_withdrawals,
        total_subscribers=total_subscribers,
        total_creators=total_creators,
        total_managers=total_managers,
        total_ops=total_ops,
        recent_txs=recent_txs,
        split=split
    )


@app.route('/admin/vaultx/revenue-split', methods=['GET', 'POST'])
@admin_required
def admin_revenue_split():
    split = get_revenue_split()
    if request.method == 'POST':
        split.creator_pct     = float(request.form.get('creator_pct', 75))
        split.ops_manager_pct = float(request.form.get('ops_manager_pct', 5))
        split.manager_pct     = float(request.form.get('manager_pct', 10))
        split.platform_pct    = float(request.form.get('platform_pct', 10))
        split.updated_at      = datetime.utcnow()
        db.session.commit()
        flash('Revenue split updated!', 'success')
    return render_template('vx_admin_revenue_split.html', split=split)


@app.route('/admin/vaultx/withdrawals')
@admin_required
def admin_withdrawals():
    status = request.args.get('status', 'pending')
    wrs = WithdrawalRequest.query.filter_by(status=status)\
        .order_by(WithdrawalRequest.requested_at.desc()).all()
    return render_template('vx_admin_withdrawals.html', wrs=wrs, status=status)


@app.route('/admin/vaultx/withdrawal/<int:wr_id>/approve', methods=['POST'])
@admin_required
def admin_approve_withdrawal(wr_id):
    wr = WithdrawalRequest.query.get_or_404(wr_id)
    wr.status       = 'approved'
    wr.processed_at = datetime.utcnow()
    wr.admin_note   = request.form.get('note', '').strip()
    db.session.commit()
    flash('Withdrawal approved.', 'success')
    return redirect(url_for('admin_withdrawals'))


@app.route('/admin/vaultx/withdrawal/<int:wr_id>/paid', methods=['POST'])
@admin_required
def admin_mark_withdrawal_paid(wr_id):
    wr = WithdrawalRequest.query.get_or_404(wr_id)
    wr.status = 'paid'
    wr.processed_at = datetime.utcnow()
    # Only the earnings records locked specifically to THIS withdrawal request
    # are consumed — never touches any other balance the user may have earned since.
    EarningsRecord.query.filter_by(withdrawal_request_id=wr.id)\
        .update({'is_available': False})
    db.session.commit()
    flash('Withdrawal marked as paid.', 'success')
    return redirect(url_for('admin_withdrawals'))


@app.route('/admin/vaultx/withdrawal/<int:wr_id>/reject', methods=['POST'])
@admin_required
def admin_reject_withdrawal(wr_id):
    wr = WithdrawalRequest.query.get_or_404(wr_id)
    wr.status       = 'rejected'
    wr.processed_at = datetime.utcnow()
    wr.admin_note   = request.form.get('note', '').strip()
    # Crucial: release the locked earnings back to available balance since the
    # withdrawal didn't go through — otherwise that money would be stuck forever.
    release_locked_earnings(wr)
    db.session.commit()
    flash('Withdrawal rejected — funds released back to available balance.', 'warning')
    return redirect(url_for('admin_withdrawals'))


@app.route('/admin/vaultx/create-operations-manager', methods=['GET', 'POST'])
@admin_required
def admin_create_ops_manager():
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        if not all([name, email, password]):
            flash('All fields required.', 'error')
            return redirect(url_for('admin_create_ops_manager'))
        if User.query.filter_by(email=email).first():
            flash('Email already in use.', 'error')
            return redirect(url_for('admin_create_ops_manager'))
        user = User(email=email, password_hash=generate_password_hash(password), role='ops_manager')
        db.session.add(user)
        db.session.flush()
        om = OperationsManager(user_id=user.id, name=name)
        db.session.add(om)
        db.session.commit()
        flash('Operations Manager created!', 'success')
        return redirect(url_for('admin_vaultx_dashboard'))
    return render_template('vx_admin_create_ops_manager.html')


@app.route('/ops/create-junior-creator', methods=['GET', 'POST'])
@ops_manager_required
def ops_create_junior_creator():
    """Ops Manager creates a Junior Creator account linked to a new profile.
    Junior Creator logs in at /creator/login and can upload immediately.
    They auto-promote to full Creator after 4 photo sales + 4 video sales.
    """
    ops_managers = OperationsManager.query.all()
    # Profiles not yet assigned to any manager and not already a sole creator account
    available_profiles = Profile.query.filter(
        Profile.manager_id.is_(None),
        Profile.account_type != 'sole_creator'
    ).filter_by(is_active=True).all()

    if request.method == 'POST':
        name        = request.form.get('name', '').strip()
        email       = request.form.get('email', '').strip().lower()
        password    = request.form.get('password', '').strip()
        username    = request.form.get('username', '').strip().lower().replace(' ', '_')
        ops_id      = request.form.get('ops_manager_id', type=int)
        profile_id  = request.form.get('profile_id', type=int)
        create_new_profile = request.form.get('create_new_profile') == 'on'

        if not all([name, email, password]):
            flash('Name, email and password are required.', 'error')
            return redirect(url_for('ops_create_junior_creator'))
        if User.query.filter_by(email=email).first():
            flash('Email already in use.', 'error')
            return redirect(url_for('ops_create_junior_creator'))
        if username and User.query.filter_by(username=username).first():
            flash('Username already in use.', 'error')
            return redirect(url_for('ops_create_junior_creator'))

        junior_user = User(
            email=email, username=username or None,
            password_hash=generate_password_hash(password),
            role='junior_creator'
        )
        db.session.add(junior_user)
        db.session.flush()

        # Create a fresh profile for the Junior Creator
        profile = None
        if create_new_profile or not profile_id:
            new_username = username or 'creator_{}'.format(junior_user.id)
            base_username = new_username
            i = 1
            while Profile.query.filter_by(username=new_username).first():
                i += 1
                new_username = '{}_{}'.format(base_username, i)
            profile = Profile(
                name=name, username=new_username, is_active=True,
                account_type='junior_creator'
            )
            db.session.add(profile)
            db.session.flush()
        elif profile_id:
            profile = Profile.query.get(profile_id)
            if profile:
                profile.account_type = 'junior_creator'

        if profile:
            ops_uid = session.get('ops_user_id') or session.get('user_id')
            om_rec = OperationsManager.query.filter_by(user_id=ops_uid).first()
            if om_rec and hasattr(profile, 'assigned_by_ops_id'):
                profile.assigned_by_ops_id = om_rec.user_id
            # Link CreatorAccount so junior creator can log in at /creator/login
            existing_ca = CreatorAccount.query.filter_by(profile_id=profile.id).first()
            if not existing_ca:
                db.session.add(CreatorAccount(
                    user_id=junior_user.id,
                    profile_id=profile.id,
                    terms_accepted=False
                ))
            db.session.commit()
            emailed = send_account_grant_email(email, name, password, role='junior_creator')
            if emailed:
                flash('Junior Creator account created for "{}". They log in at /creator/login '
                      'and auto-promote after {} photo + {} video sales. Login details were emailed to {}.'.format(
                          name, GRADUATION_MIN_PHOTOS, GRADUATION_MIN_VIDEOS, email), 'success')
            else:
                flash('Junior Creator account created for "{}", but the welcome email failed to send. '
                      'Please share the login details with them manually: {} / {}'.format(
                          name, email, password), 'warning')
        else:
            db.session.commit()
            emailed = send_account_grant_email(email, name, password, role='junior_creator')
            if emailed:
                flash('Junior Creator account created — no profile assigned. Login details were emailed to {}.'.format(email), 'warning')
            else:
                flash('Junior Creator account created — no profile assigned, and the welcome email failed to send. '
                      'Please share the login details manually: {} / {}'.format(email, password), 'warning')

        return redirect(url_for('ops_dashboard'))

    return render_template('vx_ops_create_junior_creator.html',
                           ops_managers=ops_managers,
                           available_profiles=available_profiles)


# NOTE: Direct Creator account creation has been permanently removed.
# All creators must go through: Application → Junior Creator → 4+4 sales →
# automatic promotion to Creator (see check_graduation / _graduate_to_sole_creator).
# There is intentionally no /ops/create-creator route or equivalent code path.


@app.route('/admin/vaultx/telegram-channels', methods=['GET', 'POST'])
@admin_required
def admin_telegram_channels():
    if request.method == 'POST':
        name         = request.form.get('name', '').strip()
        channel_url  = request.form.get('channel_url', '').strip()
        channel_type = request.form.get('channel_type', 'subscriber')
        tc = TelegramChannel(name=name, channel_url=channel_url, channel_type=channel_type)
        db.session.add(tc)
        db.session.commit()
        flash('Channel added!', 'success')
        return redirect(url_for('admin_telegram_channels'))
    channels = TelegramChannel.query.order_by(TelegramChannel.created_at.desc()).all()
    return render_template('vx_admin_telegram_channels.html', channels=channels)


@app.route('/admin/vaultx/telegram-channels/<int:tc_id>/delete', methods=['POST'])
@admin_required
def admin_delete_telegram_channel(tc_id):
    tc = TelegramChannel.query.get_or_404(tc_id)
    db.session.delete(tc)
    db.session.commit()
    flash('Channel removed.', 'success')
    return redirect(url_for('admin_telegram_channels'))


@app.route('/admin/vaultx/transactions')
@admin_required
def admin_vaultx_transactions():
    page = request.args.get('page', 1, type=int)
    txs = VaultTransaction.query.order_by(VaultTransaction.created_at.desc()).paginate(page=page, per_page=30)
    return render_template('vx_admin_transactions.html', txs=txs)


@app.route('/admin/vaultx/earnings')
@admin_required
def admin_vaultx_earnings():
    """Platform earnings and per-creator breakdown."""
    from sqlalchemy import func
    # Per creator earnings
    creator_earnings = db.session.query(
        Profile.name, Profile.username,
        func.sum(EarningsRecord.amount).label('total'),
        func.sum(db.case((EarningsRecord.is_available==True, EarningsRecord.amount), else_=0)).label('available')
    ).join(EarningsRecord, EarningsRecord.profile_id==Profile.id)\
     .filter(EarningsRecord.beneficiary_type=='creator')\
     .group_by(Profile.id).order_by(func.sum(EarningsRecord.amount).desc()).all()

    # Platform total
    platform_total = db.session.query(func.sum(EarningsRecord.amount))\
        .filter(EarningsRecord.beneficiary_type=='platform').scalar() or 0

    return render_template('vx_admin_earnings.html',
        creator_earnings=creator_earnings,
        platform_total=platform_total
    )


@app.route('/admin/vaultx/mark-available', methods=['POST'])
@admin_required
def admin_mark_earnings_available():
    """Admin action: make pending earnings available for withdrawal."""
    user_id = request.form.get('user_id', type=int)
    if user_id:
        EarningsRecord.query.filter_by(beneficiary_user_id=user_id, is_available=False)\
            .update({'is_available': True})
        db.session.commit()
        flash('Earnings marked as available.', 'success')
    return redirect(url_for('admin_vaultx_earnings'))


@app.route('/admin/vaultx/send-admin-dm', methods=['GET', 'POST'])
@admin_required
def admin_send_platform_dm():
    """Admin sends a styled notice to all active DM threads."""
    if request.method == 'POST':
        body      = request.form.get('body', '').strip()
        target    = request.form.get('target', 'all')  # all / profile_id
        profile_id = request.form.get('profile_id', type=int)
        if not body:
            flash('Message body is required.', 'error')
            return redirect(url_for('admin_send_platform_dm'))
        if target == 'all':
            threads = DMThread.query.all()
        else:
            threads = DMThread.query.filter_by(profile_id=profile_id).all()
        for thread in threads:
            msg = DMMessage(
                thread_id=thread.id,
                sender_type='admin',
                sender_user_id=None,
                body=body,
                is_admin_notice=True
            )
            db.session.add(msg)
            thread.last_message_at = datetime.utcnow()
        db.session.commit()
        flash(f'Admin notice sent to {len(threads)} threads.', 'success')
        return redirect(url_for('admin_send_platform_dm'))
    profiles = Profile.query.filter_by(is_active=True).all()
    return render_template('vx_admin_send_dm.html', profiles=profiles)


# ─────────────────────────────────────────────────────────────────────────────
# OPERATIONS MANAGER PORTAL
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/ops/login', methods=['GET', 'POST'])
def ops_login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(email=email, role='ops_manager').first()
        if user and check_password_hash(user.password_hash, password):
            session['ops_user_id'] = user.id
            session['user_role']   = 'ops_manager'
            return redirect(url_for('ops_dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('vx_ops_login.html')


@app.route('/ops/dashboard')
@ops_manager_required
def ops_dashboard():
    user_id = session.get('ops_user_id') or session.get('user_id')
    om      = OperationsManager.query.filter_by(user_id=user_id).first()

    # ── Profiles managed via Profile.assigned_by_ops_id (existing system) ──
    if om and hasattr(Profile, 'assigned_by_ops_id'):
        managed_profiles = Profile.query.filter_by(assigned_by_ops_id=om.user_id).all()
    else:
        managed_profiles = []

    # ── Creator managers via CreatorManagerProfile (new system) ─────────────
    cmp_records     = CreatorManagerProfile.query.filter_by(
        ops_manager_id=om.id if om else None
    ).all() if om else []

    # Distinct creator_manager Users: from old system + new system
    old_mgr_ids = list({p.manager_id for p in managed_profiles if p.manager_id})
    new_mgr_ids = [c.user_id for c in cmp_records]
    all_mgr_ids = list(set(old_mgr_ids + new_mgr_ids))
    creator_managers = User.query.filter(User.id.in_(all_mgr_ids)).all() if all_mgr_ids else []

    all_creators = managed_profiles

    # ── Performance data per profile ────────────────────────────────────────
    creator_data = []
    for profile in all_creators:
        earnings_uid = profile.manager_id if profile.manager_id else (om.user_id if om else None)
        _, _, lifetime = get_user_balances(earnings_uid) if earnings_uid else (0, 0, 0)
        creator_data.append({'profile': profile, 'lifetime': lifetime})

    # ── Pending applications (ops manager reviews these) ────────────────────
    # pending_applications = list for template iteration
    # pending_count = integer badge count
    pending_applications = CreatorApplication.query.filter_by(
        status='pending'
    ).order_by(CreatorApplication.created_at.desc()).limit(10).all()
    pending_count_ops = CreatorApplication.query.filter_by(status='pending').count()

    return render_template('vx_ops_dashboard.html',
        om=om,
        creator_managers=creator_managers,
        all_creators=all_creators,
        creator_data=creator_data,
        pending_applications=pending_applications,
        pending_count=pending_count_ops
    )


# ─────────────────────────────────────────────────────────────────────────────
# CREATOR MANAGER PORTAL
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/manager/login', methods=['GET', 'POST'])
def manager_login_vx():
    if request.method == 'POST':
        email    = request.form.get('email','').strip().lower()
        password = request.form.get('password','').strip()
        user = User.query.filter_by(email=email, role='creator_manager').first()
        if user and check_password_hash(user.password_hash, password):
            session['manager_vx_user_id'] = user.id
            session['user_role'] = 'creator_manager'
            return redirect(url_for('manager_vx_dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('vx_manager_login.html')


@app.route('/manager/dashboard')
def manager_vx_dashboard():
    if session.get('user_role') != 'creator_manager' and not session.get('is_admin'):
        return redirect(url_for('manager_login_vx'))
    user_id = session.get('manager_vx_user_id') or session.get('user_id')

    # Try CreatorManagerProfile first (new system); fall back to Profile.manager_id
    cmp = CreatorManagerProfile.query.filter_by(user_id=user_id).first()

    pending, available, lifetime = get_user_balances(user_id)
    breakdown = get_user_revenue_breakdown(user_id)

    # Profiles managed via old Profile.manager_id system
    managed_profiles = Profile.query.filter_by(manager_id=user_id, is_active=True).all()

    # Creator accounts linked via new CreatorManagerProfile system
    managed_cas = CreatorAccount.query.filter_by(
        creator_manager_id=cmp.id if cmp else None
    ).all() if cmp else []

    # Build unified stats list
    creator_stats = []
    seen_profile_ids = set()

    # From old system (Profile.manager_id)
    for profile in managed_profiles:
        if profile.id not in seen_profile_ids:
            seen_profile_ids.add(profile.id)
            # Earnings for manager-run profiles are recorded against manager's user_id
            _, _, life = get_user_balances(user_id)
            creator_stats.append({
                'profile': profile,
                'ca': None,
                'lifetime': life,
                'source': 'manager_trial'
            })

    # From new system (CreatorAccount.creator_manager_id)
    for ca in managed_cas:
        if ca.profile_id not in seen_profile_ids:
            seen_profile_ids.add(ca.profile_id)
            _, _, life = get_user_balances(ca.user_id)
            creator_stats.append({
                'profile': ca.profile,
                'ca': ca,
                'lifetime': life,
                'source': 'sole_creator'
            })

    withdrawal_open = is_withdrawal_day()
    next_win = next_withdrawal_day()

    return render_template('vx_manager_dashboard.html',
        cmp=cmp, pending=pending, available=available, lifetime=lifetime,
        breakdown=breakdown, creator_stats=creator_stats,
        withdrawal_open=withdrawal_open, next_window=next_win
    )


@app.route('/manager/withdraw', methods=['GET', 'POST'])
def manager_withdraw():
    if session.get('user_role') != 'creator_manager' and not session.get('is_admin'):
        return redirect(url_for('manager_login_vx'))
    user_id = session.get('manager_vx_user_id') or session.get('user_id')

    if not is_withdrawal_day():
        return render_template('vx_withdrawal_closed.html', next_window=next_withdrawal_day())

    pending, available, lifetime = get_user_balances(user_id)
    methods = PayoutMethod.query.filter_by(user_id=user_id).all()

    if request.method == 'POST':
        amount = float(request.form.get('amount', 0))
        method_id = request.form.get('payout_method_id')
        if amount <= 0 or amount > available:
            flash('Invalid amount.', 'error')
            return redirect(url_for('manager_withdraw'))
        pm = PayoutMethod.query.get(method_id)
        if not pm or pm.user_id != user_id:
            flash('Invalid method.', 'error')
            return redirect(url_for('manager_withdraw'))
        wr = WithdrawalRequest(
            user_id=user_id, amount=amount,
            payout_method_id=pm.id,
            method_snapshot=json.dumps({'type': pm.method_type}),
            status='pending'
        )
        db.session.add(wr)
        db.session.commit()
        flash('Withdrawal request submitted!', 'success')
        return redirect(url_for('manager_vx_dashboard'))

    return render_template('vx_withdraw.html',
        available=available, pending=pending, lifetime=lifetime, methods=methods
    )


# ─────────────────────────────────────────────────────────────────────────────
# AFTER PURCHASE — TELEGRAM REDIRECT
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/post-purchase-telegram')
def post_purchase_telegram():
    """Show subscriber Telegram join links after any purchase."""
    channels = TelegramChannel.query.filter_by(channel_type='subscriber', is_active=True).all()
    return render_template('vx_post_purchase_telegram.html', channels=channels)


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def send_account_grant_email(to_email, username, password, role='junior_creator'):
    """Send a welcome email with login credentials when an account is granted."""
    try:
        role_map = {
            'junior_creator': 'Junior Creator',
            'creator': 'Creator',
            'ops_manager': 'Ops Manager',
            'creator_manager': 'Junior Creator',  # legacy alias
        }
        role_label = role_map.get(role, 'Creator')
        msg = Message(
            subject='🎉 Your VaultX {} Account is Ready'.format(role_label),
            recipients=[to_email]
        )
        msg.html = '''
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;background:#0d0d14;color:#e0e0e0;padding:32px;border-radius:12px;">
          <h2 style="color:#C9A84C;">Welcome to VaultX 🔐</h2>
          <p>Your <strong>{role}</strong> account has been approved and set up.</p>
          <div style="background:#1a1a2e;padding:20px;border-radius:8px;margin:20px 0;">
            <p><strong>Login URL:</strong> <a href="/creator/login" style="color:#C9A84C;">/creator/login</a></p>
            <p><strong>Email:</strong> {email}</p>
            <p><strong>Username:</strong> {username}</p>
            <p><strong>Temporary Password:</strong> {password}</p>
          </div>
          <p style="color:#f87171;"><strong>⚠️ Please change your password immediately after your first login.</strong></p>
          <p style="color:#9ca3af;font-size:13px;">This is an automated message from VaultX. Do not reply.</p>
        </div>
        '''.format(role=role_label, email=to_email, username=username or to_email.split('@')[0], password=password)
        mail.send(msg)
        return True
    except Exception as e:
        print('Email send error: {}'.format(e))
        return False


def send_application_notification_email(app_record):
    """Notify admin email that a new creator application has been submitted."""
    try:
        msg = Message(
            subject='📋 New VaultX Application: {}'.format(app_record.applicant_email),
            recipients=[ADMIN_EMAIL]
        )
        msg.html = '''
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:24px;">
          <h2>New Creator Application Received</h2>
          <p><strong>Type:</strong> {app_type}</p>
          <p><strong>Name:</strong> {name}</p>
          <p><strong>Email:</strong> {email}</p>
          <p><strong>Motivation:</strong> {motivation}</p>
          <p><a href="/ops/applications" style="background:#C9A84C;color:#000;padding:10px 20px;border-radius:6px;text-decoration:none;">Review Application</a></p>
        </div>
        '''.format(
            app_type=app_record.application_type.replace('_',' ').title(),
            name=app_record.applicant_name,
            email=app_record.applicant_email,
            motivation=app_record.motivation[:300]
        )
        mail.send(msg)
    except Exception as e:
        print('Application notification email error: {}'.format(e))


# ─────────────────────────────────────────────────────────────────────────────
# AUTO-GRADUATION: manager_trial → sole_creator
# Called whenever a sale is recorded. After 4 photos + 4 videos sold over
# at least 7 days, the profile graduates automatically.
# ─────────────────────────────────────────────────────────────────────────────

GRADUATION_MIN_PHOTOS  = 4
GRADUATION_MIN_VIDEOS  = 4

def check_graduation(profile_id):
    """Check if a junior_creator (or legacy manager_trial) qualifies for full Creator promotion.

    Trigger: 4+ distinct photo sales AND 4+ distinct video sales.
    For junior_creator accounts there is no minimum days requirement — sales are the only gate.
    """
    profile = Profile.query.get(profile_id)
    if not profile or profile.account_type not in ('junior_creator', 'manager_trial'):
        return False
    # junior_creator: no day gate. manager_trial: keep legacy day gate.
    if profile.account_type == 'manager_trial':
        if not profile.manager_assigned_at:
            return False
        days_since = (datetime.utcnow() - profile.manager_assigned_at).days
        if days_since < 7:
            return False

    # Count distinct photos/videos with at least 1 sale each
    sold_photos = db.session.query(db.func.count(db.distinct(VaultTransaction.content_id)))\
        .filter(VaultTransaction.profile_id==profile_id,
                VaultTransaction.content_type=='photo',
                VaultTransaction.status=='completed').scalar() or 0
    sold_videos = db.session.query(db.func.count(db.distinct(VaultTransaction.content_id)))\
        .filter(VaultTransaction.profile_id==profile_id,
                VaultTransaction.content_type=='video',
                VaultTransaction.status=='completed').scalar() or 0

    if sold_photos >= GRADUATION_MIN_PHOTOS and sold_videos >= GRADUATION_MIN_VIDEOS:
        _graduate_to_sole_creator(profile)
        return True
    return False


def _graduate_to_sole_creator(profile):
    """Promote a junior_creator (or legacy manager_trial) profile to sole_creator.

    junior_creator path: creator already has a User + CreatorAccount → just upgrade role.
    manager_trial path: manager email becomes the new creator login (legacy behaviour).
    """
    # ── junior_creator path ──────────────────────────────────────────────────
    ca = CreatorAccount.query.filter_by(profile_id=profile.id).first()
    if ca and profile.account_type == 'junior_creator':
        creator_user = User.query.get(ca.user_id)
        if creator_user:
            creator_user.role = 'creator'
        profile.account_type = 'sole_creator'
        db.session.commit()
        try:
            if creator_user:
                send_account_grant_email(creator_user.email, profile.name or profile.username, '', role='creator')
        except Exception:
            pass
        print('✅ Profile {} promoted junior_creator → creator (sole_creator). User: {}'.format(
            profile.username, creator_user.email if creator_user else '?'))
        return

    # ── legacy manager_trial path ────────────────────────────────────────────
    manager_user = User.query.get(profile.manager_id) if profile.manager_id else None
    if not manager_user:
        return

    creator_email = manager_user.email
    temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

    existing_user = User.query.filter_by(email=creator_email).first()
    if existing_user and existing_user.role == 'creator_manager':
        existing_user.role = 'creator'
        db.session.flush()
        ca_user_id = existing_user.id
    elif existing_user:
        ca_user_id = existing_user.id
    else:
        new_user = User(
            email=creator_email,
            password_hash=generate_password_hash(temp_password),
            role='creator'
        )
        db.session.add(new_user)
        db.session.flush()
        ca_user_id = new_user.id

    profile.manager_id = None
    profile.assigned_by_ops_id = None
    profile.account_type = 'sole_creator'

    if not ca:
        ca = CreatorAccount(
            user_id=ca_user_id,
            profile_id=profile.id,
            terms_accepted=False
        )
        db.session.add(ca)

    db.session.commit()

    try:
        send_account_grant_email(creator_email, profile.username, temp_password, role='creator')
    except Exception:
        pass

    print('✅ Profile {} graduated manager_trial → sole_creator. User: {}'.format(profile.username, creator_email))


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN: USERS TABLE WITH ROLES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/admin/users')
@admin_required
def admin_users():
    """Show all users with role, username, email."""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users)


@app.route('/admin/users/<int:user_id>/change-role', methods=['POST'])
@admin_required
def admin_change_user_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role', user.role)
    allowed_roles = ['subscriber', 'creator', 'creator_manager', 'ops_manager', 'admin']
    if new_role in allowed_roles:
        user.role = new_role
        if new_role == 'admin':
            user.is_admin = True
        db.session.commit()
        flash('Role updated to {}.'.format(new_role), 'success')
    return redirect(url_for('admin_users'))


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN: TWO REVENUE SPLIT PANELS
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/admin/revenue-splits', methods=['GET', 'POST'])
@admin_required
def admin_revenue_splits():
    """Edit revenue splits for both manager-trial accounts and sole-creator accounts."""
    split = get_revenue_split()
    if request.method == 'POST':
        panel = request.form.get('panel', 'manager')
        if panel == 'manager':
            split.manager_pct     = min(float(request.form.get('manager_pct', 55.0)), 55.0)
            split.ops_manager_pct = min(float(request.form.get('ops_manager_pct', 15.0)), 30.0)
        else:
            split.creator_pct = min(float(request.form.get('creator_pct', 70.0)), 70.0)
        split.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Revenue split updated!', 'success')
        return redirect(url_for('admin_revenue_splits'))
    return render_template('admin_revenue_splits.html', split=split)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN: CREATE OPS MANAGER (admin panel only)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/admin/ops-managers', methods=['GET', 'POST'])
@admin_required
def admin_ops_managers():
    """List and create OPS managers — only admins can do this."""
    ops_managers = User.query.filter_by(role='ops_manager').order_by(User.created_at.desc()).all()
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        name     = request.form.get('name', '').strip()
        if not email or not password:
            flash('Email and password required.', 'error')
            return redirect(url_for('admin_ops_managers'))
        if User.query.filter_by(email=email).first():
            flash('Email already in use.', 'error')
            return redirect(url_for('admin_ops_managers'))
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            role='ops_manager',
            is_admin=False
        )
        db.session.add(user)
        db.session.flush()
        om = OperationsManager(user_id=user.id, name=name or email.split('@')[0])
        db.session.add(om)
        db.session.commit()
        # Send welcome email
        send_account_grant_email(email, name, password, role='ops_manager')
        flash('OPS Manager account created.', 'success')
        return redirect(url_for('admin_ops_managers'))
    return render_template('admin_ops_managers.html', ops_managers=ops_managers)


@app.route('/admin/ops-managers/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_ops_manager(user_id):
    user = User.query.get_or_404(user_id)
    om = OperationsManager.query.filter_by(user_id=user_id).first()
    if om:
        db.session.delete(om)
    db.session.delete(user)
    db.session.commit()
    flash('OPS Manager deleted.', 'success')
    return redirect(url_for('admin_ops_managers'))


# ─────────────────────────────────────────────────────────────────────────────
# UPDATED: apply_to_be_creator — now sends email to admin
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/apply-to-be-creator-v2', methods=['GET', 'POST'])
def apply_to_be_creator_v2():
    """Public page to apply to become a creator manager or verified creator.
    Sends notification email to admin on submission."""
    if request.method == 'POST':
        app_type    = request.form.get('application_type', 'junior_creator')
        name        = request.form.get('applicant_name', '').strip()
        email       = request.form.get('applicant_email', '').strip().lower()
        motivation  = request.form.get('motivation', '').strip()
        content_type= request.form.get('content_type', '').strip()
        social_links= request.form.get('social_links', '').strip()
        legal_name  = request.form.get('legal_name', '').strip()
        dob_str     = request.form.get('date_of_birth', '').strip()

        if not name or not email:
            flash('Name and email are required.', 'error')
            return redirect(url_for('apply_to_be_creator_v2'))

        # Age check for verified_creator applications
        dob = None
        if dob_str:
            try:
                from datetime import date
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
                age = (date.today() - dob).days // 365
                if age < 18:
                    flash('You must be 18 or older to apply.', 'error')
                    return redirect(url_for('apply_to_be_creator_v2'))
            except Exception:
                pass

        # Handle ID / selfie uploads
        id_filename = selfie_filename = None
        for field, prefix in [('id_document', 'id_doc'), ('selfie_document', 'selfie')]:
            f = request.files.get(field)
            if f and f.filename and allowed_image(f.filename):
                ext = f.filename.rsplit('.', 1)[1].lower()
                fname = '{}_{}_{}.{}'.format(prefix, email.replace('@','_'), int(time.time()), ext)
                f.save(os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], fname))
                if field == 'id_document':
                    id_filename = fname
                else:
                    selfie_filename = fname

        user_id = session.get('user_id')
        app_record = CreatorApplication(
            user_id=user_id,
            applicant_name=name,
            applicant_email=email,
            application_type=app_type,
            motivation=motivation,
            content_type=content_type,
            social_links=social_links,
            legal_name=legal_name,
            id_document=id_filename,
            selfie_document=selfie_filename,
            date_of_birth=dob,
            status='pending',
            stage=1
        )
        db.session.add(app_record)
        db.session.commit()

        # Notify admin via email
        send_application_notification_email(app_record)

        flash('Application submitted! We will review and contact you at {}.'.format(email), 'success')
        return redirect(url_for('application_status', app_id=app_record.id))

    preselect = request.args.get('type', 'junior_creator')
    return render_template('apply_creator.html', preselect=preselect)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN: GRANT CREATOR MANAGER ACCOUNT FROM APPLICATION
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/ops/application/<int:app_id>/issue-junior-account', methods=['POST'])
@ops_manager_required
def ops_issue_junior_creator_account(app_id):
    """Ops Manager issues a Junior Creator account from a pending application."""
    app_record = CreatorApplication.query.get_or_404(app_id)
    profile_id = request.form.get('profile_id', type=int)
    password   = request.form.get('password', '').strip()

    if not password:
        # Auto-generate
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

    email = app_record.applicant_email
    existing = User.query.filter_by(email=email).first()
    if existing:
        junior_user = existing
        junior_user.role = 'junior_creator'
        junior_user.password_hash = generate_password_hash(password)
    else:
        junior_user = User(
            email=email,
            password_hash=generate_password_hash(password),
            role='junior_creator'
        )
        db.session.add(junior_user)
        db.session.flush()

    if profile_id:
        profile = Profile.query.get(profile_id)
        if profile:
            profile.account_type = 'junior_creator'
            existing_ca = CreatorAccount.query.filter_by(profile_id=profile.id).first()
            if not existing_ca:
                db.session.add(CreatorAccount(
                    user_id=junior_user.id,
                    profile_id=profile.id,
                    terms_accepted=False
                ))

    app_record.status = 'approved'
    app_record.stage  = 7
    app_record.reviewed_by = session.get('user_id')
    if profile_id:
        app_record.issued_profile_id = profile_id
    db.session.commit()

    # Send email with credentials
    send_account_grant_email(email, app_record.applicant_name, password, role='junior_creator')
    flash('Junior Creator account issued and email sent to {}. They log in at /creator/login.'.format(email), 'success')
    return redirect(url_for('ops_applications'))


# ─────────────────────────────────────────────────────────────────────────────
# API: Mark earnings available (scheduled job simulation)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/vaultx/release-earnings', methods=['POST'])
@admin_required
def api_release_earnings():
    """Release all pending earnings to available. Call from admin or a cron job."""
    updated = EarningsRecord.query.filter_by(is_available=False).update({'is_available': True})
    db.session.commit()
    return jsonify({'ok': True, 'released': updated})


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# EMAIL HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def send_welcome_email(email, password, username, role='creator'):
    """Send a welcome/account-created email to a new creator or manager.
    Fails silently so it never blocks account creation."""
    try:
        role_label = {
            'creator': 'Verified Creator',
            'creator_manager': 'Junior Creator',
            'ops': 'Ops Manager',
        }.get(role, 'Creator')

        display_name = username or email.split('@')[0]
        login_url = 'https://mitchellkaori.top/creator/login' if role == 'creator' else 'https://mitchellkaori.top/login'

        msg = Message(
            subject='Welcome to VaultX — Your {} Account'.format(role_label),
            sender=app.config['MAIL_DEFAULT_SENDER'],
            recipients=[email]
        )
        msg.html = """
        <div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto;padding:24px;background:#0d0d1a;color:#e0e0e0;border-radius:12px;">
          <div style="text-align:center;margin-bottom:24px;">
            <span style="font-size:2rem;font-weight:900;color:#C9184A;">Vault</span><span style="font-size:2rem;font-weight:900;color:#C9A84C;">X</span>
          </div>
          <h2 style="color:#ffffff;margin-bottom:8px;">Welcome, {}! 🎉</h2>
          <p style="color:#aaaaaa;line-height:1.6;">Your <strong style="color:#C9A84C;">{}</strong> account has been created on VaultX.</p>

          <div style="background:#1a1a2e;border:1px solid #2a2a4a;border-radius:10px;padding:18px;margin:20px 0;">
            <p style="margin:0 0 8px;color:#888;font-size:.85rem;text-transform:uppercase;letter-spacing:.06em;">Your Login Details</p>
            <p style="margin:4px 0;"><strong style="color:#fff;">Email:</strong> <span style="color:#C9A84C;">{}</span></p>
            <p style="margin:4px 0;"><strong style="color:#fff;">Password:</strong> <span style="color:#a78bfa;">{}</span></p>
          </div>

          <p style="color:#888;font-size:.85rem;">Please change your password after your first login for security.</p>

          <div style="text-align:center;margin:28px 0;">
            <a href="{}" style="background:linear-gradient(135deg,#C9184A,#a01040);color:#fff;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:700;font-size:1rem;">
              Login to Your Dashboard →
            </a>
          </div>

          <p style="color:#555;font-size:.75rem;text-align:center;margin-top:24px;">
            If you did not request this account, please contact us immediately.<br>
            &copy; VaultX — All rights reserved.
          </p>
        </div>
        """.format(display_name, role_label, email, password, login_url)

        mail.send(msg)
        print("📧 Welcome email sent to {}".format(email))
    except Exception as e:
        print("📧 Welcome email failed (non-fatal):", str(e))


# DB MIGRATION for new tables
# ─────────────────────────────────────────────────────────────────────────────

def vaultx_migrate():
    """Safe idempotent migration — widens columns and adds missing ones.
    Called every startup inside create_admin() after db.create_all()."""
    try:
        from sqlalchemy import text, inspect as sa_inspect
        with app.app_context():
            inspector     = sa_inspect(db.engine)
            existing_tabs = inspector.get_table_names()
            is_postgres   = 'postgresql' in str(db.engine.url)

            with db.engine.connect() as conn:

                # ── users.role ─────────────────────────────────────────────
                if 'users' in existing_tabs:
                    ucols = [c['name'] for c in inspector.get_columns('users')]
                    if 'role' not in ucols:
                        conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(30) NOT NULL DEFAULT 'subscriber'"))
                        conn.commit()

                # ── profiles.account_type — widen to VARCHAR(50) ──────────
                # Run in its own isolated connection so Postgres errors here
                # do not roll back other migrations.
                if 'profiles' in existing_tabs and is_postgres:
                    try:
                        with db.engine.connect() as widen_conn:
                            widen_conn.execute(text(
                                "ALTER TABLE profiles ALTER COLUMN account_type TYPE VARCHAR(50)"
                            ))
                            widen_conn.commit()
                            print("profiles.account_type widened to VARCHAR(50)")
                    except Exception as widen_err:
                        print("profiles.account_type widen note:", widen_err)

                # ── creator_accounts.creator_manager_id ───────────────────
                if 'creator_accounts' in existing_tabs:
                    ca_cols = [c['name'] for c in inspector.get_columns('creator_accounts')]
                    if 'creator_manager_id' not in ca_cols:
                        conn.execute(text(
                            "ALTER TABLE creator_accounts ADD COLUMN creator_manager_id INTEGER"
                        ))
                        conn.commit()

                # ── dm_settings table — create if missing ─────────────────
                if 'dm_settings' not in existing_tabs:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS dm_settings (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            profile_id INTEGER NOT NULL UNIQUE REFERENCES profiles(id),
                            dm_enabled BOOLEAN DEFAULT 1,
                            charge_per_msg BOOLEAN DEFAULT 0,
                            msg_price FLOAT DEFAULT 1.0,
                            auto_reply_text VARCHAR(500) DEFAULT '',
                            updated_at DATETIME
                        )
                    """))
                    conn.commit()

    except Exception as e:
        print('VaultX migrate warning:', e)


# ══════════════════════════════════════════════════════════════════════════════
# ONLINE STATUS DB MIGRATION — adds is_online column to profiles if missing
# ══════════════════════════════════════════════════════════════════════════════
def ensure_online_column():
    """Add is_online to profiles table if it doesn't exist yet."""
    try:
        from sqlalchemy import text, inspect as sa_inspect
        with app.app_context():
            inspector = sa_inspect(db.engine)
            cols = [c['name'] for c in inspector.get_columns('profiles')]
            if 'is_online' not in cols:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE profiles ADD COLUMN is_online BOOLEAN DEFAULT 0'))
                    conn.commit()
    except Exception as e:
        print('ensure_online_column warning: {}'.format(e))


def create_admin():
    with app.app_context():
        db.create_all()
        ensure_online_column()
        vaultx_migrate()
        # Migrate: add role column to users if missing
        try:
            from sqlalchemy import text, inspect as sa_inspect
            inspector = sa_inspect(db.engine)
            user_cols = [c['name'] for c in inspector.get_columns('users')]
            with db.engine.connect() as conn:
                if 'role' not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(30) NOT NULL DEFAULT 'subscriber'"))
                    conn.commit()
            profile_cols = [c['name'] for c in inspector.get_columns('profiles')]
            with db.engine.connect() as conn:
                if 'manager_id' not in profile_cols:
                    conn.execute(text('ALTER TABLE profiles ADD COLUMN manager_id INTEGER REFERENCES users(id)'))
                    conn.commit()
        except Exception as e:
            print('Migration warning: {}'.format(e))
        # Ensure admin user exists and has correct role
        if not User.query.filter_by(email=ADMIN_EMAIL).first():
            hashed = generate_password_hash(ADMIN_PASSWORD)
            admin  = User(email=ADMIN_EMAIL, password_hash=hashed, is_admin=True, role='admin')
            db.session.add(admin)
            db.session.commit()
            print('Admin created: {}'.format(ADMIN_EMAIL))
        else:
            admin = User.query.filter_by(email=ADMIN_EMAIL).first()
            if admin and admin.role != 'admin':
                admin.role = 'admin'
                db.session.commit()
        # Ensure default revenue split exists
        if not RevenueSplit.query.first():
            db.session.add(RevenueSplit())
            db.session.commit()
            print('Default revenue split created.')


create_admin()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=4000)







