from datetime import datetime
from database.db import db

class OperationsManager(db.Model):
    __tablename__ = 'operations_managers'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    name        = db.Column(db.String(100), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    user        = db.relationship('User', foreign_keys=[user_id])
