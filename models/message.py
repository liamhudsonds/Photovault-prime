from datetime import datetime
from database.db import db

class CreatorMessage(db.Model):
    __tablename__ = 'creator_messages'
    id           = db.Column(db.Integer, primary_key=True)
    profile_id   = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    sender_name  = db.Column(db.String(100), default='Anonymous')
    sender_email = db.Column(db.String(200), default='')
    subject      = db.Column(db.String(300), default='New Message')
    body         = db.Column(db.Text, nullable=False)
    is_read      = db.Column(db.Boolean, default=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

class DMThread(db.Model):
    """A conversation thread between a subscriber and a creator profile."""
    __tablename__ = 'dm_threads'
    id              = db.Column(db.Integer, primary_key=True)
    subscriber_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    profile_id      = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow)
    subscriber      = db.relationship('User', foreign_keys=[subscriber_user_id])
    profile         = db.relationship('Profile', foreign_keys=[profile_id])
    messages        = db.relationship('DMMessage', backref='thread', lazy=True, order_by='DMMessage.created_at')
    __table_args__ = (db.UniqueConstraint('subscriber_user_id', 'profile_id', name='_dm_thread_uc'),)

class DMMessage(db.Model):
    """Individual messages inside a DM thread."""
    __tablename__ = 'dm_messages'
    id              = db.Column(db.Integer, primary_key=True)
    thread_id       = db.Column(db.Integer, db.ForeignKey('dm_threads.id'), nullable=False)
    sender_type     = db.Column(db.String(20), nullable=False)  # subscriber/creator/admin
    sender_user_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    body            = db.Column(db.Text, default='')
    # Locked media
    media_url       = db.Column(db.String(500), default='')  # stored URL (cloud storage / CDN)
    media_type      = db.Column(db.String(20), default='')   # photo/video/voice/text
    lock_price      = db.Column(db.Float, default=0.0)       # 0 = free
    is_unlocked     = db.Column(db.Boolean, default=False)
    # Pricing toggle
    charge_enabled  = db.Column(db.Boolean, default=False)
    message_price   = db.Column(db.Float, default=0.0)
    is_read         = db.Column(db.Boolean, default=False)
    # Admin styled
    is_admin_notice = db.Column(db.Boolean, default=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    sender          = db.relationship('User', foreign_keys=[sender_user_id])

class DMSettings(db.Model):
    """Per-profile DM monetization settings — controlled by creator/manager."""
    __tablename__ = 'dm_settings'
    id              = db.Column(db.Integer, primary_key=True)
    profile_id      = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False, unique=True)
    # DM inbox enabled/disabled
    dm_enabled      = db.Column(db.Boolean, default=True)
    # Charge per message sent (subscriber pays to send)
    charge_per_msg  = db.Column(db.Boolean, default=False)
    msg_price       = db.Column(db.Float, default=1.0)   # price per inbound message
    # Auto-reply message when offline
    auto_reply_text = db.Column(db.String(500), default='')
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow)
    profile         = db.relationship('Profile', backref=db.backref('dm_settings_obj', uselist=False))
