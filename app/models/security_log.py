"""Security logging models for tracking security events."""

from datetime import datetime
from app.extensions import db
from enum import Enum


class SecurityEventType(Enum):
    """Types of security events to log."""
    # Authentication Events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    INVALID_SIGNATURE = "invalid_signature"
    INVALID_WALLET = "invalid_wallet"
    SESSION_EXPIRED = "session_expired"

    # Authorization Events
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    PERMISSION_DENIED = "permission_denied"

    # Validation Failures
    VALIDATION_ERROR = "validation_error"
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
    XSS_ATTEMPT = "xss_attempt"
    INVALID_INPUT = "invalid_input"

    # Rate Limiting
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"

    # Suspicious Activity
    SUSPICIOUS_REQUEST = "suspicious_request"
    MULTIPLE_FAILED_LOGINS = "multiple_failed_logins"
    BOT_DETECTED = "bot_detected"

    # Data Access
    ADMIN_ACTION = "admin_action"
    SENSITIVE_DATA_ACCESS = "sensitive_data_access"
    DATA_EXPORT = "data_export"

    # Account Security
    PASSWORD_CHANGE = "password_change"
    EMAIL_CHANGE = "email_change"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"

    # System Errors
    SYSTEM_ERROR = "system_error"
    DATABASE_ERROR = "database_error"
    HTTP_ERROR = "http_error"


class SecurityLogSeverity(Enum):
    """Severity levels for security events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SecurityLog(db.Model):
    """Security event log for tracking authentication, authorization, and suspicious activities."""
    __tablename__ = 'security_logs'

    id = db.Column(db.Integer, primary_key=True)

    # Timestamp
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Event Information
    event_type = db.Column(db.Enum(SecurityEventType), nullable=False, index=True)
    severity = db.Column(db.Enum(SecurityLogSeverity), nullable=False, default=SecurityLogSeverity.INFO, index=True)

    # User Information (nullable for unauthenticated events)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    username = db.Column(db.String(100), nullable=True)  # Store username at time of event
    wallet_address = db.Column(db.String(42), nullable=True, index=True)  # For failed login attempts

    # Request Information
    ip_address = db.Column(db.String(45), nullable=True, index=True)  # IPv6 max length
    user_agent = db.Column(db.String(500), nullable=True)
    endpoint = db.Column(db.String(255), nullable=True, index=True)
    http_method = db.Column(db.String(10), nullable=True)

    # Event Details
    message = db.Column(db.Text, nullable=False)
    details = db.Column(db.JSON, nullable=True)  # Additional structured data

    # Status
    resolved = db.Column(db.Boolean, default=False, index=True)  # For tracking follow-up on security incidents
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='security_logs')
    resolved_by_user = db.relationship('User', foreign_keys=[resolved_by_id])

    def __repr__(self):
        return f'<SecurityLog {self.id}: {self.event_type.value} - {self.severity.value}>'

    def to_dict(self):
        """Convert log entry to dictionary for API/display."""
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'event_type': self.event_type.value if self.event_type else None,
            'severity': self.severity.value if self.severity else None,
            'user_id': self.user_id,
            'username': self.username,
            'wallet_address': self.wallet_address,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'endpoint': self.endpoint,
            'http_method': self.http_method,
            'message': self.message,
            'details': self.details,
            'resolved': self.resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by_id': self.resolved_by_id,
            'resolution_notes': self.resolution_notes
        }


def log_security_event(
    event_type,
    message,
    severity=SecurityLogSeverity.INFO,
    user_id=None,
    username=None,
    wallet_address=None,
    ip_address=None,
    user_agent=None,
    endpoint=None,
    http_method=None,
    details=None
):
    """
    Log a security event to the database.

    Args:
        event_type: SecurityEventType enum value
        message: Human-readable description of the event
        severity: SecurityLogSeverity enum value (default: INFO)
        user_id: ID of the user involved (optional)
        username: Username at time of event (optional)
        wallet_address: Wallet address for failed logins (optional)
        ip_address: IP address of the request (optional)
        user_agent: User agent string (optional)
        endpoint: API endpoint/route (optional)
        http_method: HTTP method (GET, POST, etc.) (optional)
        details: Additional structured data as dict (optional)

    Returns:
        SecurityLog object
    """
    try:
        log_entry = SecurityLog(
            event_type=event_type,
            severity=severity,
            message=message,
            user_id=user_id,
            username=username,
            wallet_address=wallet_address,
            ip_address=ip_address,
            user_agent=user_agent,
            endpoint=endpoint,
            http_method=http_method,
            details=details
        )

        db.session.add(log_entry)
        db.session.commit()

        return log_entry

    except Exception as e:
        db.session.rollback()
        # Fallback to application logger if DB logging fails
        from flask import current_app
        current_app.logger.error(f"Failed to log security event to database: {e}", exc_info=True)
        return None


def get_request_info():
    """
    Helper function to extract request information for logging.

    Returns:
        dict with ip_address, user_agent, endpoint, http_method
    """
    from flask import request

    return {
        'ip_address': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', '')[:500],  # Truncate to prevent overflow
        'endpoint': request.endpoint,
        'http_method': request.method
    }
