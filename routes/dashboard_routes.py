"""VaultX dashboard routes."""
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

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route('/', endpoint='index')
    
def index():
    photos = Photo.query.filter_by(is_active=True).order_by(Photo.created_at.desc()).limit(9).all()
    for p in photos:
        p.unlocked      = has_access(p.id)
        p.current_price = get_current_price(p)

    videos = Video.query.filter_by(is_active=True).order_by(Video.created_at.desc()).limit(6).all()

    total_photos = Photo.query.filter_by(is_active=True).count()
    total_videos = Video.query.filter_by(is_active=True).count()
    total_buyers = Purchase.query.distinct(Purchase.session_token).count()
    total_creators = Profile.query.filter_by(is_active=True).count()

    return render_template('index.html',
                           photos=photos,
                           videos=videos,
                           total_photos=total_photos,
                           total_videos=total_videos,
                           total_buyers=total_buyers,
                           total_creators=total_creators)



@dashboard_bp.route('/gallery', endpoint='gallery')
    
def gallery():
    selected_tier = request.args.get('tier')
    selected_cat  = request.args.get('category')
    search_query  = request.args.get('q', '').strip()
    sort_by       = request.args.get('sort', 'newest')

    q = Photo.query.filter_by(is_active=True)
    if selected_tier:
        q = q.filter_by(tier=selected_tier)
    if selected_cat:
        q = q.filter_by(category=selected_cat)
    if search_query:
        q = q.filter(db.or_(
            Photo.title.ilike('%{}%'.format(search_query)),
            Photo.description.ilike('%{}%'.format(search_query)),
            Photo.category.ilike('%{}%'.format(search_query))
        ))

    if sort_by == 'popular':
        q = q.order_by(Photo.view_count.desc())
    elif sort_by == 'price_asc':
        q = q.order_by(Photo.unlock_price.asc())
    elif sort_by == 'price_desc':
        q = q.order_by(Photo.unlock_price.desc())
    else:
        q = q.order_by(Photo.created_at.desc())

    photos     = q.all()
    categories = [r[0] for r in db.session.query(Photo.category).filter(Photo.is_active==True).distinct().all() if r[0]]

    for p in photos:
        p.unlocked      = has_access(p.id)
        p.current_price = get_current_price(p)

    return render_template('gallery.html',
                           photos=photos,
                           categories=categories,
                           selected_tier=selected_tier,
                           selected_cat=selected_cat,
                           search_query=search_query,
                           sort=sort_by)



@dashboard_bp.route('/premium', endpoint='premium_page')
    
def premium_page():
    """Dedicated premium page — shows both premium photos AND premium videos."""
    photos = Photo.query.filter_by(is_active=True, tier='premium')\
                        .order_by(Photo.created_at.desc()).all()
    videos = Video.query.filter_by(is_active=True, tier='premium')\
                        .order_by(Video.created_at.desc()).all()
    for p in photos:
        p.unlocked      = has_access(p.id)
        p.current_price = get_current_price(p)
    for v in videos:
        v.unlocked = has_video_access(v.id)
    total = len(photos) + len(videos)
    return render_template('premium_page.html',
                           photos=photos, videos=videos, total=total)



@dashboard_bp.route('/photo/<int:photo_id>', endpoint='photo_detail')
    
def photo_detail(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    photo.view_count   += 1
    db.session.commit()
    photo.current_price = dynamic_price(photo)
    photo.unlocked      = has_access(photo.id)
    return render_template('photo_detail.html', photo=photo, stripe_pk=STRIPE_PUBLISHABLE_KEY)


# ── Serve images ───────────────────────────────────────────────────────────────

@dashboard_bp.route('/img/preview/<int:photo_id>', endpoint='serve_preview')
    
def serve_preview(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    if not photo.preview_filename:
        abort(404)
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'previews', photo.preview_filename)
    return send_file(path)



@dashboard_bp.route('/img/original/<int:photo_id>', endpoint='serve_original')
    
def serve_original(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    if not has_access(photo_id):
        abort(403)
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'originals', photo.original_filename)
    return send_file(path)



@dashboard_bp.route('/videos', endpoint='video_gallery')
    
def video_gallery():
    selected_tier    = request.args.get('tier')
    selected_cat     = request.args.get('category')
    selected_creator = request.args.get('creator')

    q = Video.query.filter_by(is_active=True)
    if selected_tier:
        q = q.filter_by(tier=selected_tier)
    if selected_cat:
        q = q.filter_by(category=selected_cat)

    videos = q.order_by(Video.created_at.desc()).all()

    # Mark unlocked for each video
    for v in videos:
        v.unlocked = has_video_access(v.id)

    # Categories from DB (admin-defined)
    categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order, Category.name).all()
    creators   = Profile.query.filter_by(is_active=True).order_by(Profile.name).all()

    return render_template('video_gallery.html',
                           videos=videos,
                           categories=categories,
                           creators=creators,
                           selected_tier=selected_tier,
                           selected_cat=selected_cat,
                           selected_creator=selected_creator)



@dashboard_bp.route('/video/<int:video_id>', endpoint='video_detail')
    
def video_detail(video_id):
    video    = Video.query.get_or_404(video_id)
    unlocked = has_video_access(video_id)
    video.view_count += 1
    db.session.commit()
    return render_template('video_detail.html', video=video, unlocked=unlocked)



@dashboard_bp.route('/video/thumb/<int:video_id>', endpoint='serve_video_thumb')
    
def serve_video_thumb(video_id):
    video = Video.query.get_or_404(video_id)
    if video.thumbnail_filename:
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'video_thumbs', video.thumbnail_filename)
        if os.path.exists(path):
            return send_file(path, mimetype='image/jpeg')
    # No thumbnail: try to extract first frame from video using ffmpeg
    if video.video_filename:
        # Check multiple locations
        for vdir in [
            os.path.join(current_app.config['UPLOAD_FOLDER'], 'videos'),
            current_app.config['POST_UPLOAD_FOLDER'],
        ]:
            vpath = os.path.join(vdir, video.video_filename)
            if os.path.exists(vpath):
                try:
                    import subprocess, tempfile
                    tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
                    tmp.close()
                    result = subprocess.run(
                        ['ffmpeg', '-i', vpath, '-ss', '00:00:01', '-vframes', '1',
                         '-vf', 'scale=640:-1', '-y', tmp.name],
                        capture_output=True, timeout=15
                    )
                    if os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 0:
                        return send_file(tmp.name, mimetype='image/jpeg')
                except Exception:
                    pass
    # Fallback: generate a simple placeholder image using Pillow
    try:
        from PIL import Image, ImageDraw
        import io
        img  = Image.new('RGB', (640, 360), color=(20, 20, 30))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 639, 359], outline=(60, 60, 80), width=2)
        draw.text((290, 165), '▶', fill=(100, 100, 120))
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=70)
        buf.seek(0)
        from flask import Response
        return Response(buf.getvalue(), mimetype='image/jpeg')
    except Exception:
        abort(404)



@dashboard_bp.route('/video/preview/<int:video_id>', endpoint='serve_video_preview')
    
def serve_video_preview(video_id):
    video = Video.query.get_or_404(video_id)
    if not video.preview_filename:
        abort(404)
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'video_previews', video.preview_filename)
    return send_file(path, mimetype='video/mp4')


@dashboard_bp.route('/categories', endpoint='categories_page')
    
def categories_page():
    cats = Category.query.filter_by(is_active=True).order_by(Category.sort_order, Category.name).all()
    # Attach counts
    for cat in cats:
        cat.photo_count = Photo.query.filter_by(category=cat.name, is_active=True).count()
        cat.video_count = Video.query.filter_by(category=cat.name, is_active=True).count()
    return render_template('categories_page.html', categories=cats)
 
 

@dashboard_bp.route('/category/<slug>', endpoint='category_detail')
    
def category_detail(slug):
    cat    = Category.query.filter_by(slug=slug, is_active=True).first_or_404()
    photos = Photo.query.filter_by(category=cat.name, is_active=True).order_by(Photo.created_at.desc()).all()
    videos = Video.query.filter_by(category=cat.name, is_active=True).order_by(Video.created_at.desc()).all()
    blur_photo = int(get_setting('blur_photo', 12))
    blur_video = int(get_setting('blur_video', 16))
 
    for p in photos:
        p.unlocked      = has_access(p.id)
        p.current_price = get_current_price(p)
 
    return render_template('category_detail.html',
                           cat=cat,
                           photos=photos,
                           videos=videos,
                           blur_photo=blur_photo,
                           blur_video=blur_video)
 
 
# ── Admin: Settings (blur control + site config) ───────────────────────────────

@dashboard_bp.route('/profiles', endpoint='public_profiles')
    
def public_profiles():
    profiles = Profile.query.filter_by(is_active=True).order_by(Profile.sort_order, Profile.name).all()
    for p in profiles:
        p.post_count = ProfilePost.query.filter_by(profile_id=p.id, is_active=True).count()
        # Total likes across all posts
        p.total_likes = db.session.query(db.func.count(ProfilePostLike.id))\
            .join(ProfilePost, ProfilePost.id == ProfilePostLike.post_id)\
            .filter(ProfilePost.profile_id == p.id).scalar() or 0
    return render_template('public_profiles.html', profiles=profiles,
                           COUNTRY_FLAGS=COUNTRY_FLAGS, COUNTRY_NAMES=COUNTRY_NAMES)
 
 
COUNTRY_FLAGS = {
    'KE':'🇰🇪','US':'🇺🇸','GB':'🇬🇧','NG':'🇳🇬','ZA':'🇿🇦','GH':'🇬🇭','TZ':'🇹🇿','UG':'🇺🇬',
    'RW':'🇷🇼','ET':'🇪🇹','EG':'🇪🇬','MA':'🇲🇦','TN':'🇹🇳','SN':'🇸🇳','CI':'🇨🇮','CM':'🇨🇲',
    'IN':'🇮🇳','CN':'🇨🇳','JP':'🇯🇵','KR':'🇰🇷','PH':'🇵🇭','ID':'🇮🇩','MY':'🇲🇾','TH':'🇹🇭',
    'FR':'🇫🇷','DE':'🇩🇪','IT':'🇮🇹','ES':'🇪🇸','PT':'🇵🇹','NL':'🇳🇱','SE':'🇸🇪','NO':'🇳🇴',
    'BR':'🇧🇷','MX':'🇲🇽','AR':'🇦🇷','CO':'🇨🇴','CA':'🇨🇦','AU':'🇦🇺','NZ':'🇳🇿','AE':'🇦🇪',
    'SA':'🇸🇦','TR':'🇹🇷','PK':'🇵🇰','BD':'🇧🇩','RU':'🇷🇺','UA':'🇺🇦','PL':'🇵🇱',
}
COUNTRY_NAMES = {
    'KE':'Kenya','US':'United States','GB':'United Kingdom','NG':'Nigeria','ZA':'South Africa',
    'GH':'Ghana','TZ':'Tanzania','UG':'Uganda','RW':'Rwanda','ET':'Ethiopia','EG':'Egypt',
    'MA':'Morocco','TN':'Tunisia','SN':'Senegal','CI':'Côte d\'Ivoire','CM':'Cameroon',
    'IN':'India','CN':'China','JP':'Japan','KR':'South Korea','PH':'Philippines','ID':'Indonesia',
    'MY':'Malaysia','TH':'Thailand','FR':'France','DE':'Germany','IT':'Italy','ES':'Spain',
    'PT':'Portugal','NL':'Netherlands','SE':'Sweden','NO':'Norway','BR':'Brazil','MX':'Mexico',
    'AR':'Argentina','CO':'Colombia','CA':'Canada','AU':'Australia','NZ':'New Zealand',
    'AE':'UAE','SA':'Saudi Arabia','TR':'Turkey','PK':'Pakistan','BD':'Bangladesh',
    'RU':'Russia','UA':'Ukraine','PL':'Poland',
}


@dashboard_bp.route('/profile/<username>', endpoint='profile_page')
    
def profile_page(username):
    profile = Profile.query.filter_by(username=username, is_active=True).first_or_404()
    # Determine if the current session is the creator's manager or admin
    is_owner = False
    if session.get('is_admin'):
        is_owner = True
    elif session.get('is_manager'):
        user_id = session.get('user_id')
        if profile.manager_id and profile.manager_id == user_id:
            is_owner = True

    # Admin is a platform moderator, not a creator/subscriber. is_owner unlocks
    # content for moderation review, but admin must never see or use creator
    # engagement actions (Follow / Like / Subscribe / Message). This flag is
    # used purely to hide those controls; it does not affect content access.
    is_admin_viewer = bool(session.get('is_admin'))

    posts   = ProfilePost.query.filter_by(profile_id=profile.id, is_active=True)\
                               .order_by(ProfilePost.created_at.desc()).all()
    # Also load photos and videos so they appear in Photos/Videos tabs AND on profile
    photos  = Photo.query.filter_by(profile_id=profile.id, is_active=True)\
                         .order_by(Photo.created_at.desc()).all()
    videos  = Video.query.filter_by(profile_id=profile.id, is_active=True)\
                         .order_by(Video.created_at.desc()).all()

    tok = get_session_token()
    for post in posts:
        post.view_count += 1
        post.like_count    = ProfilePostLike.query.filter_by(post_id=post.id).count()
        post.comment_count = ProfilePostComment.query.filter_by(post_id=post.id, is_approved=True).count()
        post.i_liked       = ProfilePostLike.query.filter_by(post_id=post.id, session_token=tok).first() is not None
        # Owner always sees content unlocked
        post.is_owner_view = is_owner
        # Attach linked photo/video if any
        if post.photo_id:
            post.linked_photo = Photo.query.get(post.photo_id)
        if post.video_id:
            post.linked_video = Video.query.get(post.video_id)

    # Mark access for photos and videos
    for p in photos:
        p.unlocked = is_owner or has_access(p.id)
        p.current_price = dynamic_price(p)
    for v in videos:
        v.unlocked = is_owner or has_video_access(v.id)

    db.session.commit()
    # Other profiles to suggest
    others = Profile.query.filter(Profile.id != profile.id, Profile.is_active==True).limit(4).all()
    # Follower / subscriber counts
    follower_count    = CreatorFollow.query.filter_by(profile_id=profile.id).count()
    subscriber_count  = CreatorSubscription.query.filter_by(profile_id=profile.id).count()
    like_count        = CreatorLike.query.filter_by(profile_id=profile.id).count()
    return render_template('profile_page.html', profile=profile, posts=posts, others=others,
                           photos=photos, videos=videos,
                           is_owner=is_owner,
                           is_admin_viewer=is_admin_viewer,
                           follower_count=follower_count,
                           subscriber_count=subscriber_count,
                           like_count=like_count,
                           COUNTRY_FLAGS=COUNTRY_FLAGS, COUNTRY_NAMES=COUNTRY_NAMES)
 
 
# ── API: like a profile post ───────────────────────────────────────────────────

@dashboard_bp.route('/media/profile/<filename>', endpoint='serve_profile_media')
    
def serve_profile_media(filename):
    # Check uploads/profiles first, then static/uploads/profiles
    path1 = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles', filename)
    path2 = os.path.join(PROFILE_UPLOAD_FOLDER, filename)
    if os.path.exists(path1):
        return send_file(path1)
    if os.path.exists(path2):
        return send_file(path2)
    abort(404)


@dashboard_bp.route('/media/post/<filename>', endpoint='serve_post_media')
    
def serve_post_media(filename):
    # Check uploads/profile_posts first, then static/uploads/posts
    path1 = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile_posts', filename)
    path2 = os.path.join(POST_UPLOAD_FOLDER, filename)
    if os.path.exists(path1):
        return send_file(path1)
    if os.path.exists(path2):
        return send_file(path2)
    abort(404)

# ── Like / Unlike a Photo ──────────────────────────────────────────────────────

@dashboard_bp.route('/video/stream/<int:video_id>', endpoint='serve_video_stream')
    
def serve_video_stream(video_id):
    video = Video.query.get_or_404(video_id)
    if not video.video_filename:
        abort(404)
    # Check if creator owns it (admin) or has purchased
    is_admin_user = session.get('is_admin', False)
    if not is_admin_user and not has_video_access(video_id):
        abort(403)
    video_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'videos', video.video_filename)
    if not os.path.exists(video_path):
        # Try alternate locations
        for loc in ['static/uploads/posts', 'static/uploads']:
            alt = os.path.join(os.path.dirname(__file__), loc, video.video_filename)
            if os.path.exists(alt):
                video_path = alt
                break
        else:
            abort(404)

    file_size = os.path.getsize(video_path)
    range_header = request.headers.get('Range')
    if range_header:
        byte_start, byte_end = 0, file_size - 1
        match = __import__('re').search(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            byte_start = int(match.group(1))
            if match.group(2):
                byte_end = int(match.group(2))
        length = byte_end - byte_start + 1
        def generate():
            with open(video_path, 'rb') as f:
                f.seek(byte_start)
                remaining = length
                while remaining:
                    chunk = f.read(min(8192, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        from flask import Response
        headers = {
            'Content-Range': 'bytes {}-{}/{}'.format(byte_start, byte_end, file_size),
            'Accept-Ranges': 'bytes',
            'Content-Length': str(length),
            'Content-Type': 'video/mp4',
        }
        return Response(generate(), 206, headers)
    return send_file(video_path, mimetype='video/mp4')

