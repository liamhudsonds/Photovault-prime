"""Register all VaultX blueprints."""
from routes.auth_routes import auth_bp
from routes.creator_routes import creator_bp
from routes.subscriber_routes import subscriber_bp
from routes.admin_routes import admin_bp
from routes.operations_routes import operations_bp
from routes.dashboard_routes import dashboard_bp
from routes.payment_routes import payment_bp
from routes.wallet_routes import wallet_bp
from routes.analytics_routes import analytics_bp
from routes.notification_routes import notification_bp
from routes.api_routes import api_bp
from routes.search_routes import search_bp
from routes.course_routes import course_bp

ALL_BLUEPRINTS = [
    auth_bp, creator_bp, subscriber_bp, admin_bp, operations_bp,
    dashboard_bp, payment_bp, wallet_bp, analytics_bp, notification_bp,
    api_bp, search_bp, course_bp,
]


def register_blueprints(app):
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)
