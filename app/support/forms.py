"""
Support System Forms - Tickets and Reports
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, IntegerField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, NumberRange

from app.models.support import (
    TicketCategory, TicketStatus, TicketPriority,
    ReportType, ReportReason, ReportAction
)


class CreateTicketForm(FlaskForm):
    """Form for creating a new support ticket."""
    category = SelectField(
        'Category',
        choices=[
            (TicketCategory.BUG_REPORT.value, 'Bug Report'),
            (TicketCategory.SUGGESTION.value, 'Suggestion / Feature Request'),
            (TicketCategory.ACCOUNT_ISSUE.value, 'Account Issue'),
            (TicketCategory.PAYMENT_ISSUE.value, 'Payment / Transaction Issue'),
            (TicketCategory.REPORT_USER.value, 'Report a User'),
            (TicketCategory.OTHER.value, 'Other'),
        ],
        validators=[DataRequired()]
    )
    subject = StringField(
        'Subject',
        validators=[DataRequired(), Length(min=5, max=200)]
    )
    description = TextAreaField(
        'Description',
        validators=[DataRequired(), Length(min=20, max=5000)]
    )
    image = FileField(
        'Attach Image (Optional)',
        validators=[
            FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only (JPG, PNG, GIF)!')
        ]
    )
    submit = SubmitField('Submit Ticket')


class TicketResponseForm(FlaskForm):
    """Form for responding to a ticket."""
    message = TextAreaField(
        'Your Response',
        validators=[DataRequired(), Length(min=5, max=5000)]
    )
    submit = SubmitField('Send Response')


class StaffTicketResponseForm(FlaskForm):
    """Form for staff to respond to a ticket (includes canned responses)."""
    canned_response_id = SelectField(
        'Use Canned Response',
        choices=[('', '-- Select a canned response --')],
        coerce=lambda x: int(x) if x else None,
        validators=[Optional()]
    )
    message = TextAreaField(
        'Response',
        validators=[DataRequired(), Length(min=5, max=5000)]
    )
    is_internal_note = SelectField(
        'Type',
        choices=[
            ('false', 'Public Response (visible to user)'),
            ('true', 'Internal Note (staff only)')
        ],
        default='false'
    )
    submit = SubmitField('Send Response')


class TicketStatusForm(FlaskForm):
    """Form for changing ticket status."""
    status = SelectField(
        'Status',
        choices=[
            (TicketStatus.OPEN.value, 'Open'),
            (TicketStatus.IN_PROGRESS.value, 'In Progress'),
            (TicketStatus.AWAITING_RESPONSE.value, 'Awaiting Response'),
            (TicketStatus.RESOLVED.value, 'Resolved'),
            (TicketStatus.CLOSED.value, 'Closed'),
            (TicketStatus.ARCHIVED.value, 'Archived'),
        ],
        validators=[DataRequired()]
    )
    submit = SubmitField('Update Status')


class TicketPriorityForm(FlaskForm):
    """Form for changing ticket priority (admin only)."""
    priority = SelectField(
        'Priority',
        choices=[
            (TicketPriority.LOW.value, 'Low'),
            (TicketPriority.MEDIUM.value, 'Medium'),
            (TicketPriority.HIGH.value, 'High'),
            (TicketPriority.CRITICAL.value, 'Critical'),
        ],
        validators=[DataRequired()]
    )
    submit = SubmitField('Update Priority')


class AssignTicketForm(FlaskForm):
    """Form for assigning ticket to staff member."""
    assigned_to_id = SelectField(
        'Assign To',
        coerce=lambda x: int(x) if x else None,
        validators=[Optional()]
    )
    submit = SubmitField('Assign')


class TicketRatingForm(FlaskForm):
    """Form for user to rate support after ticket closure."""
    rating = SelectField(
        'Rating',
        choices=[
            ('5', '⭐⭐⭐⭐⭐ Excellent'),
            ('4', '⭐⭐⭐⭐ Good'),
            ('3', '⭐⭐⭐ Average'),
            ('2', '⭐⭐ Poor'),
            ('1', '⭐ Very Poor'),
        ],
        validators=[DataRequired()]
    )
    rating_comment = TextAreaField(
        'Comment (Optional)',
        validators=[Optional(), Length(max=500)]
    )
    submit = SubmitField('Submit Rating')


# ==================== REPORT FORMS ====================

class ReportMessageForm(FlaskForm):
    """Form for reporting a message."""
    message_id = HiddenField(validators=[DataRequired()])
    reason = SelectField(
        'Reason for Report',
        choices=[
            (ReportReason.INAPPROPRIATE_CONTENT.value, 'Inappropriate Content'),
            (ReportReason.HARASSMENT.value, 'Harassment / Abuse'),
            (ReportReason.SPAM.value, 'Spam'),
            (ReportReason.OTHER.value, 'Other'),
        ],
        validators=[DataRequired()]
    )
    description = TextAreaField(
        'Additional Details (Optional)',
        validators=[Optional(), Length(max=1000)]
    )
    submit = SubmitField('Submit Report')


class ReportArticleForm(FlaskForm):
    """Form for reporting a newspaper article."""
    article_id = HiddenField(validators=[DataRequired()])
    reason = SelectField(
        'Reason for Report',
        choices=[
            (ReportReason.INAPPROPRIATE_CONTENT.value, 'Inappropriate Content'),
            (ReportReason.HARASSMENT.value, 'Harassment / Abuse'),
            (ReportReason.SPAM.value, 'Spam'),
            (ReportReason.OTHER.value, 'Other'),
        ],
        validators=[DataRequired()]
    )
    description = TextAreaField(
        'Additional Details (Optional)',
        validators=[Optional(), Length(max=1000)]
    )
    submit = SubmitField('Submit Report')


class ReportCommentForm(FlaskForm):
    """Form for reporting an article comment."""
    comment_id = HiddenField(validators=[DataRequired()])
    reason = SelectField(
        'Reason for Report',
        choices=[
            (ReportReason.INAPPROPRIATE_CONTENT.value, 'Inappropriate Content'),
            (ReportReason.HARASSMENT.value, 'Harassment / Abuse'),
            (ReportReason.SPAM.value, 'Spam'),
            (ReportReason.OTHER.value, 'Other'),
        ],
        validators=[DataRequired()]
    )
    description = TextAreaField(
        'Additional Details (Optional)',
        validators=[Optional(), Length(max=1000)]
    )
    submit = SubmitField('Submit Report')


class ReportUserForm(FlaskForm):
    """Form for reporting a user profile."""
    user_id = HiddenField(validators=[DataRequired()])
    reason = SelectField(
        'Reason for Report',
        choices=[
            (ReportReason.INAPPROPRIATE_NAME_AVATAR.value, 'Inappropriate Username / Avatar'),
            (ReportReason.CHEATING.value, 'Suspected Cheating / Exploits'),
            (ReportReason.HARASSMENT.value, 'Harassment / Abuse'),
            (ReportReason.OTHER.value, 'Other'),
        ],
        validators=[DataRequired()]
    )
    description = TextAreaField(
        'Additional Details',
        validators=[DataRequired(), Length(min=20, max=1000)]
    )
    submit = SubmitField('Submit Report')


class ReportCompanyForm(FlaskForm):
    """Form for reporting a company."""
    company_id = HiddenField(validators=[DataRequired()])
    reason = SelectField(
        'Reason for Report',
        choices=[
            (ReportReason.INAPPROPRIATE_NAME_AVATAR.value, 'Inappropriate Company Name'),
            (ReportReason.CHEATING.value, 'Suspected Cheating / Exploits'),
            (ReportReason.OTHER.value, 'Other'),
        ],
        validators=[DataRequired()]
    )
    description = TextAreaField(
        'Additional Details (Optional)',
        validators=[Optional(), Length(max=1000)]
    )
    submit = SubmitField('Submit Report')


# ==================== ADMIN FORMS ====================

class ReportActionForm(FlaskForm):
    """Form for admin to take action on a report."""
    action = SelectField(
        'Action',
        choices=[
            (ReportAction.DISMISSED.value, 'Dismiss (Unfounded)'),
            (ReportAction.WARNING_ISSUED.value, 'Issue Warning'),
            (ReportAction.CONTENT_REMOVED.value, 'Remove Content'),
            (ReportAction.USER_MUTED.value, 'Mute User'),
            (ReportAction.TEMPORARY_BAN.value, 'Temporary Ban'),
            (ReportAction.PERMANENT_BAN.value, 'Permanent Ban'),
        ],
        validators=[DataRequired()]
    )
    mute_duration_hours = SelectField(
        'Mute Duration',
        choices=[
            ('24', '24 hours'),
            ('48', '48 hours'),
            ('72', '72 hours (3 days)'),
            ('168', '168 hours (1 week)'),
            ('720', '720 hours (1 month)'),
        ],
        validators=[Optional()]
    )
    ban_duration_days = SelectField(
        'Ban Duration (for temp ban)',
        choices=[
            ('1', '1 day'),
            ('3', '3 days'),
            ('7', '7 days'),
            ('14', '14 days'),
            ('30', '30 days'),
        ],
        validators=[Optional()]
    )
    action_details = TextAreaField(
        'Action Details / Notes',
        validators=[Optional(), Length(max=1000)]
    )
    submit = SubmitField('Take Action')


class CannedResponseForm(FlaskForm):
    """Form for creating/editing canned responses."""
    category = SelectField(
        'Category (Optional)',
        choices=[
            ('', '-- All Categories --'),
            (TicketCategory.BUG_REPORT.value, 'Bug Report'),
            (TicketCategory.SUGGESTION.value, 'Suggestion'),
            (TicketCategory.ACCOUNT_ISSUE.value, 'Account Issue'),
            (TicketCategory.PAYMENT_ISSUE.value, 'Payment Issue'),
            (TicketCategory.REPORT_USER.value, 'Report User'),
            (TicketCategory.OTHER.value, 'Other'),
        ],
        validators=[Optional()]
    )
    title = StringField(
        'Title',
        validators=[DataRequired(), Length(min=3, max=100)]
    )
    content = TextAreaField(
        'Response Content',
        validators=[DataRequired(), Length(min=10, max=5000)]
    )
    submit = SubmitField('Save Canned Response')
