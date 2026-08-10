from datetime import datetime
from database.db import db

class SiteSettings(db.Model):
    __tablename__ = 'site_settings'
    id    = db.Column(db.Integer, primary_key=True)
    key   = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(500), default='')
 
 
# ── MODEL: Category ────────────────────────────────────────────────────────────

class TermsAcceptance(db.Model):
    __tablename__ = 'terms_acceptances'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    accepted_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address  = db.Column(db.String(50), default='')
    user        = db.relationship('User', backref='terms_acceptances')

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

class TelegramChannel(db.Model):
    """Platform-level Telegram channel links set by Admin."""
    __tablename__ = 'telegram_channels'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    channel_url = db.Column(db.String(300), nullable=False)
    channel_type= db.Column(db.String(30), default='subscriber')  # subscriber/creator/admin
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
