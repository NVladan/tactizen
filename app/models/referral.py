# app/models/referral.py
# Referral system for user sign-ups

from datetime import datetime, timezone
from enum import Enum as PyEnum
from app.extensions import db


class ReferralStatus(PyEnum):
    """Enum for referral status."""
    PENDING = "pending"        # Referee hasn't reached level 10 yet
    COMPLETED = "completed"    # Referee reached level 10, gold awarded
    CANCELLED = "cancelled"    # Referral cancelled (e.g., referee banned)


class Referral(db.Model):
    """
    Tracks referral relationships between users.

    When a user (referrer) shares their referral link and another user (referee)
    registers using that link, a Referral record is created. When the referee
    reaches level 10, the referrer receives 10 gold and the referral is marked as completed.
    """
    __tablename__ = 'referral'

    id = db.Column(db.Integer, primary_key=True)

    # Referrer: user who shared the link
    referrer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Referee: user who signed up using the link
    referee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Status of the referral
    status = db.Column(db.Enum(ReferralStatus), default=ReferralStatus.PENDING, nullable=False, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)  # When referee reached level 10

    # Gold awarded (should be 5)
    gold_awarded = db.Column(db.Numeric(10, 2), default=0, nullable=False)

    # Relationships
    referrer = db.relationship('User', foreign_keys=[referrer_id], back_populates='referrals_made')
    referee = db.relationship('User', foreign_keys=[referee_id], back_populates='referred_by_relation')

    # Indexes for common queries
    __table_args__ = (
        db.Index('idx_referral_referrer_status', 'referrer_id', 'status'),
        db.Index('idx_referral_referee', 'referee_id'),
    )

    def complete_referral(self, gold_amount=10.0):
        """
        Mark referral as completed and record gold awarded.

        Args:
            gold_amount: Amount of gold to award (default 10.0)
        """
        from decimal import Decimal

        if self.status != ReferralStatus.PENDING:
            return False

        self.status = ReferralStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.gold_awarded = Decimal(str(gold_amount))

        return True

    def cancel_referral(self):
        """Cancel the referral (e.g., if referee is banned)."""
        if self.status == ReferralStatus.COMPLETED:
            return False  # Don't cancel completed referrals

        self.status = ReferralStatus.CANCELLED
        return True

    @property
    def is_pending(self):
        """Check if referral is still pending."""
        return self.status == ReferralStatus.PENDING

    @property
    def is_completed(self):
        """Check if referral is completed."""
        return self.status == ReferralStatus.COMPLETED

    def __repr__(self):
        return f'<Referral {self.id} Referrer:{self.referrer_id} Referee:{self.referee_id} Status:{self.status.value}>'
