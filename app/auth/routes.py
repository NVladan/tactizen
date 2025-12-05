# app/auth/routes.py

# --- Imports ---
from flask import jsonify, request, session, current_app, url_for, redirect, flash, render_template
from flask_login import login_user, logout_user, current_user, login_required
from web3.auto import w3  # Or from web3 import Web3, Account
from eth_account.messages import encode_defunct
import uuid  # To generate nonces

from app.extensions import db, limiter
from app.auth import bp  # Import the blueprint
from app.models import User, Referral, SecurityLog, SecurityEventType, SecurityLogSeverity, log_security_event, get_request_info
from app.constants import GameConstants
from app.activity_tracker import track_login, track_logout
from app.security import InputSanitizer
from app.session_security import regenerate_session, init_session_security, register_session, unregister_session


# --- Web3 Authentication Routes ---

@bp.route('/web3_message', methods=['GET'])
@limiter.limit(lambda: current_app.config.get("RATELIMIT_LOGIN", "10 per minute"))
def web3_message():
    """
    Generates a unique message (nonce) for the user to sign.
    Stores the nonce in the session.
    """
    try:
        nonce = str(uuid.uuid4())  # Generate a unique nonce
        session['login_nonce'] = nonce  # Store nonce in user's session
        # Prepare the message string for the user to sign - **NAME CHANGED HERE**
        message = f"Please sign this message to authenticate with Tactizen.\n\nNonce: {nonce}"
        current_app.logger.info(f"Generated nonce {nonce} for login attempt.")
        return jsonify({'message': message})
    except Exception as e:
        current_app.logger.error(f"Error generating web3 message: {e}", exc_info=True)
        return jsonify({'error': 'Could not generate authentication message.'}), 500


@bp.route('/verify_signature', methods=['POST'])
@limiter.limit(lambda: current_app.config.get("RATELIMIT_LOGIN", "10 per minute"))
def verify_signature():
    """
    Verifies the signature provided by the user via MetaMask.
    Logs in existing users or creates a new user account.
    """
    data = request.get_json()
    if not data or 'address' not in data or 'signature' not in data:
        return jsonify({'success': False, 'error': 'Missing address or signature.'}), 400

    # Validate wallet address
    try:
        wallet_address = InputSanitizer.sanitize_wallet_address(data.get('address'))
    except ValueError as e:
        current_app.logger.warning(f"Invalid wallet address in login attempt: {data.get('address')}")

        # Log security event
        request_info = get_request_info()
        log_security_event(
            event_type=SecurityEventType.INVALID_WALLET,
            message=f"Invalid wallet address format in login attempt: {data.get('address')}",
            severity=SecurityLogSeverity.WARNING,
            wallet_address=data.get('address'),
            **request_info
        )

        return jsonify({'success': False, 'error': str(e)}), 400

    # Validate signature format (basic check)
    signature = data.get('signature')
    if not signature or not isinstance(signature, str) or len(signature) < 100:
        current_app.logger.warning(f"Invalid signature format in login attempt")

        # Log security event
        request_info = get_request_info()
        log_security_event(
            event_type=SecurityEventType.INVALID_SIGNATURE,
            message=f"Invalid signature format in login attempt for wallet {wallet_address}",
            severity=SecurityLogSeverity.WARNING,
            wallet_address=wallet_address,
            **request_info
        )

        return jsonify({'success': False, 'error': 'Invalid signature format.'}), 400

    nonce = session.get('login_nonce')
    if not nonce:
        current_app.logger.warning(f"Login attempt failed for {wallet_address}: No nonce found in session.")
        return jsonify({'success': False, 'error': 'Authentication session expired or invalid. Please try again.'}), 400

    message_string = f"Please sign this message to authenticate with Tactizen.\n\nNonce: {nonce}"
    message_hash = encode_defunct(text=message_string)

    try:
        recovered_address = w3.eth.account.recover_message(message_hash, signature=signature)
        current_app.logger.info(
            f"Attempting login for {wallet_address}. Nonce: {nonce}. Recovered address: {recovered_address}")

        if recovered_address.lower() != wallet_address.lower():
            # Signature verification failed
            current_app.logger.warning(f"Signature verification failed for {wallet_address}")

            # Log failed login attempt
            request_info = get_request_info()
            log_security_event(
                event_type=SecurityEventType.LOGIN_FAILED,
                message=f"Failed login attempt for wallet {wallet_address}: signature mismatch",
                severity=SecurityLogSeverity.WARNING,
                wallet_address=wallet_address,
                details={'recovered_address': recovered_address},
                **request_info
            )

            return jsonify({'success': False, 'error': 'Signature verification failed.'}), 401

        user = db.session.scalar(db.select(User).where(User.wallet_address == wallet_address, User.is_deleted == False))
        message = None

        if user is None:
            current_app.logger.info(f"Creating new user for address: {wallet_address}")
            user = User(
                wallet_address=wallet_address,
                base_wallet_address=wallet_address,  # Auto-set BASE wallet same as login wallet
                activate=True,
                gold=GameConstants.INITIAL_GOLD,
                wellness=GameConstants.INITIAL_WELLNESS
            )
            db.session.add(user)
            db.session.flush()  # Get user ID before creating referral

            # Generate referral code for new user
            user.generate_referral_code()

            # Check if user was referred by someone
            referral_code = session.get('referral_code')
            if referral_code:
                referrer = db.session.scalar(db.select(User).where(User.referral_code == referral_code))
                if referrer and referrer.id != user.id:
                    # Create referral record
                    referral = Referral(
                        referrer_id=referrer.id,
                        referee_id=user.id
                    )
                    db.session.add(referral)
                    current_app.logger.info(f"Created referral: User {referrer.id} referred user {user.id}")
                session.pop('referral_code', None)  # Clear referral code from session

            db.session.commit()
            message = 'Welcome to Tactizen! Your account has been created.'
        else:
            current_app.logger.info(f"Logging in existing user: {wallet_address}")

            # Check if user is banned
            if user.is_banned:
                # Check if it's a temporary ban that has expired
                if not user.check_and_clear_expired_ban():
                    # User is still banned
                    ban_message = user.ban_reason if user.ban_reason else "Your account has been banned."
                    if user.banned_until:
                        ban_message += f" Ban expires: {user.banned_until.strftime('%Y-%m-%d %H:%M UTC')}"
                    else:
                        ban_message += " This ban is permanent."

                    current_app.logger.warning(f"Banned user {user.id} attempted to log in")
                    return jsonify({
                        'success': False,
                        'error': ban_message
                    }), 403
                else:
                    # Ban expired, allow login
                    db.session.commit()

            # Auto-set base_wallet_address for existing users who don't have it
            if not user.base_wallet_address:
                user.base_wallet_address = wallet_address
                current_app.logger.info(f"Auto-set BASE wallet for user {user.id}")

            # Generate referral code for existing users who don't have one
            if not user.referral_code:
                user.generate_referral_code()
                db.session.commit()
            message = 'Welcome back to Tactizen!'

        login_user(user, remember=True)
        session.pop('login_nonce', None)

        # Regenerate session ID to prevent session fixation attacks
        regenerate_session()

        # Initialize session security metadata
        init_session_security()

        # Register this session for concurrent session tracking
        register_session(user.id)

        # Track login activity
        track_login(user)

        # Log successful login
        request_info = get_request_info()
        log_security_event(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            message=f"User {user.username or user.wallet_address[:10]} logged in successfully",
            severity=SecurityLogSeverity.INFO,
            user_id=user.id,
            username=user.username,
            wallet_address=user.wallet_address,
            **request_info
        )

        return jsonify({
            'success': True,
            'redirect_url': url_for('main.index'),
            'message': message
        })

    except Exception as e:
        current_app.logger.error(f"Error during signature verification: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Error verifying signature.'}), 500


# --- Referral Code Capture Route ---
@bp.route('/ref/<string:referral_code>')
def capture_referral(referral_code):
    """
    Captures referral code from URL and stores it in session.
    User is redirected to main page for login/registration.
    """
    # Verify referral code exists
    referrer = db.session.scalar(db.select(User).where(User.referral_code == referral_code))

    if referrer:
        session['referral_code'] = referral_code
        current_app.logger.info(f"Captured referral code: {referral_code}")
        flash(f'You were referred by {referrer.username if referrer.username else "a friend"}! Sign up to get started.', 'info')
    else:
        current_app.logger.warning(f"Invalid referral code attempted: {referral_code}")
        flash('Invalid referral link.', 'warning')

    return redirect(url_for('main.index'))


# --- Logout Route ---
@bp.route('/logout')
@login_required  # Ensures user must be logged in to log out
def logout():
    # Track logout before logging out
    track_logout(current_user)

    # Unregister session from concurrent session tracking
    unregister_session(current_user.id)

    # Log out user and clear session
    logout_user()
    session.clear()

    # Redirect to index page instead of rendering template directly
    # This ensures proper URL context for wallet connection
    return redirect(url_for('main.index'))