# app/models/game_update.py
"""
Game Update/Changelog model for tracking game updates, patches, and announcements.
"""

from datetime import datetime
from enum import Enum
from app.extensions import db


class UpdateCategory(Enum):
    """Categories for game updates."""
    FEATURE = 'feature'           # New features
    BALANCE = 'balance'           # Balance changes
    BUGFIX = 'bugfix'             # Bug fixes
    CONTENT = 'content'           # New content (resources, items, etc.)
    UI = 'ui'                     # UI/UX improvements
    PERFORMANCE = 'performance'   # Performance improvements
    SECURITY = 'security'         # Security updates
    EVENT = 'event'               # In-game events
    ANNOUNCEMENT = 'announcement' # General announcements
    MAINTENANCE = 'maintenance'   # Maintenance notices


class GameUpdate(db.Model):
    """Model for game updates and changelog entries."""
    __tablename__ = 'game_update'

    id = db.Column(db.Integer, primary_key=True)

    # Update content
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)  # Supports markdown/HTML
    summary = db.Column(db.String(500), nullable=True)  # Short summary for preview

    # Categorization
    category = db.Column(db.Enum(UpdateCategory), nullable=False, default=UpdateCategory.FEATURE)
    version = db.Column(db.String(20), nullable=True)  # e.g., "1.2.0", "v2.1"

    # Author
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    author = db.relationship('User', backref=db.backref('game_updates', lazy='dynamic'))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = db.Column(db.DateTime, nullable=True)  # When it was published

    # Status
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    is_pinned = db.Column(db.Boolean, default=False, nullable=False)  # Pin to top
    is_important = db.Column(db.Boolean, default=False, nullable=False)  # Highlight as important

    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<GameUpdate {self.id}: {self.title}>'

    def publish(self):
        """Publish the update."""
        self.is_published = True
        self.published_at = datetime.utcnow()

    def unpublish(self):
        """Unpublish the update."""
        self.is_published = False
        self.published_at = None

    def soft_delete(self):
        """Soft delete the update."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()

    def restore(self):
        """Restore a soft-deleted update."""
        self.is_deleted = False
        self.deleted_at = None

    @property
    def category_icon(self):
        """Return FontAwesome icon class for the category."""
        icons = {
            UpdateCategory.FEATURE: 'fa-star',
            UpdateCategory.BALANCE: 'fa-balance-scale',
            UpdateCategory.BUGFIX: 'fa-bug',
            UpdateCategory.CONTENT: 'fa-box',
            UpdateCategory.UI: 'fa-paint-brush',
            UpdateCategory.PERFORMANCE: 'fa-tachometer-alt',
            UpdateCategory.SECURITY: 'fa-shield-alt',
            UpdateCategory.EVENT: 'fa-calendar-alt',
            UpdateCategory.ANNOUNCEMENT: 'fa-bullhorn',
            UpdateCategory.MAINTENANCE: 'fa-wrench',
        }
        return icons.get(self.category, 'fa-info-circle')

    @property
    def category_color(self):
        """Return color class for the category."""
        colors = {
            UpdateCategory.FEATURE: '#22c55e',      # Green
            UpdateCategory.BALANCE: '#f59e0b',      # Amber
            UpdateCategory.BUGFIX: '#ef4444',       # Red
            UpdateCategory.CONTENT: '#8b5cf6',      # Purple
            UpdateCategory.UI: '#3b82f6',           # Blue
            UpdateCategory.PERFORMANCE: '#06b6d4',  # Cyan
            UpdateCategory.SECURITY: '#f97316',     # Orange
            UpdateCategory.EVENT: '#ec4899',        # Pink
            UpdateCategory.ANNOUNCEMENT: '#6366f1', # Indigo
            UpdateCategory.MAINTENANCE: '#64748b',  # Slate
        }
        return colors.get(self.category, '#6b7280')

    @property
    def category_label(self):
        """Return human-readable label for the category."""
        labels = {
            UpdateCategory.FEATURE: 'New Feature',
            UpdateCategory.BALANCE: 'Balance Change',
            UpdateCategory.BUGFIX: 'Bug Fix',
            UpdateCategory.CONTENT: 'New Content',
            UpdateCategory.UI: 'UI/UX',
            UpdateCategory.PERFORMANCE: 'Performance',
            UpdateCategory.SECURITY: 'Security',
            UpdateCategory.EVENT: 'Event',
            UpdateCategory.ANNOUNCEMENT: 'Announcement',
            UpdateCategory.MAINTENANCE: 'Maintenance',
        }
        return labels.get(self.category, 'Update')

    @classmethod
    def get_published(cls, limit=None):
        """Get all published, non-deleted updates ordered by pinned first, then date."""
        query = cls.query.filter_by(
            is_published=True,
            is_deleted=False
        ).order_by(
            cls.is_pinned.desc(),
            cls.published_at.desc()
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    @classmethod
    def get_recent(cls, limit=5):
        """Get recent published updates for widgets/notifications."""
        return cls.query.filter_by(
            is_published=True,
            is_deleted=False
        ).order_by(
            cls.published_at.desc()
        ).limit(limit).all()
