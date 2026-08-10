from datetime import datetime
from database.db import db

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
