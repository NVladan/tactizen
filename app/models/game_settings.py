# app/models/game_settings.py
"""
Game Settings model for storing dynamic game configuration that can be toggled by admins.
"""

from datetime import datetime
from app.extensions import db


class GameSettings(db.Model):
    """
    Stores game-wide settings that can be modified by admins at runtime.
    Uses a key-value pattern for flexibility.
    """
    __tablename__ = 'game_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    updated_by = db.relationship('User', foreign_keys=[updated_by_id])

    # Setting keys as constants
    STARTER_PROTECTION_ENABLED = 'starter_protection_enabled'

    @classmethod
    def get_value(cls, key, default=None):
        """Get a setting value by key."""
        setting = db.session.scalar(
            db.select(cls).where(cls.key == key)
        )
        if setting:
            # Convert string to appropriate type
            if setting.value.lower() in ('true', '1', 'yes'):
                return True
            elif setting.value.lower() in ('false', '0', 'no'):
                return False
            return setting.value
        return default

    @classmethod
    def set_value(cls, key, value, description=None, updated_by_id=None):
        """Set a setting value."""
        setting = db.session.scalar(
            db.select(cls).where(cls.key == key)
        )
        if setting:
            setting.value = str(value)
            if description:
                setting.description = description
            if updated_by_id:
                setting.updated_by_id = updated_by_id
        else:
            setting = cls(
                key=key,
                value=str(value),
                description=description,
                updated_by_id=updated_by_id
            )
            db.session.add(setting)
        db.session.commit()
        return setting

    @classmethod
    def is_starter_protection_enabled(cls):
        """Check if starter protection is enabled."""
        from flask import current_app
        # First check database setting, then fall back to config
        db_value = cls.get_value(cls.STARTER_PROTECTION_ENABLED)
        if db_value is not None:
            return db_value
        # Fall back to config value
        return current_app.config.get('STARTER_PROTECTION_ENABLED', True)

    def __repr__(self):
        return f'<GameSettings {self.key}={self.value}>'
