"""Request logging middleware."""
import time
from flask import request, g


def register_logging(app):
    @app.before_request
    def start_timer():
        g.start = time.time()

    @app.after_request
    def log_request(response):
        if hasattr(g, 'start'):
            elapsed = time.time() - g.start
            app.logger.debug('%s %s %.3fs', request.method, request.path, elapsed)
        return response
