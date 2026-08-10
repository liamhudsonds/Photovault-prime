from datetime import datetime
from database.db import db

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

class VideoLike(db.Model):
    __tablename__ = 'video_likes'
    id            = db.Column(db.Integer, primary_key=True)
    video_id      = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    session_token = db.Column(db.String(100), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('video_id', 'session_token', name='_video_like_uc'),)
