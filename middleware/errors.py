"""Global error handlers."""
from flask import render_template, jsonify


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        return render_template('base.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({'error': 'Internal server error'}), 500
