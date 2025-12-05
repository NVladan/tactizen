# app/government/__init__.py

from flask import Blueprint

bp = Blueprint('government', __name__, url_prefix='/government')

from app.government import routes
from app.government import alliance_routes
