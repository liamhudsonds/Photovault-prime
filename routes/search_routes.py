"""VaultX search routes."""
from flask import Blueprint

from flask import (
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

search_bp = Blueprint("search", __name__)

@search_bp.route('/api/search', endpoint='api_search')
    
def api_search():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({'photos': [], 'videos': [], 'creators': []})

    like = '%{}%'.format(q)

    photos = Photo.query.filter(
        Photo.is_active == True,
        db.or_(Photo.title.ilike(like), Photo.description.ilike(like), Photo.category.ilike(like))
    ).order_by(Photo.view_count.desc()).limit(8).all()

    videos = Video.query.filter(
        Video.is_active == True,
        db.or_(Video.title.ilike(like), Video.description.ilike(like), Video.category.ilike(like))
    ).order_by(Video.view_count.desc()).limit(8).all()

    creators = Profile.query.filter(
        Profile.is_active == True,
        db.or_(Profile.name.ilike(like), Profile.username.ilike(like),
               Profile.tagline.ilike(like), Profile.category.ilike(like))
    ).limit(6).all()

    return jsonify({
        'photos': [{'id': p.id, 'title': p.title, 'tier': p.tier,
                    'price': p.unlock_price, 'views': p.view_count} for p in photos],
        'videos': [{'id': v.id, 'title': v.title, 'tier': v.tier,
                    'price': v.unlock_price, 'views': v.view_count,
                    'thumb': v.thumbnail_filename} for v in videos],
        'creators': [{'id': c.id, 'name': c.name, 'username': c.username,
                      'tagline': c.tagline, 'avatar': c.avatar_filename} for c in creators]
    })



@search_bp.route('/search', endpoint='search_page')
    
def search_page():
    q = request.args.get('q', '').strip()
    like = '%{}%'.format(q) if q else None
    photos, videos, creators = [], [], []
    if q and len(q) >= 2:
        photos = Photo.query.filter(
            Photo.is_active == True,
            db.or_(Photo.title.ilike(like), Photo.description.ilike(like), Photo.category.ilike(like))
        ).order_by(Photo.view_count.desc()).all()
        for p in photos:
            p.unlocked = has_access(p.id)
            p.current_price = dynamic_price(p)

        videos = Video.query.filter(
            Video.is_active == True,
            db.or_(Video.title.ilike(like), Video.description.ilike(like), Video.category.ilike(like))
        ).order_by(Video.view_count.desc()).all()
        for v in videos:
            v.unlocked = has_video_access(v.id)

        creators = Profile.query.filter(
            Profile.is_active == True,
            db.or_(Profile.name.ilike(like), Profile.username.ilike(like),
                   Profile.tagline.ilike(like))
        ).all()

    return render_template('search.html', q=q, photos=photos, videos=videos, creators=creators)


# ── Comment Likes / Reactions ─────────────────────────────────────────────────