from datetime import datetime
from database.db import db

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

class CreatorFollow(db.Model):
    __tablename__ = 'creator_follows'
    id           = db.Column(db.Integer, primary_key=True)
    profile_id   = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    session_token= db.Column(db.String(100), nullable=False)
    follower_name= db.Column(db.String(100), default='Visitor')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('profile_id', 'session_token', name='_follow_uc'),)

class CreatorLike(db.Model):
    __tablename__ = 'creator_likes'
    id           = db.Column(db.Integer, primary_key=True)
    profile_id   = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    session_token= db.Column(db.String(100), nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('profile_id', 'session_token', name='_clk_uc'),)
