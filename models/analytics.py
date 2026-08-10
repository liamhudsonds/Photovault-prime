from datetime import datetime
from database.db import db

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
