# app/admin/__init__.py
"""
Admin blueprint for managing soft-deleted records and administrative tasks.
"""

from flask import Blueprint

bp = Blueprint('admin', __name__, url_prefix='/admin')

from app.admin import routes
