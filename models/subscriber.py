from datetime import datetime

from database.db import db


class SubscriberProfile(db.Model):
    """Extended profile data for subscribers."""
    __tablename__ = 'subscriber_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    display_name = db.Column(db.String(100), default='')
    avatar_url = db.Column(db.String(500), default='')
    total_spent = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='subscriber_profile', uselist=False)
