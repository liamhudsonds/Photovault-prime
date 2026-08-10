"""VaultX auth routes."""
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

auth_bp = Blueprint("auth", __name__)

@auth_bp.route('/login', methods=['GET', 'POST'], endpoint='login')
    
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user     = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            if user.is_blocked:
                return render_template('login.html', error='Account blocked.')
            session['user_id']    = user.id
            session['is_admin']   = user.is_admin
            session['is_manager'] = (user.role in ('creator_manager', 'ops_manager'))
            session['user_role']  = user.role
            # Smart redirect based on role
            if user.is_admin or user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'ops_manager':
                return redirect(url_for('ops_dashboard'))
            elif user.role == 'creator_manager':
                return redirect(url_for('manager_vx_dashboard'))
            elif user.role in ('junior_creator', 'creator'):
                # check if they have a CreatorAccount
                ca = CreatorAccount.query.filter_by(user_id=user.id).first()
                if ca:
                    session['creator_account_id'] = ca.id
                    session['creator_user_id'] = user.id
                    session['creator_profile_id'] = ca.profile_id
                    return redirect(url_for('creator_home'))
                return redirect(url_for('index'))
            else:
                return redirect(url_for('index'))
        return render_template('login.html', error='Invalid credentials.')
    return render_template('login.html')



@auth_bp.route('/register', methods=['GET', 'POST'], endpoint='register')
    
def register():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error='Email already registered.')
        hashed = generate_password_hash(password, method='pbkdf2:sha256')
        user   = User(email=email, password_hash=hashed, role='subscriber')
        db.session.add(user)
        db.session.commit()
        session['user_id']  = user.id
        session['is_admin'] = False
        session['is_manager'] = False
        session['user_role'] = 'subscriber'
        return redirect(url_for('index'))
    return render_template('register.html')



@auth_bp.route('/logout', endpoint='logout')
    
def logout():
    session.clear()
    return redirect(url_for('index'))



@auth_bp.route('/admin/login', methods=['GET', 'POST'], endpoint='admin_login')
    
def admin_login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user     = User.query.filter_by(email=email, is_admin=True).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id']  = user.id
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        return render_template('admin_login.html', error='Invalid admin credentials.')
    return render_template('admin_login.html')



@auth_bp.route('/verify-email', methods=['GET', 'POST'], endpoint='verify_email_page')
    
def verify_email_page():
    tok = get_session_token()
    ev  = EmailVerification.query.filter_by(session_token=tok).first()
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        if not email:
            flash('Please enter an email address.', 'error')
            return redirect(url_for('verify_email_page'))
        # Generate verification token
        verify_token = ''.join(random.choices(string.ascii_letters + string.digits, k=48))
        if ev:
            ev.email = email; ev.token = verify_token
            ev.is_verified = False; ev.verified_at = None
        else:
            ev = EmailVerification(session_token=tok, email=email, token=verify_token)
            db.session.add(ev)
        db.session.commit()
        # Send verification email
        verify_url = url_for('verify_email_confirm', token=verify_token, _external=True)
        try:
            msg = Message(
                subject='Verify your email — PhotoVault',
                recipients=[email],
                html='''<div style="font-family:sans-serif;max-width:480px;margin:auto">
                    <h2 style="color:#C9A84C">PhotoVault</h2>
                    <p>Click the button below to verify your email and receive notifications.</p>
                    <a href="{url}" style="display:inline-block;background:#C9A84C;color:#000;
                       padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold">
                       Verify Email</a>
                    <p style="color:#888;font-size:12px;margin-top:16px">
                    Link expires in 24 hours. If you did not request this, ignore it.</p>
                    </div>'''.format(url=verify_url)
            )
            mail.send(msg)
            flash('Verification email sent! Check your inbox.', 'success')
        except Exception as e:
            flash('Could not send email — please check your mail config.', 'error')
            print('Mail error:', e)
        return redirect(url_for('verify_email_page'))

    verified = ev.is_verified if ev else False
    email    = ev.email if ev else ''
    return render_template('verify_email.html', verified=verified, email=email)


@auth_bp.route('/verify-email/confirm/<token>', endpoint='verify_email_confirm')
    
def verify_email_confirm(token):
    ev = EmailVerification.query.filter_by(token=token).first()
    if not ev:
        flash('Invalid or expired verification link.', 'error')
        return redirect(url_for('verify_email_page'))
    ev.is_verified = True
    ev.verified_at = datetime.utcnow()
    # Set session to match
    session['session_token'] = ev.session_token
    db.session.commit()
    push_notification(ev.session_token, 'verified',
        'Email Verified ✓', 'You\'ll now receive notifications from PhotoVault.', '/')
    flash('Email verified successfully! You\'ll now receive notifications.', 'success')
    return redirect(url_for('index'))


@auth_bp.route('/creator/login', methods=['GET', 'POST'], endpoint='creator_login')
    
def creator_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        # Look up user by email
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            # ── CREATOR MANAGER acting as their assigned creator ──────────────
            if user.role == 'creator_manager':
                # Find the profile assigned to this manager
                profile = Profile.query.filter_by(manager_id=user.id).first()
                if profile:
                    # Log them in as "manager acting as creator"
                    session['user_id']    = user.id
                    session['is_admin']   = False
                    session['is_manager'] = True
                    session['user_role']  = 'creator_manager'
                    session['manager_profile_id'] = profile.id
                    flash('Logged in as Junior Creator managing {}'.format(profile.name), 'success')
                    return redirect(url_for('creator_dashboard'))
                else:
                    flash('You have no creator profile assigned yet. Contact admin.', 'error')
                    return render_template('vx_creator_login.html')

            # ── SOLE CREATOR with a CreatorAccount ────────────────────────────
            ca = CreatorAccount.query.filter_by(user_id=user.id).first()
            if not ca:
                flash('No creator profile is linked to this account.', 'error')
                return render_template('vx_creator_login.html')

            if user.role not in ('creator', 'junior_creator'):
                user.role = 'junior_creator'
                db.session.commit()

            session['creator_account_id']  = ca.id
            session['creator_user_id']     = user.id
            session['creator_profile_id']  = ca.profile_id
            if not ca.terms_accepted:
                return redirect(url_for('creator_terms'))
            telegram_channels = TelegramChannel.query.filter_by(channel_type='creator', is_active=True).all()
            if telegram_channels:
                session['show_creator_telegram'] = True
            return redirect(url_for('creator_home'))

        if user:
            flash('Incorrect password. Please try again.', 'error')
        else:
            flash('No account found with that email.', 'error')
    return render_template('vx_creator_login.html')



@auth_bp.route('/creator/terms', methods=['GET', 'POST'], endpoint='creator_terms')
    
def creator_terms():
    ca_id = session.get('creator_account_id')
    if not ca_id:
        return redirect(url_for('creator_login'))
    ca = CreatorAccount.query.get(ca_id)
    if request.method == 'POST':
        ca.terms_accepted = True
        ca.terms_accepted_at = datetime.utcnow()
        ta = TermsAcceptance(user_id=ca.user_id, ip_address=request.remote_addr)
        db.session.add(ta)
        db.session.commit()
        return redirect(url_for('creator_home'))
    return render_template('vx_creator_terms.html')



@auth_bp.route('/creator/logout', endpoint='creator_logout')
    
def creator_logout():
    session.pop('creator_account_id', None)
    session.pop('creator_user_id', None)
    session.pop('creator_profile_id', None)
    return redirect(url_for('creator_login'))



@auth_bp.route('/ops/login', methods=['GET', 'POST'], endpoint='ops_login')
    
def ops_login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(email=email, role='ops_manager').first()
        if user and check_password_hash(user.password_hash, password):
            session['ops_user_id'] = user.id
            session['user_role']   = 'ops_manager'
            return redirect(url_for('ops_dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('vx_ops_login.html')



@auth_bp.route('/manager/login', methods=['GET', 'POST'], endpoint='manager_login_vx')
    
def manager_login_vx():
    if request.method == 'POST':
        email    = request.form.get('email','').strip().lower()
        password = request.form.get('password','').strip()
        user = User.query.filter_by(email=email, role='creator_manager').first()
        if user and check_password_hash(user.password_hash, password):
            session['manager_vx_user_id'] = user.id
            session['user_role'] = 'creator_manager'
            return redirect(url_for('manager_vx_dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('vx_manager_login.html')

