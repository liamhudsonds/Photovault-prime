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
def get_revenue_split():
    split = RevenueSplit.query.first()
    if not split:
        split = RevenueSplit()
        db.session.add(split)
        db.session.commit()
    return split

# Hard ceiling — no sole creator (no matter what admin configures) earns more than this
MAX_CREATOR_PCT = 70.0

# Upload limits before a creator must subscribe to Premium for unlimited uploads/live hours
UPLOAD_LIMITS = {
    'basic':   {'photos': 15,  'videos': 8,    'live_hours_per_month': 4},
    'premium': {'photos': None,'videos': None, 'live_hours_per_month': None},  # None = unlimited
}
PREMIUM_MONTHLY_PRICE = 29.99  # 100% platform revenue

def split_revenue(transaction: VaultTransaction):
    """Create EarningsRecord rows for each beneficiary.

    Revenue rules (hard caps enforced regardless of admin config):
    - Sole verified creator (account_type == 'sole_creator', self-applied + approved):
        creator gets up to 70% (hard cap), platform gets the remainder.
    - Sole creator account that was ISSUED by admin directly (never went through
      the manager-trial/application flow) earns slightly less than a self-applied
      verified creator — 65% instead of 70% — platform gets the remainder.
    - Manager-run account (account_type == 'manager_trial', Profile.manager_id set):
        creator manager earns manager_pct (e.g. 55%) — this is the ENTIRETY of what
        the manager earns; they hold no other stake.
        The OPS manager who assigned them earns ops_manager_pct (e.g. 15%).
        Platform absorbs whatever remains.
        NOTE: the underlying creator/profile itself earns nothing extra here —
        the manager IS the one "being" the creator for revenue purposes during trial.
    """
    gross   = transaction.gross_amount
    profile = transaction.profile
    if not profile:
        return

    split = get_revenue_split()
    records = []

    if profile.manager_id and profile.account_type != 'sole_creator':
        # ── Manager-run account ──────────────────────────────────────────
        manager_pct = min(split.manager_pct, 55.0)  # never exceeds configured/default cap
        ops_pct     = max(split.ops_manager_pct, 0.0)
        if manager_pct + ops_pct > 100:
            ops_pct = max(0.0, 100 - manager_pct)
        platform_pct = max(0.0, 100 - manager_pct - ops_pct)

        records.append(EarningsRecord(
            transaction_id=transaction.id,
            beneficiary_type='creator_manager',
            beneficiary_user_id=profile.manager_id,
            profile_id=profile.id,
            amount=round(gross * manager_pct / 100, 2),
            content_type=transaction.content_type
        ))
        if ops_pct > 0 and profile.assigned_by_ops_id:
            records.append(EarningsRecord(
                transaction_id=transaction.id,
                beneficiary_type='ops_manager',
                beneficiary_user_id=profile.assigned_by_ops_id,
                profile_id=profile.id,
                amount=round(gross * ops_pct / 100, 2),
                content_type=transaction.content_type
            ))
            platform_amount = round(gross * platform_pct / 100, 2)
        else:
            # No OPS manager attached — their cut rolls into platform
            platform_amount = round(gross * (platform_pct + ops_pct) / 100, 2)

        records.append(EarningsRecord(
            transaction_id=transaction.id,
            beneficiary_type='platform',
            beneficiary_user_id=None,
            profile_id=profile.id,
            amount=platform_amount,
            content_type=transaction.content_type
        ))

    else:
        # ── Sole verified creator account ────────────────────────────────
        creator_account = CreatorAccount.query.filter_by(profile_id=profile.id).first()
        creator_user_id = creator_account.user_id if creator_account else None

        # Hard cap: no sole creator ever earns more than MAX_CREATOR_PCT (70%)
        if profile.account_type == 'sole_creator_admin_issued':
            creator_pct = min(split.creator_pct, 65.0)
        else:
            creator_pct = min(split.creator_pct, MAX_CREATOR_PCT)
        platform_pct = max(0.0, 100 - creator_pct)

        records.append(EarningsRecord(
            transaction_id=transaction.id,
            beneficiary_type='creator',
            beneficiary_user_id=creator_user_id,
            profile_id=profile.id,
            amount=round(gross * creator_pct / 100, 2),
            content_type=transaction.content_type
        ))
        records.append(EarningsRecord(
            transaction_id=transaction.id,
            beneficiary_type='platform',
            beneficiary_user_id=None,
            profile_id=profile.id,
            amount=round(gross * platform_pct / 100, 2),
            content_type=transaction.content_type
        ))

    for r in records:
        db.session.add(r)
    db.session.commit()

    # Check if this profile qualifies for automatic graduation
    try:
        check_graduation(profile.id)
    except Exception as e:
        print('Graduation check error: {}'.format(e))

def get_user_balances(user_id):
    """Returns (pending, available, lifetime) for a user.

    'available' EXCLUDES any earnings already locked against a pending/approved/paid
    withdrawal request — this is what prevents double-withdrawal / conflicting payouts.
    """
    records = EarningsRecord.query.filter_by(beneficiary_user_id=user_id).all()
    pending   = sum(r.amount for r in records if not r.is_available and not r.withdrawal_request_id)
    available = sum(r.amount for r in records if r.is_available and not r.withdrawal_request_id)
    lifetime  = sum(r.amount for r in records)
    return pending, available, lifetime

def get_user_revenue_breakdown(user_id):
    """Returns dict of revenue by content_type for a user."""
    records = EarningsRecord.query.filter_by(beneficiary_user_id=user_id).all()
    breakdown = {}
    for r in records:
        breakdown[r.content_type] = breakdown.get(r.content_type, 0) + r.amount
    return breakdown

def lock_earnings_for_withdrawal(user_id, amount, withdrawal_request):
    """Lock exactly `amount` worth of available, unlocked EarningsRecord rows
    against this withdrawal request so they can never be claimed again by a
    second withdrawal. Returns True if the full amount could be locked.

    This is the fix for the double-withdrawal/conflict bug: without this,
    'available' balance was never actually deducted when a request was made.
    """
    remaining = amount
    records = EarningsRecord.query.filter_by(
        beneficiary_user_id=user_id, is_available=True, withdrawal_request_id=None
    ).order_by(EarningsRecord.created_at.asc()).all()

    locked_records = []
    for r in records:
        if remaining <= 0:
            break
        # Lock the whole record (simplest, avoids needing partial-amount splitting)
        locked_records.append(r)
        remaining -= r.amount

    if remaining > 0.009:  # not enough available earnings to cover the request
        return False

    for r in locked_records:
        r.withdrawal_request_id = withdrawal_request.id
    db.session.commit()
    return True

def release_locked_earnings(withdrawal_request):
    """If a withdrawal is rejected, unlock its earnings so they become available again."""
    EarningsRecord.query.filter_by(withdrawal_request_id=withdrawal_request.id)\
        .update({'withdrawal_request_id': None})
    db.session.commit()

def check_graduation(profile_id):
    """Check if a junior_creator (or legacy manager_trial) qualifies for full Creator promotion.

    Trigger: 4+ distinct photo sales AND 4+ distinct video sales.
    For junior_creator accounts there is no minimum days requirement — sales are the only gate.
    """
    profile = Profile.query.get(profile_id)
    if not profile or profile.account_type not in ('junior_creator', 'manager_trial'):
        return False
    # junior_creator: no day gate. manager_trial: keep legacy day gate.
    if profile.account_type == 'manager_trial':
        if not profile.manager_assigned_at:
            return False
        days_since = (datetime.utcnow() - profile.manager_assigned_at).days
        if days_since < 7:
            return False

    # Count distinct photos/videos with at least 1 sale each
    sold_photos = db.session.query(db.func.count(db.distinct(VaultTransaction.content_id)))\
        .filter(VaultTransaction.profile_id==profile_id,
                VaultTransaction.content_type=='photo',
                VaultTransaction.status=='completed').scalar() or 0
    sold_videos = db.session.query(db.func.count(db.distinct(VaultTransaction.content_id)))\
        .filter(VaultTransaction.profile_id==profile_id,
                VaultTransaction.content_type=='video',
                VaultTransaction.status=='completed').scalar() or 0

    if sold_photos >= GRADUATION_MIN_PHOTOS and sold_videos >= GRADUATION_MIN_VIDEOS:
        _graduate_to_sole_creator(profile)
        return True
    return False

def _graduate_to_sole_creator(profile):
    """Promote a junior_creator (or legacy manager_trial) profile to sole_creator.

    junior_creator path: creator already has a User + CreatorAccount → just upgrade role.
    manager_trial path: manager email becomes the new creator login (legacy behaviour).
    """
    # ── junior_creator path ──────────────────────────────────────────────────
    ca = CreatorAccount.query.filter_by(profile_id=profile.id).first()
    if ca and profile.account_type == 'junior_creator':
        creator_user = User.query.get(ca.user_id)
        if creator_user:
            creator_user.role = 'creator'
        profile.account_type = 'sole_creator'
        db.session.commit()
        try:
            if creator_user:
                send_account_grant_email(creator_user.email, profile.name or profile.username, '', role='creator')
        except Exception:
            pass
        print('✅ Profile {} promoted junior_creator → creator (sole_creator). User: {}'.format(
            profile.username, creator_user.email if creator_user else '?'))
        return

    # ── legacy manager_trial path ────────────────────────────────────────────
    manager_user = User.query.get(profile.manager_id) if profile.manager_id else None
    if not manager_user:
        return

    creator_email = manager_user.email
    temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

    existing_user = User.query.filter_by(email=creator_email).first()
    if existing_user and existing_user.role == 'creator_manager':
        existing_user.role = 'creator'
        db.session.flush()
        ca_user_id = existing_user.id
    elif existing_user:
        ca_user_id = existing_user.id
    else:
        new_user = User(
            email=creator_email,
            password_hash=generate_password_hash(temp_password),
            role='creator'
        )
        db.session.add(new_user)
        db.session.flush()
        ca_user_id = new_user.id

    profile.manager_id = None
    profile.assigned_by_ops_id = None
    profile.account_type = 'sole_creator'

    if not ca:
        ca = CreatorAccount(
            user_id=ca_user_id,
            profile_id=profile.id,
            terms_accepted=False
        )
        db.session.add(ca)

    db.session.commit()

    try:
        send_account_grant_email(creator_email, profile.username, temp_password, role='creator')
    except Exception:
        pass

    print('✅ Profile {} graduated manager_trial → sole_creator. User: {}'.format(profile.username, creator_email))

def is_withdrawal_day():
    """Returns True if today is Wednesday (2) or Saturday (5)."""
    return datetime.utcnow().weekday() in (2, 5)

def next_withdrawal_day():
    """Returns the name of the next withdrawal window."""
    today = datetime.utcnow().weekday()
    # Wednesday=2, Saturday=5
    if today < 2:
        return 'Wednesday'
    elif today < 5:
        return 'Saturday'
    else:
        return 'Wednesday'

def make_transaction_ref():
    return 'VX-' + str(uuid.uuid4()).replace('-', '').upper()[:16]

def junior_creator_sales_count(user_id):
    """Count of completed transactions on a profile for a junior creator —
    used to display progress toward the 4+4 qualification threshold."""
    ca = CreatorAccount.query.filter_by(user_id=user_id).first()
    if not ca:
        return {'photos': 0, 'videos': 0}
    photo_sales = VaultTransaction.query.filter_by(
        profile_id=ca.profile_id, content_type='photo', status='completed'
    ).count()
    video_sales = VaultTransaction.query.filter_by(
        profile_id=ca.profile_id, content_type='video', status='completed'
    ).count()
    return {'photos': photo_sales, 'videos': video_sales}

def junior_creator_is_eligible_for_promotion(user_id):
    """Check if a junior_creator has met the 4+4 sales qualification for
    automatic promotion to full Creator. Returns (bool, message)."""
    min_sales = GRADUATION_MIN_PHOTOS
    ca = CreatorAccount.query.filter_by(user_id=user_id).first()
    if not ca:
        return False, 'No creator profile linked to this account.'
    profile = ca.profile
    sales = junior_creator_sales_count(user_id)
    if sales['photos'] < min_sales or sales['videos'] < min_sales:
        return False, 'You need {} photo sales and {} video sales (currently {} photos, {} videos).'.format(
            min_sales, min_sales, sales['photos'], sales['videos'])
    return True, 'Eligible'
