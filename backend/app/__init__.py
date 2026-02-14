from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from app.api.routes import api_bp


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)  # ok for MVP; tighten later

    app.register_blueprint(api_bp)
    return app
