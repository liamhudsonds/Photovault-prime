"""VaultX notification routes."""
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

notification_bp = Blueprint("notification", __name__)

@notification_bp.route('/api/notifications', endpoint='api_notifications')
    
def api_notifications():
    tok = get_session_token()
    notes = Notification.query.filter_by(session_token=tok)\
                .order_by(Notification.created_at.desc()).limit(30).all()
    unread = sum(1 for n in notes if not n.is_read)
    result = [{'id': n.id, 'type': n.notif_type, 'title': n.title,
               'body': n.body, 'link': n.link,
               'read': n.is_read, 'ago': _time_ago(n.created_at)} for n in notes]
    return jsonify({'notifications': result, 'unread': unread})


@notification_bp.route('/api/notifications/read', methods=['POST'], endpoint='api_mark_notifications_read')
    
def api_mark_notifications_read():
    tok = get_session_token()
    notif_id = (request.get_json() or {}).get('id')
    if notif_id:
        n = Notification.query.filter_by(id=notif_id, session_token=tok).first()
        if n: n.is_read = True
    else:
        Notification.query.filter_by(session_token=tok).update({'is_read': True})
    db.session.commit()
    return jsonify({'ok': True})


@notification_bp.route('/api/notifications/clear', methods=['POST'], endpoint='api_clear_notifications')
    
def api_clear_notifications():
    tok = get_session_token()
    Notification.query.filter_by(session_token=tok).delete()
    db.session.commit()
    return jsonify({'ok': True})

