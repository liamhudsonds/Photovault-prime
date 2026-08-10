"""Authentication context middleware."""
from services.creator_service import is_admin_override, upload_url


def register_auth_context(app):
    @app.context_processor
    def inject_upload_context():
        return {
            'is_admin_override': is_admin_override(),
            'upload_url': upload_url,
        }

    @app.teardown_request
    def cleanup(exception=None):
        from database.db import db
        if exception:
            db.session.rollback()
