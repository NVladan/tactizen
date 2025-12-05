# app/models/friendship.py

from datetime import datetime
from sqlalchemy import Index
from . import db

class FriendshipStatus:
    """Friendship status enum."""
    PENDING = 'pending'
    ACCEPTED = 'accepted'

class Friendship(db.Model):
    """
    Represents a friendship between two users.

    The friendship is directional for request tracking:
    - requester_id: User who sent the friend request
    - receiver_id: User who received the friend request
    - status: 'pending' or 'accepted'

    When accepted, the friendship is bidirectional (both users are friends).
    """
    __tablename__ = 'friendship'

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default=FriendshipStatus.PENDING, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    accepted_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    requester = db.relationship('User', foreign_keys=[requester_id], backref='friendship_requests_sent')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='friendship_requests_received')

    # Table constraints
    __table_args__ = (
        # Prevent duplicate friendships (both directions)
        Index('idx_friendship_unique', 'requester_id', 'receiver_id', unique=True),
        # Index for finding all friendships for a user
        Index('idx_friendship_users', 'requester_id', 'receiver_id'),
    )

    def accept(self):
        """Accept a pending friend request."""
        if self.status == FriendshipStatus.PENDING:
            self.status = FriendshipStatus.ACCEPTED
            self.accepted_at = datetime.utcnow()
            return True
        return False

    @property
    def is_pending(self):
        """Check if friendship is pending."""
        return self.status == FriendshipStatus.PENDING

    @property
    def is_accepted(self):
        """Check if friendship is accepted."""
        return self.status == FriendshipStatus.ACCEPTED

    def __repr__(self):
        return f'<Friendship {self.requester_id} -> {self.receiver_id} ({self.status})>'
