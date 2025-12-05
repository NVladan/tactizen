# app/auth/__init__.py
from flask import Blueprint

# 1. Create the Blueprint object FIRST
bp = Blueprint('auth', __name__)

# 2. THEN import the routes file which uses the 'bp' object
from app.auth import routes