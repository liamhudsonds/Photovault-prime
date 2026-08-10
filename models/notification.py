from datetime import datetime
from database.db import db

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
