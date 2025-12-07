# app/__init__.py
from flask import Flask, jsonify
from flask_login import current_user
from config import Config
from .extensions import db, migrate, login, limiter, cache, csrf
from app.models import User
# Import your context processors
from .context_processors import inject_forms, utility_processor # Import utility_processor
# Import logging configuration
from .logging_config import setup_logging
# Import security utilities
from .security import add_security_headers, register_security_filters
# Import activity tracking
from .activity_tracker import track_page_view

# Import utils if needed elsewhere, otherwise remove if only for leveling
# from . import utils

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Setup logging (do this early, after config is loaded)
    setup_logging(app)

    # Register security filters for templates
    register_security_filters(app)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)
    csrf.init_app(app)

    # Register blueprints here
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp)

    from app.party import bp as party_bp
    app.register_blueprint(party_bp)

    from app.government import bp as government_bp
    app.register_blueprint(government_bp)

    from app.government.zk_routes import zk_bp
    app.register_blueprint(zk_bp)
    csrf.exempt(zk_bp)  # ZK voting uses cryptographic proof instead of CSRF

    from app.main.company_routes import company_bp
    app.register_blueprint(company_bp)

    from app.main.friendship_routes import bp as friendship_bp
    app.register_blueprint(friendship_bp)

    from app.routes.nft_routes import nft_bp
    app.register_blueprint(nft_bp)

    from app.routes.wallet_routes import wallet_bp
    app.register_blueprint(wallet_bp)

    from app.routes.marketplace_routes import marketplace_bp
    app.register_blueprint(marketplace_bp)

    from app.support import bp as support_bp
    app.register_blueprint(support_bp)

    from app.military_unit import bp as military_unit_bp
    app.register_blueprint(military_unit_bp, url_prefix='/military-unit')

    # Register API blueprint (conditionally)
    if app.config.get('API_ENABLED'):
        from app.api import bp as api_bp
        app.register_blueprint(api_bp)
        # Exempt API routes from CSRF (they use token auth)
        csrf.exempt(api_bp)
        app.logger.info("API endpoints enabled")
    else:
        app.logger.info("API endpoints disabled (set API_ENABLED=true to enable)")

    # Initialize scheduler for automated election management
    from app.scheduler import init_scheduler
    init_scheduler(app)

    # Register CLI commands
    from app.cli import register_cli_commands
    register_cli_commands(app)

    # Register error handlers
    from app.error_handlers import register_error_handlers
    register_error_handlers(app)

    # User loader callback
    @login.user_loader
    def load_user(user_id):
        # Ensure user_id is valid before querying
        try:
            uid = int(user_id)
        except (ValueError, TypeError):
            return None
        return db.session.get(User, uid)

    # Register context processors
    app.context_processor(inject_forms)
    app.context_processor(utility_processor) # Register the new processor here

    # Track user activity and check bans before each request
    @app.before_request
    def track_activity():
        from app.session_security import (
            check_session_timeout,
            validate_session_fingerprint,
            update_session_activity,
            invalidate_session
        )

        # Check session security for authenticated users
        if current_user.is_authenticated:
            from flask import session, request, jsonify

            # Helper to check if this is an AJAX request
            def is_ajax_request():
                return request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json

            # If user is authenticated but session has no security metadata,
            # they were loaded from a "remember me" cookie after session expired.
            # Force re-login for security.
            if not session.get('_created_at'):
                invalidate_session("Session restored from remember cookie - please log in again")
                from flask import flash, redirect, url_for
                if is_ajax_request():
                    return jsonify({'error': 'session_expired', 'message': 'Your session has expired. Please log in again.'}), 401
                flash('Your session has expired. Please log in again.', 'warning')
                return redirect(url_for('main.index'))

            # Check session timeout (absolute and inactivity)
            is_expired, timeout_reason = check_session_timeout(
                absolute_timeout=app.config.get('PERMANENT_SESSION_LIFETIME', 86400),
                inactivity_timeout=app.config.get('SESSION_INACTIVITY_TIMEOUT', 3600)
            )

            if is_expired:
                invalidate_session(timeout_reason)
                from flask import flash, redirect, url_for
                if is_ajax_request():
                    return jsonify({'error': 'session_expired', 'message': f'Your session has expired: {timeout_reason}. Please log in again.'}), 401
                flash(f'Your session has expired: {timeout_reason}. Please log in again.', 'warning')
                return redirect(url_for('main.index'))

            # Validate session fingerprint (detect session hijacking)
            is_valid, fingerprint_reason = validate_session_fingerprint()
            if not is_valid:
                from app.models import SecurityEventType, SecurityLogSeverity, log_security_event, get_request_info
                request_info = get_request_info()
                log_security_event(
                    event_type=SecurityEventType.SUSPICIOUS_REQUEST,
                    message=f"Possible session hijacking detected: {fingerprint_reason}",
                    severity=SecurityLogSeverity.ERROR,
                    user_id=current_user.id,
                    username=current_user.username,
                    **request_info
                )
                invalidate_session(fingerprint_reason)
                from flask import flash, redirect, url_for
                if is_ajax_request():
                    return jsonify({'error': 'session_invalid', 'message': 'Security alert: Your session has been invalidated. Please log in again.'}), 401
                flash('Security alert: Your session has been invalidated. Please log in again.', 'danger')
                return redirect(url_for('main.index'))

            # Update session activity timestamp
            update_session_activity()

        # Check if logged-in user is banned
        if current_user.is_authenticated and current_user.is_banned:
            from flask_login import logout_user
            from flask import flash, redirect, url_for, request

            # Allow logout endpoint to proceed
            if request.endpoint == 'auth.logout':
                return

            # Check if temporary ban has expired
            if not current_user.check_and_clear_expired_ban():
                # User is still banned - force logout
                ban_message = current_user.ban_reason if current_user.ban_reason else "Your account has been banned."
                if current_user.banned_until:
                    ban_message += f" Ban expires: {current_user.banned_until.strftime('%Y-%m-%d %H:%M UTC')}"
                else:
                    ban_message += " This ban is permanent."

                logout_user()
                flash(ban_message, 'danger')
                return redirect(url_for('main.index'))
            else:
                # Ban expired, clear it and allow continued access
                db.session.commit()

        # Track page views
        track_page_view()

    # Add security headers to all responses
    @app.after_request
    def set_security_headers(response):
        return add_security_headers(response)

    return app

