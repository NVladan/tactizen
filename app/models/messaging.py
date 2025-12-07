# app/models/messaging.py

import enum
from datetime import datetime
from app.extensions import db

# --- Enums ---

class AlertType(str, enum.Enum):
    LEVEL_UP = 'level_up'
    HOUSE_EXPIRED = 'house_expired'
    ELECTION_WIN = 'election_win'
    ADMIN_ANNOUNCEMENT = 'admin_announcement'
    EMPLOYMENT = 'employment'
    FRIEND_REQUEST = 'friend_request'
    FRIEND_REQUEST_ACCEPTED = 'friend_request_accepted'
    WAR_DECLARED = 'war_declared'
    SUPPORT_TICKET = 'support_ticket'
    BOUNTY_COMPLETED = 'bounty_completed'
    ITEMS_RECEIVED = 'items_received'
    MISSION_COMPLETE = 'mission_complete'


class AlertPriority(str, enum.Enum):
    LOW = 'low'
    NORMAL = 'normal'
    MEDIUM = 'medium'
    IMPORTANT = 'important'
    URGENT = 'urgent'


# --- Models ---

class Message(db.Model):
    """User-to-user private messages with threading support."""
    __tablename__ = 'message'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    subject = db.Column(db.String(200), nullable=True)
    content = db.Column(db.Text, nullable=False)
    parent_message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=True)

    # Read status
    is_read = db.Column(db.Boolean, default=False, nullable=False)

    # Soft delete (per user)
    sender_deleted = db.Column(db.Boolean, default=False, nullable=False)
    recipient_deleted = db.Column(db.Boolean, default=False, nullable=False)

    # Admin removal (hides from both users, shows "[Message removed by moderator]")
    admin_removed = db.Column(db.Boolean, default=False, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')
    parent = db.relationship('Message', remote_side=[id], backref='replies')

    def __repr__(self):
        return f'<Message {self.id} from {self.sender_id} to {self.recipient_id}>'

    @property
    def is_reply(self):
        """Check if this message is a reply to another message."""
        return self.parent_message_id is not None

    def get_thread_messages(self):
        """Get all messages in this thread in chronological order."""
        # Find root message
        root = self
        while root.parent_message_id:
            root = Message.query.get(root.parent_message_id)

        # Get all messages in thread
        thread_messages = [root]

        def add_replies(msg):
            for reply in msg.replies:
                thread_messages.append(reply)
                add_replies(reply)

        add_replies(root)
        return sorted(thread_messages, key=lambda x: x.created_at)


class Alert(db.Model):
    """System notifications and alerts for users."""
    __tablename__ = 'alert'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    alert_type = db.Column(db.String(50), nullable=False, index=True)
    priority = db.Column(db.String(20), default='normal', nullable=False)

    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)

    # JSON field for additional data (gold_earned, new_level, party_name, vote_count, etc.)
    alert_data = db.Column(db.JSON, nullable=True)

    # Optional link/action button
    link_url = db.Column(db.String(200), nullable=True)
    link_text = db.Column(db.String(100), nullable=True)

    # Read status
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = db.relationship('User', backref='alerts')

    def __repr__(self):
        return f'<Alert {self.id} {self.alert_type.value} for user {self.user_id}>'

    @property
    def priority_color(self):
        """Get Bootstrap color class based on priority."""
        colors = {
            AlertPriority.NORMAL: 'info',
            AlertPriority.IMPORTANT: 'warning',
            AlertPriority.URGENT: 'danger'
        }
        return colors.get(self.priority, 'info')

    @property
    def icon(self):
        """Get icon based on alert type."""
        icons = {
            AlertType.LEVEL_UP: 'fa-level-up-alt',
            AlertType.HOUSE_EXPIRED: 'fa-home',
            AlertType.ELECTION_WIN: 'fa-trophy',
            AlertType.ADMIN_ANNOUNCEMENT: 'fa-bullhorn',
            AlertType.BOUNTY_COMPLETED: 'fa-coins',
            AlertType.ITEMS_RECEIVED: 'fa-gift'
        }
        return icons.get(self.alert_type, 'fa-bell')


class BlockedUser(db.Model):
    """Track blocked users to prevent unwanted messages."""
    __tablename__ = 'blocked_user'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blocked_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='blocked_users')
    blocked_user = db.relationship('User', foreign_keys=[blocked_user_id])

    # Unique constraint - can't block same user twice
    __table_args__ = (
        db.UniqueConstraint('user_id', 'blocked_user_id', name='unique_block'),
    )

    def __repr__(self):
        return f'<BlockedUser {self.user_id} blocked {self.blocked_user_id}>'
