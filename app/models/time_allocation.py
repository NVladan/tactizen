# app/models/time_allocation.py

from datetime import datetime, date
from . import db


class TimeAllocation(db.Model):
    """Tracks daily time allocation for users across different activities."""
    __tablename__ = 'time_allocation'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    allocation_date = db.Column(db.Date, nullable=False, index=True)

    # Hours allocated for each activity (0-12 for training/work, 0-24 total)
    hours_training = db.Column(db.Integer, default=0, nullable=False)
    hours_studying = db.Column(db.Integer, default=0, nullable=False)
    hours_working = db.Column(db.Integer, default=0, nullable=False)

    # Track which skills were trained/studied
    training_skill = db.Column(db.String(50), nullable=True)  # infantry, armoured, aviation
    studying_skill = db.Column(db.String(50), nullable=True)  # resource_extraction, manufacture, construction

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = db.relationship('User', backref='time_allocations')

    # Unique constraint - one record per user per day
    __table_args__ = (
        db.UniqueConstraint('user_id', 'allocation_date', name='unique_user_daily_allocation'),
        db.CheckConstraint('hours_training >= 0 AND hours_training <= 12', name='check_training_hours'),
        db.CheckConstraint('hours_studying >= 0 AND hours_studying <= 12', name='check_studying_hours'),
        db.CheckConstraint('hours_working >= 0 AND hours_working <= 12', name='check_working_hours'),
        db.CheckConstraint('hours_training + hours_studying + hours_working <= 24', name='check_total_hours'),
    )

    @property
    def total_hours_allocated(self):
        """Total hours allocated across all activities."""
        return self.hours_training + self.hours_studying + self.hours_working

    @property
    def remaining_hours(self):
        """Remaining hours available for allocation."""
        return 24 - self.total_hours_allocated

    def __repr__(self):
        return f'<TimeAllocation User:{self.user_id} Date:{self.allocation_date} T:{self.hours_training} S:{self.hours_studying} W:{self.hours_working}>'


class WorkSession(db.Model):
    """Tracks individual work sessions when users work at companies."""
    __tablename__ = 'work_session'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False, index=True)
    employment_id = db.Column(db.Integer, db.ForeignKey('employment.id'), nullable=True, index=True)  # Nullable to preserve work history after employment ends

    # Work details
    hours_worked = db.Column(db.Integer, nullable=False)
    skill_level = db.Column(db.Float, nullable=False)  # Skill level at time of work
    production_points = db.Column(db.Float, nullable=False)  # Hours * skill_level

    # Payment details
    wage_per_pp = db.Column(db.Numeric(10, 4), nullable=False)  # Wage per production point
    total_payment = db.Column(db.Numeric(20, 8), nullable=False)  # Total payment received

    # Energy/Wellness costs
    energy_spent = db.Column(db.Integer, nullable=False)
    wellness_spent = db.Column(db.Integer, nullable=False)

    # Timestamp
    worked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    work_date = db.Column(db.Date, nullable=False, index=True)  # For daily tracking

    # Relationships
    user = db.relationship('User', backref='work_sessions')
    company = db.relationship('Company', backref='work_sessions')
    employment = db.relationship('Employment', backref='work_sessions')

    def __repr__(self):
        return f'<WorkSession User:{self.user_id} Company:{self.company_id} Hours:{self.hours_worked} PP:{self.production_points}>'
