from datetime import datetime
from database.db import db

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
