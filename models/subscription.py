from datetime import datetime
from database.db import db

class CreatorSubscription(db.Model):
    __tablename__ = 'creator_subscriptions'
    id           = db.Column(db.Integer, primary_key=True)
    profile_id   = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    session_token= db.Column(db.String(100), nullable=False)
    name         = db.Column(db.String(100), default='Visitor')
    email        = db.Column(db.String(200), default='')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('profile_id', 'session_token', name='_sub_uc'),)

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
