# app/models/activity.py
"""
Activity tracking models for monitoring user actions and behavior.
"""

import enum
from datetime import datetime
from sqlalchemy import Index
from . import db


class ActivityType(enum.Enum):
    """Types of activities to track."""
    # Authentication
    LOGIN = 'login'
    LOGOUT = 'logout'

    # Page Views
    PAGE_VIEW = 'page_view'

    # Game Actions
    MARKET_BUY = 'market_buy'
    MARKET_SELL = 'market_sell'
    CURRENCY_EXCHANGE = 'currency_exchange'
    TRAVEL = 'travel'
    TRAIN = 'train'
    STUDY = 'study'
    PROFILE_UPDATE = 'profile_update'

    # Admin Actions
    ADMIN_ACTION = 'admin_action'
    CACHE_CLEAR = 'cache_clear'

    # Social
    PROFILE_VIEW = 'profile_view'

    # Errors
    ERROR_403 = 'error_403'
    ERROR_404 = 'error_404'
    ERROR_500 = 'error_500'


class ActivityLog(db.Model):
    """
    Detailed log of user activities.

    Stores granular information about user actions for:
    - Analytics and statistics
    - Security auditing
    - User behavior analysis
    - Troubleshooting
    """
    __tablename__ = 'activity_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)  # Nullable for anonymous
    activity_type = db.Column(db.Enum(ActivityType), nullable=False, index=True)

    # Request information
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 support
    user_agent = db.Column(db.String(255), nullable=True)
    endpoint = db.Column(db.String(255), nullable=True, index=True)  # Route endpoint
    method = db.Column(db.String(10), nullable=True)  # GET, POST, etc.

    # Additional context (JSON for flexibility)
    details = db.Column(db.JSON, nullable=True)  # Flexible storage for activity-specific data

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('activities', lazy='dynamic'))

    # Table constraints and indexes
    __table_args__ = (
        Index('idx_activity_user_type', 'user_id', 'activity_type'),
        Index('idx_activity_created', 'created_at'),
        Index('idx_activity_user_created', 'user_id', 'created_at'),
    )

    def __repr__(self):
        return f'<ActivityLog {self.activity_type.value} user:{self.user_id} at {self.created_at}>'

    @classmethod
    def log_activity(cls, activity_type, user_id=None, ip_address=None,
                    user_agent=None, endpoint=None, method=None, details=None):
        """
        Convenience method to log an activity.

        Args:
            activity_type (ActivityType or str): Type of activity
            user_id (int, optional): User ID (None for anonymous)
            ip_address (str, optional): IP address
            user_agent (str, optional): User agent string
            endpoint (str, optional): Flask endpoint
            method (str, optional): HTTP method
            details (dict, optional): Additional context as dict

        Returns:
            ActivityLog: The created activity log entry
        """
        if isinstance(activity_type, str):
            activity_type = ActivityType(activity_type)

        log_entry = cls(
            user_id=user_id,
            activity_type=activity_type,
            ip_address=ip_address,
            user_agent=user_agent,
            endpoint=endpoint,
            method=method,
            details=details
        )

        db.session.add(log_entry)
        return log_entry

    @classmethod
    def get_user_activities(cls, user_id, activity_type=None, limit=50):
        """
        Get recent activities for a user.

        Args:
            user_id (int): User ID
            activity_type (ActivityType, optional): Filter by type
            limit (int): Maximum number of results

        Returns:
            list: List of ActivityLog entries
        """
        query = cls.query.filter_by(user_id=user_id)

        if activity_type:
            query = query.filter_by(activity_type=activity_type)

        return query.order_by(cls.created_at.desc()).limit(limit).all()

    @classmethod
    def get_recent_activities(cls, activity_type=None, limit=100):
        """
        Get recent activities across all users.

        Args:
            activity_type (ActivityType, optional): Filter by type
            limit (int): Maximum number of results

        Returns:
            list: List of ActivityLog entries
        """
        query = cls.query

        if activity_type:
            query = query.filter_by(activity_type=activity_type)

        return query.order_by(cls.created_at.desc()).limit(limit).all()


class UserSession(db.Model):
    """
    Track user login sessions for security and analytics.

    Stores information about each login session including:
    - Login time and duration
    - IP address and user agent
    - Logout time (if explicit logout)
    """
    __tablename__ = 'user_session'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Session information
    session_token = db.Column(db.String(255), unique=True, index=True, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)

    # Timestamps
    login_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    logout_at = db.Column(db.DateTime, nullable=True)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Session status
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('sessions', lazy='dynamic'))

    # Table constraints
    __table_args__ = (
        Index('idx_session_user_active', 'user_id', 'is_active'),
        Index('idx_session_login', 'login_at'),
    )

    def __repr__(self):
        return f'<UserSession user:{self.user_id} login:{self.login_at}>'

    @property
    def duration(self):
        """Calculate session duration."""
        end_time = self.logout_at or datetime.utcnow()
        return end_time - self.login_at

    @property
    def is_expired(self, timeout_hours=24):
        """Check if session is expired (inactive for too long)."""
        if not self.is_active:
            return True

        inactive_duration = datetime.utcnow() - self.last_activity
        return inactive_duration.total_seconds() > (timeout_hours * 3600)

    def end_session(self):
        """Mark session as ended."""
        self.logout_at = datetime.utcnow()
        self.is_active = False

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()
