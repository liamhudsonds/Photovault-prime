from datetime import datetime
from database.db import db

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
