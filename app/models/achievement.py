"""
Achievement system models.

Tracks user achievements and awards gold rewards.
"""

import enum
from datetime import datetime
from decimal import Decimal
from app.extensions import db


class AchievementCategory(str, enum.Enum):
    """Categories of achievements."""
    WORK = 'work'
    TRAINING = 'training'
    STUDY = 'study'
    COMBAT = 'combat'
    SOCIAL = 'social'
    EXPLORATION = 'exploration'
    ECONOMIC = 'economic'
    POLITICAL = 'political'
    MEDIA = 'media'


class Achievement(db.Model):
    """
    Defines an achievement that users can unlock.

    Achievements are predefined milestones that reward players
    with gold and recognition.
    """
    __tablename__ = 'achievement'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(20), nullable=False, index=True)

    icon = db.Column(db.String(50), default='fa-trophy')
    gold_reward = db.Column(db.Integer, default=5, nullable=False)
    free_nft_reward = db.Column(db.Integer, default=0, nullable=False)  # Free NFT mints awarded

    requirement_value = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user_achievements = db.relationship('UserAchievement', back_populates='achievement', lazy='dynamic')

    def __repr__(self):
        return f'<Achievement {self.code}: {self.name}>'


class UserAchievement(db.Model):
    """
    Tracks which achievements a user has unlocked.

    Once unlocked, the achievement is permanent and the gold reward
    is awarded immediately.
    """
    __tablename__ = 'user_achievement'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievement.id'), nullable=False, index=True)

    unlocked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    gold_awarded = db.Column(db.Integer, nullable=False)

    user = db.relationship('User', backref='achievements_earned')
    achievement = db.relationship('Achievement', back_populates='user_achievements')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'achievement_id', name='unique_user_achievement'),
        db.Index('idx_user_achievements', 'user_id'),
    )

    def __repr__(self):
        return f'<UserAchievement user={self.user_id} achievement={self.achievement_id}>'


class AchievementProgress(db.Model):
    """
    Tracks user's progress toward achievements.

    This table stores counters and streaks for achievements that
    require累积 progress (like "work 30 days in a row").
    """
    __tablename__ = 'achievement_progress'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    achievement_code = db.Column(db.String(50), nullable=False, index=True)

    current_value = db.Column(db.Integer, default=0, nullable=False)
    current_streak = db.Column(db.Integer, default=0, nullable=False)
    best_streak = db.Column(db.Integer, default=0, nullable=False)

    last_activity_date = db.Column(db.Date, nullable=True)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref='achievement_progress')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'achievement_code', name='unique_user_progress'),
        db.Index('idx_user_progress', 'user_id', 'achievement_code'),
    )

    def __repr__(self):
        return f'<AchievementProgress user={self.user_id} code={self.achievement_code} value={self.current_value}>'
