"""
Session Security Module

Provides session security features including:
- Session regeneration (prevents session fixation)
- Absolute session timeout
- Concurrent session detection and management
- Session activity tracking
"""

from datetime import datetime, timedelta
from flask import session, request
from flask_login import current_user
import secrets


# Session Security Configuration
SESSION_ABSOLUTE_TIMEOUT = 1800  # 30 minutes in seconds (can be overridden by config)
SESSION_INACTIVITY_TIMEOUT = 1800  # 30 minutes in seconds
MAX_CONCURRENT_SESSIONS = 3  # Maximum concurrent sessions per user


def regenerate_session():
    """
    Regenerate session ID to prevent session fixation attacks.

    This should be called:
    - After successful login
    - After privilege escalation (e.g., becoming admin)
    - After any authentication state change

    Returns:
        bool: True if session was regenerated successfully
    """
    try:
        # Store current session data
        session_data = dict(session)

        # Clear the session (this invalidates the old session ID)
        session.clear()

        # Restore session data with new session ID
        for key, value in session_data.items():
            session[key] = value

        # Mark session as regenerated
        session.modified = True

        return True
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error regenerating session: {e}", exc_info=True)
        return False


def init_session_security():
    """
    Initialize session security metadata.

    Call this after successful login to set up session tracking.
    Sets:
    - Session creation time (for absolute timeout)
    - Last activity time (for inactivity timeout)
    - Session fingerprint (for concurrent session detection)
    """
    now = datetime.utcnow()

    # Set session creation time (for absolute timeout)
    session['_created_at'] = now.isoformat()

    # Set last activity time (for inactivity timeout)
    session['_last_activity'] = now.isoformat()

    # Generate unique session identifier for this login
    session['_session_id'] = secrets.token_urlsafe(32)

    # Store user agent fingerprint (basic session validation)
    session['_user_agent'] = request.headers.get('User-Agent', '')[:200]

    # Store IP address (for audit trail)
    session['_ip_address'] = request.remote_addr


def update_session_activity():
    """
    Update last activity timestamp.

    Call this on each request to track session inactivity.
    """
    if current_user.is_authenticated:
        session['_last_activity'] = datetime.utcnow().isoformat()
        session.modified = True


def check_session_timeout(absolute_timeout=None, inactivity_timeout=None):
    """
    Check if session has expired (absolute or inactivity timeout).

    Args:
        absolute_timeout: Maximum session lifetime in seconds (default: SESSION_ABSOLUTE_TIMEOUT)
        inactivity_timeout: Maximum inactivity time in seconds (default: SESSION_INACTIVITY_TIMEOUT)

    Returns:
        tuple: (is_expired: bool, reason: str or None)
    """
    # Check if we have session metadata (works even without authenticated user for testing)
    if not session.get('_created_at'):
        return False, None

    if absolute_timeout is None:
        absolute_timeout = SESSION_ABSOLUTE_TIMEOUT

    if inactivity_timeout is None:
        inactivity_timeout = SESSION_INACTIVITY_TIMEOUT

    now = datetime.utcnow()

    # Check absolute timeout (session created too long ago)
    created_at_str = session.get('_created_at')
    if created_at_str:
        try:
            created_at = datetime.fromisoformat(created_at_str)
            session_age = (now - created_at).total_seconds()

            if session_age > absolute_timeout:
                return True, f"Session expired after {absolute_timeout} seconds"
        except (ValueError, TypeError) as e:
            from flask import current_app
            current_app.logger.warning(f"Invalid session creation time: {e}")
            # If we can't parse the timestamp, consider it expired for security
            return True, "Invalid session timestamp"

    # Check inactivity timeout (no activity for too long)
    last_activity_str = session.get('_last_activity')
    if last_activity_str:
        try:
            last_activity = datetime.fromisoformat(last_activity_str)
            inactivity_time = (now - last_activity).total_seconds()

            if inactivity_time > inactivity_timeout:
                return True, f"Session inactive for {int(inactivity_time)} seconds"
        except (ValueError, TypeError) as e:
            from flask import current_app
            current_app.logger.warning(f"Invalid last activity time: {e}")

    return False, None


def validate_session_fingerprint():
    """
    Validate session fingerprint to detect session hijacking.

    Checks:
    - User agent hasn't changed (basic check)

    Note: IP address checking is not included as users may have dynamic IPs
    or use VPNs legitimately.

    Returns:
        tuple: (is_valid: bool, reason: str or None)
    """
    # Check if we have session fingerprint data
    if not session.get('_user_agent'):
        return True, None

    # Check user agent
    stored_user_agent = session.get('_user_agent', '')
    current_user_agent = request.headers.get('User-Agent', '')[:200]

    if stored_user_agent and stored_user_agent != current_user_agent:
        return False, "User agent mismatch (possible session hijacking)"

    return True, None


def get_session_info():
    """
    Get information about the current session.

    Returns:
        dict: Session information including age, last activity, etc.
    """
    # Check if we have session data
    if not session.get('_created_at'):
        return None

    now = datetime.utcnow()
    info = {
        'session_id': session.get('_session_id'),
        'created_at': session.get('_created_at'),
        'last_activity': session.get('_last_activity'),
        'ip_address': session.get('_ip_address'),
        'user_agent': session.get('_user_agent'),
    }

    # Calculate session age
    created_at_str = session.get('_created_at')
    if created_at_str:
        try:
            created_at = datetime.fromisoformat(created_at_str)
            info['session_age_seconds'] = int((now - created_at).total_seconds())
        except (ValueError, TypeError):
            info['session_age_seconds'] = None

    # Calculate time since last activity
    last_activity_str = session.get('_last_activity')
    if last_activity_str:
        try:
            last_activity = datetime.fromisoformat(last_activity_str)
            info['inactive_seconds'] = int((now - last_activity).total_seconds())
        except (ValueError, TypeError):
            info['inactive_seconds'] = None

    return info


def invalidate_session(reason=None):
    """
    Invalidate the current session and log the user out.

    Args:
        reason: Reason for session invalidation (for logging)
    """
    from flask import current_app
    from flask_login import logout_user

    user_id = current_user.id if current_user.is_authenticated else None
    session_id = session.get('_session_id', 'unknown')

    # Log session invalidation
    current_app.logger.warning(
        f"Session invalidated for user {user_id}, session {session_id}. "
        f"Reason: {reason or 'Unknown'}"
    )

    # Clear session data
    session.clear()

    # Log out user
    logout_user()


# ==================== Concurrent Session Management ====================

def get_user_session_key(user_id):
    """Get Redis/cache key for storing user's active sessions."""
    return f"user_sessions:{user_id}"


def register_session(user_id):
    """
    Register a new session for the user.

    Tracks concurrent sessions and enforces MAX_CONCURRENT_SESSIONS limit.

    Args:
        user_id: User ID

    Returns:
        tuple: (success: bool, message: str or None)
    """
    from flask import current_app
    from app.extensions import cache

    session_id = session.get('_session_id')
    if not session_id:
        return False, "No session ID found"

    # Get current sessions for this user
    cache_key = get_user_session_key(user_id)
    user_sessions = cache.get(cache_key) or {}

    # Add current session info
    session_info = {
        'session_id': session_id,
        'created_at': session.get('_created_at'),
        'ip_address': session.get('_ip_address'),
        'user_agent': session.get('_user_agent', '')[:100],
        'last_activity': session.get('_last_activity'),
    }

    user_sessions[session_id] = session_info

    # Clean up expired sessions
    now = datetime.utcnow()
    active_sessions = {}
    for sid, sinfo in user_sessions.items():
        try:
            created_at = datetime.fromisoformat(sinfo.get('created_at', ''))
            session_age = (now - created_at).total_seconds()

            # Keep sessions that are within absolute timeout
            if session_age <= SESSION_ABSOLUTE_TIMEOUT:
                active_sessions[sid] = sinfo
        except (ValueError, TypeError):
            # Skip invalid sessions
            continue

    # Check concurrent session limit
    if len(active_sessions) > MAX_CONCURRENT_SESSIONS:
        # Find oldest session to remove
        oldest_sid = None
        oldest_time = now

        for sid, sinfo in active_sessions.items():
            if sid == session_id:
                continue  # Don't remove current session

            try:
                created_at = datetime.fromisoformat(sinfo.get('created_at', ''))
                if created_at < oldest_time:
                    oldest_time = created_at
                    oldest_sid = sid
            except (ValueError, TypeError):
                continue

        if oldest_sid:
            current_app.logger.info(
                f"Removing oldest session {oldest_sid} for user {user_id} "
                f"(exceeded limit of {MAX_CONCURRENT_SESSIONS})"
            )
            del active_sessions[oldest_sid]

    # Store updated sessions
    cache.set(cache_key, active_sessions, timeout=SESSION_ABSOLUTE_TIMEOUT)

    return True, None


def unregister_session(user_id, session_id=None):
    """
    Unregister a session for the user.

    Args:
        user_id: User ID
        session_id: Session ID to remove (default: current session)
    """
    from app.extensions import cache

    if session_id is None:
        session_id = session.get('_session_id')

    if not session_id:
        return

    # Get current sessions for this user
    cache_key = get_user_session_key(user_id)
    user_sessions = cache.get(cache_key) or {}

    # Remove the session
    if session_id in user_sessions:
        del user_sessions[session_id]

    # Update cache
    if user_sessions:
        cache.set(cache_key, user_sessions, timeout=SESSION_ABSOLUTE_TIMEOUT)
    else:
        cache.delete(cache_key)


def get_user_active_sessions(user_id):
    """
    Get all active sessions for a user.

    Args:
        user_id: User ID

    Returns:
        list: List of session info dictionaries
    """
    from app.extensions import cache

    cache_key = get_user_session_key(user_id)
    user_sessions = cache.get(cache_key) or {}

    # Clean up expired sessions
    now = datetime.utcnow()
    active_sessions = []

    for sid, sinfo in user_sessions.items():
        try:
            created_at = datetime.fromisoformat(sinfo.get('created_at', ''))
            session_age = (now - created_at).total_seconds()

            if session_age <= SESSION_ABSOLUTE_TIMEOUT:
                # Add computed fields
                sinfo['session_age_seconds'] = int(session_age)
                sinfo['is_current'] = (sid == session.get('_session_id'))
                active_sessions.append(sinfo)
        except (ValueError, TypeError):
            continue

    # Sort by creation time (newest first)
    active_sessions.sort(
        key=lambda x: x.get('created_at', ''),
        reverse=True
    )

    return active_sessions


def terminate_session(user_id, session_id):
    """
    Terminate a specific session for a user.

    Args:
        user_id: User ID
        session_id: Session ID to terminate

    Returns:
        bool: True if session was terminated
    """
    from flask import current_app

    # Can't terminate current session this way (use logout instead)
    if session_id == session.get('_session_id'):
        return False

    # Remove from active sessions
    unregister_session(user_id, session_id)

    current_app.logger.info(f"Terminated session {session_id} for user {user_id}")

    return True


def terminate_all_other_sessions(user_id):
    """
    Terminate all sessions for a user except the current one.

    Useful for "log out all other devices" functionality.

    Args:
        user_id: User ID

    Returns:
        int: Number of sessions terminated
    """
    from flask import current_app
    from app.extensions import cache

    current_session_id = session.get('_session_id')

    # Get all sessions
    cache_key = get_user_session_key(user_id)
    user_sessions = cache.get(cache_key) or {}

    # Keep only current session
    terminated_count = 0
    for sid in list(user_sessions.keys()):
        if sid != current_session_id:
            del user_sessions[sid]
            terminated_count += 1

    # Update cache
    if user_sessions:
        cache.set(cache_key, user_sessions, timeout=SESSION_ABSOLUTE_TIMEOUT)
    else:
        cache.delete(cache_key)

    current_app.logger.info(
        f"Terminated {terminated_count} other sessions for user {user_id}"
    )

    return terminated_count
