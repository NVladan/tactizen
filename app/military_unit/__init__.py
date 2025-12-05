# app/military_unit/__init__.py
"""
Military Unit Blueprint

Handles military unit (regiment) creation, management, bounty contracts,
and related functionality.
"""

from flask import Blueprint

bp = Blueprint('military_unit', __name__)

from . import routes  # noqa: E402, F401
