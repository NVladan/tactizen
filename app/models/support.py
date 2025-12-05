"""
Support System Models - Tickets and Reports
"""
from datetime import datetime
from enum import Enum
from app.extensions import db


# ==================== ENUMS ====================

class TicketCategory(Enum):
    """Categories for support tickets."""
    BUG_REPORT = "bug_report"
    SUGGESTION = "suggestion"
    ACCOUNT_ISSUE = "account_issue"
    PAYMENT_ISSUE = "payment_issue"
    REPORT_USER = "report_user"
    OTHER = "other"


class TicketStatus(Enum):
    """Status flow for tickets."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    AWAITING_RESPONSE = "awaiting_response"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ARCHIVED = "archived"


class TicketPriority(Enum):
    """Priority levels for tickets (admin-set only)."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReportType(Enum):
    """Types of content that can be reported."""
    MESSAGE = "message"
    NEWSPAPER_ARTICLE = "newspaper_article"
    ARTICLE_COMMENT = "article_comment"
    USER_PROFILE = "user_profile"
    COMPANY = "company"


class ReportReason(Enum):
    """Reasons for reporting content."""
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    HARASSMENT = "harassment"
    SPAM = "spam"
    CHEATING = "cheating"
    INAPPROPRIATE_NAME_AVATAR = "inappropriate_name_avatar"
    OTHER = "other"


class ReportStatus(Enum):
    """Status for reports."""
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ReportAction(Enum):
    """Actions that can be taken on reports."""
    DISMISSED = "dismissed"
    WARNING_ISSUED = "warning_issued"
    CONTENT_REMOVED = "content_removed"
    USER_MUTED = "user_muted"
    TEMPORARY_BAN = "temporary_ban"
    PERMANENT_BAN = "permanent_ban"


class AuditActionType(Enum):
    """Types of actions for audit log."""
    CREATED = "created"
    STATUS_CHANGED = "status_changed"
    PRIORITY_CHANGED = "priority_changed"
    ASSIGNED = "assigned"
    RESPONSE_ADDED = "response_added"
    INTERNAL_NOTE_ADDED = "internal_note_added"
    CLOSED = "closed"
    ARCHIVED = "archived"
    REOPENED = "reopened"
    RATED = "rated"


# ==================== MODELS ====================

class SupportTicket(db.Model):
    """Support ticket submitted by a player."""
    __tablename__ = 'support_ticket'

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False, index=True)

    # Submitter
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('support_tickets', lazy='dynamic'))

    # Ticket details
    category = db.Column(db.Enum(TicketCategory), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)

    # Image attachment (optional, max 1)
    image_filename = db.Column(db.String(255), nullable=True)

    # Status and priority
    status = db.Column(db.Enum(TicketStatus), default=TicketStatus.OPEN, nullable=False, index=True)
    priority = db.Column(db.Enum(TicketPriority), default=TicketPriority.MEDIUM, nullable=False, index=True)

    # Assignment
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id], backref=db.backref('assigned_tickets', lazy='dynamic'))

    # Rating (1-5 stars, after closure)
    rating = db.Column(db.Integer, nullable=True)
    rating_comment = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False)

    # Relationships
    responses = db.relationship('TicketResponse', backref='ticket', lazy='dynamic', order_by='TicketResponse.created_at')
    audit_logs = db.relationship('TicketAuditLog', backref='ticket', lazy='dynamic', order_by='TicketAuditLog.created_at.desc()')

    @staticmethod
    def generate_ticket_number():
        """Generate a unique ticket number like TKT-2025-00001."""
        year = datetime.utcnow().year
        last_ticket = SupportTicket.query.filter(
            SupportTicket.ticket_number.like(f'TKT-{year}-%')
        ).order_by(SupportTicket.id.desc()).first()

        if last_ticket:
            try:
                last_num = int(last_ticket.ticket_number.split('-')[-1])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1

        return f"TKT-{year}-{new_num:05d}"

    def __repr__(self):
        return f'<SupportTicket {self.ticket_number}>'


class TicketResponse(db.Model):
    """Response to a support ticket (from user or staff)."""
    __tablename__ = 'ticket_response'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('support_ticket.id'), nullable=False)

    # Who responded
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('ticket_responses', lazy='dynamic'))

    # Response content
    message = db.Column(db.Text, nullable=False)
    is_staff_response = db.Column(db.Boolean, default=False)
    is_internal_note = db.Column(db.Boolean, default=False)  # Only visible to staff

    # If using canned response
    canned_response_id = db.Column(db.Integer, db.ForeignKey('canned_response.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<TicketResponse {self.id} on Ticket {self.ticket_id}>'


class TicketAuditLog(db.Model):
    """Audit log for tracking all actions on tickets."""
    __tablename__ = 'ticket_audit_log'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('support_ticket.id'), nullable=False)

    # Who performed the action
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('ticket_audit_actions', lazy='dynamic'))

    # Action details
    action_type = db.Column(db.Enum(AuditActionType), nullable=False)
    old_value = db.Column(db.String(100), nullable=True)
    new_value = db.Column(db.String(100), nullable=True)
    details = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<TicketAuditLog {self.id} - {self.action_type.value}>'


class CannedResponse(db.Model):
    """Pre-written responses for common ticket issues."""
    __tablename__ = 'canned_response'

    id = db.Column(db.Integer, primary_key=True)

    # Category this response is for (optional)
    category = db.Column(db.Enum(TicketCategory), nullable=True)

    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)

    # Who created it
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_by = db.relationship('User', backref=db.backref('canned_responses_created', lazy='dynamic'))

    # Usage stats
    times_used = db.Column(db.Integer, default=0)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<CannedResponse {self.id} - {self.title}>'


class Report(db.Model):
    """Report submitted against content or users."""
    __tablename__ = 'report'

    id = db.Column(db.Integer, primary_key=True)
    report_number = db.Column(db.String(20), unique=True, nullable=False, index=True)

    # Who submitted the report
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reporter = db.relationship('User', foreign_keys=[reporter_id], backref=db.backref('reports_submitted', lazy='dynamic'))

    # Who/what is being reported
    reported_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reported_user = db.relationship('User', foreign_keys=[reported_user_id], backref=db.backref('reports_against', lazy='dynamic'))

    # Report type and reason
    report_type = db.Column(db.Enum(ReportType), nullable=False, index=True)
    reason = db.Column(db.Enum(ReportReason), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Reference to reported content (polymorphic)
    reported_message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=True)
    reported_article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=True)
    reported_comment_id = db.Column(db.Integer, db.ForeignKey('article_comment.id'), nullable=True)
    reported_company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)

    # Snapshot of content at time of report (in case it's edited/deleted)
    content_snapshot = db.Column(db.JSON, nullable=True)

    # Status and handling
    status = db.Column(db.Enum(ReportStatus), default=ReportStatus.PENDING, nullable=False, index=True)
    action_taken = db.Column(db.Enum(ReportAction), nullable=True)
    action_details = db.Column(db.Text, nullable=True)

    # For mute action - duration in hours
    mute_duration_hours = db.Column(db.Integer, nullable=True)

    # Who handled it
    handled_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    handled_by = db.relationship('User', foreign_keys=[handled_by_id], backref=db.backref('reports_handled', lazy='dynamic'))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    handled_at = db.Column(db.DateTime, nullable=True)

    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False)

    # Relationships
    reported_message = db.relationship('Message', backref=db.backref('reports', lazy='dynamic'))
    reported_article = db.relationship('Article', backref=db.backref('reports', lazy='dynamic'))
    reported_comment = db.relationship('ArticleComment', backref=db.backref('reports', lazy='dynamic'))
    reported_company = db.relationship('Company', backref=db.backref('reports', lazy='dynamic'))

    @staticmethod
    def generate_report_number():
        """Generate a unique report number like RPT-2025-00001."""
        year = datetime.utcnow().year
        last_report = Report.query.filter(
            Report.report_number.like(f'RPT-{year}-%')
        ).order_by(Report.id.desc()).first()

        if last_report:
            try:
                last_num = int(last_report.report_number.split('-')[-1])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1

        return f"RPT-{year}-{new_num:05d}"

    def create_content_snapshot(self):
        """Create a snapshot of the reported content."""
        snapshot = {
            'captured_at': datetime.utcnow().isoformat(),
            'report_type': self.report_type.value
        }

        if self.report_type == ReportType.MESSAGE and self.reported_message:
            msg = self.reported_message
            snapshot['content'] = msg.content
            snapshot['sender_id'] = msg.sender_id
            snapshot['sender_username'] = msg.sender.username if msg.sender else None
            snapshot['sent_at'] = msg.created_at.isoformat() if msg.created_at else None

        elif self.report_type == ReportType.NEWSPAPER_ARTICLE and self.reported_article:
            article = self.reported_article
            snapshot['title'] = article.title
            snapshot['content'] = article.content
            snapshot['author_id'] = article.author_id
            snapshot['author_username'] = article.author.username if article.author else None
            snapshot['published_at'] = article.created_at.isoformat() if article.created_at else None

        elif self.report_type == ReportType.ARTICLE_COMMENT and self.reported_comment:
            comment = self.reported_comment
            snapshot['content'] = comment.content
            snapshot['author_id'] = comment.user_id
            snapshot['author_username'] = comment.user.username if comment.user else None
            snapshot['posted_at'] = comment.created_at.isoformat() if comment.created_at else None
            snapshot['article_id'] = comment.article_id
            snapshot['article_title'] = comment.article.title if comment.article else None

        elif self.report_type == ReportType.USER_PROFILE and self.reported_user:
            user = self.reported_user
            snapshot['username'] = user.username
            snapshot['avatar'] = user.avatar if hasattr(user, 'avatar') else None
            snapshot['bio'] = user.bio if hasattr(user, 'bio') else None

        elif self.report_type == ReportType.COMPANY and self.reported_company:
            company = self.reported_company
            snapshot['company_name'] = company.name
            snapshot['company_type'] = company.company_type.value if company.company_type else None
            snapshot['owner_id'] = company.owner_id
            snapshot['owner_username'] = company.owner.username if company.owner else None

        self.content_snapshot = snapshot
        return snapshot

    def __repr__(self):
        return f'<Report {self.report_number}>'


class UserMute(db.Model):
    """Track user mutes (can't post articles or messages)."""
    __tablename__ = 'user_mute'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('mutes', lazy='dynamic'))

    # Why they were muted
    report_id = db.Column(db.Integer, db.ForeignKey('report.id'), nullable=True)
    report = db.relationship('Report', backref=db.backref('mute_record', uselist=False))

    reason = db.Column(db.Text, nullable=True)

    # Who muted them
    muted_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    muted_by = db.relationship('User', foreign_keys=[muted_by_id], backref=db.backref('mutes_issued', lazy='dynamic'))

    # Duration
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    # Was it lifted early?
    lifted_at = db.Column(db.DateTime, nullable=True)
    lifted_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    lifted_by = db.relationship('User', foreign_keys=[lifted_by_id])

    is_active = db.Column(db.Boolean, default=True)

    def is_currently_active(self):
        """Check if mute is currently active."""
        if not self.is_active:
            return False
        if self.lifted_at:
            return False
        return datetime.utcnow() < self.expires_at

    def __repr__(self):
        return f'<UserMute {self.id} - User {self.user_id}>'
