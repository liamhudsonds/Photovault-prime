"""VaultX admin routes."""
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

admin_bp = Blueprint("admin", __name__)

@admin_bp.route('/admin', endpoint='admin_dashboard')
    
@admin_required
def admin_dashboard():
    total_photos    = Photo.query.count()
    total_videos    = Video.query.count()
    total_users     = User.query.filter_by(is_admin=False).count()
    total_revenue   = db.session.query(db.func.sum(Payment.amount)).filter_by(status='completed').scalar() or 0
    total_purchases = Purchase.query.count()

    recent_payments = Payment.query.order_by(Payment.created_at.desc()).limit(10).all()
    photos          = Photo.query.order_by(Photo.created_at.desc()).all()
    videos          = Video.query.order_by(Video.created_at.desc()).all()
    users           = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).all()

    return render_template(
        'admin_dashboard.html',
        total_photos=total_photos,
        total_videos=total_videos,
        total_users=total_users,
        total_revenue=total_revenue,
        total_purchases=total_purchases,
        recent_payments=recent_payments,
        photos=photos,
        videos=videos,
        users=users,
        admin=session.get('admin')
    )



@admin_bp.route('/admin/photo/<int:photo_id>/edit', methods=['GET', 'POST'], endpoint='admin_edit_photo')
    
@admin_required
def admin_edit_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    if request.method == 'POST':
        photo.title           = request.form.get('title', photo.title)
        photo.description     = request.form.get('description', photo.description)
        photo.category        = request.form.get('category', photo.category)
        photo.tier            = request.form.get('tier', photo.tier)
        photo.unlock_price    = float(request.form.get('price', photo.unlock_price))
        photo.unlock_duration = int(request.form.get('duration', photo.unlock_duration))
        photo.dynamic_pricing = request.form.get('dynamic_pricing') == 'on'
        photo.is_active       = request.form.get('is_active') == 'on'
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_edit_photo.html', photo=photo)



@admin_bp.route('/admin/photo/<int:photo_id>/delete', methods=['POST'], endpoint='admin_delete_photo')
    
@admin_required
def admin_delete_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    photo.is_active = False
    db.session.commit()
    return redirect(url_for('admin_dashboard'))



@admin_bp.route('/admin/user/<int:user_id>/block', methods=['POST'], endpoint='admin_block_user')
    
@admin_required
def admin_block_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_blocked = not user.is_blocked
    db.session.commit()
    return redirect(url_for('admin_dashboard'))



@admin_bp.route('/admin/revenue', endpoint='admin_revenue')
    
@admin_required
def admin_revenue():
    payments   = Payment.query.filter_by(status='completed').order_by(Payment.created_at.desc()).all()
    by_gateway = {}
    for p in payments:
        by_gateway[p.gateway] = by_gateway.get(p.gateway, 0) + p.amount
    return render_template('admin_revenue.html', payments=payments, by_gateway=by_gateway)



@admin_bp.route('/admin/video/<int:video_id>/delete', methods=['POST'], endpoint='admin_delete_video')
    
@admin_required
def admin_delete_video(video_id):
    video = Video.query.get_or_404(video_id)
    for folder, attr in [('videos', 'video_filename'), ('video_thumbs', 'thumbnail_filename'),
                         ('video_previews', 'preview_filename')]:
        fn = getattr(video, attr)
        if fn:
            try:
                os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], folder, fn))
            except OSError:
                pass
    db.session.delete(video)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))


# ── API ────────────────────────────────────────────────────────────────────────

@admin_bp.route('/admin/settings', methods=['GET', 'POST'], endpoint='admin_settings')
    
@admin_required
def admin_settings():
    if request.method == 'POST':
        # Blur levels
        blur_photo = request.form.get('blur_photo', '12')
        blur_video = request.form.get('blur_video', '16')
        blur_checkout = request.form.get('blur_checkout', '6')
        blur_detail   = request.form.get('blur_detail', '18')
        blur_tint_color = request.form.get('blur_tint_color', 'purple-gold')
 
        set_setting('blur_photo',     blur_photo)
        set_setting('blur_video',     blur_video)
        set_setting('blur_checkout',  blur_checkout)
        set_setting('blur_detail',    blur_detail)
        set_setting('blur_tint_color', blur_tint_color)
 
        # Site config
        set_setting('site_name',        request.form.get('site_name', 'PhotoVault'))
        set_setting('site_tagline',     request.form.get('site_tagline', ''))
        set_setting('allow_comments',   '1' if request.form.get('allow_comments') else '0')
        set_setting('allow_likes',      '1' if request.form.get('allow_likes') else '0')
        set_setting('show_view_counts', '1' if request.form.get('show_view_counts') else '0')
 
        return redirect(url_for('admin_settings'))
 
    settings = {
        'blur_photo':      get_setting('blur_photo', '12'),
        'blur_video':      get_setting('blur_video', '16'),
        'blur_checkout':   get_setting('blur_checkout', '6'),
        'blur_detail':     get_setting('blur_detail', '18'),
        'blur_tint_color': get_setting('blur_tint_color', 'purple-gold'),
        'site_name':       get_setting('site_name', 'PhotoVault'),
        'site_tagline':    get_setting('site_tagline', ''),
        'allow_comments':  get_setting('allow_comments', '1'),
        'allow_likes':     get_setting('allow_likes', '1'),
        'show_view_counts':get_setting('show_view_counts', '1'),
    }
    return render_template('admin_settings.html', settings=settings)
 
 
# ── Admin: Settings API (live preview) ────────────────────────────────────────

@admin_bp.route('/admin/categories', endpoint='admin_categories')
    
@admin_required
def admin_categories():
    cats = Category.query.order_by(Category.sort_order, Category.name).all()
    for cat in cats:
        cat.photo_count = Photo.query.filter_by(category=cat.name).count()
        cat.video_count = Video.query.filter_by(category=cat.name).count()
    return render_template('admin_categories.html', categories=cats)
 
 
# ── Admin: Create category ─────────────────────────────────────────────────────

@admin_bp.route('/admin/categories/create', methods=['POST'], endpoint='admin_create_category')
    
@admin_required
def admin_create_category():
    name         = request.form.get('name', '').strip()
    description  = request.form.get('description', '').strip()
    icon         = request.form.get('icon', '📁').strip() or '📁'
    content_type = request.form.get('content_type', 'both')
    sort_order   = int(request.form.get('sort_order', 0))
 
    if not name:
        return redirect(url_for('admin_categories'))
 
    slug = make_slug(name)
    # Ensure unique slug
    base_slug = slug
    counter   = 1
    while Category.query.filter_by(slug=slug).first():
        slug = '{}-{}'.format(base_slug, counter)
        counter += 1
 
    cat = Category(name=name, slug=slug, description=description,
                   icon=icon, content_type=content_type, sort_order=sort_order)
    db.session.add(cat)
    db.session.commit()
    return redirect(url_for('admin_categories'))
 
 
# ── Admin: Edit category ───────────────────────────────────────────────────────

@admin_bp.route('/admin/categories/<int:cat_id>/edit', methods=['POST'], endpoint='admin_edit_category')
    
@admin_required
def admin_edit_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    cat.name         = request.form.get('name', cat.name).strip()
    cat.description  = request.form.get('description', '').strip()
    cat.icon         = request.form.get('icon', cat.icon).strip() or cat.icon
    cat.content_type = request.form.get('content_type', cat.content_type)
    cat.sort_order   = int(request.form.get('sort_order', cat.sort_order))
    cat.is_active    = bool(request.form.get('is_active'))
    db.session.commit()
    return redirect(url_for('admin_categories'))
 
 
# ── Admin: Delete category ─────────────────────────────────────────────────────

@admin_bp.route('/admin/categories/<int:cat_id>/delete', methods=['POST'], endpoint='admin_delete_category')
    
@admin_required
def admin_delete_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    db.session.delete(cat)
    db.session.commit()
    return redirect(url_for('admin_categories'))
 
 
# ── Admin: Bulk assign category to photos ─────────────────────────────────────

@admin_bp.route('/admin/categories/assign', methods=['POST'], endpoint='admin_assign_category')
    
@admin_required
def admin_assign_category():
    photo_ids    = request.form.getlist('photo_ids')
    category_name = request.form.get('category_name', '').strip()
    for pid in photo_ids:
        photo = Photo.query.get(int(pid))
        if photo:
            photo.category = category_name
    db.session.commit()
    return redirect(url_for('admin_categories'))
 

@admin_bp.route('/admin/comments', endpoint='admin_comments')
    
@admin_required
def admin_comments():
    comments = Comment.query.order_by(Comment.created_at.desc()).all()
    return render_template('admin_comments.html', comments=comments)



@admin_bp.route('/admin/comment/<int:comment_id>/approve', methods=['POST'], endpoint='admin_approve_comment')
    
@admin_required
def admin_approve_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    comment.is_approved = not comment.is_approved
    db.session.commit()
    return redirect(url_for('admin_comments'))



@admin_bp.route('/admin/comment/<int:comment_id>/delete', methods=['POST'], endpoint='admin_delete_comment')
    
@admin_required
def admin_delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for('admin_comments'))



@admin_bp.route('/admin/analytics', endpoint='admin_analytics')
    
@admin_required
def admin_analytics():
    # ── Revenue by gateway ──────────────────────────────────────────────────
    gateways   = db.session.query(Payment.gateway, db.func.sum(Payment.amount))\
                           .filter_by(status='completed').group_by(Payment.gateway).all()
    by_gateway = {g: float(a or 0) for g, a in gateways}
 
    # ── Revenue: photos vs videos (videos stored with different photo_id range)
    total_revenue  = sum(by_gateway.values())
    # ── Top selling photos ──────────────────────────────────────────────────
    top_photos = db.session.query(Photo, db.func.count(Purchase.id).label('sales'))\
        .join(Purchase, Purchase.photo_id == Photo.id)\
        .group_by(Photo.id).order_by(db.text('sales DESC')).limit(8).all()
    # ── Sales by tier ────────────────────────────────────────────────────────
    tier_sales = db.session.query(Photo.tier, db.func.count(Purchase.id))\
        .join(Purchase, Purchase.photo_id == Photo.id)\
        .group_by(Photo.tier).all()
    by_tier = {t: int(c) for t, c in tier_sales}
 
    # ── Revenue by category ──────────────────────────────────────────────────
    cat_rev = db.session.query(Photo.category, db.func.sum(Payment.amount))\
        .join(Payment, Payment.photo_id == Photo.id)\
        .filter(Payment.status=='completed')\
        .group_by(Photo.category).order_by(db.text('sum(payments.amount) DESC')).limit(8).all()
    by_category = [(c or 'Uncategorized', float(a or 0)) for c, a in cat_rev]
 
    # ── Profile performance ──────────────────────────────────────────────────
    profiles = Profile.query.filter_by(is_active=True).all()
    profile_stats = []
    for prf in profiles:
        posts = ProfilePost.query.filter_by(profile_id=prf.id, is_active=True).all()
        total_views = sum(p.view_count for p in posts)
        total_likes = ProfilePostLike.query.join(ProfilePost)\
            .filter(ProfilePost.profile_id == prf.id).count()
        post_count  = len(posts)
        profile_stats.append({
            'id': prf.id, 'name': prf.name, 'username': prf.username,
            'avatar': prf.avatar_filename, 'accent': prf.accent_color,
            'views': total_views, 'likes': total_likes, 'posts': post_count
        })
    profile_stats.sort(key=lambda x: x['views'], reverse=True)
 
    # ── Monthly revenue (last 6 months) ─────────────────────────────────────
    monthly = []
    for i in range(5, -1, -1):
        d     = datetime.utcnow() - timedelta(days=30*i)
        label = d.strftime('%b %Y')
        rev   = db.session.query(db.func.sum(Payment.amount))\
            .filter(Payment.status=='completed',
                    db.extract('month', Payment.created_at)==d.month,
                    db.extract('year',  Payment.created_at)==d.year).scalar() or 0
        monthly.append({'label': label, 'revenue': float(rev)})
 
    # ── Views over time (last 7 days) ────────────────────────────────────────
    daily_views = []
    for i in range(6, -1, -1):
        d = datetime.now(UTC) - timedelta(days=i)
        daily_views.append({'label': d.strftime('%a'), 'day': d.strftime('%Y-%m-%d')})
 
    return render_template('admin_analytics.html',
        by_gateway=by_gateway, total_revenue=total_revenue,
        top_photos=top_photos, by_tier=by_tier,
        by_category=by_category, profile_stats=profile_stats,
        monthly=monthly, daily_views=daily_views)



@admin_bp.route('/admin/trending', endpoint='admin_trending')
    
@admin_required
def admin_trending():
    """Admin view of trending posts + engagement scores."""
    rows = db.session.query(ProfilePost, PostEngagement, Profile)\
        .join(PostEngagement, PostEngagement.post_id == ProfilePost.id)\
        .join(Profile, Profile.id == ProfilePost.profile_id)\
        .filter(ProfilePost.is_active == True)\
        .order_by(PostEngagement.score.desc()).limit(50).all()

    # Creator leaderboard
    creator_scores = db.session.query(
        Profile,
        db.func.sum(PostEngagement.score).label('total_score'),
        db.func.count(ProfilePost.id).label('post_count')
    ).join(ProfilePost, ProfilePost.profile_id == Profile.id)\
     .join(PostEngagement, PostEngagement.post_id == ProfilePost.id)\
     .group_by(Profile.id)\
     .order_by(db.text('total_score DESC')).limit(20).all()

    return render_template('admin_trending.html',
        rows=rows, creator_scores=creator_scores)


@admin_bp.route('/admin/post/<int:post_id>/recalculate', methods=['POST'], endpoint='admin_recalculate_engagement')
    
@admin_required
def admin_recalculate_engagement(post_id):
    recalculate_engagement(post_id)
    flash('Engagement score recalculated.', 'success')
    return redirect(request.referrer or url_for('admin_trending'))


@admin_bp.route('/admin/engagement/recalculate-all', methods=['POST'], endpoint='admin_recalculate_all')
    
@admin_required
def admin_recalculate_all():
    posts = ProfilePost.query.filter_by(is_active=True).all()
    for p in posts:
        recalculate_engagement(p.id)
    flash('All engagement scores recalculated ({} posts).'.format(len(posts)), 'success')
    return redirect(url_for('admin_trending'))

# ── API: leaderboard for homepage widget ────────────────────────────────────

@admin_bp.route('/admin/creator/<int:profile_id>/toggle-online', methods=['POST'], endpoint='admin_toggle_online')
    
@admin_required
def admin_toggle_online(profile_id):
    profile = Profile.query.get_or_404(profile_id)
    profile.is_online = not profile.is_online
    if not profile.is_online:
        profile.last_seen = datetime.utcnow()
    db.session.commit()
    # Also update CreatorProfile if it exists
    cp = CreatorProfile.query.filter_by(profile_id=profile_id).first()
    if cp:
        cp.is_online = profile.is_online
        if not profile.is_online:
            cp.last_seen = datetime.utcnow()
        db.session.commit()
    if profile.is_online:
        notify_followers(profile_id, 'online',
            '🟢 {} is online!'.format(profile.name),
            'Tap to visit their profile now.',
            '/creator/{}'.format(profile.username))
    return jsonify({'online': profile.is_online})

# ── Follow/Unfollow ──────────────────────────────────────────────────────────

@admin_bp.route('/admin/inbox', endpoint='admin_inbox')
    
@admin_required
def admin_inbox():
    messages = db.session.query(CreatorMessage, Profile)\
        .join(Profile, Profile.id == CreatorMessage.profile_id)\
        .order_by(CreatorMessage.created_at.desc()).all()
    unread_count = CreatorMessage.query.filter_by(is_read=False).count()
    return render_template('admin_inbox.html', messages=messages, unread_count=unread_count)

# ── Serve video stream (supports range requests for seek) ────────────────────

@admin_bp.route('/admin/vaultx', endpoint='admin_vaultx_dashboard')
    
@admin_required
def admin_vaultx_dashboard():
    """VaultX main admin hub."""
    # Revenue totals
    total_revenue = db.session.query(db.func.sum(VaultTransaction.gross_amount))\
        .filter(VaultTransaction.status=='completed').scalar() or 0.0
    platform_earnings = db.session.query(db.func.sum(EarningsRecord.amount))\
        .filter(EarningsRecord.beneficiary_type=='platform').scalar() or 0.0
    pending_withdrawals = WithdrawalRequest.query.filter_by(status='pending').count()
    total_subscribers = User.query.filter_by(role='subscriber').count()
    total_creators    = User.query.filter_by(role='creator').count()
    total_managers    = User.query.filter_by(role='creator_manager').count()
    total_ops         = User.query.filter_by(role='ops_manager').count()

    # Recent transactions
    recent_txs = VaultTransaction.query.order_by(VaultTransaction.created_at.desc()).limit(15).all()

    split = get_revenue_split()

    return render_template('vx_admin_dashboard.html',
        total_revenue=total_revenue,
        platform_earnings=platform_earnings,
        pending_withdrawals=pending_withdrawals,
        total_subscribers=total_subscribers,
        total_creators=total_creators,
        total_managers=total_managers,
        total_ops=total_ops,
        recent_txs=recent_txs,
        split=split
    )



@admin_bp.route('/admin/vaultx/revenue-split', methods=['GET', 'POST'], endpoint='admin_revenue_split')
    
@admin_required
def admin_revenue_split():
    split = get_revenue_split()
    if request.method == 'POST':
        split.creator_pct     = float(request.form.get('creator_pct', 75))
        split.ops_manager_pct = float(request.form.get('ops_manager_pct', 5))
        split.manager_pct     = float(request.form.get('manager_pct', 10))
        split.platform_pct    = float(request.form.get('platform_pct', 10))
        split.updated_at      = datetime.utcnow()
        db.session.commit()
        flash('Revenue split updated!', 'success')
    return render_template('vx_admin_revenue_split.html', split=split)



@admin_bp.route('/admin/vaultx/withdrawals', endpoint='admin_withdrawals')
    
@admin_required
def admin_withdrawals():
    status = request.args.get('status', 'pending')
    wrs = WithdrawalRequest.query.filter_by(status=status)\
        .order_by(WithdrawalRequest.requested_at.desc()).all()
    return render_template('vx_admin_withdrawals.html', wrs=wrs, status=status)



@admin_bp.route('/admin/vaultx/withdrawal/<int:wr_id>/approve', methods=['POST'], endpoint='admin_approve_withdrawal')
    
@admin_required
def admin_approve_withdrawal(wr_id):
    wr = WithdrawalRequest.query.get_or_404(wr_id)
    wr.status       = 'approved'
    wr.processed_at = datetime.utcnow()
    wr.admin_note   = request.form.get('note', '').strip()
    db.session.commit()
    flash('Withdrawal approved.', 'success')
    return redirect(url_for('admin_withdrawals'))



@admin_bp.route('/admin/vaultx/withdrawal/<int:wr_id>/paid', methods=['POST'], endpoint='admin_mark_withdrawal_paid')
    
@admin_required
def admin_mark_withdrawal_paid(wr_id):
    wr = WithdrawalRequest.query.get_or_404(wr_id)
    wr.status = 'paid'
    wr.processed_at = datetime.utcnow()
    # Only the earnings records locked specifically to THIS withdrawal request
    # are consumed — never touches any other balance the user may have earned since.
    EarningsRecord.query.filter_by(withdrawal_request_id=wr.id)\
        .update({'is_available': False})
    db.session.commit()
    flash('Withdrawal marked as paid.', 'success')
    return redirect(url_for('admin_withdrawals'))



@admin_bp.route('/admin/vaultx/withdrawal/<int:wr_id>/reject', methods=['POST'], endpoint='admin_reject_withdrawal')
    
@admin_required
def admin_reject_withdrawal(wr_id):
    wr = WithdrawalRequest.query.get_or_404(wr_id)
    wr.status       = 'rejected'
    wr.processed_at = datetime.utcnow()
    wr.admin_note   = request.form.get('note', '').strip()
    # Crucial: release the locked earnings back to available balance since the
    # withdrawal didn't go through — otherwise that money would be stuck forever.
    release_locked_earnings(wr)
    db.session.commit()
    flash('Withdrawal rejected — funds released back to available balance.', 'warning')
    return redirect(url_for('admin_withdrawals'))



@admin_bp.route('/admin/vaultx/create-operations-manager', methods=['GET', 'POST'], endpoint='admin_create_ops_manager')
    
@admin_required
def admin_create_ops_manager():
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        if not all([name, email, password]):
            flash('All fields required.', 'error')
            return redirect(url_for('admin_create_ops_manager'))
        if User.query.filter_by(email=email).first():
            flash('Email already in use.', 'error')
            return redirect(url_for('admin_create_ops_manager'))
        user = User(email=email, password_hash=generate_password_hash(password), role='ops_manager')
        db.session.add(user)
        db.session.flush()
        om = OperationsManager(user_id=user.id, name=name)
        db.session.add(om)
        db.session.commit()
        flash('Operations Manager created!', 'success')
        return redirect(url_for('admin_vaultx_dashboard'))
    return render_template('vx_admin_create_ops_manager.html')



@admin_bp.route('/admin/vaultx/telegram-channels', methods=['GET', 'POST'], endpoint='admin_telegram_channels')
    
@admin_required
def admin_telegram_channels():
    if request.method == 'POST':
        name         = request.form.get('name', '').strip()
        channel_url  = request.form.get('channel_url', '').strip()
        channel_type = request.form.get('channel_type', 'subscriber')
        tc = TelegramChannel(name=name, channel_url=channel_url, channel_type=channel_type)
        db.session.add(tc)
        db.session.commit()
        flash('Channel added!', 'success')
        return redirect(url_for('admin_telegram_channels'))
    channels = TelegramChannel.query.order_by(TelegramChannel.created_at.desc()).all()
    return render_template('vx_admin_telegram_channels.html', channels=channels)



@admin_bp.route('/admin/vaultx/telegram-channels/<int:tc_id>/delete', methods=['POST'], endpoint='admin_delete_telegram_channel')
    
@admin_required
def admin_delete_telegram_channel(tc_id):
    tc = TelegramChannel.query.get_or_404(tc_id)
    db.session.delete(tc)
    db.session.commit()
    flash('Channel removed.', 'success')
    return redirect(url_for('admin_telegram_channels'))



@admin_bp.route('/admin/vaultx/transactions', endpoint='admin_vaultx_transactions')
    
@admin_required
def admin_vaultx_transactions():
    page = request.args.get('page', 1, type=int)
    txs = VaultTransaction.query.order_by(VaultTransaction.created_at.desc()).paginate(page=page, per_page=30)
    return render_template('vx_admin_transactions.html', txs=txs)



@admin_bp.route('/admin/vaultx/earnings', endpoint='admin_vaultx_earnings')
    
@admin_required
def admin_vaultx_earnings():
    """Platform earnings and per-creator breakdown."""
    from sqlalchemy import func
    # Per creator earnings
    creator_earnings = db.session.query(
        Profile.name, Profile.username,
        func.sum(EarningsRecord.amount).label('total'),
        func.sum(db.case((EarningsRecord.is_available==True, EarningsRecord.amount), else_=0)).label('available')
    ).join(EarningsRecord, EarningsRecord.profile_id==Profile.id)\
     .filter(EarningsRecord.beneficiary_type=='creator')\
     .group_by(Profile.id).order_by(func.sum(EarningsRecord.amount).desc()).all()

    # Platform total
    platform_total = db.session.query(func.sum(EarningsRecord.amount))\
        .filter(EarningsRecord.beneficiary_type=='platform').scalar() or 0

    return render_template('vx_admin_earnings.html',
        creator_earnings=creator_earnings,
        platform_total=platform_total
    )



@admin_bp.route('/admin/vaultx/mark-available', methods=['POST'], endpoint='admin_mark_earnings_available')
    
@admin_required
def admin_mark_earnings_available():
    """Admin action: make pending earnings available for withdrawal."""
    user_id = request.form.get('user_id', type=int)
    if user_id:
        EarningsRecord.query.filter_by(beneficiary_user_id=user_id, is_available=False)\
            .update({'is_available': True})
        db.session.commit()
        flash('Earnings marked as available.', 'success')
    return redirect(url_for('admin_vaultx_earnings'))



@admin_bp.route('/admin/vaultx/send-admin-dm', methods=['GET', 'POST'], endpoint='admin_send_platform_dm')
    
@admin_required
def admin_send_platform_dm():
    """Admin sends a styled notice to all active DM threads."""
    if request.method == 'POST':
        body      = request.form.get('body', '').strip()
        target    = request.form.get('target', 'all')  # all / profile_id
        profile_id = request.form.get('profile_id', type=int)
        if not body:
            flash('Message body is required.', 'error')
            return redirect(url_for('admin_send_platform_dm'))
        if target == 'all':
            threads = DMThread.query.all()
        else:
            threads = DMThread.query.filter_by(profile_id=profile_id).all()
        for thread in threads:
            msg = DMMessage(
                thread_id=thread.id,
                sender_type='admin',
                sender_user_id=None,
                body=body,
                is_admin_notice=True
            )
            db.session.add(msg)
            thread.last_message_at = datetime.utcnow()
        db.session.commit()
        flash(f'Admin notice sent to {len(threads)} threads.', 'success')
        return redirect(url_for('admin_send_platform_dm'))
    profiles = Profile.query.filter_by(is_active=True).all()
    return render_template('vx_admin_send_dm.html', profiles=profiles)


# ─────────────────────────────────────────────────────────────────────────────
# OPERATIONS MANAGER PORTAL
# ─────────────────────────────────────────────────────────────────────────────


@admin_bp.route('/admin/users', endpoint='admin_users')
    
@admin_required
def admin_users():
    """Show all users with role, username, email."""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users)



@admin_bp.route('/admin/users/<int:user_id>/change-role', methods=['POST'], endpoint='admin_change_user_role')
    
@admin_required
def admin_change_user_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role', user.role)
    allowed_roles = ['subscriber', 'creator', 'creator_manager', 'ops_manager', 'admin']
    if new_role in allowed_roles:
        user.role = new_role
        if new_role == 'admin':
            user.is_admin = True
        db.session.commit()
        flash('Role updated to {}.'.format(new_role), 'success')
    return redirect(url_for('admin_users'))


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN: TWO REVENUE SPLIT PANELS
# ─────────────────────────────────────────────────────────────────────────────


@admin_bp.route('/admin/revenue-splits', methods=['GET', 'POST'], endpoint='admin_revenue_splits')
    
@admin_required
def admin_revenue_splits():
    """Edit revenue splits for both manager-trial accounts and sole-creator accounts."""
    split = get_revenue_split()
    if request.method == 'POST':
        panel = request.form.get('panel', 'manager')
        if panel == 'manager':
            split.manager_pct     = min(float(request.form.get('manager_pct', 55.0)), 55.0)
            split.ops_manager_pct = min(float(request.form.get('ops_manager_pct', 15.0)), 30.0)
        else:
            split.creator_pct = min(float(request.form.get('creator_pct', 70.0)), 70.0)
        split.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Revenue split updated!', 'success')
        return redirect(url_for('admin_revenue_splits'))
    return render_template('admin_revenue_splits.html', split=split)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN: CREATE OPS MANAGER (admin panel only)
# ─────────────────────────────────────────────────────────────────────────────


@admin_bp.route('/admin/ops-managers', methods=['GET', 'POST'], endpoint='admin_ops_managers')
    
@admin_required
def admin_ops_managers():
    """List and create OPS managers — only admins can do this."""
    ops_managers = User.query.filter_by(role='ops_manager').order_by(User.created_at.desc()).all()
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        name     = request.form.get('name', '').strip()
        if not email or not password:
            flash('Email and password required.', 'error')
            return redirect(url_for('admin_ops_managers'))
        if User.query.filter_by(email=email).first():
            flash('Email already in use.', 'error')
            return redirect(url_for('admin_ops_managers'))
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            role='ops_manager',
            is_admin=False
        )
        db.session.add(user)
        db.session.flush()
        om = OperationsManager(user_id=user.id, name=name or email.split('@')[0])
        db.session.add(om)
        db.session.commit()
        # Send welcome email
        send_account_grant_email(email, name, password, role='ops_manager')
        flash('OPS Manager account created.', 'success')
        return redirect(url_for('admin_ops_managers'))
    return render_template('admin_ops_managers.html', ops_managers=ops_managers)



@admin_bp.route('/admin/ops-managers/<int:user_id>/delete', methods=['POST'], endpoint='admin_delete_ops_manager')
    
@admin_required
def admin_delete_ops_manager(user_id):
    user = User.query.get_or_404(user_id)
    om = OperationsManager.query.filter_by(user_id=user_id).first()
    if om:
        db.session.delete(om)
    db.session.delete(user)
    db.session.commit()
    flash('OPS Manager deleted.', 'success')
    return redirect(url_for('admin_ops_managers'))


# ─────────────────────────────────────────────────────────────────────────────
# UPDATED: apply_to_be_creator — now sends email to admin
# ─────────────────────────────────────────────────────────────────────────────
