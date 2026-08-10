"""VaultX subscriber routes."""
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

subscriber_bp = Blueprint("subscriber", __name__)

@subscriber_bp.route('/dm/<username>', endpoint='dm_thread')
    
def dm_thread(username):
    """Subscriber opens DM with a creator."""
    if not session.get('user_id'):
        return redirect(url_for('login'))
    profile = Profile.query.filter_by(username=username, is_active=True).first_or_404()
    user_id = session['user_id']
    thread = DMThread.query.filter_by(subscriber_user_id=user_id, profile_id=profile.id).first()
    if not thread:
        thread = DMThread(subscriber_user_id=user_id, profile_id=profile.id)
        db.session.add(thread)
        db.session.commit()
    messages = DMMessage.query.filter_by(thread_id=thread.id).order_by(DMMessage.created_at).all()
    return render_template('vx_dm_thread.html', thread=thread, profile=profile, messages=messages)



@subscriber_bp.route('/dm/<username>/send', methods=['POST'], endpoint='dm_send')
    
def dm_send(username):
    if not session.get('user_id'):
        return jsonify({'error': 'Login required'}), 401
    profile = Profile.query.filter_by(username=username, is_active=True).first_or_404()

    # Check DM settings
    dm_cfg = DMSettings.query.filter_by(profile_id=profile.id).first()
    if dm_cfg and not dm_cfg.dm_enabled:
        return jsonify({'error': 'DMs are disabled for this creator.'}), 403

    user_id = session['user_id']
    thread = DMThread.query.filter_by(subscriber_user_id=user_id, profile_id=profile.id).first()
    if not thread:
        thread = DMThread(subscriber_user_id=user_id, profile_id=profile.id)
        db.session.add(thread)
        db.session.flush()

    body = (request.form.get('body') or request.get_json(silent=True, force=True) or {}).get('body', '') if request.is_json else request.form.get('body', '')
    if not body and not request.is_json:
        body = request.form.get('body', '')

    # If creator charges per message, record a transaction
    charge = dm_cfg.msg_price if (dm_cfg and dm_cfg.charge_per_msg and dm_cfg.msg_price > 0) else 0
    if charge > 0:
        tok = get_session_token()
        tx = VaultTransaction(
            reference=make_transaction_ref(),
            subscriber_user_id=user_id,
            session_token=tok,
            profile_id=profile.id,
            content_type='dm',
            gateway='stripe',
            gross_amount=charge,
            status='completed'
        )
        db.session.add(tx)
        db.session.flush()
        split_revenue(tx)

    msg = DMMessage(
        thread_id=thread.id,
        sender_type='subscriber',
        sender_user_id=user_id,
        body=body.strip()[:2000],
        charge_enabled=(dm_cfg.charge_per_msg if dm_cfg else False),
        message_price=charge
    )
    db.session.add(msg)
    thread.last_message_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True, 'id': msg.id, 'charge': charge})



@subscriber_bp.route('/dm/unlock/<int:msg_id>', methods=['POST'], endpoint='dm_unlock_message')
    
def dm_unlock_message(msg_id):
    """Subscriber pays to unlock a locked DM via a real Stripe Checkout session.

    The transaction is only marked 'completed' by the /payments/stripe/webhook
    handler once Stripe confirms the payment actually happened — this route
    never grants access on its own.
    """
    if not session.get('user_id'):
        return jsonify({'error': 'Login required'}), 401
    msg = DMMessage.query.get_or_404(msg_id)
    if msg.is_unlocked or msg.lock_price <= 0:
        return jsonify({'ok': True, 'already_unlocked': True})

    thread  = msg.thread
    profile = thread.profile
    user_id = session['user_id']
    tok     = get_session_token()

    # Reuse an existing pending transaction for this message+user so that
    # re-clicking "unlock" doesn't spawn duplicate Stripe sessions/records.
    tx = VaultTransaction.query.filter_by(
        content_type='dm', content_id=msg.id,
        subscriber_user_id=user_id, status='pending'
    ).first()
    if not tx:
        tx = VaultTransaction(
            reference=make_transaction_ref(),
            subscriber_user_id=user_id,
            session_token=tok,
            profile_id=profile.id,
            content_type='dm',
            content_id=msg.id,
            gateway='stripe',
            gross_amount=msg.lock_price,
            status='pending'
        )
        db.session.add(tx)
        db.session.commit()

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Unlock message from {}'.format(profile.name),
                    },
                    'unit_amount': int(round(msg.lock_price * 100)),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('dm_thread', username=profile.username, _external=True) + '?unlocked=1',
            cancel_url=url_for('dm_thread', username=profile.username, _external=True) + '?unlock_cancelled=1',
            metadata={
                'vaultx_type': 'dm_unlock',
                'vault_ref': tx.reference,
                'session_token': tok,
            }
        )
    except Exception as e:
        print('🔥 DM unlock Stripe error:', str(e))
        return jsonify({'error': 'Could not start payment. Please try again.'}), 500

    return jsonify({'ok': True, 'checkout_url': checkout_session.url})


# ─────────────────────────────────────────────────────────────────────────────
# SUBSCRIPTION
# ─────────────────────────────────────────────────────────────────────────────


@subscriber_bp.route('/subscribe/<username>', methods=['POST'], endpoint='subscribe_to_creator')
    
def subscribe_to_creator(username):
    if not session.get('user_id'):
        return jsonify({'error': 'Login required'}), 401
    profile = Profile.query.filter_by(username=username, is_active=True).first_or_404()
    user_id = session['user_id']
    price   = float(request.form.get('price', 15.0))

    existing = Subscription.query.filter_by(subscriber_user_id=user_id, profile_id=profile.id, status='active').first()
    if existing:
        return jsonify({'ok': True, 'already_subscribed': True})

    tok = get_session_token()
    tx = VaultTransaction(
        reference=make_transaction_ref(),
        subscriber_user_id=user_id,
        session_token=tok,
        profile_id=profile.id,
        content_type='subscription',
        gateway='stripe',
        gross_amount=price,
        status='completed'
    )
    db.session.add(tx)
    db.session.flush()
    split_revenue(tx)

    sub = Subscription(
        subscriber_user_id=user_id,
        profile_id=profile.id,
        monthly_price=price,
        expires_at=datetime.utcnow() + timedelta(days=30),
        gateway='stripe'
    )
    db.session.add(sub)

    # Update subscriber spend
    sp = SubscriberProfile.query.filter_by(user_id=user_id).first()
    if sp:
        sp.total_spent += price
    db.session.commit()

    # After purchase → show Telegram channel
    subscriber_channels = TelegramChannel.query.filter_by(channel_type='subscriber', is_active=True).all()
    telegram_links = [c.channel_url for c in subscriber_channels]
    return jsonify({'ok': True, 'telegram_channels': telegram_links})


# ─────────────────────────────────────────────────────────────────────────────
# TIPPING
# ─────────────────────────────────────────────────────────────────────────────


@subscriber_bp.route('/tip/<username>', methods=['POST'], endpoint='send_tip')
    
def send_tip(username):
    if not session.get('user_id'):
        return jsonify({'error': 'Login required'}), 401
    profile = Profile.query.filter_by(username=username, is_active=True).first_or_404()
    amount  = float(request.get_json(force=True, silent=True).get('amount', 0) or request.form.get('amount', 0))
    message = (request.get_json(force=True, silent=True) or {}).get('message', request.form.get('message', ''))
    if amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400
    tok = get_session_token()
    tx = VaultTransaction(
        reference=make_transaction_ref(),
        subscriber_user_id=session['user_id'],
        session_token=tok,
        profile_id=profile.id,
        content_type='tip',
        gateway='stripe',
        gross_amount=amount,
        status='completed'
    )
    db.session.add(tx)
    db.session.flush()
    split_revenue(tx)
    tip = Tip(
        subscriber_user_id=session['user_id'],
        session_token=tok,
        profile_id=profile.id,
        amount=amount,
        message=message[:300],
        transaction_id=tx.id
    )
    db.session.add(tip)
    db.session.commit()
    return jsonify({'ok': True})


# ─────────────────────────────────────────────────────────────────────────────
# SUBSCRIBER DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────


@subscriber_bp.route('/my/dashboard', endpoint='subscriber_dashboard')
    
def subscriber_dashboard():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    user_id = session['user_id']
    user = db.session.get(User, user_id)

    sp = SubscriberProfile.query.filter_by(user_id=user_id).first()
    if not sp:
        sp = SubscriberProfile(user_id=user_id)
        db.session.add(sp)
        db.session.commit()

    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Spending stats
    txs = VaultTransaction.query.filter_by(subscriber_user_id=user_id, status='completed').all()
    total_spent  = sum(t.gross_amount for t in txs)
    this_month   = sum(t.gross_amount for t in txs if t.created_at >= month_start)
    photos_bought  = sum(1 for t in txs if t.content_type == 'photo')
    videos_bought  = sum(1 for t in txs if t.content_type == 'video')
    dm_purchases   = sum(1 for t in txs if t.content_type == 'dm')
    subs_count     = Subscription.query.filter_by(subscriber_user_id=user_id, status='active').count()
    tips_sent      = Tip.query.filter_by(subscriber_user_id=user_id).count()

    # Favorite creators (most transacted)
    from sqlalchemy import func
    fav_creators = db.session.query(Profile, func.count(VaultTransaction.id).label('cnt'))\
        .join(VaultTransaction, VaultTransaction.profile_id == Profile.id)\
        .filter(VaultTransaction.subscriber_user_id == user_id)\
        .group_by(Profile.id).order_by(func.count(VaultTransaction.id).desc()).limit(5).all()

    # Active subscriptions
    active_subs = Subscription.query.filter_by(subscriber_user_id=user_id, status='active').all()

    # Recent purchases
    recent_txs = VaultTransaction.query.filter_by(subscriber_user_id=user_id, status='completed')\
        .order_by(VaultTransaction.created_at.desc()).limit(20).all()

    # DM threads
    threads = DMThread.query.filter_by(subscriber_user_id=user_id)\
        .order_by(DMThread.last_message_at.desc()).limit(10).all()

    return render_template('vx_subscriber_dashboard.html',
        user=user, sp=sp,
        total_spent=total_spent, this_month=this_month,
        photos_bought=photos_bought, videos_bought=videos_bought,
        dm_purchases=dm_purchases, subs_count=subs_count, tips_sent=tips_sent,
        fav_creators=fav_creators,
        active_subs=active_subs,
        recent_txs=recent_txs,
        threads=threads
    )


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — VAULTX MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
