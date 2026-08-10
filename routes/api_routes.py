"""VaultX api routes."""
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

api_bp = Blueprint("api", __name__)

@api_bp.route('/api/access/<int:photo_id>', endpoint='api_check_access')
    
def api_check_access(photo_id):
    return jsonify({'access': has_access(photo_id)})


# =====================================
# 1. THE ACTUAL CLEANUP FUNCTION
# =====================================

@api_bp.route('/api/settings/blur', endpoint='api_blur_settings')
    
def api_blur_settings():
    return jsonify({
        'blur_photo':    int(get_setting('blur_photo', 12)),
        'blur_video':    int(get_setting('blur_video', 16)),
        'blur_checkout': int(get_setting('blur_checkout', 6)),
        'blur_detail':   int(get_setting('blur_detail', 18)),
        'tint':          get_setting('blur_tint_color', 'purple-gold'),
    })
 
 
# ── Admin: Category list ───────────────────────────────────────────────────────

@api_bp.route('/api/post/<int:post_id>/like', methods=['POST'], endpoint='toggle_post_like')
    
def toggle_post_like(post_id):
    tok      = get_session_token()
    existing = ProfilePostLike.query.filter_by(post_id=post_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(ProfilePostLike(post_id=post_id, session_token=tok))
        liked = True
    db.session.commit()
    count = ProfilePostLike.query.filter_by(post_id=post_id).count()
    return jsonify({'liked': liked, 'count': count})
 
 
# ── API: comment on a profile post ────────────────────────────────────────────

@api_bp.route('/api/post/<int:post_id>/comment', methods=['POST'], endpoint='post_profile_comment')
    
def post_profile_comment(post_id):
    data        = request.get_json()
    body        = (data.get('body') or '').strip()
    author_name = (data.get('author_name') or 'Anonymous').strip()[:80]
    emoji       = (data.get('emoji') or '').strip()[:5]
    tok         = get_session_token()
 
    if not body or len(body) < 1:
        return jsonify({'error': 'Comment cannot be empty'}), 400
    if len(body) > 500:
        return jsonify({'error': 'Too long (max 500 chars)'}), 400
 
    # Rate limit: 10 comments per session per post
    if ProfilePostComment.query.filter_by(post_id=post_id, session_token=tok).count() >= 10:
        return jsonify({'error': 'Comment limit reached'}), 429
 
    comment = ProfilePostComment(post_id=post_id, session_token=tok,
                                  author_name=author_name, body=body, emoji_reaction=emoji)
    db.session.add(comment)
    db.session.commit()
    # Log activity + update engagement score
    post = ProfilePost.query.get(post_id)
    if post:
        try:
            log_activity('comment', author_name, profile_id=post.profile_id,
                         post_id=post_id, meta=post.title or 'a post')
            recalculate_engagement(post_id)
        except Exception:
            pass
    return jsonify({
        'id':           comment.id,
        'author_name':  comment.author_name,
        'body':         comment.body,
        'emoji':        comment.emoji_reaction,
        'created_at':   comment.created_at.strftime('%b %d, %Y'),
        'is_mine':      True
    })
 
 
# ── API: get comments for a post ──────────────────────────────────────────────

@api_bp.route('/api/post/<int:post_id>/comments', endpoint='get_post_comments')
    
def get_post_comments(post_id):
    tok      = get_session_token()
    comments = ProfilePostComment.query.filter_by(post_id=post_id, is_approved=True)\
                                       .order_by(ProfilePostComment.created_at.asc()).limit(100).all()
    return jsonify([{
        'id':          c.id,
        'author_name': c.author_name,
        'body':        c.body,
        'emoji':       c.emoji_reaction,
        'created_at':  c.created_at.strftime('%b %d'),
        'is_mine':     c.session_token == tok
    } for c in comments])
 
 

@api_bp.route('/api/photo/<int:photo_id>/like', methods=['POST'], endpoint='toggle_photo_like')
    
def toggle_photo_like(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    tok   = get_session_token()
    existing = PhotoLike.query.filter_by(photo_id=photo_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(PhotoLike(photo_id=photo_id, session_token=tok))
        liked = True
    db.session.commit()
    count = PhotoLike.query.filter_by(photo_id=photo_id).count()
    return jsonify({'liked': liked, 'count': count})


# ── Like / Unlike a Video ──────────────────────────────────────────────────────

@api_bp.route('/api/video/<int:video_id>/like', methods=['POST'], endpoint='toggle_video_like')
    
def toggle_video_like(video_id):
    video = Video.query.get_or_404(video_id)
    tok   = get_session_token()
    existing = VideoLike.query.filter_by(video_id=video_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(VideoLike(video_id=video_id, session_token=tok))
        liked = True
    db.session.commit()
    count = VideoLike.query.filter_by(video_id=video_id).count()
    return jsonify({'liked': liked, 'count': count})


# ── Post a Comment ─────────────────────────────────────────────────────────────

@api_bp.route('/api/comment', methods=['POST'], endpoint='post_comment')
    
def post_comment():
    data         = request.get_json()
    content_type = data.get('content_type', 'photo')
    content_id   = data.get('content_id')
    body         = (data.get('body') or '').strip()
    author_name  = (data.get('author_name') or 'Anonymous').strip()[:80]
    tok          = get_session_token()

    if not body or len(body) < 2:
        return jsonify({'error': 'Comment too short'}), 400
    if len(body) > 1000:
        return jsonify({'error': 'Comment too long (max 1000 chars)'}), 400
    if not content_id:
        return jsonify({'error': 'Missing content_id'}), 400

    # Basic spam guard: max 5 comments per session per content item
    existing_count = Comment.query.filter_by(
        session_token=tok, content_type=content_type, content_id=content_id
    ).count()
    if existing_count >= 5:
        return jsonify({'error': 'Comment limit reached for this item'}), 429

    comment = Comment(content_type=content_type, content_id=content_id,
                      session_token=tok, author_name=author_name, body=body)
    db.session.add(comment)
    db.session.commit()

    return jsonify({
        'id':          comment.id,
        'author_name': comment.author_name,
        'body':        comment.body,
        'created_at':  comment.created_at.strftime('%b %d, %Y')
    })


# ── Get Comments ───────────────────────────────────────────────────────────────
# (duplicate get_comments removed)


# ── Delete own comment ─────────────────────────────────────────────────────────

@api_bp.route('/api/comment/<int:comment_id>/delete', methods=['POST'], endpoint='delete_comment')
    
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    tok     = get_session_token()
    if comment.session_token != tok and not session.get('is_admin'):
        return jsonify({'error': 'Not allowed'}), 403
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'deleted': True})


# ── Engagement stats for a photo (for cards) ──────────────────────────────────

@api_bp.route('/api/stats/photo/<int:photo_id>', endpoint='photo_stats')
    
def photo_stats(photo_id):
    tok      = get_session_token()
    likes    = PhotoLike.query.filter_by(photo_id=photo_id).count()
    comments = Comment.query.filter_by(content_type='photo', content_id=photo_id, is_approved=True).count()
    i_liked  = PhotoLike.query.filter_by(photo_id=photo_id, session_token=tok).first() is not None
    photo    = Photo.query.get_or_404(photo_id)
    return jsonify({'likes': likes, 'comments': comments, 'views': photo.view_count, 'liked': i_liked})


# ── Engagement stats for a video ──────────────────────────────────────────────

@api_bp.route('/api/stats/video/<int:video_id>', endpoint='video_stats')
    
def video_stats(video_id):
    tok      = get_session_token()
    likes    = VideoLike.query.filter_by(video_id=video_id).count()
    comments = Comment.query.filter_by(content_type='video', content_id=video_id, is_approved=True).count()
    i_liked  = VideoLike.query.filter_by(video_id=video_id, session_token=tok).first() is not None
    video    = Video.query.get_or_404(video_id)
    return jsonify({'likes': likes, 'comments': comments, 'views': video.view_count, 'liked': i_liked})


# ── Trending: most viewed + liked in last 7 days ──────────────────────────────

@api_bp.route('/api/comments/<content_type>/<int:content_id>', endpoint='api_get_comments')
    
def api_get_comments(content_type, content_id):
    """Return comments for a photo or video, pinned first."""
    comments = Comment.query.filter_by(
        content_type=content_type, content_id=content_id,
        is_approved=True, reply_to_id=None
    ).order_by(Comment.is_pinned.desc(), Comment.created_at.asc()).all()

    out = []
    for c in comments:
        out.append({
            'id': c.id,
            'author_name': c.author_name,
            'body': c.body,
            'tagged_user': c.tagged_user or '',
            'is_pinned': c.is_pinned,
            'is_highlighted': c.is_highlighted,
            'created_at': c.created_at.strftime('%H:%M · %b %d'),
            'replies': [{
                'id': r.id,
                'author_name': r.author_name,
                'body': r.body,
                'tagged_user': r.tagged_user or '',
                'reply_to_name': r.reply_to_name or '',
                'created_at': r.created_at.strftime('%H:%M · %b %d'),
            } for r in Comment.query.filter_by(
                reply_to_id=c.id, is_approved=True
            ).order_by(Comment.created_at.asc()).all()]
        })
    return jsonify(out)



@api_bp.route('/api/comments/post', methods=['POST'], endpoint='api_post_comment_v2')
    
def api_post_comment_v2():
    """Post a comment with optional reply_to and tag."""
    data         = request.get_json() or {}
    body         = (data.get('body') or '').strip()
    content_type = data.get('content_type', 'video')
    content_id   = data.get('content_id')
    author_name  = (data.get('author_name') or 'Anonymous').strip()[:80]
    reply_to_id  = data.get('reply_to_id')
    reply_to_name= (data.get('reply_to_name') or '').strip()[:80]
    tagged_user  = (data.get('tagged_user') or '').strip()[:80]
    tok          = get_session_token()

    if not body or len(body) < 1: return jsonify({'error': 'Empty comment'}), 400
    if len(body) > 1000: return jsonify({'error': 'Too long'}), 400
    if not content_id: return jsonify({'error': 'Missing content_id'}), 400

    existing = Comment.query.filter_by(session_token=tok, content_type=content_type,
                                        content_id=content_id).count()
    if existing >= 10:
        return jsonify({'error': 'Comment limit reached'}), 429

    c = Comment(content_type=content_type, content_id=int(content_id),
                session_token=tok, author_name=author_name, body=body,
                reply_to_id=int(reply_to_id) if reply_to_id else None,
                reply_to_name=reply_to_name,
                tagged_user=tagged_user)
    db.session.add(c)
    db.session.commit()
    return jsonify({
        'id': c.id, 'author_name': c.author_name, 'body': c.body,
        'tagged_user': c.tagged_user, 'reply_to_name': c.reply_to_name,
        'is_pinned': False, 'is_highlighted': False,
        'created_at': c.created_at.strftime('%H:%M · %b %d'),
        'replies': []
    })



@api_bp.route('/api/comments/<int:comment_id>/pin', methods=['POST'], endpoint='api_pin_comment')
    
def api_pin_comment(comment_id):
    c = Comment.query.get_or_404(comment_id)
    # Allow admin OR creator who owns the content
    if not session.get('is_admin'):
        # Check if logged-in creator owns the content
        creator_authed = False
        if session.get('creator_account_id'):
            ca = CreatorAccount.query.get(session['creator_account_id'])
            if ca:
                if c.content_type == 'photo':
                    item = Photo.query.get(c.content_id)
                    creator_authed = item and item.profile_id == ca.profile_id
                elif c.content_type == 'video':
                    item = Video.query.get(c.content_id)
                    creator_authed = item and item.profile_id == ca.profile_id
        # Also allow manager
        if not creator_authed and session.get('is_manager'):
            user_id = session.get('user_id')
            profile = Profile.query.filter_by(manager_id=user_id).first()
            if profile:
                if c.content_type == 'photo':
                    item = Photo.query.get(c.content_id)
                    creator_authed = item and item.profile_id == profile.id
                elif c.content_type == 'video':
                    item = Video.query.get(c.content_id)
                    creator_authed = item and item.profile_id == profile.id
        if not creator_authed:
            return jsonify({'error': 'Unauthorized'}), 403
    c.is_pinned = not c.is_pinned
    db.session.commit()
    return jsonify({'pinned': c.is_pinned})



@api_bp.route('/api/comments/<int:comment_id>/highlight', methods=['POST'], endpoint='api_highlight_comment')
    
def api_highlight_comment(comment_id):
    c = Comment.query.get_or_404(comment_id)
    if not session.get('is_admin'):
        creator_authed = False
        if session.get('creator_account_id'):
            ca = CreatorAccount.query.get(session['creator_account_id'])
            if ca:
                if c.content_type == 'photo':
                    item = Photo.query.get(c.content_id)
                    creator_authed = item and item.profile_id == ca.profile_id
                elif c.content_type == 'video':
                    item = Video.query.get(c.content_id)
                    creator_authed = item and item.profile_id == ca.profile_id
        if not creator_authed and session.get('is_manager'):
            user_id = session.get('user_id')
            profile = Profile.query.filter_by(manager_id=user_id).first()
            if profile:
                if c.content_type == 'photo':
                    item = Photo.query.get(c.content_id)
                    creator_authed = item and item.profile_id == profile.id
                elif c.content_type == 'video':
                    item = Video.query.get(c.content_id)
                    creator_authed = item and item.profile_id == profile.id
        if not creator_authed:
            return jsonify({'error': 'Unauthorized'}), 403
    c.is_highlighted = not c.is_highlighted
    db.session.commit()
    return jsonify({'highlighted': c.is_highlighted})



@api_bp.route('/api/comments/<int:comment_id>/delete', methods=['POST'], endpoint='api_delete_comment')
    
def api_delete_comment(comment_id):
    c = Comment.query.get_or_404(comment_id)
    if not session.get('is_admin'):
        creator_authed = False
        if session.get('creator_account_id'):
            ca = CreatorAccount.query.get(session['creator_account_id'])
            if ca:
                if c.content_type == 'photo':
                    item = Photo.query.get(c.content_id)
                    creator_authed = item and item.profile_id == ca.profile_id
                elif c.content_type == 'video':
                    item = Video.query.get(c.content_id)
                    creator_authed = item and item.profile_id == ca.profile_id
        if not creator_authed and session.get('is_manager'):
            user_id = session.get('user_id')
            profile = Profile.query.filter_by(manager_id=user_id).first()
            if profile:
                if c.content_type == 'photo':
                    item = Photo.query.get(c.content_id)
                    creator_authed = item and item.profile_id == profile.id
                elif c.content_type == 'video':
                    item = Video.query.get(c.content_id)
                    creator_authed = item and item.profile_id == profile.id
        if not creator_authed:
            return jsonify({'error': 'Unauthorized'}), 403
    content_type = c.content_type
    content_id   = c.content_id
    Comment.query.filter_by(reply_to_id=comment_id).delete()
    db.session.delete(c)
    db.session.commit()
    return jsonify({'ok': True})



@api_bp.route('/api/video/<int:video_id>/view', methods=['POST'], endpoint='api_video_view')
    
def api_video_view(video_id):
    """Count a view only once per session."""
    tok     = get_session_token()
    key     = 'viewed_video_{}'.format(video_id)
    already = session.get(key, False)
    if not already:
        video = Video.query.get(video_id)
        if video:
            video.view_count = (video.view_count or 0) + 1
            db.session.commit()
        session[key] = True
    video = Video.query.get(video_id)
    return jsonify({'view_count': video.view_count if video else 0, 'already': already})



@api_bp.route('/api/photo/<int:photo_id>/view', methods=['POST'], endpoint='api_photo_view')
    
def api_photo_view(photo_id):
    """Count a photo view only once per session."""
    tok     = get_session_token()
    key     = 'viewed_photo_{}'.format(photo_id)
    already = session.get(key, False)
    if not already:
        photo = db.session.get(Photo, photo_id)
        if photo:
            photo.view_count = (photo.view_count or 0) + 1
            db.session.commit()
        session[key] = True
    photo = db.session.get(Photo, photo_id)
    return jsonify({'view_count': photo.view_count if photo else 0, 'already': already})


@api_bp.route('/api/email-status', endpoint='api_email_status')
    
def api_email_status():
    tok = get_session_token()
    ev  = EmailVerification.query.filter_by(session_token=tok).first()
    return jsonify({'verified': ev.is_verified if ev else False,
                    'email': ev.email if ev else ''})



@api_bp.route('/api/post/<int:post_id>/unlock', methods=['POST'], endpoint='api_unlock_post')
    
def api_unlock_post(post_id):
    """Mark a post as unlocked for this session (after payment verification).
    For now records unlock and updates engagement; payment integration hooks in here.
    """
    tok  = get_session_token()
    post = ProfilePost.query.get_or_404(post_id)
    existing = PostUnlock.query.filter_by(post_id=post_id, session_token=tok).first()
    if existing:
        return jsonify({'ok': True, 'already_unlocked': True})
    data = request.get_json() or {}
    db.session.add(PostUnlock(post_id=post_id, session_token=tok,
        amount=data.get('amount', 0), payment_ref=data.get('ref', '')))
    db.session.commit()
    recalculate_engagement(post_id)
    log_activity('unlock', 'Someone', profile_id=post.profile_id, post_id=post_id,
                 meta=post.title or 'a post')
    return jsonify({'ok': True, 'unlocked': True})


@api_bp.route('/api/post/<int:post_id>/access', endpoint='api_post_access')
    
def api_post_access(post_id):
    tok = get_session_token()
    return jsonify({'access': has_post_access(post_id, tok)})



@api_bp.route('/api/post/<int:post_id>/like-v2', methods=['POST'], endpoint='toggle_post_like_v2')
    
def toggle_post_like_v2(post_id):
    """Enhanced like toggle that logs activity and recalculates engagement."""
    tok  = get_session_token()
    post = ProfilePost.query.get_or_404(post_id)
    existing = ProfilePostLike.query.filter_by(post_id=post_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(ProfilePostLike(post_id=post_id, session_token=tok))
        liked = True
        log_activity('like', 'Someone', profile_id=post.profile_id,
                     post_id=post_id, meta=post.title or 'a post')
        # Notify followers when post gets liked (threshold: every 10 likes)
        like_count = ProfilePostLike.query.filter_by(post_id=post_id).count()
        if like_count % 10 == 0:
            notify_followers(post.profile_id, 'like',
                '🔥 Post trending!',
                '"{}" just hit {} likes!'.format(post.title or 'A post', like_count),
                '/profile/{}'.format(Profile.query.get(post.profile_id).username if post.profile_id else ''))
    db.session.commit()
    recalculate_engagement(post_id)
    count = ProfilePostLike.query.filter_by(post_id=post_id).count()
    return jsonify({'liked': liked, 'count': count})

# Enhanced follow that logs activity and sends notifications

@api_bp.route('/api/creator/<int:profile_id>/follow-v2', methods=['POST'], endpoint='api_creator_follow_v2')
    
def api_creator_follow_v2(profile_id):
    if session.get('is_admin'):
        return jsonify({'error': 'Admin accounts cannot follow creators.'}), 403
    tok     = get_session_token()
    profile = Profile.query.get_or_404(profile_id)
    data    = request.get_json() or {}
    name    = data.get('name', 'Visitor')[:100]
    existing = CreatorFollow.query.filter_by(profile_id=profile_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        followed = False
    else:
        db.session.add(CreatorFollow(profile_id=profile_id, session_token=tok, follower_name=name))
        followed = True
        log_activity('follow', name, profile_id=profile_id, meta=profile.name)
        push_notification(tok, 'follow',
            'You\'re now following {}!'.format(profile.name),
            'You\'ll be notified when they post new content.',
            '/creator/{}'.format(profile.username))
    db.session.commit()
    count = CreatorFollow.query.filter_by(profile_id=profile_id).count()
    return jsonify({'followed': followed, 'count': count})

# Enhanced view tracking for profile posts

@api_bp.route('/api/post/<int:post_id>/view', methods=['POST'], endpoint='api_post_view')
    
def api_post_view(post_id):
    post = ProfilePost.query.get(post_id)
    if not post:
        return jsonify({'ok': False}), 404
    post.view_count = (post.view_count or 0) + 1
    db.session.commit()
    recalculate_engagement(post_id)
    return jsonify({'ok': True, 'views': post.view_count})



@api_bp.route('/api/creator/<int:profile_id>/follow', methods=['POST'], endpoint='api_creator_follow')
    
def api_creator_follow(profile_id):
    if session.get('is_admin'):
        return jsonify({'error': 'Admin accounts cannot follow creators.'}), 403
    tok  = get_session_token()
    data = request.get_json() or {}
    name = data.get('name', 'Visitor')[:100]
    existing = CreatorFollow.query.filter_by(profile_id=profile_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        followed = False
    else:
        db.session.add(CreatorFollow(profile_id=profile_id, session_token=tok, follower_name=name))
        followed = True
    db.session.commit()
    count = CreatorFollow.query.filter_by(profile_id=profile_id).count()
    return jsonify({'followed': followed, 'count': count})

# ── Like/Unlike Profile ──────────────────────────────────────────────────────

@api_bp.route('/api/creator/<int:profile_id>/like', methods=['POST'], endpoint='api_creator_like')
    
def api_creator_like(profile_id):
    if session.get('is_admin'):
        return jsonify({'error': 'Admin accounts cannot like creators.'}), 403
    tok = get_session_token()
    existing = CreatorLike.query.filter_by(profile_id=profile_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(CreatorLike(profile_id=profile_id, session_token=tok))
        liked = True
    db.session.commit()
    count = CreatorLike.query.filter_by(profile_id=profile_id).count()
    return jsonify({'liked': liked, 'count': count})

# ── Subscribe ────────────────────────────────────────────────────────────────

@api_bp.route('/api/creator/<int:profile_id>/subscribe', methods=['POST'], endpoint='api_creator_subscribe')
    
def api_creator_subscribe(profile_id):
    if session.get('is_admin'):
        return jsonify({'error': 'Admin accounts cannot subscribe to creators.'}), 403
    tok  = get_session_token()
    data = request.get_json() or {}
    existing = CreatorSubscription.query.filter_by(profile_id=profile_id, session_token=tok).first()
    if existing:
        db.session.delete(existing)
        subscribed = False
    else:
        db.session.add(CreatorSubscription(profile_id=profile_id, session_token=tok,
                        name=data.get('name','Visitor'), email=data.get('email','')))
        subscribed = True
    db.session.commit()
    count = CreatorSubscription.query.filter_by(profile_id=profile_id).count()
    return jsonify({'subscribed': subscribed, 'count': count})

# ── Send Message to Creator ──────────────────────────────────────────────────

@api_bp.route('/api/creator/<int:profile_id>/message', methods=['POST'], endpoint='api_creator_message')
    
def api_creator_message(profile_id):
    if session.get('is_admin'):
        return jsonify({'error': 'Admin accounts cannot send creator messages.'}), 403
    profile = Profile.query.get_or_404(profile_id)
    data    = request.get_json() or {}
    body    = (data.get('body') or '').strip()
    if not body:
        return jsonify({'error': 'Message cannot be empty'}), 400
    msg = CreatorMessage(
        profile_id   = profile_id,
        sender_name  = (data.get('sender_name') or 'Anonymous').strip()[:100],
        sender_email = (data.get('sender_email') or '').strip()[:200],
        subject      = (data.get('subject') or 'New Message').strip()[:300],
        body         = body[:2000]
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({'ok': True, 'id': msg.id})

# ── Admin: Global inbox (all DM messages across all creators) ────────────────

@api_bp.route('/api/comment/<int:comment_id>/like', methods=['POST'], endpoint='api_comment_like')
    
def api_comment_like(comment_id):
    tok = get_session_token()
    comment = Comment.query.get_or_404(comment_id)
    # Use a simple site setting key to track comment likes
    key = 'clike_{}_{}'.format(comment_id, tok[:16])
    existing = get_setting(key)
    if existing:
        set_setting(key, '')
        # Decrement like count stored in setting
        count_key = 'clike_count_{}'.format(comment_id)
        count = max(0, int(get_setting(count_key, '0')) - 1)
        set_setting(count_key, str(count))
        return jsonify({'liked': False, 'count': count})
    else:
        set_setting(key, '1')
        count_key = 'clike_count_{}'.format(comment_id)
        count = int(get_setting(count_key, '0')) + 1
        set_setting(count_key, str(count))
        return jsonify({'liked': True, 'count': count})



@api_bp.route('/api/comment/<int:comment_id>/likes', endpoint='api_comment_likes')
    
def api_comment_likes(comment_id):
    tok = get_session_token()
    count_key = 'clike_count_{}'.format(comment_id)
    key = 'clike_{}_{}'.format(comment_id, tok[:16])
    count = int(get_setting(count_key, '0'))
    liked = bool(get_setting(key))
    return jsonify({'count': count, 'liked': liked})

