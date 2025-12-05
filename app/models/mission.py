"""
Mission system models.

Tracks daily missions, weekly challenges, and tutorial quests.
Players can complete missions for gold, XP, and item rewards.
"""

import enum
from datetime import datetime
from decimal import Decimal
from app.extensions import db


class MissionType(str, enum.Enum):
    """Types of missions available."""
    DAILY = 'daily'
    WEEKLY = 'weekly'
    TUTORIAL = 'tutorial'
    SPECIAL = 'special'


class MissionCategory(str, enum.Enum):
    """Categories of missions."""
    COMBAT = 'combat'
    WORK = 'work'
    TRAINING = 'training'
    STUDY = 'study'
    SOCIAL = 'social'
    ECONOMIC = 'economic'
    EXPLORATION = 'exploration'


class Mission(db.Model):
    """
    Defines a mission that users can complete.

    Missions are tasks with specific requirements and rewards.
    Daily/weekly missions are randomly assigned from a pool.
    Tutorial missions follow a specific sequence.
    """
    __tablename__ = 'mission'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    mission_type = db.Column(db.String(20), nullable=False, index=True)
    category = db.Column(db.String(20), nullable=False)
    icon = db.Column(db.String(50), default='fa-tasks')

    # Requirements
    action_type = db.Column(db.String(50), nullable=False)  # 'fight', 'work', 'train', 'study', etc.
    requirement_count = db.Column(db.Integer, default=1, nullable=False)

    # Rewards
    gold_reward = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    xp_reward = db.Column(db.Integer, default=0, nullable=False)
    resource_reward_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=True)
    resource_reward_quantity = db.Column(db.Integer, default=0, nullable=False)
    resource_reward_quality = db.Column(db.Integer, default=1, nullable=False)

    # Tutorial ordering
    tutorial_order = db.Column(db.Integer, nullable=True)
    prerequisite_mission_id = db.Column(db.Integer, db.ForeignKey('mission.id'), nullable=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    resource_reward = db.relationship('Resource', foreign_keys=[resource_reward_id])
    prerequisite_mission = db.relationship('Mission', remote_side=[id], foreign_keys=[prerequisite_mission_id])
    user_missions = db.relationship('UserMission', back_populates='mission', lazy='dynamic')

    def __repr__(self):
        return f'<Mission {self.code}: {self.name}>'

    @property
    def mission_type_enum(self):
        """Return MissionType enum value."""
        return MissionType(self.mission_type)

    @property
    def category_enum(self):
        """Return MissionCategory enum value."""
        return MissionCategory(self.category)


class UserMission(db.Model):
    """
    Tracks a user's progress on an assigned mission.

    Daily and weekly missions expire on reset if not claimed.
    Tutorial missions persist until completed.
    """
    __tablename__ = 'user_mission'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    mission_id = db.Column(db.Integer, db.ForeignKey('mission.id'), nullable=False, index=True)

    # Progress tracking
    current_progress = db.Column(db.Integer, default=0, nullable=False)
    is_completed = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_claimed = db.Column(db.Boolean, default=False, nullable=False)

    # Timestamps
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    claimed_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True, index=True)

    # Relationships
    user = db.relationship('User', backref='user_missions')
    mission = db.relationship('Mission', back_populates='user_missions')

    __table_args__ = (
        db.Index('idx_user_mission_lookup', 'user_id', 'mission_id'),
        db.Index('idx_user_active_missions', 'user_id', 'is_completed', 'is_claimed'),
    )

    def __repr__(self):
        return f'<UserMission user={self.user_id} mission={self.mission_id} progress={self.current_progress}/{self.mission.requirement_count if self.mission else "?"}>'

    @property
    def progress_percent(self):
        """Calculate completion percentage."""
        if not self.mission or self.mission.requirement_count == 0:
            return 0
        return min(100, int((self.current_progress / self.mission.requirement_count) * 100))

    @property
    def is_expired(self):
        """Check if mission has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def add_progress(self, amount=1):
        """
        Add progress to mission.
        Returns True if mission was completed by this progress.
        """
        if self.is_completed or self.is_claimed:
            return False

        if self.is_expired:
            return False

        self.current_progress += amount

        if self.current_progress >= self.mission.requirement_count:
            self.current_progress = self.mission.requirement_count
            self.is_completed = True
            self.completed_at = datetime.utcnow()
            return True

        return False
