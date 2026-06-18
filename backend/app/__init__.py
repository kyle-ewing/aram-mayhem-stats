"""Application factory.

Wires up Flask, CORS, the API blueprint, and JSON error handling. All business
logic lives in ``services/``; this module only assembles the app.
"""
from __future__ import annotations

from flask import Flask, jsonify
from flask_cors import CORS

from .config import Config
from .db import init_db
from .errors import ApiError, RateLimitError


def create_app(config: type[Config] = Config) -> Flask:
    """Build and configure the Flask application."""
    app = Flask(__name__)
    app.config["DEBUG"] = config.DEBUG

    CORS(app, origins=config.CORS_ORIGINS)

    init_db(config.DATABASE_PATH)

    from .api import bp as api_bp

    app.register_blueprint(api_bp, url_prefix="/api")

    _register_error_handlers(app)

    return app


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        response = jsonify(err.to_dict())
        response.status_code = err.status_code
        if isinstance(err, RateLimitError) and err.retry_after is not None:
            response.headers["Retry-After"] = str(err.retry_after)
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(err: Exception):
        # Never leak internal details (or the API key) to clients.
        response = jsonify({"error": "Internal server error"})
        response.status_code = 500
        return response
