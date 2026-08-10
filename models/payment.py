from datetime import datetime
from database.db import db

class Order(db.Model):
    __tablename__   = 'orders'
    id              = db.Column(db.Integer, primary_key=True)
    order_id        = db.Column(db.String(100), unique=True, nullable=False)
    customer_name   = db.Column(db.String(255), nullable=False)
    customer_email  = db.Column(db.String(255), nullable=False)
    total_price     = db.Column(db.Float, default=0)
    total_items     = db.Column(db.Integer, default=0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    delivery_status = db.Column(db.String(20), default='pending')
    downloads       = db.Column(db.Integer, default=0)
    items           = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id            = db.Column(db.Integer, primary_key=True)
    order_id      = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id    = db.Column(db.Integer, db.ForeignKey('photos.id'), nullable=False)
    product_name  = db.Column(db.String(255))
    quantity      = db.Column(db.Integer, default=1)
    unit_price    = db.Column(db.Float, nullable=False)
    total_price   = db.Column(db.Float, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

class Purchase(db.Model):
    __tablename__   = 'purchases'
    id              = db.Column(db.Integer, primary_key=True)
    session_token   = db.Column(db.String(100), nullable=False)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    photo_id        = db.Column(db.Integer, db.ForeignKey('photos.id'), nullable=False)
    payment_method  = db.Column(db.String(50))
    amount          = db.Column(db.Float)
    expires_at      = db.Column(db.DateTime)
    is_permanent    = db.Column(db.Boolean, default=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    __tablename__  = 'payments'
    id             = db.Column(db.Integer, primary_key=True)
    order_id       = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    session_token  = db.Column(db.String(100))
    gateway        = db.Column(db.String(50))
    transaction_id = db.Column(db.String(200))
    amount         = db.Column(db.Float)
    status         = db.Column(db.String(50), default='pending')
    photo_id       = db.Column(db.Integer, db.ForeignKey('photos.id'))
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
