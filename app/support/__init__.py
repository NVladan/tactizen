"""
Support System Blueprint - Tickets and Reports
"""
from flask import Blueprint

bp = Blueprint('support', __name__, url_prefix='/support')

from app.support import routes
