from functools import wraps
from flask import session, redirect, url_for


from models import CreatorAccount


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

def manager_required(f):
    """Allows both admins and creator_managers through."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin') and not session.get('is_manager'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def ops_manager_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin') and session.get('user_role') not in ('ops_manager',):
            return redirect(url_for('ops_login'))
        return f(*args, **kwargs)
    return decorated

def creator_only_required(f):
    """Allows ONLY creator_managers/creators through — admins are blocked.

    Content creation (photo/video uploads) is exclusively a creator
    responsibility. Admins manage the platform and users, but no longer
    have direct upload access.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_manager'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def creator_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('creator_account_id'):
            return redirect(url_for('creator_login'))
        ca = CreatorAccount.query.get(session['creator_account_id'])
        if not ca:
            return redirect(url_for('creator_login'))
        if not ca.terms_accepted:
            return redirect(url_for('creator_terms'))
        return f(*args, **kwargs)
    return decorated
