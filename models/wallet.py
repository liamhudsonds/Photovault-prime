from datetime import datetime
from database.db import db

class RevenueSplit(db.Model):
    """Platform-wide revenue split configuration (stored in DB, editable by admin).

    Two distinct splits:
    - Sole verified creator: creator_pct (max 70%) / platform takes the rest
    - Manager-run (admin-issued, unmanaged-by-self) creator account:
        manager_pct (creator manager keeps this, e.g. 55%) +
        ops_manager_pct (the OPS manager who assigned them, e.g. 15%) +
        remaining goes to platform
    """
    __tablename__ = 'revenue_splits'
    id              = db.Column(db.Integer, primary_key=True)
    creator_pct     = db.Column(db.Float, default=70.0)   # sole verified creator share (hard cap 70)
    manager_pct     = db.Column(db.Float, default=55.0)   # creator-manager share of a manager-run account
    ops_manager_pct = db.Column(db.Float, default=15.0)   # ops manager override cut on manager-run accounts
    platform_pct    = db.Column(db.Float, default=30.0)   # platform share on sole-creator sales (informational)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow)

class VaultTransaction(db.Model):
    """Every purchase creates one transaction record."""
    __tablename__ = 'vault_transactions'
    id              = db.Column(db.Integer, primary_key=True)
    reference       = db.Column(db.String(120), unique=True, nullable=False)
    subscriber_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_token   = db.Column(db.String(100), nullable=False)
    profile_id      = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=True)
    content_type    = db.Column(db.String(30), default='photo')  # photo/video/subscription/dm/tip/voice
    content_id      = db.Column(db.Integer, nullable=True)
    gateway         = db.Column(db.String(30), default='stripe')
    gross_amount    = db.Column(db.Float, nullable=False)
    currency        = db.Column(db.String(10), default='USD')
    status          = db.Column(db.String(20), default='pending')  # pending/completed/failed/refunded
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    subscriber      = db.relationship('User', foreign_keys=[subscriber_user_id])
    profile         = db.relationship('Profile', foreign_keys=[profile_id])

class EarningsRecord(db.Model):
    """One record per beneficiary per transaction."""
    __tablename__ = 'earnings_records'
    id              = db.Column(db.Integer, primary_key=True)
    transaction_id  = db.Column(db.Integer, db.ForeignKey('vault_transactions.id'), nullable=False)
    beneficiary_type= db.Column(db.String(30), nullable=False)  # creator/creator_manager/ops_manager/platform
    beneficiary_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    profile_id      = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=True)
    amount          = db.Column(db.Float, nullable=False)
    content_type    = db.Column(db.String(30), default='photo')
    is_available    = db.Column(db.Boolean, default=False)  # True after payout window
    # Once a withdrawal request is created against this record, it gets locked
    # here so it can never be double-counted into a second withdrawal request.
    withdrawal_request_id = db.Column(db.Integer, db.ForeignKey('withdrawal_requests.id'), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    transaction     = db.relationship('VaultTransaction', backref='earnings')
    beneficiary     = db.relationship('User', foreign_keys=[beneficiary_user_id])

class PayoutMethod(db.Model):
    """Each user stores their preferred payout method."""
    __tablename__ = 'payout_methods'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    method_type = db.Column(db.String(20), nullable=False)  # mpesa/bank/paypal/crypto
    mpesa_number= db.Column(db.String(20), default='')
    bank_name   = db.Column(db.String(100), default='')
    bank_account= db.Column(db.String(100), default='')
    paypal_email= db.Column(db.String(200), default='')
    crypto_wallet = db.Column(db.String(200), default='')
    crypto_type = db.Column(db.String(20), default='USDT')
    is_default  = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    user        = db.relationship('User', backref='payout_methods')

class WithdrawalRequest(db.Model):
    """Creator / Manager withdrawal requests (only Wed & Sat)."""
    __tablename__ = 'withdrawal_requests'
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount          = db.Column(db.Float, nullable=False)
    payout_method_id= db.Column(db.Integer, db.ForeignKey('payout_methods.id'), nullable=True)
    method_snapshot = db.Column(db.Text, default='{}')  # JSON snapshot of method at request time
    status          = db.Column(db.String(20), default='pending')  # pending/approved/rejected/paid
    admin_note      = db.Column(db.Text, default='')
    requested_at    = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at    = db.Column(db.DateTime, nullable=True)
    user            = db.relationship('User', backref='withdrawal_requests')
    payout_method   = db.relationship('PayoutMethod')

class Tip(db.Model):
    """Tips sent by subscribers to creators."""
    __tablename__ = 'tips'
    id              = db.Column(db.Integer, primary_key=True)
    subscriber_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_token   = db.Column(db.String(100), default='')
    profile_id      = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    amount          = db.Column(db.Float, nullable=False)
    message         = db.Column(db.String(300), default='')
    transaction_id  = db.Column(db.Integer, db.ForeignKey('vault_transactions.id'), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
