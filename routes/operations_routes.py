"""VaultX operations routes."""
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

operations_bp = Blueprint("operations", __name__)

@operations_bp.route('/ops/applications', endpoint='ops_applications')
    
@ops_manager_required
def ops_applications():
    """Ops Manager views and manages Junior Creator applications."""
    applications = CreatorApplication.query.order_by(CreatorApplication.created_at.desc()).all()
    pending_count = CreatorApplication.query.filter_by(status='pending').count()
    profiles = Profile.query.filter_by(is_active=True).all()
    # Pass available (unassigned) profiles for issuing demo accounts
    linked_profile_ids = [p.manager_id for p in Profile.query.filter(Profile.manager_id.isnot(None)).all()]
    available_profiles = Profile.query.filter(
        Profile.manager_id.is_(None),
        Profile.is_active == True
    ).all()
    return render_template('ops_applications.html', applications=applications,
                           pending_count=pending_count, profiles=profiles,
                           available_profiles=available_profiles)



@operations_bp.route('/ops/application/<int:app_id>/issue-account', methods=['POST'], endpoint='ops_issue_creator_manager')
    
@ops_manager_required
def ops_issue_creator_manager(app_id):
    """OPS manager issues a creator manager (demo) account from an application."""
    app_record  = CreatorApplication.query.get_or_404(app_id)
    password    = request.form.get('password', '').strip()
    profile_id  = request.form.get('profile_id', type=int)

    if not password or len(password) < 6:
        flash('Password must be at least 6 characters.', 'error')
        return redirect(url_for('ops_applications'))

    email = app_record.applicant_email

    if User.query.filter_by(email=email).first():
        flash('An account already exists for this email.', 'error')
        return redirect(url_for('ops_applications'))

    # Create user with junior_creator role
    user = User(
        email=email,
        password_hash=generate_password_hash(password),
        role='junior_creator'
    )
    db.session.add(user)
    db.session.flush()

    # Determine which OPS manager is issuing
    ops_user_id = session.get('ops_user_id') or session.get('user_id')
    om = OperationsManager.query.filter_by(user_id=ops_user_id).first()

    if profile_id:
        profile = db.session.get(Profile, profile_id)
        if profile:
            profile.account_type = 'junior_creator'
            if om and hasattr(profile, 'assigned_by_ops_id'):
                profile.assigned_by_ops_id = om.user_id
            # Junior creator logs in at /creator/login via CreatorAccount
            existing_ca = CreatorAccount.query.filter_by(profile_id=profile.id).first()
            if not existing_ca:
                new_ca = CreatorAccount(
                    user_id=user.id,
                    profile_id=profile.id,
                    terms_accepted=False
                )
                db.session.add(new_ca)

    # Update application status
    app_record.status     = 'approved'
    app_record.updated_at = datetime.utcnow()
    app_record.reviewed_by = ops_user_id
    if profile_id:
        app_record.issued_profile_id = profile_id

    db.session.commit()

    # Email the applicant their credentials
    send_account_grant_email(email, app_record.applicant_name or email.split('@')[0], password, role='junior_creator')

    flash('Junior Creator account issued to {}. They log in at /creator/login and will be auto-promoted after {} photo + {} video sales.'.format(
        email, GRADUATION_MIN_PHOTOS, GRADUATION_MIN_VIDEOS), 'success')
    return redirect(url_for('ops_applications'))



@operations_bp.route('/ops/application/<int:app_id>/update', methods=['POST'], endpoint='ops_update_application')
    
@ops_manager_required
def ops_update_application(app_id):
    """Ops Manager updates application status and stage."""
    app_record = CreatorApplication.query.get_or_404(app_id)
    new_status = request.form.get('status', app_record.status)
    new_stage  = int(request.form.get('stage', app_record.stage))
    rejection_reason = request.form.get('rejection_reason', '').strip()

    app_record.status = new_status
    app_record.stage  = new_stage
    app_record.rejection_reason = rejection_reason
    app_record.updated_at = datetime.utcnow()
    app_record.reviewed_by = session.get('user_id')
    db.session.commit()
    flash('Application updated.', 'success')
    return redirect(url_for('ops_applications'))





@operations_bp.route('/ops/create-junior-creator', methods=['GET', 'POST'], endpoint='ops_create_junior_creator')
    
@ops_manager_required
def ops_create_junior_creator():
    """Ops Manager creates a Junior Creator account linked to a new profile.
    Junior Creator logs in at /creator/login and can upload immediately.
    They auto-promote to full Creator after 4 photo sales + 4 video sales.
    """
    ops_managers = OperationsManager.query.all()
    # Profiles not yet assigned to any manager and not already a sole creator account
    available_profiles = Profile.query.filter(
        Profile.manager_id.is_(None),
        Profile.account_type != 'sole_creator'
    ).filter_by(is_active=True).all()

    if request.method == 'POST':
        name        = request.form.get('name', '').strip()
        email       = request.form.get('email', '').strip().lower()
        password    = request.form.get('password', '').strip()
        username    = request.form.get('username', '').strip().lower().replace(' ', '_')
        ops_id      = request.form.get('ops_manager_id', type=int)
        profile_id  = request.form.get('profile_id', type=int)
        create_new_profile = request.form.get('create_new_profile') == 'on'

        if not all([name, email, password]):
            flash('Name, email and password are required.', 'error')
            return redirect(url_for('ops_create_junior_creator'))
        if User.query.filter_by(email=email).first():
            flash('Email already in use.', 'error')
            return redirect(url_for('ops_create_junior_creator'))
        if username and User.query.filter_by(username=username).first():
            flash('Username already in use.', 'error')
            return redirect(url_for('ops_create_junior_creator'))

        junior_user = User(
            email=email, username=username or None,
            password_hash=generate_password_hash(password),
            role='junior_creator'
        )
        db.session.add(junior_user)
        db.session.flush()

        # Create a fresh profile for the Junior Creator
        profile = None
        if create_new_profile or not profile_id:
            new_username = username or 'creator_{}'.format(junior_user.id)
            base_username = new_username
            i = 1
            while Profile.query.filter_by(username=new_username).first():
                i += 1
                new_username = '{}_{}'.format(base_username, i)
            profile = Profile(
                name=name, username=new_username, is_active=True,
                account_type='junior_creator'
            )
            db.session.add(profile)
            db.session.flush()
        elif profile_id:
            profile = Profile.query.get(profile_id)
            if profile:
                profile.account_type = 'junior_creator'

        if profile:
            ops_uid = session.get('ops_user_id') or session.get('user_id')
            om_rec = OperationsManager.query.filter_by(user_id=ops_uid).first()
            if om_rec and hasattr(profile, 'assigned_by_ops_id'):
                profile.assigned_by_ops_id = om_rec.user_id
            # Link CreatorAccount so junior creator can log in at /creator/login
            existing_ca = CreatorAccount.query.filter_by(profile_id=profile.id).first()
            if not existing_ca:
                db.session.add(CreatorAccount(
                    user_id=junior_user.id,
                    profile_id=profile.id,
                    terms_accepted=False
                ))
            db.session.commit()
            emailed = send_account_grant_email(email, name, password, role='junior_creator')
            if emailed:
                flash('Junior Creator account created for "{}". They log in at /creator/login '
                      'and auto-promote after {} photo + {} video sales. Login details were emailed to {}.'.format(
                          name, GRADUATION_MIN_PHOTOS, GRADUATION_MIN_VIDEOS, email), 'success')
            else:
                flash('Junior Creator account created for "{}", but the welcome email failed to send. '
                      'Please share the login details with them manually: {} / {}'.format(
                          name, email, password), 'warning')
        else:
            db.session.commit()
            emailed = send_account_grant_email(email, name, password, role='junior_creator')
            if emailed:
                flash('Junior Creator account created — no profile assigned. Login details were emailed to {}.'.format(email), 'warning')
            else:
                flash('Junior Creator account created — no profile assigned, and the welcome email failed to send. '
                      'Please share the login details manually: {} / {}'.format(email, password), 'warning')

        return redirect(url_for('ops_dashboard'))

    return render_template('vx_ops_create_junior_creator.html',
                           ops_managers=ops_managers,
                           available_profiles=available_profiles)


# NOTE: Direct Creator account creation has been permanently removed.
# All creators must go through: Application → Junior Creator → 4+4 sales →
# automatic promotion to Creator (see check_graduation / _graduate_to_sole_creator).
# There is intentionally no /ops/create-creator route or equivalent code path.



@operations_bp.route('/ops/dashboard', endpoint='ops_dashboard')
    
@ops_manager_required
def ops_dashboard():
    user_id = session.get('ops_user_id') or session.get('user_id')
    om      = OperationsManager.query.filter_by(user_id=user_id).first()

    # ── Profiles managed via Profile.assigned_by_ops_id (existing system) ──
    if om and hasattr(Profile, 'assigned_by_ops_id'):
        managed_profiles = Profile.query.filter_by(assigned_by_ops_id=om.user_id).all()
    else:
        managed_profiles = []

    # ── Creator managers via CreatorManagerProfile (new system) ─────────────
    cmp_records     = CreatorManagerProfile.query.filter_by(
        ops_manager_id=om.id if om else None
    ).all() if om else []

    # Distinct creator_manager Users: from old system + new system
    old_mgr_ids = list({p.manager_id for p in managed_profiles if p.manager_id})
    new_mgr_ids = [c.user_id for c in cmp_records]
    all_mgr_ids = list(set(old_mgr_ids + new_mgr_ids))
    creator_managers = User.query.filter(User.id.in_(all_mgr_ids)).all() if all_mgr_ids else []

    all_creators = managed_profiles

    # ── Performance data per profile ────────────────────────────────────────
    creator_data = []
    for profile in all_creators:
        earnings_uid = profile.manager_id if profile.manager_id else (om.user_id if om else None)
        _, _, lifetime = get_user_balances(earnings_uid) if earnings_uid else (0, 0, 0)
        creator_data.append({'profile': profile, 'lifetime': lifetime})

    # ── Pending applications (ops manager reviews these) ────────────────────
    # pending_applications = list for template iteration
    # pending_count = integer badge count
    pending_applications = CreatorApplication.query.filter_by(
        status='pending'
    ).order_by(CreatorApplication.created_at.desc()).limit(10).all()
    pending_count_ops = CreatorApplication.query.filter_by(status='pending').count()

    return render_template('vx_ops_dashboard.html',
        om=om,
        creator_managers=creator_managers,
        all_creators=all_creators,
        creator_data=creator_data,
        pending_applications=pending_applications,
        pending_count=pending_count_ops
    )


# ─────────────────────────────────────────────────────────────────────────────
# CREATOR MANAGER PORTAL
# ─────────────────────────────────────────────────────────────────────────────


@operations_bp.route('/ops/application/<int:app_id>/issue-junior-account', methods=['POST'], endpoint='ops_issue_junior_creator_account')
    
@ops_manager_required
def ops_issue_junior_creator_account(app_id):
    """Ops Manager issues a Junior Creator account from a pending application."""
    app_record = CreatorApplication.query.get_or_404(app_id)
    profile_id = request.form.get('profile_id', type=int)
    password   = request.form.get('password', '').strip()

    if not password:
        # Auto-generate
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

    email = app_record.applicant_email
    existing = User.query.filter_by(email=email).first()
    if existing:
        junior_user = existing
        junior_user.role = 'junior_creator'
        junior_user.password_hash = generate_password_hash(password)
    else:
        junior_user = User(
            email=email,
            password_hash=generate_password_hash(password),
            role='junior_creator'
        )
        db.session.add(junior_user)
        db.session.flush()

    if profile_id:
        profile = Profile.query.get(profile_id)
        if profile:
            profile.account_type = 'junior_creator'
            existing_ca = CreatorAccount.query.filter_by(profile_id=profile.id).first()
            if not existing_ca:
                db.session.add(CreatorAccount(
                    user_id=junior_user.id,
                    profile_id=profile.id,
                    terms_accepted=False
                ))

    app_record.status = 'approved'
    app_record.stage  = 7
    app_record.reviewed_by = session.get('user_id')
    if profile_id:
        app_record.issued_profile_id = profile_id
    db.session.commit()

    # Send email with credentials
    send_account_grant_email(email, app_record.applicant_name, password, role='junior_creator')
    flash('Junior Creator account issued and email sent to {}. They log in at /creator/login.'.format(email), 'success')
    return redirect(url_for('ops_applications'))


# ─────────────────────────────────────────────────────────────────────────────
# API: Mark earnings available (scheduled job simulation)
# ─────────────────────────────────────────────────────────────────────────────
