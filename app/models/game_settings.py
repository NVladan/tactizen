# app/models/game_settings.py
"""
Game Settings model for storing dynamic game configuration that can be toggled by admins.
"""

from datetime import datetime, date
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
    GAME_START_DATE = 'game_start_date'  # Format: YYYY-MM-DD

    # Global Multiplier keys
    XP_MULTIPLIER = 'xp_multiplier'  # Default: 1.0
    GOLD_DROP_MULTIPLIER = 'gold_drop_multiplier'  # Default: 1.0
    PRODUCTION_SPEED_MULTIPLIER = 'production_speed_multiplier'  # Default: 1.0
    WORK_XP_MULTIPLIER = 'work_xp_multiplier'  # Default: 1.0
    TRAINING_XP_MULTIPLIER = 'training_xp_multiplier'  # Default: 1.0
    BATTLE_XP_MULTIPLIER = 'battle_xp_multiplier'  # Default: 1.0
    TRAVEL_COST_MULTIPLIER = 'travel_cost_multiplier'  # Default: 1.0 (lower = cheaper)
    COMPANY_TAX_MULTIPLIER = 'company_tax_multiplier'  # Default: 1.0

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

    @classmethod
    def get_game_day(cls):
        """
        Get the current game day (days since game started).
        Returns day 1 on the start date, day 2 on the next day, etc.
        """
        start_date_str = cls.get_value(cls.GAME_START_DATE)
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                today = date.today()
                days_elapsed = (today - start_date).days
                return max(1, days_elapsed + 1)  # Day 1 on start date
            except (ValueError, TypeError):
                pass
        # Default: return day 1 if no start date set
        return 1

    @classmethod
    def get_game_start_date(cls):
        """Get the game start date as a date object."""
        start_date_str = cls.get_value(cls.GAME_START_DATE)
        if start_date_str:
            try:
                return datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
        return None

    def __repr__(self):
        return f'<GameSettings {self.key}={self.value}>'

    # --- Global Multiplier Methods ---
    @classmethod
    def get_multiplier(cls, key, default=1.0):
        """Get a multiplier value, ensuring it's a float."""
        value = cls.get_value(key)
        if value is not None:
            try:
                return float(value)
            except (ValueError, TypeError):
                pass
        return default

    @classmethod
    def get_xp_multiplier(cls):
        """Get global XP multiplier (affects all XP gains)."""
        return cls.get_multiplier(cls.XP_MULTIPLIER, 1.0)

    @classmethod
    def get_gold_drop_multiplier(cls):
        """Get gold drop multiplier (affects gold from work, battles, etc)."""
        return cls.get_multiplier(cls.GOLD_DROP_MULTIPLIER, 1.0)

    @classmethod
    def get_production_speed_multiplier(cls):
        """Get production speed multiplier (higher = faster production)."""
        return cls.get_multiplier(cls.PRODUCTION_SPEED_MULTIPLIER, 1.0)

    @classmethod
    def get_work_xp_multiplier(cls):
        """Get work XP multiplier."""
        return cls.get_multiplier(cls.WORK_XP_MULTIPLIER, 1.0)

    @classmethod
    def get_training_xp_multiplier(cls):
        """Get training XP multiplier."""
        return cls.get_multiplier(cls.TRAINING_XP_MULTIPLIER, 1.0)

    @classmethod
    def get_battle_xp_multiplier(cls):
        """Get battle XP multiplier."""
        return cls.get_multiplier(cls.BATTLE_XP_MULTIPLIER, 1.0)

    @classmethod
    def get_travel_cost_multiplier(cls):
        """Get travel cost multiplier (lower = cheaper travel)."""
        return cls.get_multiplier(cls.TRAVEL_COST_MULTIPLIER, 1.0)

    @classmethod
    def get_company_tax_multiplier(cls):
        """Get company tax multiplier."""
        return cls.get_multiplier(cls.COMPANY_TAX_MULTIPLIER, 1.0)

    @classmethod
    def get_all_multipliers(cls):
        """Get all multipliers as a dictionary."""
        return {
            'xp': cls.get_xp_multiplier(),
            'gold_drop': cls.get_gold_drop_multiplier(),
            'production_speed': cls.get_production_speed_multiplier(),
            'work_xp': cls.get_work_xp_multiplier(),
            'training_xp': cls.get_training_xp_multiplier(),
            'battle_xp': cls.get_battle_xp_multiplier(),
            'travel_cost': cls.get_travel_cost_multiplier(),
            'company_tax': cls.get_company_tax_multiplier(),
        }
