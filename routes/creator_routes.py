"""VaultX creator routes."""
from flask import Blueprint, current_app

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

creator_bp = Blueprint("creator", __name__)

@creator_bp.route('/apply-to-be-creator', methods=['GET', 'POST'], endpoint='apply_to_be_creator')
    
def apply_to_be_creator():
    """Public page to apply to become a creator manager or verified creator."""
    if request.method == 'POST':
        app_type    = request.form.get('application_type', 'junior_creator')
        name        = request.form.get('applicant_name', '').strip()
        email       = request.form.get('applicant_email', '').strip().lower()
        motivation  = request.form.get('motivation', '').strip()
        content_type= request.form.get('content_type', '').strip()
        social_links= request.form.get('social_links', '').strip()
        legal_name  = request.form.get('legal_name', '').strip()

        if not name or not email:
            flash('Name and email are required.', 'error')
            return redirect(url_for('apply_to_be_creator'))

        # Handle ID document upload for verified creator applicants
        id_filename = None
        if app_type == 'verified_creator':
            id_file = request.files.get('id_document')
            if id_file and id_file.filename and allowed_image(id_file.filename):
                ext = id_file.filename.rsplit('.', 1)[1].lower()
                id_filename = 'id_doc_{}_{}.{}'.format(email.replace('@','_'), int(time.time()), ext)
                save_path = os.path.join(current_app.config['PROFILE_UPLOAD_FOLDER'], id_filename)
                id_file.save(save_path)

        user_id = session.get('user_id')
        app_record = CreatorApplication(
            user_id=user_id,
            applicant_name=name,
            applicant_email=email,
            application_type=app_type,
            motivation=motivation,
            content_type=content_type,
            social_links=social_links,
            legal_name=legal_name,
            id_document=id_filename,
            status='pending',
            stage=1
        )
        db.session.add(app_record)
        db.session.commit()
        # Notify admin
        try:
            send_application_notification_email(app_record)
        except Exception:
            pass
        flash('Application submitted! We will review and get back to you.', 'success')
        return redirect(url_for('application_status', app_id=app_record.id))

    preselect = request.args.get('type', 'junior_creator')
    return render_template('apply_creator.html', preselect=preselect)



@creator_bp.route('/application-status/<int:app_id>', endpoint='application_status')
    
def application_status(app_id):
    """Show application progress to the applicant."""
    app_record = CreatorApplication.query.get_or_404(app_id)
    stage_labels = [
        'Application Submitted',
        'Documents Uploaded',
        'Under Review',
        'Manager Assignment',
        'Performance Evaluation',
        'Verification Approved',
        'Creator Account Issued',
    ]
    return render_template('application_status.html',
                           app_record=app_record,
                           stage_labels=stage_labels)



@creator_bp.route('/creator/<username>', endpoint='creator_page')
    
def creator_page(username):
    """Alias for /profile/<username> so trending links work."""
    return profile_page(username)


@creator_bp.route('/creator-dashboard', endpoint='creator_dashboard')
    
@manager_required
def creator_dashboard():
    """Main dashboard for creator managers — shows only their assigned creator."""
    profile, _ = resolve_creator_dashboard_profile(require_profile=False)

    user_id = session.get('user_id')

    if not profile:
        return render_template('creator_dashboard.html',
                               profile=None,
                               COUNTRY_FLAGS=COUNTRY_FLAGS,
                               COUNTRY_NAMES=COUNTRY_NAMES)

    # Gather stats
    photos    = Photo.query.filter_by(profile_id=profile.id).order_by(Photo.created_at.desc()).all()
    videos    = Video.query.filter_by(profile_id=profile.id).order_by(Video.created_at.desc()).all()
    posts     = ProfilePost.query.filter_by(profile_id=profile.id).order_by(ProfilePost.created_at.desc()).all()

    total_views = sum(p.view_count or 0 for p in posts)
    total_likes = ProfilePostLike.query.join(ProfilePost)\
        .filter(ProfilePost.profile_id == profile.id).count()

    # Earnings for this manager/creator
    earnings_user_id = user_id
    vx_pending, vx_available, vx_lifetime = get_user_balances(earnings_user_id)

    # Sold content counts (for graduation progress)
    sold_photos = db.session.query(db.func.count(db.distinct(VaultTransaction.content_id)))\
        .filter(VaultTransaction.profile_id==profile.id,
                VaultTransaction.content_type=='photo',
                VaultTransaction.status=='completed').scalar() or 0
    sold_videos = db.session.query(db.func.count(db.distinct(VaultTransaction.content_id)))\
        .filter(VaultTransaction.profile_id==profile.id,
                VaultTransaction.content_type=='video',
                VaultTransaction.status=='completed').scalar() or 0

    # Revenue split info
    split = get_revenue_split()
    if profile.account_type == 'sole_creator':
        creator_pct = split.creator_pct
        split_label = 'Creator'
    elif profile.account_type == 'junior_creator':
        creator_pct = split.manager_pct
        split_label = 'Junior Creator (Probation)'
    else:
        creator_pct = split.manager_pct
        split_label = 'Manager Trial'

    return render_template(
        'creator_dashboard.html',
        profile=profile,
        photos=photos,
        videos=videos,
        posts=posts,
        total_views=total_views,
        total_likes=total_likes,
        vx_pending=vx_pending,
        vx_available=vx_available,
        vx_lifetime=vx_lifetime,
        sold_photos=sold_photos,
        sold_videos=sold_videos,
        creator_pct=creator_pct,
        split_label=split_label,
        GRAD_MIN_PHOTOS=GRADUATION_MIN_PHOTOS,
        GRAD_MIN_VIDEOS=GRADUATION_MIN_VIDEOS,
        COUNTRY_FLAGS=COUNTRY_FLAGS,
        COUNTRY_NAMES=COUNTRY_NAMES,
        dm_settings=DMSettings.query.filter_by(profile_id=profile.id).first(),
    )



@creator_bp.route('/creator-dashboard/videos', endpoint='creator_dashboard_videos')
    
@manager_required
def creator_dashboard_videos():
    """Video management page for the assigned creator."""
    profile, _ = resolve_creator_dashboard_profile()

    videos = Video.query.filter_by(profile_id=profile.id).order_by(Video.created_at.desc()).all()
    return render_template(
        'creator_dashboard_videos.html',
        profile=profile,
        videos=videos,
        COUNTRY_FLAGS=COUNTRY_FLAGS,
        COUNTRY_NAMES=COUNTRY_NAMES,
    )



@creator_bp.route('/creator-dashboard/upload-photo', methods=['GET', 'POST'], endpoint='creator_upload_photo')
    
@creator_only_required
def creator_upload_photo():
    """Creator manager uploads a photo for their assigned creator."""
    profile, _ = resolve_creator_dashboard_profile()

    if request.method == 'POST':
        allowed, limit_msg = check_upload_allowed(profile, 'photo')
        if not allowed:
            flash(limit_msg, 'error')
            return redirect(upload_url('vx_become_creator_premium', profile.id))

        title       = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category    = request.form.get('category', '').strip()
        tier        = request.form.get('tier', 'basic').strip()
        unlock_price= float(request.form.get('unlock_price', 2.0) or 2.0)
        blur_strength= int(request.form.get('blur_strength', 12) or 12)
        photo_file  = request.files.get('photo_file')

        # Premium-only: high-res / premium tier requires active Premium subscription
        if tier == 'premium' and not profile.is_premium:
            flash('Uploading to the Premium tier requires a Premium subscription.', 'error')
            return redirect(url_for('vx_become_creator_premium'))

        if not title:
            flash('Title is required.', 'error')
            return redirect(upload_url('creator_upload_photo', profile.id))
        if not photo_file or not photo_file.filename:
            flash('Please select a photo to upload.', 'error')
            return redirect(upload_url('creator_upload_photo', profile.id))
        if not allowed_file(photo_file.filename):
            flash('Invalid file type. Use JPG, PNG, or WEBP.', 'error')
            return redirect(upload_url('creator_upload_photo', profile.id))

        ext = photo_file.filename.rsplit('.', 1)[1].lower()
        uid = str(uuid.uuid4())
        orig_filename    = '{}.{}'.format(uid, ext)
        preview_filename = 'prev_{}.jpg'.format(uid)

        orig_dir    = os.path.join(current_app.config['UPLOAD_FOLDER'], 'originals')
        preview_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'previews')
        os.makedirs(orig_dir, exist_ok=True)
        os.makedirs(preview_dir, exist_ok=True)

        orig_path    = os.path.join(orig_dir, orig_filename)
        preview_path = os.path.join(preview_dir, preview_filename)

        photo_file.save(orig_path)
        ok = generate_watermark_preview(orig_path, preview_path, blur_strength)
        if not ok:
            import shutil
            shutil.copy(orig_path, preview_path)

        photo = Photo(
            profile_id=profile.id,
            title=title,
            description=description,
            category=category,
            tier=tier,
            original_filename=orig_filename,
            preview_filename=preview_filename,
            unlock_price=unlock_price,
            unlock_duration=int(request.form.get('unlock_duration', 24) or 24),
            is_active=True,
        )
        db.session.add(photo)
        db.session.flush()

        # Also create ProfilePost so it appears on creator profile
        profile_post = ProfilePost(
            profile_id=profile.id,
            title=title,
            caption=description,
            post_type='photo',
            photo_id=photo.id,
            blur_strength=blur_strength,
            is_active=True,
        )
        db.session.add(profile_post)
        db.session.commit()

        flash('Photo uploaded successfully!', 'success')
        return redirect(upload_url('creator_dashboard', profile.id))

    categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order, Category.name).all()
    return render_template(
        'creator_upload_photo.html',
        profile=profile,
        categories=categories,
        COUNTRY_FLAGS=COUNTRY_FLAGS,
        COUNTRY_NAMES=COUNTRY_NAMES,
    )



@creator_bp.route('/creator-dashboard/upload-video', methods=['GET', 'POST'], endpoint='creator_upload_video')
    
@creator_only_required
def creator_upload_video():
    """Creator manager uploads a video for their assigned creator."""
    profile, _ = resolve_creator_dashboard_profile()

    if request.method == 'POST':
        allowed, limit_msg = check_upload_allowed(profile, 'video')
        if not allowed:
            flash(limit_msg, 'error')
            return redirect(upload_url('vx_become_creator_premium', profile.id))

        title       = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category    = request.form.get('category', '').strip()
        tier        = request.form.get('tier', 'basic').strip()
        unlock_price = float(request.form.get('unlock_price', 5.0) or 5.0)
        # Creator chooses which part of the video plays as the hover/preview clip
        preview_start_seconds    = int(request.form.get('preview_start_seconds', 0) or 0)
        preview_duration_seconds = max(3, min(5, int(request.form.get('preview_duration_seconds', 4) or 4)))
        blur_strength             = max(0, min(40, int(request.form.get('blur_strength', 8) or 8)))

        # Premium-only tier (longer length / higher quality / no price ceiling)
        if tier == 'premium' and not profile.is_premium:
            flash('Uploading to the Premium tier requires a Premium subscription.', 'error')
            return redirect(url_for('vx_become_creator_premium'))
        if not profile.is_premium and unlock_price > 50:
            flash('Basic plan videos are capped at $50. Upgrade to Premium to set a higher price.', 'error')
            return redirect(url_for('creator_upload_video'))

        video_file = request.files.get('video_file')

        if not title:
            flash('Title is required.', 'error')
            return redirect(upload_url('creator_upload_video', profile.id))

        video_filename = None
        if video_file and video_file.filename and allowed_video(video_file.filename):
            ext = video_file.filename.rsplit('.', 1)[1].lower()
            video_filename = 'vid_{}_{}.{}'.format(profile.username, str(uuid.uuid4())[:8], ext)
            videos_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'videos')
            os.makedirs(videos_dir, exist_ok=True)
            video_file.save(os.path.join(videos_dir, video_filename))

        # No manual thumbnail upload — the hover-preview clip IS the thumbnail.
        # The frontend plays preview_duration_seconds of video starting at
        # preview_start_seconds on hover, blurred at blur_strength.
        video = Video(
            profile_id=profile.id,
            title=title,
            description=description,
            category=category,
            tier=tier,
            video_filename=video_filename,
            thumbnail_filename=None,
            unlock_price=unlock_price,
            unlock_duration=int(request.form.get('unlock_duration', 24) or 24),
            preview_start_seconds=preview_start_seconds,
            preview_duration_seconds=preview_duration_seconds,
            blur_strength=blur_strength,
            is_active=True,
        )
        db.session.add(video)
        db.session.flush()

        # Create ProfilePost so video appears on creator profile
        profile_post = ProfilePost(
            profile_id=profile.id,
            title=title,
            caption=description,
            post_type='video',
            video_id=video.id,
            blur_strength=blur_strength,
            is_active=True,
        )
        db.session.add(profile_post)
        db.session.commit()
        flash('Video uploaded successfully!', 'success')
        return redirect(upload_url('creator_dashboard_videos', profile.id))

    categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order, Category.name).all()
    return render_template(
        'creator_upload_video.html',
        profile=profile,
        categories=categories,
        COUNTRY_FLAGS=COUNTRY_FLAGS,
        COUNTRY_NAMES=COUNTRY_NAMES,
    )



@creator_bp.route('/creator-dashboard/video/<int:video_id>/delete', methods=['POST'], endpoint='creator_delete_video')
    
@manager_required
def creator_delete_video(video_id):
    """Creator manager deletes one of their creator's videos."""
    video = Video.query.get_or_404(video_id)
    # Access control — only the assigned manager can delete
    profile = Profile.query.filter_by(manager_id=session.get('user_id')).first()
    if not profile or profile.id != video.profile_id:
        abort(403)
    profile_id = profile.id

    db.session.delete(video)
    db.session.commit()
    flash('Video deleted.', 'success')
    return redirect(upload_url('creator_dashboard_videos', profile_id))



@creator_bp.route('/creator-dashboard/premium', methods=['GET', 'POST'], endpoint='vx_become_creator_premium')
    
@manager_required
def vx_become_creator_premium():
    """Either role (sole creator's manager OR admin-managed account) can
    subscribe their profile to Premium. 100% of this revenue goes to the
    platform — it never appears in the creator/manager/ops split."""
    user_id  = session.get('user_id')
    is_admin = session.get('is_admin', False)

    profile_id = request.args.get('profile_id', type=int) or request.form.get('profile_id', type=int)
    if is_admin and profile_id:
        profile = Profile.query.get_or_404(profile_id)
    elif profile_id and Profile.query.filter_by(id=profile_id, manager_id=user_id).first():
        profile = Profile.query.get_or_404(profile_id)
    else:
        profile = Profile.query.filter_by(manager_id=user_id).first()
        if not profile:
            # Maybe they are a sole creator instead of a manager
            ca = CreatorAccount.query.filter_by(user_id=user_id).first()
            profile = ca.profile if ca else None
    if not profile:
        return redirect(url_for('creator_dashboard'))

    if request.method == 'POST':
        # Simulate successful payment confirmation (Stripe/Paystack/Binance hookup point)
        profile.is_premium         = True
        profile.premium_started_at = datetime.utcnow()

        # Record this as a pure-platform transaction — no creator/manager/ops split
        txn = VaultTransaction(
            reference=make_transaction_ref(),
            session_token=get_session_token(),
            profile_id=profile.id,
            content_type='premium_subscription',
            gross_amount=PREMIUM_MONTHLY_PRICE,
            gateway=request.form.get('gateway', 'stripe'),
            status='completed'
        )
        db.session.add(txn)
        db.session.flush()
        db.session.add(EarningsRecord(
            transaction_id=txn.id,
            beneficiary_type='platform',
            beneficiary_user_id=None,
            profile_id=profile.id,
            amount=PREMIUM_MONTHLY_PRICE,
            content_type='premium_subscription',
            is_available=True
        ))
        db.session.commit()
        flash('🌟 Premium activated! Unlimited uploads and live hours are now unlocked.', 'success')
        return redirect(url_for('creator_dashboard'))

    return render_template('vx_creator_premium.html', profile=profile, price=PREMIUM_MONTHLY_PRICE)



@creator_bp.route('/creator/home', endpoint='creator_home')
    
@creator_required
def creator_home():
    ca = CreatorAccount.query.get(session['creator_account_id'])
    profile = ca.profile
    user_id = ca.user_id
    pending, available, lifetime = get_user_balances(user_id)
    breakdown = get_user_revenue_breakdown(user_id)

    # Revenue by period
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start  = today_start - timedelta(days=now.weekday())
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def period_earnings(start):
        return db.session.query(db.func.sum(EarningsRecord.amount))\
            .filter(EarningsRecord.beneficiary_user_id==user_id,
                    EarningsRecord.created_at>=start).scalar() or 0.0

    today_rev   = period_earnings(today_start)
    weekly_rev  = period_earnings(week_start)
    monthly_rev = period_earnings(month_start)

    # Subscriber count
    subscriber_count = Subscription.query.filter_by(profile_id=profile.id, status='active').count()

    # Show telegram channels popup
    show_telegram = session.pop('show_creator_telegram', False)
    creator_channels = TelegramChannel.query.filter_by(channel_type='creator', is_active=True).all()

    withdrawal_open = is_withdrawal_day()
    next_window = next_withdrawal_day()

    return render_template('vx_creator_home.html',
        ca=ca, profile=profile,
        pending=pending, available=available, lifetime=lifetime,
        breakdown=breakdown,
        today_rev=today_rev, weekly_rev=weekly_rev, monthly_rev=monthly_rev,
        subscriber_count=subscriber_count,
        show_telegram=show_telegram,
        creator_channels=creator_channels,
        withdrawal_open=withdrawal_open,
        next_window=next_window
    )



@creator_bp.route('/manager/edit-profile', methods=['GET', 'POST'], endpoint='manager_edit_profile')
    
@manager_required
def manager_edit_profile():
    """Creator manager edits the profile they manage."""
    user_id = session.get('user_id')
    profile = Profile.query.filter_by(manager_id=user_id).first_or_404()

    categories = Category.query.filter_by(is_active=True).all()
    blur = get_blur_settings(profile.id)

    if request.method == 'POST':
        profile.name        = request.form.get('name', profile.name).strip()
        profile.bio          = request.form.get('bio', profile.bio).strip()
        profile.tagline      = request.form.get('tagline', profile.tagline).strip()
        profile.category     = request.form.get('category', profile.category).strip()
        profile.accent_color = request.form.get('accent_color', profile.accent_color).strip()
        profile.country_code = request.form.get('country_code', profile.country_code).strip()

        # ── Blur strength — the creator/manager controls this, not admin ────
        blur.photo_blur = max(0, min(40, int(request.form.get('photo_blur', blur.photo_blur) or blur.photo_blur)))
        blur.video_blur = max(0, min(40, int(request.form.get('video_blur', blur.video_blur) or blur.video_blur)))
        blur.updated_at = datetime.utcnow()

        # ── Manager account credentials (manager = account owner) ──────────
        if not is_admin:
            manager_user = User.query.get(user_id)
            if manager_user:
                new_email = request.form.get('email', '').strip().lower()
                if new_email and new_email != manager_user.email and not User.query.filter_by(email=new_email).first():
                    manager_user.email = new_email
                new_pass = request.form.get('new_password', '').strip()
                if new_pass and len(new_pass) >= 6:
                    manager_user.password_hash = generate_password_hash(new_pass)

        # ── Social links — fully dynamic, no fixed platform list ────────────
        SocialLink.query.filter_by(profile_id=profile.id).delete()
        platforms = request.form.getlist('social_platform[]')
        urls      = request.form.getlist('social_url[]')
        for i, (plat, url) in enumerate(zip(platforms, urls)):
            plat = plat.strip().lower()
            url  = url.strip()
            if plat and url:
                db.session.add(SocialLink(
                    profile_id=profile.id, platform=plat, url=url, sort_order=i
                ))

        # Avatar upload from device (file takes priority, no URL fallback required)
        avatar_file = request.files.get('avatar')
        if avatar_file and avatar_file.filename and allowed_image(avatar_file.filename):
            ext = avatar_file.filename.rsplit('.', 1)[1].lower()
            fname = 'avatar_{}_{}.{}'.format(profile.id, int(time.time()), ext)
            save_path = os.path.join(current_app.config['PROFILE_UPLOAD_FOLDER'], fname)
            avatar_file.save(save_path)
            profile.avatar_filename = fname

        # Cover upload from device
        cover_file = request.files.get('cover')
        if cover_file and cover_file.filename and allowed_image(cover_file.filename):
            ext = cover_file.filename.rsplit('.', 1)[1].lower()
            fname = 'cover_{}_{}.{}'.format(profile.id, int(time.time()), ext)
            save_path = os.path.join(current_app.config['PROFILE_UPLOAD_FOLDER'], fname)
            cover_file.save(save_path)
            profile.cover_filename = fname

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('creator_dashboard'))

    social_links = SocialLink.query.filter_by(profile_id=profile.id).order_by(SocialLink.sort_order).all()
    manager_user = User.query.get(user_id) if not is_admin else None
    return render_template('creator_edit_profile.html',
                           profile=profile,
                           categories=categories,
                           blur=blur,
                           social_links=social_links,
                           manager_user=manager_user,
                           COUNTRY_FLAGS=COUNTRY_FLAGS,
                           COUNTRY_NAMES=COUNTRY_NAMES)



@creator_bp.route('/creator/edit-profile', methods=['GET', 'POST'], endpoint='creator_edit_profile')
    
@creator_required
def creator_edit_profile():
    ca = CreatorAccount.query.get(session['creator_account_id'])
    profile = ca.profile
    user = ca.user
    blur = get_blur_settings(profile.id)

    if request.method == 'POST':
        profile.name        = request.form.get('name', profile.name).strip()
        profile.username    = request.form.get('username', profile.username).strip().lower()
        profile.bio         = request.form.get('bio', profile.bio).strip()
        profile.country_code= request.form.get('country_code', profile.country_code).strip()
        profile.category    = request.form.get('category', profile.category).strip()

        # Avatar — file upload takes priority over URL
        avatar_file = request.files.get('avatar_file')
        if avatar_file and avatar_file.filename and allowed_image(avatar_file.filename):
            ext = avatar_file.filename.rsplit('.', 1)[1].lower()
            fname = 'avatar_{}_{}.{}'.format(profile.id, int(time.time()), ext)
            save_path = os.path.join(current_app.config['PROFILE_UPLOAD_FOLDER'], fname)
            avatar_file.save(save_path)
            profile.avatar_filename = fname
        else:
            avatar_url = request.form.get('avatar_url', '').strip()
            if avatar_url:
                profile.avatar_filename = avatar_url

        # Cover — file upload takes priority over URL
        cover_file = request.files.get('cover_file')
        if cover_file and cover_file.filename and allowed_image(cover_file.filename):
            ext = cover_file.filename.rsplit('.', 1)[1].lower()
            fname = 'cover_{}_{}.{}'.format(profile.id, int(time.time()), ext)
            save_path = os.path.join(current_app.config['PROFILE_UPLOAD_FOLDER'], fname)
            cover_file.save(save_path)
            profile.cover_filename = fname
        else:
            cover_url = request.form.get('cover_url', '').strip()
            if cover_url:
                profile.cover_filename = cover_url

        # Password change
        new_pass = request.form.get('new_password', '').strip()
        if new_pass and len(new_pass) >= 6:
            user.password_hash = generate_password_hash(new_pass)

        # Email change
        new_email = request.form.get('email', '').strip()
        if new_email and new_email != user.email:
            user.email = new_email

        # ── Blur strength — creator-controlled, not admin-only ──────────────
        blur.photo_blur = max(0, min(40, int(request.form.get('photo_blur', blur.photo_blur) or blur.photo_blur)))
        blur.video_blur = max(0, min(40, int(request.form.get('video_blur', blur.video_blur) or blur.video_blur)))
        blur.updated_at = datetime.utcnow()

        # ── Social links — fully dynamic, creator adds as many as they want ──
        SocialLink.query.filter_by(profile_id=profile.id).delete()
        platforms = request.form.getlist('social_platform[]')
        urls      = request.form.getlist('social_url[]')
        for i, (plat, url) in enumerate(zip(platforms, urls)):
            plat = plat.strip().lower()
            url  = url.strip()
            if plat and url:
                db.session.add(SocialLink(
                    profile_id=profile.id, platform=plat, url=url, sort_order=i
                ))

        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('creator_home'))

    categories   = Category.query.filter_by(is_active=True).all()
    social_links = SocialLink.query.filter_by(profile_id=profile.id).order_by(SocialLink.sort_order).all()
    return render_template('vx_creator_edit_profile.html', ca=ca, profile=profile, user=user,
                           categories=categories, blur=blur, social_links=social_links,
                           COUNTRY_FLAGS=COUNTRY_FLAGS, COUNTRY_NAMES=COUNTRY_NAMES)


# ─────────────────────────────────────────────────────────────────────────────
# CREATOR WITHDRAWAL
# ─────────────────────────────────────────────────────────────────────────────


@creator_bp.route('/creator/payout-methods', methods=['GET', 'POST'], endpoint='creator_payout_methods')
    
def creator_payout_methods():
    user_id, profile, ca = _resolve_creator_context()
    if not user_id:
        return redirect(url_for('creator_login'))
    if request.method == 'POST':
        method_type = request.form.get('method_type', 'mpesa')
        pm = PayoutMethod(
            user_id     = user_id,
            method_type = method_type,
            mpesa_number= request.form.get('mpesa_number','').strip(),
            bank_name   = request.form.get('bank_name','').strip(),
            bank_account= request.form.get('bank_account','').strip(),
            paypal_email= request.form.get('paypal_email','').strip(),
            crypto_wallet=request.form.get('crypto_wallet','').strip(),
            crypto_type = request.form.get('crypto_type','USDT').strip(),
            is_default  = True
        )
        PayoutMethod.query.filter_by(user_id=user_id, is_default=True).update({'is_default': False})
        db.session.add(pm)
        db.session.commit()
        flash('Payout method saved!', 'success')
        return redirect(url_for('creator_payout_methods'))
    methods = PayoutMethod.query.filter_by(user_id=user_id).all()
    return render_template('vx_payout_methods.html', ca=ca, profile=profile, methods=methods)



@creator_bp.route('/creator/withdraw', methods=['GET', 'POST'], endpoint='creator_withdraw')
    
def creator_withdraw():
    user_id, profile, ca = _resolve_creator_context()
    if not user_id:
        return redirect(url_for('creator_login'))

    if not is_withdrawal_day():
        next_win = next_withdrawal_day()
        return render_template('vx_withdrawal_closed.html', next_window=next_win, ca=ca)

    pending, available, lifetime = get_user_balances(user_id)
    methods = PayoutMethod.query.filter_by(user_id=user_id).all()

    if request.method == 'POST':
        amount = float(request.form.get('amount', 0))
        method_id = request.form.get('payout_method_id')

        if amount <= 0 or amount > available:
            flash('Invalid amount. You can only withdraw available balance.', 'error')
            return redirect(url_for('creator_withdraw'))

        if not method_id:
            flash('Please select a payout method.', 'error')
            return redirect(url_for('creator_withdraw'))

        pm = PayoutMethod.query.get(method_id)
        if not pm or pm.user_id != user_id:
            flash('Invalid payout method.', 'error')
            return redirect(url_for('creator_withdraw'))

        snapshot = json.dumps({
            'type': pm.method_type,
            'mpesa': pm.mpesa_number,
            'bank': pm.bank_name,
            'account': pm.bank_account,
            'paypal': pm.paypal_email,
            'crypto': pm.crypto_wallet,
            'crypto_type': pm.crypto_type
        })

        wr = WithdrawalRequest(
            user_id=user_id,
            amount=amount,
            payout_method_id=pm.id,
            method_snapshot=snapshot,
            status='pending'
        )
        db.session.add(wr)
        db.session.commit()

        if not lock_earnings_for_withdrawal(user_id, amount, wr):
            db.session.delete(wr)
            db.session.commit()
            flash('Could not lock funds — please refresh and try again.', 'error')
            return redirect(url_for('creator_withdraw'))

        flash('Withdrawal request submitted! Admin will process it soon.', 'success')
        if ca:
            return redirect(url_for('creator_home'))
        return redirect(url_for('creator_dashboard'))

    return render_template('vx_withdraw.html',
        ca=ca, profile=profile, available=available, pending=pending, lifetime=lifetime, methods=methods)



@creator_bp.route('/creator/withdrawal-history', endpoint='creator_withdrawal_history')
    
def creator_withdrawal_history():
    user_id, profile, ca = _resolve_creator_context()
    if not user_id:
        return redirect(url_for('creator_login'))
    requests_list = WithdrawalRequest.query.filter_by(user_id=user_id)\
        .order_by(WithdrawalRequest.requested_at.desc()).all()
    return render_template('vx_withdrawal_history.html', ca=ca, profile=profile, requests=requests_list)


# ─────────────────────────────────────────────────────────────────────────────
# DM SYSTEM
# ─────────────────────────────────────────────────────────────────────────────


@creator_bp.route('/creator/application-status', endpoint='creator_application_status')
    
def creator_application_status():
    """Creator manager can see their own application status."""
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('creator_login'))
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('creator_login'))
    # Find their application by email
    app_record = CreatorApplication.query.filter_by(
        applicant_email=user.email
    ).order_by(CreatorApplication.created_at.desc()).first()
    profile = Profile.query.filter_by(manager_id=user_id).first()
    return render_template('creator_application_status.html',
                           app_record=app_record, user=user, profile=profile)



@creator_bp.route('/creator/dm-settings', methods=['GET', 'POST'], endpoint='creator_dm_settings')
    
def creator_dm_settings():
    """Creator/Manager controls DM inbox monetization."""
    user_id, profile, ca = _resolve_creator_context()
    if not user_id or not profile:
        return redirect(url_for('creator_login'))

    settings = DMSettings.query.filter_by(profile_id=profile.id).first()
    if not settings:
        settings = DMSettings(profile_id=profile.id)
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        settings.dm_enabled     = request.form.get('dm_enabled') == 'on'
        settings.charge_per_msg = request.form.get('charge_per_msg') == 'on'
        settings.msg_price      = max(0.0, float(request.form.get('msg_price', 1.0) or 1.0))
        settings.auto_reply_text= request.form.get('auto_reply_text', '').strip()[:500]
        settings.updated_at     = datetime.utcnow()
        db.session.commit()
        flash('DM settings updated!', 'success')
        if ca:
            return redirect(url_for('creator_home'))
        return redirect(url_for('creator_dashboard'))

    return render_template('creator_dm_settings.html', ca=ca, profile=profile, settings=settings)



@creator_bp.route('/creator/dm-inbox', endpoint='creator_dm_inbox')
    
def creator_dm_inbox():
    # Allow both sole creators and assigned managers
    if session.get('creator_account_id'):
        ca = CreatorAccount.query.get(session['creator_account_id'])
        if not ca:
            return redirect(url_for('creator_login'))
        profile_id = ca.profile_id
        threads = DMThread.query.filter_by(profile_id=profile_id)\
            .order_by(DMThread.last_message_at.desc()).all()
        return render_template('vx_creator_dm_inbox.html', ca=ca, threads=threads)
    elif session.get('is_manager'):
        user_id = session.get('user_id')
        profile = Profile.query.filter_by(manager_id=user_id).first()
        if not profile:
            flash('No creator profile assigned to your account.', 'error')
            return redirect(url_for('creator_dashboard'))
        threads = DMThread.query.filter_by(profile_id=profile.id)\
            .order_by(DMThread.last_message_at.desc()).all()
        return render_template('vx_creator_dm_inbox.html', ca=None, profile=profile, threads=threads)
    return redirect(url_for('creator_login'))



@creator_bp.route('/creator/dm-thread/<int:thread_id>', methods=['GET', 'POST'], endpoint='creator_dm_reply')
    
def creator_dm_reply(thread_id):
    # Resolve who is replying — sole creator or manager
    ca = None
    profile = None
    sender_user_id = None

    if session.get('creator_account_id'):
        ca = CreatorAccount.query.get(session['creator_account_id'])
        if not ca:
            return redirect(url_for('creator_login'))
        profile_id = ca.profile_id
        sender_user_id = ca.user_id
    elif session.get('is_manager'):
        user_id = session.get('user_id')
        profile = Profile.query.filter_by(manager_id=user_id).first()
        if not profile:
            return redirect(url_for('creator_dashboard'))
        profile_id = profile.id
        sender_user_id = user_id
    else:
        return redirect(url_for('creator_login'))

    thread = DMThread.query.filter_by(id=thread_id, profile_id=profile_id).first_or_404()

    if request.method == 'POST':
        body        = request.form.get('body', '').strip()
        lock_price  = float(request.form.get('lock_price', 0) or 0)
        media_url   = request.form.get('media_url', '').strip()
        media_type  = request.form.get('media_type', '').strip()

        msg = DMMessage(
            thread_id=thread.id,
            sender_type='creator',
            sender_user_id=sender_user_id,
            body=body[:2000],
            media_url=media_url,
            media_type=media_type,
            lock_price=lock_price,
            is_unlocked=(lock_price == 0)
        )
        db.session.add(msg)
        thread.last_message_at = datetime.utcnow()
        db.session.commit()
        flash('Message sent!', 'success')
        return redirect(url_for('creator_dm_reply', thread_id=thread_id))

    messages = DMMessage.query.filter_by(thread_id=thread.id).order_by(DMMessage.created_at).all()
    return render_template('vx_creator_dm_reply.html', ca=ca, profile=profile, thread=thread, messages=messages)



@creator_bp.route('/manager/dashboard', endpoint='manager_vx_dashboard')
    
def manager_vx_dashboard():
    if session.get('user_role') != 'creator_manager' and not session.get('is_admin'):
        return redirect(url_for('manager_login_vx'))
    user_id = session.get('manager_vx_user_id') or session.get('user_id')

    # Try CreatorManagerProfile first (new system); fall back to Profile.manager_id
    cmp = CreatorManagerProfile.query.filter_by(user_id=user_id).first()

    pending, available, lifetime = get_user_balances(user_id)
    breakdown = get_user_revenue_breakdown(user_id)

    # Profiles managed via old Profile.manager_id system
    managed_profiles = Profile.query.filter_by(manager_id=user_id, is_active=True).all()

    # Creator accounts linked via new CreatorManagerProfile system
    managed_cas = CreatorAccount.query.filter_by(
        creator_manager_id=cmp.id if cmp else None
    ).all() if cmp else []

    # Build unified stats list
    creator_stats = []
    seen_profile_ids = set()

    # From old system (Profile.manager_id)
    for profile in managed_profiles:
        if profile.id not in seen_profile_ids:
            seen_profile_ids.add(profile.id)
            # Earnings for manager-run profiles are recorded against manager's user_id
            _, _, life = get_user_balances(user_id)
            creator_stats.append({
                'profile': profile,
                'ca': None,
                'lifetime': life,
                'source': 'manager_trial'
            })

    # From new system (CreatorAccount.creator_manager_id)
    for ca in managed_cas:
        if ca.profile_id not in seen_profile_ids:
            seen_profile_ids.add(ca.profile_id)
            _, _, life = get_user_balances(ca.user_id)
            creator_stats.append({
                'profile': ca.profile,
                'ca': ca,
                'lifetime': life,
                'source': 'sole_creator'
            })

    withdrawal_open = is_withdrawal_day()
    next_win = next_withdrawal_day()

    return render_template('vx_manager_dashboard.html',
        cmp=cmp, pending=pending, available=available, lifetime=lifetime,
        breakdown=breakdown, creator_stats=creator_stats,
        withdrawal_open=withdrawal_open, next_window=next_win
    )



@creator_bp.route('/manager/withdraw', methods=['GET', 'POST'], endpoint='manager_withdraw')
    
def manager_withdraw():
    if session.get('user_role') != 'creator_manager' and not session.get('is_admin'):
        return redirect(url_for('manager_login_vx'))
    user_id = session.get('manager_vx_user_id') or session.get('user_id')

    if not is_withdrawal_day():
        return render_template('vx_withdrawal_closed.html', next_window=next_withdrawal_day())

    pending, available, lifetime = get_user_balances(user_id)
    methods = PayoutMethod.query.filter_by(user_id=user_id).all()

    if request.method == 'POST':
        amount = float(request.form.get('amount', 0))
        method_id = request.form.get('payout_method_id')
        if amount <= 0 or amount > available:
            flash('Invalid amount.', 'error')
            return redirect(url_for('manager_withdraw'))
        pm = PayoutMethod.query.get(method_id)
        if not pm or pm.user_id != user_id:
            flash('Invalid method.', 'error')
            return redirect(url_for('manager_withdraw'))
        wr = WithdrawalRequest(
            user_id=user_id, amount=amount,
            payout_method_id=pm.id,
            method_snapshot=json.dumps({'type': pm.method_type}),
            status='pending'
        )
        db.session.add(wr)
        db.session.commit()
        flash('Withdrawal request submitted!', 'success')
        return redirect(url_for('manager_vx_dashboard'))

    return render_template('vx_withdraw.html',
        available=available, pending=pending, lifetime=lifetime, methods=methods
    )


# ─────────────────────────────────────────────────────────────────────────────
# AFTER PURCHASE — TELEGRAM REDIRECT
# ─────────────────────────────────────────────────────────────────────────────


@creator_bp.route('/post-purchase-telegram', endpoint='post_purchase_telegram')
    
def post_purchase_telegram():
    """Show subscriber Telegram join links after any purchase."""
    channels = TelegramChannel.query.filter_by(channel_type='subscriber', is_active=True).all()
    return render_template('vx_post_purchase_telegram.html', channels=channels)


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL HELPERS
# ─────────────────────────────────────────────────────────────────────────────


@creator_bp.route('/apply-to-be-creator-v2', methods=['GET', 'POST'], endpoint='apply_to_be_creator_v2')
    
def apply_to_be_creator_v2():
    """Public page to apply to become a creator manager or verified creator.
    Sends notification email to admin on submission."""
    if request.method == 'POST':
        app_type    = request.form.get('application_type', 'junior_creator')
        name        = request.form.get('applicant_name', '').strip()
        email       = request.form.get('applicant_email', '').strip().lower()
        motivation  = request.form.get('motivation', '').strip()
        content_type= request.form.get('content_type', '').strip()
        social_links= request.form.get('social_links', '').strip()
        legal_name  = request.form.get('legal_name', '').strip()
        dob_str     = request.form.get('date_of_birth', '').strip()

        if not name or not email:
            flash('Name and email are required.', 'error')
            return redirect(url_for('apply_to_be_creator_v2'))

        # Age check for verified_creator applications
        dob = None
        if dob_str:
            try:
                from datetime import date
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
                age = (date.today() - dob).days // 365
                if age < 18:
                    flash('You must be 18 or older to apply.', 'error')
                    return redirect(url_for('apply_to_be_creator_v2'))
            except Exception:
                pass

        # Handle ID / selfie uploads
        id_filename = selfie_filename = None
        for field, prefix in [('id_document', 'id_doc'), ('selfie_document', 'selfie')]:
            f = request.files.get(field)
            if f and f.filename and allowed_image(f.filename):
                ext = f.filename.rsplit('.', 1)[1].lower()
                fname = '{}_{}_{}.{}'.format(prefix, email.replace('@','_'), int(time.time()), ext)
                f.save(os.path.join(current_app.config['PROFILE_UPLOAD_FOLDER'], fname))
                if field == 'id_document':
                    id_filename = fname
                else:
                    selfie_filename = fname

        user_id = session.get('user_id')
        app_record = CreatorApplication(
            user_id=user_id,
            applicant_name=name,
            applicant_email=email,
            application_type=app_type,
            motivation=motivation,
            content_type=content_type,
            social_links=social_links,
            legal_name=legal_name,
            id_document=id_filename,
            selfie_document=selfie_filename,
            date_of_birth=dob,
            status='pending',
            stage=1
        )
        db.session.add(app_record)
        db.session.commit()

        # Notify admin via email
        send_application_notification_email(app_record)

        flash('Application submitted! We will review and contact you at {}.'.format(email), 'success')
        return redirect(url_for('application_status', app_id=app_record.id))

    preselect = request.args.get('type', 'junior_creator')
    return render_template('apply_creator.html', preselect=preselect)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN: GRANT CREATOR MANAGER ACCOUNT FROM APPLICATION
# ─────────────────────────────────────────────────────────────────────────────
