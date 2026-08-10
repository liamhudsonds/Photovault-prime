"""VaultX analytics routes."""
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

analytics_bp = Blueprint("analytics", __name__)

@analytics_bp.route('/api/trending', endpoint='trending')
    
def trending():
    week_ago = datetime.utcnow() - timedelta(days=7)
    photos   = Photo.query.filter_by(is_active=True).order_by(Photo.view_count.desc()).limit(6).all()
    result   = []
    for p in photos:
        likes = PhotoLike.query.filter_by(photo_id=p.id).count()
        result.append({'id': p.id, 'title': p.title, 'views': p.view_count,
                       'likes': likes, 'tier': p.tier, 'type': 'photo'})
    return jsonify(result)


# ── Admin: moderate comments ───────────────────────────────────────────────────

@analytics_bp.route('/api/repost', methods=['POST'], endpoint='api_repost')
    
def api_repost():
    """Toggle a repost for a photo or video."""
    data         = request.get_json() or {}
    content_type = data.get('content_type', 'photo')  # 'photo' or 'video'
    content_id   = int(data.get('content_id', 0))
    name         = (data.get('name') or 'Anonymous').strip()[:100]
    caption      = (data.get('caption') or '').strip()[:300]
    tok          = get_session_token()

    if not content_id:
        return jsonify({'error': 'Missing content_id'}), 400

    # Validate content exists
    if content_type == 'photo':
        item = Photo.query.get(content_id)
    else:
        item = Video.query.get(content_id)
    if not item:
        return jsonify({'error': 'Content not found'}), 404

    # Toggle repost
    existing = Repost.query.filter_by(
        session_token=tok, content_type=content_type, content_id=content_id
    ).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        reposted = False
    else:
        rp = Repost(session_token=tok, reposter_name=name,
                    content_type=content_type, content_id=content_id,
                    caption=caption)
        db.session.add(rp)
        db.session.commit()
        reposted = True
        # Log activity
        try:
            log_activity('repost', name, meta=item.title or 'content')
        except Exception:
            pass

    count = Repost.query.filter_by(content_type=content_type, content_id=content_id).count()
    return jsonify({'reposted': reposted, 'count': count})



@analytics_bp.route('/api/repost/status', endpoint='api_repost_status')
    
def api_repost_status():
    """Check if current session has reposted a specific item."""
    content_type = request.args.get('type', 'photo')
    content_id   = int(request.args.get('id', 0))
    tok          = get_session_token()
    existing = Repost.query.filter_by(
        session_token=tok, content_type=content_type, content_id=content_id
    ).first()
    count = Repost.query.filter_by(content_type=content_type, content_id=content_id).count()
    return jsonify({'reposted': existing is not None, 'count': count})



@analytics_bp.route('/api/reposts/feed', endpoint='api_reposts_feed')
    
def api_reposts_feed():
    """Public feed of recent reposts with content details."""
    limit  = min(int(request.args.get('limit', 20)), 50)
    reposts = Repost.query.order_by(Repost.created_at.desc()).limit(limit).all()
    result  = []
    for rp in reposts:
        entry = {
            'id':            rp.id,
            'reposter_name': rp.reposter_name,
            'content_type':  rp.content_type,
            'content_id':    rp.content_id,
            'caption':       rp.caption,
            'created_at':    _time_ago(rp.created_at),
        }
        if rp.content_type == 'photo':
            item = Photo.query.get(rp.content_id)
            if item:
                entry['title']        = item.title
                entry['preview_url']  = '/img/preview/{}'.format(item.id)
                entry['detail_url']   = '/photo/{}'.format(item.id)
                entry['price']        = item.unlock_price
                entry['tier']         = item.tier
        else:
            item = Video.query.get(rp.content_id)
            if item:
                entry['title']        = item.title
                entry['preview_url']  = '/video/thumb/{}'.format(item.id) if item.thumbnail_filename else ''
                entry['detail_url']   = '/video/{}'.format(item.id)
                entry['price']        = item.unlock_price
                entry['tier']         = item.tier
        if 'title' in entry:
            result.append(entry)
    return jsonify(result)



@analytics_bp.route('/reposts', endpoint='reposts_feed_page')
    
def reposts_feed_page():
    """Public repost feed page."""
    return render_template('reposts_feed.html')


@analytics_bp.route('/trending', endpoint='trending_page')
    
def trending_page():
    """Public trending feed — top scored posts + trending creators."""
    # Top scored posts (join PostEngagement)
    top_posts = db.session.query(ProfilePost, PostEngagement, Profile)\
        .join(PostEngagement, PostEngagement.post_id == ProfilePost.id)\
        .join(Profile, Profile.id == ProfilePost.profile_id)\
        .filter(ProfilePost.is_active == True, Profile.is_active == True)\
        .order_by(PostEngagement.score.desc()).limit(20).all()

    # Trending creators by total post score
    creator_scores = db.session.query(
        Profile,
        db.func.sum(PostEngagement.score).label('total_score')
    ).join(ProfilePost, ProfilePost.profile_id == Profile.id)\
     .join(PostEngagement, PostEngagement.post_id == ProfilePost.id)\
     .filter(Profile.is_active == True)\
     .group_by(Profile.id)\
     .order_by(db.text('total_score DESC')).limit(8).all()

    # Recent new uploads (last 48 hrs)
    cutoff = datetime.utcnow() - timedelta(hours=48)
    new_posts = db.session.query(ProfilePost, Profile)\
        .join(Profile, Profile.id == ProfilePost.profile_id)\
        .filter(ProfilePost.is_active == True, ProfilePost.created_at >= cutoff,
                Profile.is_active == True)\
        .order_by(ProfilePost.created_at.desc()).limit(12).all()

    # Activity feed
    activity = ActivityFeed.query.order_by(ActivityFeed.created_at.desc()).limit(15).all()

    return render_template('trending.html',
        top_posts=top_posts, creator_scores=creator_scores,
        new_posts=new_posts, activity=activity)



@analytics_bp.route('/api/activity', endpoint='api_activity')
    
def api_activity():
    rows = ActivityFeed.query.order_by(ActivityFeed.created_at.desc()).limit(15).all()
    result = []
    for r in rows:
        result.append({
            'type':       r.event_type,
            'actor':      r.actor_name,
            'meta':       r.meta,
            'profile_id': r.profile_id,
            'post_id':    r.post_id,
            'ago':        _time_ago(r.created_at),
        })
    return jsonify(result)


@analytics_bp.route('/api/leaderboard', endpoint='api_leaderboard')
    
def api_leaderboard():
    """Top creators by total engagement score."""
    rows = db.session.query(
        Profile,
        db.func.sum(PostEngagement.score).label('total_score')
    ).join(ProfilePost, ProfilePost.profile_id == Profile.id)\
     .join(PostEngagement, PostEngagement.post_id == ProfilePost.id)\
     .filter(Profile.is_active == True)\
     .group_by(Profile.id)\
     .order_by(db.text('total_score DESC')).limit(10).all()

    result = [{'id': p.id, 'name': p.name, 'username': p.username,
               'avatar': p.avatar_filename, 'score': float(s or 0),
               'accent': p.accent_color} for p, s in rows]
    return jsonify(result)

# ── API: trending posts (public) ─────────────────────────────────────────────

@analytics_bp.route('/api/trending-posts', endpoint='api_trending_posts')
    
def api_trending_posts():
    limit = min(int(request.args.get('limit', 10)), 50)
    rows  = db.session.query(ProfilePost, PostEngagement, Profile)\
        .join(PostEngagement, PostEngagement.post_id == ProfilePost.id)\
        .join(Profile, Profile.id == ProfilePost.profile_id)\
        .filter(ProfilePost.is_active == True, Profile.is_active == True)\
        .order_by(PostEngagement.score.desc()).limit(limit).all()
    result = []
    for post, eng, profile in rows:
        result.append({
            'post_id':    post.id,
            'title':      post.title,
            'media':      post.media_filename,
            'post_type':  post.post_type,
            'profile':    profile.name,
            'username':   profile.username,
            'avatar':     profile.avatar_filename,
            'score':      eng.score,
            'views':      eng.view_count,
            'likes':      eng.like_count,
            'comments':   eng.comment_count,
            'unlocks':    eng.unlock_count,
        })
    return jsonify(result)

# ── Creator Stats API ────────────────────────────────────────────────────────

@analytics_bp.route('/api/creator/<int:profile_id>/stats', endpoint='api_creator_stats')
    
def api_creator_stats(profile_id):
    tok = get_session_token()
    followers   = CreatorFollow.query.filter_by(profile_id=profile_id).count()
    subscribers = CreatorSubscription.query.filter_by(profile_id=profile_id).count()
    likes       = CreatorLike.query.filter_by(profile_id=profile_id).count()
    i_follow    = CreatorFollow.query.filter_by(profile_id=profile_id, session_token=tok).first() is not None
    i_like      = CreatorLike.query.filter_by(profile_id=profile_id, session_token=tok).first() is not None
    i_sub       = CreatorSubscription.query.filter_by(profile_id=profile_id, session_token=tok).first() is not None
    return jsonify({'followers': followers, 'subscribers': subscribers, 'likes': likes,
                    'i_follow': i_follow, 'i_like': i_like, 'i_sub': i_sub})

# ── Creator Online Status API ─────────────────────────────────────────────────

@analytics_bp.route('/api/creator/<int:profile_id>/online-status', endpoint='api_creator_online_status')
    
def api_creator_online_status(profile_id):
    profile = Profile.query.get_or_404(profile_id)
    last_seen_str = ''
    if not profile.is_online and profile.last_seen:
        try:
            diff = datetime.utcnow() - profile.last_seen
            s = int(diff.total_seconds())
            if s < 60:       last_seen_str = 'just now'
            elif s < 3600:   last_seen_str = '{} min ago'.format(s // 60)
            elif s < 86400:  last_seen_str = '{} hr ago'.format(s // 3600)
            else:            last_seen_str = '{} days ago'.format(s // 86400)
        except Exception:
            last_seen_str = ''
    return jsonify({'online': profile.is_online, 'last_seen': last_seen_str,
                    'username': profile.username,
                    'url': '/creator/{}'.format(profile.username)})

# ── Online creators for popup notifications ───────────────────────────────────

@analytics_bp.route('/api/online-creators', endpoint='api_online_creators')
    
def api_online_creators():
    profiles = Profile.query.filter_by(is_active=True).order_by(Profile.name).all()
    result = []
    for p in profiles:
        last_seen_str = ''
        if p.last_seen:
            try:
                diff = datetime.utcnow() - p.last_seen
                s = int(diff.total_seconds())
                if s < 60:       last_seen_str = 'just now'
                elif s < 3600:   last_seen_str = '{} min ago'.format(s // 60)
                elif s < 86400:  last_seen_str = '{} hr ago'.format(s // 3600)
                else:            last_seen_str = '{} days ago'.format(s // 86400)
            except Exception:
                last_seen_str = ''
        result.append({
            'id':        p.id,
            'name':      p.name,
            'username':  p.username,
            # 'url' is the canonical profile link — used by the popup JS
            'url':       '/creator/{}'.format(p.username),
            'avatar':    p.avatar_filename,
            'online':    p.is_online,
            'last_seen': last_seen_str
        })
    return jsonify(result)

# ── Admin: toggle creator online status ──────────────────────────────────────