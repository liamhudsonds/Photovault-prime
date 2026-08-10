from datetime import datetime, timedelta, UTC
import os, uuid, random, string, hashlib, hmac, re, json
from flask import session, current_app, url_for
from werkzeug.security import generate_password_hash
from flask_mail import Message
from PIL import Image, ImageDraw, ImageFont
import io

from database.db import db, mail
from models import *
from utils.constants import *
def recalculate_engagement(post_id):
    """Recompute engagement score for a post and update PostEngagement row."""
    post   = ProfilePost.query.get(post_id)
    if not post:
        return
    views    = post.view_count or 0
    likes    = ProfilePostLike.query.filter_by(post_id=post_id).count()
    comments = ProfilePostComment.query.filter_by(post_id=post_id, is_approved=True).count()
    unlocks  = PostUnlock.query.filter_by(post_id=post_id).count()
    score    = (views * SCORE_VIEW) + (likes * SCORE_LIKE) + \
               (comments * SCORE_COMMENT) + (unlocks * SCORE_UNLOCK)
    eng = PostEngagement.query.filter_by(post_id=post_id).first()
    if eng:
        eng.score = score; eng.view_count = views; eng.like_count = likes
        eng.comment_count = comments; eng.unlock_count = unlocks
        eng.updated_at = datetime.utcnow()
    else:
        db.session.add(PostEngagement(post_id=post_id, score=score,
            view_count=views, like_count=likes,
            comment_count=comments, unlock_count=unlocks))
    db.session.commit()

def log_activity(event_type, actor_name='Someone', profile_id=None, post_id=None, meta=''):
    """Append an event to the activity feed (cap at 200 rows)."""
    db.session.add(ActivityFeed(event_type=event_type, actor_name=actor_name,
                                 profile_id=profile_id, post_id=post_id, meta=meta))
    db.session.commit()
    # Trim to latest 200
    oldest_ids = db.session.query(ActivityFeed.id).order_by(ActivityFeed.id.desc())\
                            .offset(200).all()
    if oldest_ids:
        ActivityFeed.query.filter(ActivityFeed.id.in_([r[0] for r in oldest_ids])).delete(synchronize_session=False)
        db.session.commit()

def push_notification(session_token, notif_type, title, body, link=''):
    """Push a notification to a specific session."""
    db.session.add(Notification(session_token=session_token,
        notif_type=notif_type, title=title, body=body, link=link))
    db.session.commit()

def notify_followers(profile_id, notif_type, title, body, link='', exclude_token=None):
    """Push a notification to all followers of a profile."""
    follows = CreatorFollow.query.filter_by(profile_id=profile_id).all()
    for f in follows:
        if f.session_token != exclude_token:
            push_notification(f.session_token, notif_type, title, body, link)

def broadcast_notification(notif_type, title, body, link='', exclude_token=None):
    """Send notification to all distinct sessions that have at least one notification (i.e. opted in).
    For new-post broadcasts, send to followers of the relevant profile.
    """
    pass   # Used for specific follow-based broadcasts — see below
