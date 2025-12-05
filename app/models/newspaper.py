# app/models/newspaper.py
"""
Newspaper and article models for the player journalism system.

Players can create newspapers (costs 5 Gold), write articles,
and interact through votes, subscriptions, and comments.
"""

from datetime import datetime, timedelta
from app.extensions import db
from app.mixins import SoftDeleteMixin


class Newspaper(SoftDeleteMixin, db.Model):
    """
    Represents a player-owned newspaper.

    Each player can own one newspaper tied to their citizenship country.
    Costs 5 Gold to create.
    """
    __tablename__ = 'newspaper'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)

    # Avatar flag (similar to User model - actual file stored separately)
    avatar = db.Column(db.Boolean, default=False, nullable=False)

    # Foreign keys
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    owner = db.relationship('User', backref=db.backref('newspaper', uselist=False))
    country = db.relationship('Country', backref='newspapers')
    articles = db.relationship('Article', back_populates='newspaper', lazy='dynamic', cascade="all, delete-orphan")
    subscriptions = db.relationship('NewspaperSubscription', back_populates='newspaper', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Newspaper {self.name}>'

    @property
    def subscriber_count(self):
        """Get total number of subscribers."""
        return self.subscriptions.count()

    @property
    def article_count(self):
        """Get total number of published articles (excluding soft-deleted)."""
        return self.articles.filter_by(is_deleted=False).count()


class Article(SoftDeleteMixin, db.Model):
    """
    Represents an article published in a newspaper.

    Articles are visible in feeds for 24 hours after publication,
    but can always be accessed via direct link until soft-deleted.
    """
    __tablename__ = 'article'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)  # HTML content similar to Sajborg.com Post

    # Foreign keys
    newspaper_id = db.Column(db.Integer, db.ForeignKey('newspaper.id'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    newspaper = db.relationship('Newspaper', back_populates='articles')
    author = db.relationship('User', backref='articles')
    votes = db.relationship('ArticleVote', back_populates='article', lazy='dynamic', cascade="all, delete-orphan")
    comments = db.relationship('ArticleComment', back_populates='article', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Article {self.title}>'

    @property
    def vote_count(self):
        """Get total number of votes (upvotes only)."""
        return self.votes.count()

    @property
    def comment_count(self):
        """Get total number of comments (excluding soft-deleted)."""
        return self.comments.filter_by(is_deleted=False).count()

    @property
    def is_in_feed(self):
        """Check if article is still visible in feeds (within 24 hours of creation)."""
        if self.is_deleted:
            return False
        return datetime.utcnow() - self.created_at < timedelta(hours=24)

    def has_user_voted(self, user_id):
        """Check if a specific user has voted on this article."""
        return self.votes.filter_by(user_id=user_id).first() is not None


class ArticleVote(db.Model):
    """
    Represents an upvote on an article.

    Each user can vote once per article (upvote only, no downvotes).
    """
    __tablename__ = 'article_vote'

    id = db.Column(db.Integer, primary_key=True)

    # Foreign keys
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    article = db.relationship('Article', back_populates='votes')
    user = db.relationship('User', backref='article_votes')

    # Ensure one vote per user per article
    __table_args__ = (
        db.UniqueConstraint('article_id', 'user_id', name='unique_article_vote'),
    )

    def __repr__(self):
        return f'<ArticleVote user={self.user_id} article={self.article_id}>'


class NewspaperSubscription(db.Model):
    """
    Represents a user's subscription to a newspaper.

    Subscriptions allow users to see newspaper articles in a dedicated feed.
    """
    __tablename__ = 'newspaper_subscription'

    id = db.Column(db.Integer, primary_key=True)

    # Foreign keys
    newspaper_id = db.Column(db.Integer, db.ForeignKey('newspaper.id'), nullable=False, index=True)
    subscriber_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    newspaper = db.relationship('Newspaper', back_populates='subscriptions')
    subscriber = db.relationship('User', backref='newspaper_subscriptions')

    # Ensure one subscription per user per newspaper
    __table_args__ = (
        db.UniqueConstraint('newspaper_id', 'subscriber_id', name='unique_newspaper_subscription'),
    )

    def __repr__(self):
        return f'<NewspaperSubscription user={self.subscriber_id} newspaper={self.newspaper_id}>'


class ArticleComment(SoftDeleteMixin, db.Model):
    """
    Represents a comment on an article.

    Supports nested comments up to 3 levels deep.
    Comments are cascade-deleted if the parent article is deleted.
    """
    __tablename__ = 'article_comment'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)

    # Foreign keys
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    parent_comment_id = db.Column(db.Integer, db.ForeignKey('article_comment.id'), nullable=True, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    article = db.relationship('Article', back_populates='comments')
    user = db.relationship('User', backref='article_comments')
    parent = db.relationship('ArticleComment', remote_side=[id], backref='replies')

    def __repr__(self):
        return f'<ArticleComment {self.id} by user={self.user_id}>'

    @property
    def nesting_level(self):
        """Calculate the nesting level of this comment (0 = top-level, 1 = reply, etc.)."""
        level = 0
        parent = self.parent
        while parent:
            level += 1
            parent = parent.parent
        return level

    @property
    def can_reply(self):
        """Check if this comment can receive replies (max 3 levels deep)."""
        return self.nesting_level < 2  # 0, 1, 2 are allowed; level 3 cannot have replies
