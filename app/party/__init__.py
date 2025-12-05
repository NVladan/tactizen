# app/party/__init__.py

from flask import Blueprint

bp = Blueprint('party', __name__, url_prefix='/party')

from app.party import routes
