# app/models/game_event.py
"""
Game Event model for timed events (Double XP weekends, gold rush, etc.)
"""

from datetime import datetime
from enum import Enum
from app.extensions import db


class EventType(str, Enum):
    """Types of game events."""
    DOUBLE_XP = 'double_xp'
    GOLD_RUSH = 'gold_rush'
    PRODUCTION_BOOST = 'production_boost'
    BATTLE_BONUS = 'battle_bonus'
    TRAINING_BOOST = 'training_boost'
    WORK_BONUS = 'work_bonus'
    REDUCED_TRAVEL = 'reduced_travel'
    TAX_HOLIDAY = 'tax_holiday'
    CUSTOM = 'custom'


class GameEvent(db.Model):
    """
    Represents a timed game event that applies multipliers.
    Events can be scheduled in advance and will automatically activate/deactivate.
    """
    __tablename__ = 'game_events'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)

    # Multiplier to apply (e.g., 2.0 for double, 1.5 for 50% boost)
    multiplier = db.Column(db.Float, default=2.0, nullable=False)

    # Which setting key this event affects (from GameSettings constants)
    affects_setting = db.Column(db.String(100), nullable=True)

    # Schedule
    start_time = db.Column(db.DateTime, nullable=False, index=True)
    end_time = db.Column(db.DateTime, nullable=False, index=True)

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_announced = db.Column(db.Boolean, default=False, nullable=False)  # Show in announcements

    # Styling
    banner_color = db.Column(db.String(7), default='#f59e0b', nullable=False)  # Hex color
    icon = db.Column(db.String(50), default='fa-star', nullable=False)  # FontAwesome icon

    # Admin tracking
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    created_by = db.relationship('User', foreign_keys=[created_by_id])

    # Event type configurations (default settings)
    EVENT_CONFIGS = {
        EventType.DOUBLE_XP.value: {
            'affects': 'xp_multiplier',
            'default_multiplier': 2.0,
            'icon': 'fa-bolt',
            'color': '#8b5cf6',
            'description': 'All XP gains are doubled!'
        },
        EventType.GOLD_RUSH.value: {
            'affects': 'gold_drop_multiplier',
            'default_multiplier': 2.0,
            'icon': 'fa-coins',
            'color': '#f59e0b',
            'description': 'Gold rewards are doubled!'
        },
        EventType.PRODUCTION_BOOST.value: {
            'affects': 'production_speed_multiplier',
            'default_multiplier': 1.5,
            'icon': 'fa-industry',
            'color': '#10b981',
            'description': 'Production speed increased by 50%!'
        },
        EventType.BATTLE_BONUS.value: {
            'affects': 'battle_xp_multiplier',
            'default_multiplier': 2.0,
            'icon': 'fa-shield-alt',
            'color': '#ef4444',
            'description': 'Battle XP and rewards are doubled!'
        },
        EventType.TRAINING_BOOST.value: {
            'affects': 'training_xp_multiplier',
            'default_multiplier': 2.0,
            'icon': 'fa-dumbbell',
            'color': '#3b82f6',
            'description': 'Training XP is doubled!'
        },
        EventType.WORK_BONUS.value: {
            'affects': 'work_xp_multiplier',
            'default_multiplier': 2.0,
            'icon': 'fa-briefcase',
            'color': '#22c55e',
            'description': 'Work XP and salary bonuses!'
        },
        EventType.REDUCED_TRAVEL.value: {
            'affects': 'travel_cost_multiplier',
            'default_multiplier': 0.5,
            'icon': 'fa-plane',
            'color': '#06b6d4',
            'description': 'Travel costs reduced by 50%!'
        },
        EventType.TAX_HOLIDAY.value: {
            'affects': 'company_tax_multiplier',
            'default_multiplier': 0.5,
            'icon': 'fa-percentage',
            'color': '#ec4899',
            'description': 'Company taxes reduced by 50%!'
        },
        EventType.CUSTOM.value: {
            'affects': None,
            'default_multiplier': 1.5,
            'icon': 'fa-star',
            'color': '#6366f1',
            'description': 'Special event!'
        },
    }

    def __repr__(self):
        return f'<GameEvent {self.name} ({self.event_type})>'

    @property
    def is_running(self):
        """Check if the event is currently running."""
        now = datetime.utcnow()
        return self.is_active and self.start_time <= now <= self.end_time

    @property
    def is_upcoming(self):
        """Check if the event is scheduled for the future."""
        return self.is_active and datetime.utcnow() < self.start_time

    @property
    def is_ended(self):
        """Check if the event has ended."""
        return datetime.utcnow() > self.end_time

    @property
    def time_remaining(self):
        """Get time remaining for active event."""
        if not self.is_running:
            return None
        return self.end_time - datetime.utcnow()

    @property
    def time_until_start(self):
        """Get time until event starts."""
        if not self.is_upcoming:
            return None
        return self.start_time - datetime.utcnow()

    @property
    def duration_hours(self):
        """Get event duration in hours."""
        delta = self.end_time - self.start_time
        return delta.total_seconds() / 3600

    @classmethod
    def get_active_events(cls):
        """Get all currently running events."""
        now = datetime.utcnow()
        return cls.query.filter(
            cls.is_active == True,
            cls.start_time <= now,
            cls.end_time >= now
        ).all()

    @classmethod
    def get_upcoming_events(cls, limit=5):
        """Get upcoming scheduled events."""
        now = datetime.utcnow()
        return cls.query.filter(
            cls.is_active == True,
            cls.start_time > now
        ).order_by(cls.start_time).limit(limit).all()

    @classmethod
    def get_event_multiplier(cls, setting_key):
        """
        Get the combined multiplier for a setting from all active events.
        Multipliers stack multiplicatively.
        """
        active_events = cls.get_active_events()
        combined_multiplier = 1.0

        for event in active_events:
            if event.affects_setting == setting_key:
                combined_multiplier *= event.multiplier

        return combined_multiplier

    @classmethod
    def get_effective_multiplier(cls, setting_key, base_value=1.0):
        """
        Get the effective multiplier combining base GameSettings value and active events.
        """
        from app.models.game_settings import GameSettings

        # Get base multiplier from GameSettings
        base_multiplier = GameSettings.get_multiplier(setting_key, base_value)

        # Get event multiplier
        event_multiplier = cls.get_event_multiplier(setting_key)

        return base_multiplier * event_multiplier

    @classmethod
    def create_event(cls, event_type, name, start_time, end_time, multiplier=None,
                     description=None, created_by_id=None):
        """
        Create a new event with sensible defaults based on event type.
        """
        config = cls.EVENT_CONFIGS.get(event_type, cls.EVENT_CONFIGS[EventType.CUSTOM.value])

        event = cls(
            name=name,
            event_type=event_type,
            affects_setting=config['affects'],
            multiplier=multiplier or config['default_multiplier'],
            description=description or config['description'],
            icon=config['icon'],
            banner_color=config['color'],
            start_time=start_time,
            end_time=end_time,
            created_by_id=created_by_id
        )

        db.session.add(event)
        return event
