"""
API Token Model

Provides secure API authentication using tokens.
Each token has:
- Unique token string (hashed in database)
- Expiration date
- Permissions/scopes
- Usage tracking
- IP whitelist (optional)
"""

from datetime import datetime, timedelta
from app.extensions import db
from enum import Enum
import secrets
import hashlib


class APITokenScope(Enum):
    """API token permission scopes."""
    # Read-only scopes
    READ_PROFILE = "read:profile"
    READ_INVENTORY = "read:inventory"
    READ_MARKET = "read:market"
    READ_MESSAGES = "read:messages"
    READ_STATS = "read:stats"

    # Write scopes
    WRITE_MARKET = "write:market"
    WRITE_MESSAGES = "write:messages"
    WRITE_ACTIONS = "write:actions"  # Work, train, travel, etc.

    # Admin scopes
    ADMIN_READ = "admin:read"
    ADMIN_WRITE = "admin:write"

    # Full access
    FULL_ACCESS = "full:access"


class APIToken(db.Model):
    """API authentication tokens for programmatic access."""
    __tablename__ = 'api_tokens'

    id = db.Column(db.Integer, primary_key=True)

    # Token identification
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

    # Token hash (never store raw token)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)

    # Token prefix for identification (first 8 chars, not sensitive)
    token_prefix = db.Column(db.String(8), nullable=False)

    # Owner
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    user = db.relationship('User', backref=db.backref('api_tokens', lazy='dynamic'))

    # Permissions (stored as JSON array of scopes)
    scopes = db.Column(db.JSON, nullable=False, default=list)

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)  # NULL = never expires
    last_used_at = db.Column(db.DateTime)

    # Usage tracking
    total_requests = db.Column(db.Integer, default=0, nullable=False)

    # IP whitelist (optional, stored as JSON array)
    # If set, token only works from these IPs
    allowed_ips = db.Column(db.JSON)

    # Security
    last_used_ip = db.Column(db.String(45))  # IPv6 max length

    def __repr__(self):
        return f'<APIToken {self.name} ({self.token_prefix}...)>'

    @staticmethod
    def generate_token():
        """
        Generate a secure random API token.

        Returns:
            str: Token in format 'cr_' + 32 random hex chars (total 35 chars)
        """
        # Generate 16 random bytes = 32 hex chars
        random_part = secrets.token_hex(16)
        return f"cr_{random_part}"

    @staticmethod
    def hash_token(token):
        """
        Hash a token for storage.

        Args:
            token: Raw token string

        Returns:
            str: SHA-256 hash of token
        """
        return hashlib.sha256(token.encode()).hexdigest()

    @classmethod
    def create_token(cls, user_id, name, scopes, description=None, expires_in_days=None, allowed_ips=None):
        """
        Create a new API token.

        Args:
            user_id: User ID who owns the token
            name: Human-readable token name
            scopes: List of APITokenScope values
            description: Optional description
            expires_in_days: Token lifetime in days (None = never expires)
            allowed_ips: Optional list of allowed IP addresses

        Returns:
            tuple: (APIToken object, raw_token_string)
        """
        # Generate token
        raw_token = cls.generate_token()
        token_hash = cls.hash_token(raw_token)
        token_prefix = raw_token[:8]  # 'cr_' + first 5 chars of random part

        # Convert scopes to strings
        scope_strings = [s.value if isinstance(s, APITokenScope) else s for s in scopes]

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # Create token object
        token = cls(
            name=name,
            description=description,
            token_hash=token_hash,
            token_prefix=token_prefix,
            user_id=user_id,
            scopes=scope_strings,
            expires_at=expires_at,
            allowed_ips=allowed_ips
        )

        return token, raw_token

    @classmethod
    def verify_token(cls, raw_token):
        """
        Verify and retrieve token from database.

        Args:
            raw_token: Raw token string from API request

        Returns:
            APIToken object if valid, None otherwise
        """
        if not raw_token or not raw_token.startswith('cr_'):
            return None

        token_hash = cls.hash_token(raw_token)
        token = cls.query.filter_by(token_hash=token_hash).first()

        if not token:
            return None

        # Check if token is active
        if not token.is_active:
            return None

        # Check if token is expired
        if token.expires_at and token.expires_at < datetime.utcnow():
            return None

        return token

    def has_scope(self, required_scope):
        """
        Check if token has a specific scope.

        Args:
            required_scope: APITokenScope or string to check

        Returns:
            bool: True if token has the scope
        """
        if isinstance(required_scope, APITokenScope):
            required_scope = required_scope.value

        # Full access grants all scopes
        if APITokenScope.FULL_ACCESS.value in self.scopes:
            return True

        return required_scope in self.scopes

    def is_ip_allowed(self, ip_address):
        """
        Check if token can be used from this IP address.

        Args:
            ip_address: IP address to check

        Returns:
            bool: True if IP is allowed (or no IP whitelist configured)
        """
        # If no IP whitelist, all IPs are allowed
        if not self.allowed_ips:
            return True

        # Check if IP is in whitelist
        return ip_address in self.allowed_ips

    def record_usage(self, ip_address):
        """
        Record token usage.

        Args:
            ip_address: IP address of the request
        """
        self.total_requests += 1
        self.last_used_at = datetime.utcnow()
        self.last_used_ip = ip_address
        db.session.commit()

    def revoke(self):
        """Revoke (deactivate) this token."""
        self.is_active = False
        db.session.commit()

    def is_expired(self):
        """
        Check if token is expired.

        Returns:
            bool: True if expired
        """
        if not self.expires_at:
            return False
        return self.expires_at < datetime.utcnow()

    def days_until_expiry(self):
        """
        Get number of days until token expires.

        Returns:
            int: Days until expiry, None if never expires
        """
        if not self.expires_at:
            return None

        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)

    def to_dict(self, include_token=False):
        """
        Convert token to dictionary for API response.

        Args:
            include_token: Whether to include raw token (only for creation)

        Returns:
            dict: Token information
        """
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'token_prefix': self.token_prefix,
            'scopes': self.scopes,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'total_requests': self.total_requests,
            'allowed_ips': self.allowed_ips,
            'days_until_expiry': self.days_until_expiry(),
            'is_expired': self.is_expired()
        }

        return data
