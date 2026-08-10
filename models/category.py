from datetime import datetime
from database.db import db

class Category(db.Model):
    __tablename__ = 'categories'
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(100), unique=True, nullable=False)
    slug         = db.Column(db.String(100), unique=True, nullable=False)
    description  = db.Column(db.String(300), default='')
    icon         = db.Column(db.String(10), default='📁')     # emoji icon
    cover_photo_id  = db.Column(db.Integer, nullable=True)    # optional cover photo
    content_type = db.Column(db.String(10), default='both')   # 'photo','video','both'
    sort_order   = db.Column(db.Integer, default=0)
    is_active    = db.Column(db.Boolean, default=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
