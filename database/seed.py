"""Database seeding and migrations."""
from werkzeug.security import generate_password_hash
from sqlalchemy import text, inspect as sa_inspect

from database.db import db
from models import User, RevenueSplit
from config import Config


def ensure_online_column():
    try:
        with db.engine.connect() as conn:
            inspector = sa_inspect(db.engine)
            cols = [c['name'] for c in inspector.get_columns('profiles')]
            if 'is_online' not in cols:
                conn.execute(text('ALTER TABLE profiles ADD COLUMN is_online BOOLEAN DEFAULT 0'))
                conn.commit()
    except Exception as e:
        print('ensure_online_column warning: {}'.format(e))


def vaultx_migrate():
    try:
        inspector = sa_inspect(db.engine)
        existing_tabs = inspector.get_table_names()
        is_postgres = 'postgresql' in str(db.engine.url)
        with db.engine.connect() as conn:
            if 'users' in existing_tabs:
                ucols = [c['name'] for c in inspector.get_columns('users')]
                if 'role' not in ucols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(30) NOT NULL DEFAULT 'subscriber'"))
                    conn.commit()
            if 'profiles' in existing_tabs and is_postgres:
                try:
                    with db.engine.connect() as widen_conn:
                        widen_conn.execute(text(
                            "ALTER TABLE profiles ALTER COLUMN account_type TYPE VARCHAR(50)"
                        ))
                        widen_conn.commit()
                except Exception as widen_err:
                    print('profiles.account_type widen note:', widen_err)
            if 'creator_accounts' in existing_tabs:
                ca_cols = [c['name'] for c in inspector.get_columns('creator_accounts')]
                if 'creator_manager_id' not in ca_cols:
                    conn.execute(text(
                        "ALTER TABLE creator_accounts ADD COLUMN creator_manager_id INTEGER"
                    ))
                    conn.commit()
            if 'dm_settings' not in existing_tabs:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS dm_settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        profile_id INTEGER NOT NULL UNIQUE REFERENCES profiles(id),
                        dm_enabled BOOLEAN DEFAULT 1,
                        charge_per_msg BOOLEAN DEFAULT 0,
                        msg_price FLOAT DEFAULT 1.0,
                        auto_reply_text VARCHAR(500) DEFAULT '',
                        updated_at DATETIME
                    )
                """))
                conn.commit()
    except Exception as e:
        print('VaultX migrate warning:', e)


def create_admin():
    db.create_all()
    ensure_online_column()
    vaultx_migrate()
    try:
        inspector = sa_inspect(db.engine)
        user_cols = [c['name'] for c in inspector.get_columns('users')]
        with db.engine.connect() as conn:
            if 'role' not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(30) NOT NULL DEFAULT 'subscriber'"))
                conn.commit()
        profile_cols = [c['name'] for c in inspector.get_columns('profiles')]
        with db.engine.connect() as conn:
            if 'manager_id' not in profile_cols:
                conn.execute(text('ALTER TABLE profiles ADD COLUMN manager_id INTEGER REFERENCES users(id)'))
                conn.commit()
    except Exception as e:
        print('Migration warning: {}'.format(e))

    if not User.query.filter_by(email=Config.ADMIN_EMAIL).first():
        hashed = generate_password_hash(Config.ADMIN_PASSWORD)
        admin = User(email=Config.ADMIN_EMAIL, password_hash=hashed, is_admin=True, role='admin')
        db.session.add(admin)
        db.session.commit()
        print('Admin created: {}'.format(Config.ADMIN_EMAIL))
    else:
        admin = User.query.filter_by(email=Config.ADMIN_EMAIL).first()
        if admin and admin.role != 'admin':
            admin.role = 'admin'
            db.session.commit()

    if not RevenueSplit.query.first():
        db.session.add(RevenueSplit())
        db.session.commit()
        print('Default revenue split created.')
