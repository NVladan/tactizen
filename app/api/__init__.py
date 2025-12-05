"""
API Blueprint

Provides RESTful API endpoints for programmatic access to Tactizen.
API is disabled by default. Set API_ENABLED=true in config to enable.
"""

from flask import Blueprint

bp = Blueprint('api', __name__, url_prefix='/api')

# Import routes after blueprint creation to avoid circular imports
from app.api import routes, token_routes
