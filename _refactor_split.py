#!/usr/bin/env python3
"""Split app_build_v2.py into modular VaultX architecture."""
import os
import re
from pathlib import Path

ROOT = Path(__file__).parent
SOURCE = ROOT / 'app_build_v2.py'
SOURCE_TEXT = SOURCE.read_text(encoding='utf-8')
LINES = SOURCE_TEXT.splitlines(keepends=True)

MODEL_MAP = {
    'User': 'user',
    'Photo': 'project',
    'Profile': 'project',
    'ProfilePost': 'project',
    'ProfilePostLike': 'project',
    'ProfilePostComment': 'project',
    'PhotoLike': 'project',
    'Video': 'video',
    'VideoLike': 'video',
    'Order': 'payment',
    'OrderItem': 'payment',
    'Purchase': 'payment',
    'Payment': 'payment',
    'SiteSettings': 'settings',
    'TermsAcceptance': 'settings',
    'Category': 'category',
    'CreatorProfile': 'creator',
    'CreatorApplication': 'creator',
    'CreatorAccount': 'creator',
    'CreatorManagerProfile': 'creator',
    'CreatorBlurSettings': 'settings',
    'SocialLink': 'creator',
    'CreatorMessage': 'message',
    'CreatorFollow': 'creator',
    'CreatorSubscription': 'subscription',
    'CreatorLike': 'creator',
    'PostEngagement': 'analytics',
    'PostUnlock': 'activity',
    'ActivityFeed': 'activity',
    'Notification': 'notification',
    'EmailVerification': 'activity',
    'Repost': 'activity',
    'Comment': 'activity',
    'OperationsManager': 'operations_manager',
    'RevenueSplit': 'wallet',
    'VaultTransaction': 'wallet',
    'EarningsRecord': 'wallet',
    'PayoutMethod': 'wallet',
    'WithdrawalRequest': 'wallet',
    'Tip': 'wallet',
    'DMThread': 'message',
    'DMMessage': 'message',
    'DMSettings': 'message',
    'Subscription': 'subscription',
    'TelegramChannel': 'settings',
    'SubscriberProfile': 'subscriber',
}

BLUEPRINT_RULES = [
    ('auth_routes', re.compile(r"^/(login|register|logout|verify-email|admin/login|creator/(login|logout|terms)|ops/login|manager/login)")),
    ('payment_routes', re.compile(r"^/(checkout|payments|payment|charge|download|photo-original|premiums|test-email)")),
    ('admin_routes', re.compile(r"^/admin")),
    ('operations_routes', re.compile(r"^/ops")),
    ('creator_routes', re.compile(r"^/(creator|manager|creator-dashboard|apply-to-be-creator|application-status|post-purchase-telegram)")),
    ('subscriber_routes', re.compile(r"^/(my/dashboard|subscribe|tip|dm/)")),
    ('notification_routes', re.compile(r"^/api/notifications")),
    ('search_routes', re.compile(r"^/(search|api/search)")),
    ('analytics_routes', re.compile(r"^/(admin/analytics|admin/trending|trending|api/trending|api/leaderboard|api/activity|api/trending-posts|api/creator/.+/stats|api/creator/.+/online|api/online-creators|admin/creator/.+/toggle-online|reposts|api/repost)")),
    ('wallet_routes', re.compile(r"^/(admin/vaultx|api/vaultx)")),
    ('api_routes', re.compile(r"^/api/")),
    ('dashboard_routes', re.compile(r".")),  # catch-all public
]

DIRS = [
    'models', 'routes', 'services', 'utils', 'database', 'database/migrations',
    'middleware', 'templates', 'static/css', 'static/js', 'static/images',
    'static/uploads', 'static/videos', 'static/avatars', 'logs', 'tests', 'instance',
]

ROUTE_IMPORTS = """from flask import (
    Flask, render_template, request, flash, jsonify, session,
    redirect, url_for, send_file, abort, send_from_directory,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Message
from datetime import datetime, timedelta, UTC
import os, uuid, stripe, hashlib, hmac, time, json, requests, errno, random, string, io, re
from PIL import Image, ImageDraw, ImageFont

from database.db import db, mail, download_tokens
from models import *
from utils.decorators import (
    admin_required, manager_required, ops_manager_required,
    creator_only_required, creator_required,
)
from utils.helpers import *
from utils.constants import *
from utils.security import get_session_token, has_access, has_video_access, has_post_access
from utils.validators import allowed_file, allowed_video, allowed_image, allowed_video_file
from utils.formatter import dynamic_price, get_current_price, make_slug, _time_ago
from services.email_service import (
    send_welcome_email, send_account_grant_email, send_application_notification_email,
)
from services.payment_service import create_binance_signature
from services.wallet_service import (
    get_revenue_split, split_revenue, get_user_balances, get_user_revenue_breakdown,
    lock_earnings_for_withdrawal, release_locked_earnings, check_graduation,
    is_withdrawal_day, next_withdrawal_day, make_transaction_ref,
    junior_creator_sales_count, junior_creator_is_eligible_for_promotion,
)
from services.upload_service import generate_watermark_preview, get_blur_settings, check_upload_allowed
from services.notification_service import (
    recalculate_engagement, log_activity, push_notification,
    notify_followers, broadcast_notification,
)
from services.analytics_service import *
from services.creator_service import resolve_creator_dashboard_profile, upload_url, is_admin_override
from services.auth_service import get_setting, set_setting
from config import Config
import stripe as stripe_module
"""

HELPER_FUNCTIONS = {
    'utils/validators.py': [
        'allowed_file', 'allowed_video', 'allowed_image', 'allowed_video_file',
    ],
    'utils/security.py': [
        'get_session_token', 'has_access', 'has_video_access', 'has_post_access',
    ],
    'utils/formatter.py': [
        'dynamic_price', 'get_current_price', 'make_slug', '_time_ago',
    ],
    'utils/helpers.py': [
        'safe_makedirs', 'upload_url', 'is_admin_override',
        'resolve_creator_dashboard_profile', 'calculate_age',
    ],
    'services/payment_service.py': ['create_binance_signature'],
    'services/upload_service.py': [
        'generate_watermark_preview', 'get_blur_settings', 'check_upload_allowed',
    ],
    'services/notification_service.py': [
        'recalculate_engagement', 'log_activity', 'push_notification',
        'notify_followers', 'broadcast_notification',
    ],
    'services/wallet_service.py': [
        'get_revenue_split', 'split_revenue', 'get_user_balances',
        'get_user_revenue_breakdown', 'lock_earnings_for_withdrawal',
        'release_locked_earnings', 'check_graduation', '_graduate_to_sole_creator',
        'is_withdrawal_day', 'next_withdrawal_day', 'make_transaction_ref',
        'junior_creator_sales_count', 'junior_creator_is_eligible_for_promotion',
    ],
    'services/auth_service.py': ['get_setting', 'set_setting'],
    'services/email_service.py': [
        'send_welcome_email', 'send_account_grant_email', 'send_application_notification_email',
    ],
    'services/creator_service.py': [
        'resolve_creator_dashboard_profile', 'upload_url', 'is_admin_override',
    ],
}


def ensure_dirs():
    for d in DIRS:
        (ROOT / d).mkdir(parents=True, exist_ok=True)


def extract_class(name):
    pattern = re.compile(rf'^class {name}\(db\.Model\):', re.MULTILINE)
    m = pattern.search(SOURCE_TEXT)
    if not m:
        return None
    start = m.start()
    rest = SOURCE_TEXT[m.end():]
    next_class = re.search(r'\nclass \w+\(db\.Model\):', rest)
    next_section = re.search(r'\n# ══', rest)
    next_route = re.search(r'\n@app\.route\(', rest)
    next_helper = re.search(r'\n# ──(?:─+)?\n# (?:HELPERS|ENGAGEMENT|NEW MODELS|CREATOR AUTH)', rest)
    next_top_level_def = re.search(r'\ndef \w+\(', rest)
    ends = [len(SOURCE_TEXT)]
    if next_class:
        ends.append(m.end() + next_class.start())
    if next_section:
        ends.append(m.end() + next_section.start())
    if next_route:
        ends.append(m.end() + next_route.start())
    if next_helper:
        ends.append(m.end() + next_helper.start())
    if next_top_level_def:
        ends.append(m.end() + next_top_level_def.start())
    end = min(ends)
    return SOURCE_TEXT[start:end].rstrip() + '\n'


def write_models():
    models_by_file = {}
    for cls, fname in MODEL_MAP.items():
        body = extract_class(cls)
        if not body:
            print(f'WARN: model {cls} not found')
            continue
        models_by_file.setdefault(fname, []).append(body)

    for fname, bodies in models_by_file.items():
        content = (
            'from datetime import datetime\n'
            'from database.db import db\n\n'
            + '\n'.join(bodies)
        )
        (ROOT / 'models' / f'{fname}.py').write_text(content, encoding='utf-8')

    placeholders = ['admin', 'course', 'report']
    for p in placeholders:
        path = ROOT / 'models' / f'{p}.py'
        if not path.exists():
            path.write_text(
                f'"""Placeholder for future {p} models."""\nfrom database.db import db\n',
                encoding='utf-8',
            )

    init_lines = ['"""VaultX SQLAlchemy models."""\n']
    for f in sorted(set(list(MODEL_MAP.values()) + placeholders)):
        init_lines.append(f'from models.{f} import *  # noqa: F401, F403')
    (ROOT / 'models' / '__init__.py').write_text('\n'.join(init_lines) + '\n', encoding='utf-8')


def find_function(name):
    pat = re.compile(rf'^def {name}\(', re.MULTILINE)
    m = pat.search(SOURCE_TEXT)
    if not m:
        return None
    start = m.start()
    lines = SOURCE_TEXT[m.start():].splitlines(keepends=True)
    result = []
    for i, line in enumerate(lines):
        if i > 0 and (line.startswith('def ') or line.startswith('@app.') or line.startswith('class ')):
            break
        if i > 0 and line.startswith('# ─') and 'def ' not in line:
            break
        result.append(line)
    return ''.join(result).rstrip() + '\n'


def write_helpers_and_services():
    written = set()
    for filepath, funcs in HELPER_FUNCTIONS.items():
        parts = []
        for fn in funcs:
            body = find_function(fn)
            if body:
                parts.append(body)
                written.add(fn)
            else:
                print(f'WARN: function {fn} not found')
        if parts:
            header = (
                'from datetime import datetime, timedelta, UTC\n'
                'import os, uuid, random, string, hashlib, hmac, re, json\n'
                'from flask import session, current_app, url_for\n'
                'from werkzeug.security import generate_password_hash\n'
                'from flask_mail import Message\n'
                'from PIL import Image, ImageDraw, ImageFont\n'
                'import io\n\n'
                'from database.db import db, mail\n'
                'from models import *\n'
                'from utils.constants import *\n'
            )
            (ROOT / filepath).write_text(header + '\n'.join(parts), encoding='utf-8')

    # Decorators
    dec_funcs = [
        'admin_required', 'manager_required', 'ops_manager_required',
        'creator_only_required', 'creator_required',
    ]
    dec_parts = ['from functools import wraps\nfrom flask import session, redirect, url_for\n\n']
    dec_parts.append('from models import CreatorAccount\n\n')
    for fn in dec_funcs:
        body = find_function(fn)
        if body:
            dec_parts.append(body)
    (ROOT / 'utils' / 'decorators.py').write_text('\n'.join(dec_parts), encoding='utf-8')

    # Constants from source top
    const_block = '''
import os

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
ALLOWED_VIDEO_EXT = {'mp4', 'mov', 'webm', 'avi'}

MAX_CREATOR_PCT = 70.0
UPLOAD_LIMITS = {
    'basic': {'photos': 15, 'videos': 8, 'live_hours_per_month': 4},
    'premium': {'photos': None, 'videos': None, 'live_hours_per_month': None},
}
PREMIUM_MONTHLY_PRICE = 29.99

SCORE_VIEW = 1
SCORE_LIKE = 2
SCORE_COMMENT = 3
SCORE_UNLOCK = 5

GRADUATION_MIN_PHOTOS = 4
GRADUATION_MIN_VIDEOS = 4

PROFILE_UPLOAD_FOLDER = 'static/uploads/profiles'
POST_UPLOAD_FOLDER = 'static/uploads/posts'
'''
    (ROOT / 'utils' / 'constants.py').write_text(const_block.strip() + '\n', encoding='utf-8')


def classify_route(path):
    for bp_name, pattern in BLUEPRINT_RULES:
        if pattern.search(path):
            return bp_name
    return 'dashboard_routes'


def extract_routes():
    route_pattern = re.compile(
        r"(@app\.route\(([^\n]+)\)\n(?:@[^\n]+\n)*def (\w+)\([^)]*\):)",
        re.MULTILINE,
    )
    routes = []
    for m in route_pattern.finditer(SOURCE_TEXT):
        block_start = m.start()
        func_name = m.group(3)
        route_args = m.group(2)
        path_match = re.search(r"['\"]([^'\"]+)['\"]", route_args)
        path = path_match.group(1) if path_match else '/'
        rest = SOURCE_TEXT[m.end():]
        next_m = route_pattern.search(rest)
        next_def = re.search(r'\n(def |class |@app\.|# ══|if __name__)', rest)
        end_offset = len(rest)
        if next_m:
            end_offset = min(end_offset, next_m.start())
        if next_def:
            end_offset = min(end_offset, next_def.start())
        body = SOURCE_TEXT[block_start:m.end() + end_offset]
        routes.append((classify_route(path), func_name, path, body))
    return routes


def write_routes(routes):
    grouped = {}
    for bp, func_name, path, body in routes:
        new_body = body.replace('@app.route(', f'@{bp.replace("_routes", "_bp")}.route(')
        if 'endpoint=' not in new_body.split('\n')[0]:
            new_body = re.sub(
                rf'(@{bp.replace("_routes", "_bp")}\.route\([^\n]+\))',
                rf"\1\n    ",
                new_body,
                count=1,
            )
            # Add endpoint=func_name to preserve url_for names
            new_body = re.sub(
                rf'(@{re.escape(bp.replace("_routes", "_bp"))}\.route\(([^)]+)\))',
                lambda m: f"{m.group(1)[:-1]}, endpoint='{func_name}')" if 'endpoint=' not in m.group(0) else m.group(0),
                new_body,
                count=1,
            )
        grouped.setdefault(bp, []).append(new_body)

    bp_var = {
        'auth_routes': 'auth_bp',
        'creator_routes': 'creator_bp',
        'subscriber_routes': 'subscriber_bp',
        'admin_routes': 'admin_bp',
        'operations_routes': 'operations_bp',
        'dashboard_routes': 'dashboard_bp',
        'project_routes': 'project_bp',
        'course_routes': 'course_bp',
        'payment_routes': 'payment_bp',
        'wallet_routes': 'wallet_bp',
        'analytics_routes': 'analytics_bp',
        'notification_routes': 'notification_bp',
        'api_routes': 'api_bp',
        'search_routes': 'search_bp',
    }

    for bp_file, bodies in grouped.items():
        var = bp_var.get(bp_file, bp_file.replace('_routes', '_bp'))
        content = (
            f'"""VaultX {bp_file.replace("_", " ")}."""\n'
            f'from flask import Blueprint\n\n'
            f'{ROUTE_IMPORTS}\n'
            f'{var} = Blueprint("{bp_file.replace("_routes", "")}", __name__)\n\n'
            + '\n\n'.join(bodies)
        )
        (ROOT / 'routes' / f'{bp_file}.py').write_text(content, encoding='utf-8')

    # Empty course routes placeholder
    if not (ROOT / 'routes' / 'course_routes.py').exists():
        (ROOT / 'routes' / 'course_routes.py').write_text(
            '"""Future courses module routes."""\nfrom flask import Blueprint\n\ncourse_bp = Blueprint("course", __name__)\n',
            encoding='utf-8',
        )

    init = '''"""Register all VaultX blueprints."""
from routes.auth_routes import auth_bp
from routes.creator_routes import creator_bp
from routes.subscriber_routes import subscriber_bp
from routes.admin_routes import admin_bp
from routes.operations_routes import operations_bp
from routes.dashboard_routes import dashboard_bp
from routes.payment_routes import payment_bp
from routes.wallet_routes import wallet_bp
from routes.analytics_routes import analytics_bp
from routes.notification_routes import notification_bp
from routes.api_routes import api_bp
from routes.search_routes import search_bp
from routes.course_routes import course_bp

ALL_BLUEPRINTS = [
    auth_bp, creator_bp, subscriber_bp, admin_bp, operations_bp,
    dashboard_bp, payment_bp, wallet_bp, analytics_bp, notification_bp,
    api_bp, search_bp, course_bp,
]


def register_blueprints(app):
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)
'''
    (ROOT / 'routes' / '__init__.py').write_text(init, encoding='utf-8')


def write_config_and_db():
    config = '''"""VaultX application configuration."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024
    TEMPLATES_AUTO_RELOAD = True
    SEND_FILE_MAX_AGE_DEFAULT = 0

    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS') == 'True'
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL') == 'True'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = ('VaultX', os.getenv('MAIL_DEFAULT_SENDER'))

    PROFILE_UPLOAD_FOLDER = 'static/uploads/profiles'
    POST_UPLOAD_FOLDER = 'static/uploads/posts'

    PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY')
    PAYSTACK_PUBLISHABLE_KEY = os.getenv('PAYSTACK_PUBLISHABLE_KEY')
    PAYSTACK_INITIALIZE_URL = os.getenv('PAYSTACK_INITIALIZE_URL')

    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_YOUR_STRIPE_SECRET')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', 'whsec_YOUR_WEBHOOK_SECRET')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', 'pk_test_YOUR_STRIPE_PK')

    BINANCE_API_KEY = os.environ.get('BINANCE_API_KEY', '')
    BINANCE_SECRET_KEY = os.environ.get('BINANCE_SECRET_KEY', '')
    BINANCE_BASE_URL = 'https://bpay.binanceapi.com'

    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
'''
    (ROOT / 'config.py').write_text(config, encoding='utf-8')

    db_py = '''"""Database and Flask extension initialization."""
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail

db = SQLAlchemy()
mail = Mail()
download_tokens = {}

# Reserved for future Flask-Login integration
login_manager = None


def init_extensions(app):
    db.init_app(app)
    mail.init_app(app)
    return db, mail
'''
    (ROOT / 'database' / 'db.py').write_text(db_py, encoding='utf-8')

    seed = '''"""Database seeding and migrations."""
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
'''
    (ROOT / 'database' / 'seed.py').write_text(seed, encoding='utf-8')


def write_middleware():
    errors = '''"""Global error handlers."""
from flask import render_template, jsonify


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        return render_template('base.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({'error': 'Internal server error'}), 500
'''
    (ROOT / 'middleware' / 'errors.py').write_text(errors, encoding='utf-8')

    logging_mw = '''"""Request logging middleware."""
import time
from flask import request, g


def register_logging(app):
    @app.before_request
    def start_timer():
        g.start = time.time()

    @app.after_request
    def log_request(response):
        if hasattr(g, 'start'):
            elapsed = time.time() - g.start
            app.logger.debug('%s %s %.3fs', request.method, request.path, elapsed)
        return response
'''
    (ROOT / 'middleware' / 'logging.py').write_text(logging_mw, encoding='utf-8')

    auth_mw = '''"""Authentication context middleware."""
from services.creator_service import is_admin_override, upload_url


def register_auth_context(app):
    @app.context_processor
    def inject_upload_context():
        return {
            'is_admin_override': is_admin_override(),
            'upload_url': upload_url,
        }

    @app.teardown_request
    def cleanup(exception=None):
        from database.db import db
        if exception:
            db.session.rollback()
'''
    (ROOT / 'middleware' / 'auth.py').write_text(auth_mw, encoding='utf-8')

    perms = '''"""Permission middleware helpers — see utils.decorators for route guards."""
'''
    (ROOT / 'middleware' / 'permissions.py').write_text(perms, encoding='utf-8')


def write_app():
    app_py = '''# -*- coding: utf-8 -*-
"""VaultX — Flask application entry point."""
import os
import errno
import stripe

from flask import Flask
from dotenv import load_dotenv

from config import Config
from database.db import init_extensions
from database.seed import create_admin
from routes import register_blueprints
from middleware.errors import register_error_handlers
from middleware.logging import register_logging
from middleware.auth import register_auth_context
from utils.helpers import safe_makedirs
from utils.constants import PROFILE_UPLOAD_FOLDER, POST_UPLOAD_FOLDER

load_dotenv()


def create_app(config_class=Config):
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Upload folders
    os.makedirs(PROFILE_UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(POST_UPLOAD_FOLDER, exist_ok=True)
    for sub in ('originals', 'previews', 'videos', 'video_thumbs', 'video_previews', 'profiles', 'profile_posts'):
        safe_makedirs(os.path.join(app.config['UPLOAD_FOLDER'], sub))

    init_extensions(app)

    # Payment providers
    stripe.api_key = app.config['STRIPE_SECRET_KEY']

    # Jinja2 globals
    app.jinja_env.globals['enumerate'] = enumerate
    app.jinja_env.globals['range'] = range
    app.jinja_env.globals['len'] = len
    app.jinja_env.globals['zip'] = zip

    register_blueprints(app)
    register_error_handlers(app)
    register_logging(app)
    register_auth_context(app)

    with app.app_context():
        create_admin()

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=4000)
'''
    (ROOT / 'app.py').write_text(app_py, encoding='utf-8')


def write_service_stubs():
    stubs = {
        'services/analytics_service.py': '"""Analytics business logic — see routes for API handlers."""\n',
        'services/recommendation_service.py': '"""Future recommendation engine."""\n',
        'services/report_service.py': '"""Future reporting service."""\n',
        'services/subscriber_service.py': '"""Subscriber business logic."""\n',
        'utils/permissions.py': '"""Role and permission checks."""\n',
        'tests/__init__.py': '',
    }
    for path, content in stubs.items():
        p = ROOT / path
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_text(content, encoding='utf-8')


def main():
    ensure_dirs()
    write_config_and_db()
    write_models()
    write_helpers_and_services()
    routes = extract_routes()
    print(f'Extracted {len(routes)} routes')
    write_routes(routes)
    write_middleware()
    write_app()
    write_service_stubs()
    print('Refactoring complete.')


if __name__ == '__main__':
    main()
