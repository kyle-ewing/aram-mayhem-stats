"""API blueprint package.

Route handlers are thin: they parse/validate request input, delegate to
``services/``, and jsonify the result. No business logic or Riot calls here.
"""
from __future__ import annotations

from .routes import bp

__all__ = ["bp"]
