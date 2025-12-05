from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'main.index'
login.login_message = 'Please log in to access this page.'
login.login_message_category = 'info'

@login.unauthorized_handler
def unauthorized_callback():
    """Handle unauthorized access - return JSON for AJAX, redirect for regular requests."""
    from flask import request, redirect, url_for, flash, jsonify, session, get_flashed_messages

    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'error': 'unauthorized', 'message': 'Please log in to access this page.'}), 401

    # Regular request - only flash if this message isn't already pending
    # This prevents duplicate messages when multiple redirects occur
    flashes = session.get('_flashes', [])
    login_msg_exists = any(msg[1] == login.login_message for msg in flashes)
    if not login_msg_exists:
        flash(login.login_message, login.login_message_category)

    return redirect(url_for(login.login_view))

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

cache = Cache()
csrf = CSRFProtect()