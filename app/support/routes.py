"""
Support System Routes - Tickets and Reports
"""
import os
import uuid
from datetime import datetime, timedelta
from flask import (
    render_template, redirect, url_for, flash, request, current_app, abort, jsonify
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import or_, and_, func

from app.support import bp
from app.extensions import db
from app.models import (
    User, Message, Article, Company, Alert, AlertType, AlertPriority
)
from app.models.support import (
    SupportTicket, TicketResponse, TicketAuditLog, CannedResponse,
    Report, UserMute, TicketCategory, TicketStatus, TicketPriority,
    ReportType, ReportReason, ReportStatus, ReportAction, AuditActionType
)
from app.support.forms import (
    CreateTicketForm, TicketResponseForm, StaffTicketResponseForm,
    TicketStatusForm, TicketPriorityForm, AssignTicketForm, TicketRatingForm,
    ReportMessageForm, ReportArticleForm, ReportCommentForm, ReportUserForm, ReportCompanyForm,
    ReportActionForm, CannedResponseForm
)


# ==================== HELPER FUNCTIONS ====================

def allowed_file(filename):
    """Check if file extension is allowed."""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_ticket_image(file):
    """Save uploaded ticket image and return filename."""
    if file and allowed_file(file.filename):
        # Check file size (5MB max)
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)

        if size > 5 * 1024 * 1024:  # 5MB
            return None, "File too large. Maximum size is 5MB."

        # Generate unique filename
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"ticket_{uuid.uuid4().hex}.{ext}"

        # Ensure upload directory exists
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'tickets')
        os.makedirs(upload_dir, exist_ok=True)

        # Save file
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)

        return filename, None
    return None, "Invalid file type."


def create_audit_log(ticket, user, action_type, old_value=None, new_value=None, details=None):
    """Create an audit log entry for a ticket action."""
    log = TicketAuditLog(
        ticket_id=ticket.id,
        user_id=user.id,
        action_type=action_type,
        old_value=old_value,
        new_value=new_value,
        details=details
    )
    db.session.add(log)
    return log


def is_staff(user):
    """Check if user is admin or moderator."""
    return user.is_admin or getattr(user, 'is_moderator', False)


def send_ticket_alert(user_id, title, message, ticket_id=None):
    """Send an in-game alert about ticket update."""
    alert = Alert(
        user_id=user_id,
        alert_type=AlertType.SUPPORT_TICKET.value,
        priority=AlertPriority.NORMAL.value,
        title=title,
        content=message,
        link_url=url_for('support.view_ticket', ticket_id=ticket_id) if ticket_id else None,
        link_text='View Ticket' if ticket_id else None
    )
    db.session.add(alert)


def send_report_alert(user_id, title, message):
    """Send an in-game alert about report action."""
    alert = Alert(
        user_id=user_id,
        alert_type=AlertType.SUPPORT_TICKET.value,
        priority=AlertPriority.IMPORTANT.value,
        title=title,
        content=message
    )
    db.session.add(alert)


# ==================== PLAYER TICKET ROUTES ====================

@bp.route('/tickets')
@login_required
def my_tickets():
    """View list of user's tickets."""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')

    query = SupportTicket.query.filter_by(
        user_id=current_user.id,
        is_deleted=False
    )

    if status_filter:
        try:
            status = TicketStatus(status_filter)
            query = query.filter_by(status=status)
        except ValueError:
            pass

    tickets = query.order_by(SupportTicket.updated_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )

    return render_template('support/my_tickets.html',
                          title='My Support Tickets',
                          tickets=tickets,
                          status_filter=status_filter,
                          TicketStatus=TicketStatus)


@bp.route('/tickets/create', methods=['GET', 'POST'])
@login_required
def create_ticket():
    """Create a new support ticket."""
    form = CreateTicketForm()

    if form.validate_on_submit():
        # Generate ticket number
        ticket_number = SupportTicket.generate_ticket_number()

        # Handle image upload
        image_filename = None
        if form.image.data:
            image_filename, error = save_ticket_image(form.image.data)
            if error:
                flash(error, 'danger')
                return render_template('support/create_ticket.html', form=form)

        # Create ticket
        ticket = SupportTicket(
            ticket_number=ticket_number,
            user_id=current_user.id,
            category=TicketCategory(form.category.data),
            subject=form.subject.data,
            description=form.description.data,
            image_filename=image_filename,
            status=TicketStatus.OPEN,
            priority=TicketPriority.MEDIUM
        )
        db.session.add(ticket)
        db.session.flush()

        # Create audit log
        create_audit_log(ticket, current_user, AuditActionType.CREATED,
                        details=f"Ticket created: {form.subject.data}")

        db.session.commit()

        flash(f'Ticket {ticket_number} created successfully!', 'success')
        return redirect(url_for('support.view_ticket', ticket_id=ticket.id))

    return render_template('support/create_ticket.html',
                          title='Create Support Ticket',
                          form=form)


@bp.route('/tickets/<int:ticket_id>')
@login_required
def view_ticket(ticket_id):
    """View a specific ticket."""
    ticket = SupportTicket.query.get_or_404(ticket_id)

    # Check access - owner or staff
    if ticket.user_id != current_user.id and not is_staff(current_user):
        abort(403)

    # Get responses (filter internal notes for non-staff)
    if is_staff(current_user):
        responses = ticket.responses.all()
    else:
        responses = ticket.responses.filter_by(is_internal_note=False).all()

    # Forms
    response_form = TicketResponseForm() if not is_staff(current_user) else None
    staff_response_form = StaffTicketResponseForm() if is_staff(current_user) else None
    rating_form = TicketRatingForm() if (
        ticket.user_id == current_user.id and
        ticket.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED] and
        ticket.rating is None
    ) else None

    # Load canned responses for staff
    if staff_response_form:
        canned_responses = CannedResponse.query.filter_by(is_active=True).all()
        staff_response_form.canned_response_id.choices = [('', '-- Select --')] + [
            (str(cr.id), cr.title) for cr in canned_responses
        ]

    return render_template('support/view_ticket.html',
                          title=f'Ticket {ticket.ticket_number}',
                          ticket=ticket,
                          responses=responses,
                          response_form=response_form,
                          staff_response_form=staff_response_form,
                          rating_form=rating_form,
                          is_staff=is_staff(current_user))


@bp.route('/tickets/<int:ticket_id>/respond', methods=['POST'])
@login_required
def respond_to_ticket(ticket_id):
    """Add a response to a ticket."""
    ticket = SupportTicket.query.get_or_404(ticket_id)

    # Check access
    if ticket.user_id != current_user.id and not is_staff(current_user):
        abort(403)

    # Can't respond to archived tickets
    if ticket.status == TicketStatus.ARCHIVED:
        flash('Cannot respond to archived tickets.', 'warning')
        return redirect(url_for('support.view_ticket', ticket_id=ticket_id))

    if is_staff(current_user):
        form = StaffTicketResponseForm()
        # Rebuild choices
        canned_responses = CannedResponse.query.filter_by(is_active=True).all()
        form.canned_response_id.choices = [('', '-- Select --')] + [
            (str(cr.id), cr.title) for cr in canned_responses
        ]
    else:
        form = TicketResponseForm()

    if form.validate_on_submit():
        is_internal = is_staff(current_user) and form.is_internal_note.data == 'true' if hasattr(form, 'is_internal_note') else False

        # Check for canned response
        canned_id = None
        if is_staff(current_user) and hasattr(form, 'canned_response_id') and form.canned_response_id.data:
            canned_id = form.canned_response_id.data
            canned = CannedResponse.query.get(canned_id)
            if canned:
                canned.times_used += 1

        response = TicketResponse(
            ticket_id=ticket.id,
            user_id=current_user.id,
            message=form.message.data,
            is_staff_response=is_staff(current_user),
            is_internal_note=is_internal,
            canned_response_id=canned_id
        )
        db.session.add(response)

        # Update ticket
        ticket.updated_at = datetime.utcnow()

        # If user responds, set to awaiting response (for staff)
        # If staff responds, keep current status or set to awaiting response (for user)
        if not is_staff(current_user):
            if ticket.status == TicketStatus.AWAITING_RESPONSE:
                ticket.status = TicketStatus.OPEN
        else:
            if ticket.status == TicketStatus.OPEN:
                ticket.status = TicketStatus.AWAITING_RESPONSE

        # Create audit log
        create_audit_log(ticket, current_user, AuditActionType.RESPONSE_ADDED if not is_internal else AuditActionType.INTERNAL_NOTE_ADDED)

        # Send alert to user if staff responded (and not internal note)
        if is_staff(current_user) and not is_internal:
            send_ticket_alert(
                ticket.user_id,
                'Ticket Update',
                f'Your ticket {ticket.ticket_number} has received a response.',
                ticket.id
            )

        db.session.commit()
        flash('Response added successfully.', 'success')

    return redirect(url_for('support.view_ticket', ticket_id=ticket_id))


@bp.route('/tickets/<int:ticket_id>/rate', methods=['POST'])
@login_required
def rate_ticket(ticket_id):
    """Rate support after ticket resolution."""
    ticket = SupportTicket.query.get_or_404(ticket_id)

    # Only owner can rate
    if ticket.user_id != current_user.id:
        abort(403)

    # Can only rate resolved/closed tickets that haven't been rated
    if ticket.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
        flash('Can only rate resolved or closed tickets.', 'warning')
        return redirect(url_for('support.view_ticket', ticket_id=ticket_id))

    if ticket.rating is not None:
        flash('Ticket has already been rated.', 'warning')
        return redirect(url_for('support.view_ticket', ticket_id=ticket_id))

    form = TicketRatingForm()
    if form.validate_on_submit():
        ticket.rating = int(form.rating.data)
        ticket.rating_comment = form.rating_comment.data

        create_audit_log(ticket, current_user, AuditActionType.RATED,
                        new_value=form.rating.data)

        db.session.commit()
        flash('Thank you for your feedback!', 'success')

    return redirect(url_for('support.view_ticket', ticket_id=ticket_id))


# ==================== PLAYER REPORT ROUTES ====================

@bp.route('/report/message/<int:message_id>', methods=['GET', 'POST'])
@login_required
def report_message(message_id):
    """Report a private message."""
    message = Message.query.get_or_404(message_id)

    # Must be recipient of message
    if message.recipient_id != current_user.id:
        abort(403)

    form = ReportMessageForm()
    form.message_id.data = message_id

    if form.validate_on_submit():
        # Check for existing report
        existing = Report.query.filter_by(
            reporter_id=current_user.id,
            reported_message_id=message_id,
            is_deleted=False
        ).first()

        if existing:
            flash('You have already reported this message.', 'warning')
            return redirect(url_for('main.messages'))

        report = Report(
            report_number=Report.generate_report_number(),
            reporter_id=current_user.id,
            reported_user_id=message.sender_id,
            report_type=ReportType.MESSAGE,
            reason=ReportReason(form.reason.data),
            description=form.description.data,
            reported_message_id=message_id,
            reported_message=message,  # Set the relationship for snapshot
            status=ReportStatus.PENDING
        )
        report.create_content_snapshot()
        db.session.add(report)
        db.session.commit()

        flash('Report submitted successfully. Our team will review it.', 'success')
        return redirect(url_for('main.messages'))

    return render_template('support/report_message.html',
                          title='Report Message',
                          form=form,
                          message=message)


@bp.route('/report/article/<int:article_id>', methods=['GET', 'POST'])
@login_required
def report_article(article_id):
    """Report a newspaper article."""
    article = Article.query.get_or_404(article_id)

    form = ReportArticleForm()
    form.article_id.data = article_id

    if form.validate_on_submit():
        # Check for existing report
        existing = Report.query.filter_by(
            reporter_id=current_user.id,
            reported_article_id=article_id,
            is_deleted=False
        ).first()

        if existing:
            flash('You have already reported this article.', 'warning')
            return redirect(url_for('main.view_article', newspaper_id=article.newspaper_id, article_id=article_id))

        report = Report(
            report_number=Report.generate_report_number(),
            reporter_id=current_user.id,
            reported_user_id=article.author_id,
            report_type=ReportType.NEWSPAPER_ARTICLE,
            reason=ReportReason(form.reason.data),
            description=form.description.data,
            reported_article_id=article_id,
            reported_article=article,  # Set the relationship for snapshot
            status=ReportStatus.PENDING
        )
        report.create_content_snapshot()
        db.session.add(report)
        db.session.commit()

        flash('Report submitted successfully. Our team will review it.', 'success')
        return redirect(url_for('main.view_article', newspaper_id=article.newspaper_id, article_id=article_id))

    return render_template('support/report_article.html',
                          title='Report Article',
                          form=form,
                          article=article)


@bp.route('/report/comment/<int:comment_id>', methods=['GET', 'POST'])
@login_required
def report_comment(comment_id):
    """Report an article comment."""
    from app.models.newspaper import ArticleComment
    comment = ArticleComment.query.get_or_404(comment_id)

    if comment.user_id == current_user.id:
        flash('You cannot report your own comment.', 'warning')
        return redirect(url_for('main.view_article', newspaper_id=comment.article.newspaper_id, article_id=comment.article_id))

    form = ReportCommentForm()
    form.comment_id.data = comment_id

    if form.validate_on_submit():
        # Check for existing report
        existing = Report.query.filter_by(
            reporter_id=current_user.id,
            reported_comment_id=comment_id,
            is_deleted=False
        ).first()

        if existing:
            flash('You have already reported this comment.', 'warning')
            return redirect(url_for('main.view_article', newspaper_id=comment.article.newspaper_id, article_id=comment.article_id))

        report = Report(
            report_number=Report.generate_report_number(),
            reporter_id=current_user.id,
            reported_user_id=comment.user_id,
            report_type=ReportType.ARTICLE_COMMENT,
            reason=ReportReason(form.reason.data),
            description=form.description.data,
            reported_comment_id=comment_id,
            reported_comment=comment,  # Set the relationship for snapshot
            status=ReportStatus.PENDING
        )
        report.create_content_snapshot()
        db.session.add(report)
        db.session.commit()

        flash('Report submitted successfully. Our team will review it.', 'success')
        return redirect(url_for('main.view_article', newspaper_id=comment.article.newspaper_id, article_id=comment.article_id))

    return render_template('support/report_comment.html',
                          title='Report Comment',
                          form=form,
                          comment=comment)


@bp.route('/report/user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def report_user(user_id):
    """Report a user profile."""
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash('You cannot report yourself.', 'warning')
        return redirect(url_for('main.view_profile', username=user.username))

    form = ReportUserForm()
    form.user_id.data = user_id

    if form.validate_on_submit():
        # Check for existing pending report
        existing = Report.query.filter_by(
            reporter_id=current_user.id,
            reported_user_id=user_id,
            report_type=ReportType.USER_PROFILE,
            status=ReportStatus.PENDING,
            is_deleted=False
        ).first()

        if existing:
            flash('You already have a pending report against this user.', 'warning')
            return redirect(url_for('main.view_profile', username=user.username))

        report = Report(
            report_number=Report.generate_report_number(),
            reporter_id=current_user.id,
            reported_user_id=user_id,
            reported_user=user,  # Set the relationship for snapshot
            report_type=ReportType.USER_PROFILE,
            reason=ReportReason(form.reason.data),
            description=form.description.data,
            status=ReportStatus.PENDING
        )
        report.create_content_snapshot()
        db.session.add(report)
        db.session.commit()

        flash('Report submitted successfully. Our team will review it.', 'success')
        return redirect(url_for('main.view_profile', username=user.username))

    return render_template('support/report_user.html',
                          title='Report User',
                          form=form,
                          reported_user=user)


@bp.route('/report/company/<int:company_id>', methods=['GET', 'POST'])
@login_required
def report_company(company_id):
    """Report a company."""
    company = Company.query.get_or_404(company_id)

    form = ReportCompanyForm()
    form.company_id.data = company_id

    if form.validate_on_submit():
        # Check for existing pending report
        existing = Report.query.filter_by(
            reporter_id=current_user.id,
            reported_company_id=company_id,
            status=ReportStatus.PENDING,
            is_deleted=False
        ).first()

        if existing:
            flash('You already have a pending report against this company.', 'warning')
            return redirect(url_for('main.view_company', company_id=company_id))

        report = Report(
            report_number=Report.generate_report_number(),
            reporter_id=current_user.id,
            reported_user_id=company.owner_id,
            report_type=ReportType.COMPANY,
            reason=ReportReason(form.reason.data),
            description=form.description.data,
            reported_company_id=company_id,
            reported_company=company,  # Set the relationship for snapshot
            status=ReportStatus.PENDING
        )
        report.create_content_snapshot()
        db.session.add(report)
        db.session.commit()

        flash('Report submitted successfully. Our team will review it.', 'success')
        return redirect(url_for('main.view_company', company_id=company_id))

    return render_template('support/report_company.html',
                          title='Report Company',
                          form=form,
                          company=company)


# ==================== ADMIN/MOD ROUTES ====================

@bp.route('/admin/tickets')
@login_required
def admin_tickets():
    """Admin view of all tickets."""
    if not is_staff(current_user):
        abort(403)

    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    category_filter = request.args.get('category', '')
    assigned_filter = request.args.get('assigned', '')

    query = SupportTicket.query.filter_by(is_deleted=False)

    # Apply filters
    if status_filter:
        try:
            query = query.filter_by(status=TicketStatus(status_filter))
        except ValueError:
            pass

    if priority_filter:
        try:
            query = query.filter_by(priority=TicketPriority(priority_filter))
        except ValueError:
            pass

    if category_filter:
        try:
            query = query.filter_by(category=TicketCategory(category_filter))
        except ValueError:
            pass

    if assigned_filter == 'me':
        query = query.filter_by(assigned_to_id=current_user.id)
    elif assigned_filter == 'unassigned':
        query = query.filter_by(assigned_to_id=None)

    # Sort by priority (critical first) then by date
    tickets = query.order_by(
        SupportTicket.priority.desc(),
        SupportTicket.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)

    # Get staff members for assignment
    staff_members = User.query.filter(
        or_(User.is_admin == True, getattr(User, 'is_moderator', False) == True)
    ).all()

    return render_template('support/admin/tickets.html',
                          title='Manage Tickets',
                          tickets=tickets,
                          staff_members=staff_members,
                          status_filter=status_filter,
                          priority_filter=priority_filter,
                          category_filter=category_filter,
                          assigned_filter=assigned_filter,
                          TicketStatus=TicketStatus,
                          TicketPriority=TicketPriority,
                          TicketCategory=TicketCategory)


@bp.route('/admin/tickets/<int:ticket_id>/status', methods=['POST'])
@login_required
def update_ticket_status(ticket_id):
    """Update ticket status."""
    if not is_staff(current_user):
        abort(403)

    ticket = SupportTicket.query.get_or_404(ticket_id)
    new_status = request.form.get('status')

    try:
        old_status = ticket.status
        ticket.status = TicketStatus(new_status)
        ticket.updated_at = datetime.utcnow()

        if ticket.status == TicketStatus.RESOLVED:
            ticket.resolved_at = datetime.utcnow()
        elif ticket.status == TicketStatus.CLOSED:
            ticket.closed_at = datetime.utcnow()

        create_audit_log(ticket, current_user, AuditActionType.STATUS_CHANGED,
                        old_value=old_status.value,
                        new_value=new_status)

        # Notify user
        send_ticket_alert(
            ticket.user_id,
            'Ticket Status Updated',
            f'Your ticket {ticket.ticket_number} status changed to {ticket.status.value.replace("_", " ").title()}.',
            ticket.id
        )

        db.session.commit()
        flash('Ticket status updated.', 'success')
    except ValueError:
        flash('Invalid status.', 'danger')

    return redirect(url_for('support.view_ticket', ticket_id=ticket_id))


@bp.route('/admin/tickets/<int:ticket_id>/priority', methods=['POST'])
@login_required
def update_ticket_priority(ticket_id):
    """Update ticket priority."""
    if not is_staff(current_user):
        abort(403)

    ticket = SupportTicket.query.get_or_404(ticket_id)
    new_priority = request.form.get('priority')

    try:
        old_priority = ticket.priority
        ticket.priority = TicketPriority(new_priority)
        ticket.updated_at = datetime.utcnow()

        create_audit_log(ticket, current_user, AuditActionType.PRIORITY_CHANGED,
                        old_value=old_priority.value,
                        new_value=new_priority)

        db.session.commit()
        flash('Ticket priority updated.', 'success')
    except ValueError:
        flash('Invalid priority.', 'danger')

    return redirect(url_for('support.view_ticket', ticket_id=ticket_id))


@bp.route('/admin/tickets/<int:ticket_id>/assign', methods=['POST'])
@login_required
def assign_ticket(ticket_id):
    """Assign ticket to staff member."""
    if not is_staff(current_user):
        abort(403)

    ticket = SupportTicket.query.get_or_404(ticket_id)
    assignee_id = request.form.get('assigned_to_id')

    old_assignee = ticket.assigned_to.username if ticket.assigned_to else 'Unassigned'

    if assignee_id:
        assignee = User.query.get(int(assignee_id))
        if assignee and is_staff(assignee):
            ticket.assigned_to_id = assignee.id
            new_assignee = assignee.username
        else:
            flash('Invalid staff member.', 'danger')
            return redirect(url_for('support.view_ticket', ticket_id=ticket_id))
    else:
        ticket.assigned_to_id = None
        new_assignee = 'Unassigned'

    ticket.updated_at = datetime.utcnow()

    create_audit_log(ticket, current_user, AuditActionType.ASSIGNED,
                    old_value=old_assignee,
                    new_value=new_assignee)

    db.session.commit()
    flash('Ticket assignment updated.', 'success')

    return redirect(url_for('support.view_ticket', ticket_id=ticket_id))


@bp.route('/admin/reports')
@login_required
def admin_reports():
    """Admin view of all reports."""
    if not is_staff(current_user):
        abort(403)

    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    type_filter = request.args.get('type', '')

    query = Report.query.filter_by(is_deleted=False)

    if status_filter:
        try:
            query = query.filter_by(status=ReportStatus(status_filter))
        except ValueError:
            pass

    if type_filter:
        try:
            query = query.filter_by(report_type=ReportType(type_filter))
        except ValueError:
            pass

    reports = query.order_by(Report.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template('support/admin/reports.html',
                          title='Manage Reports',
                          reports=reports,
                          status_filter=status_filter,
                          type_filter=type_filter,
                          ReportStatus=ReportStatus,
                          ReportType=ReportType)


@bp.route('/admin/reports/<int:report_id>')
@login_required
def view_report(report_id):
    """View a specific report."""
    if not is_staff(current_user):
        abort(403)

    report = Report.query.get_or_404(report_id)
    form = ReportActionForm()

    # Get user's report history
    user_reports = Report.query.filter_by(
        reported_user_id=report.reported_user_id,
        is_deleted=False
    ).filter(Report.id != report_id).order_by(Report.created_at.desc()).limit(10).all()

    # Get canned responses for reports (REPORT_USER category)
    canned_responses = CannedResponse.query.filter(
        CannedResponse.is_active == True,
        or_(
            CannedResponse.category == TicketCategory.REPORT_USER,
            CannedResponse.category == None
        )
    ).order_by(CannedResponse.title).all()

    return render_template('support/admin/view_report.html',
                          title=f'Report {report.report_number}',
                          report=report,
                          form=form,
                          user_reports=user_reports,
                          canned_responses=canned_responses,
                          ReportAction=ReportAction)


@bp.route('/admin/reports/<int:report_id>/action', methods=['POST'])
@login_required
def take_report_action(report_id):
    """Take action on a report."""
    if not is_staff(current_user):
        abort(403)

    report = Report.query.get_or_404(report_id)
    form = ReportActionForm()

    if form.validate_on_submit():
        action = ReportAction(form.action.data)
        report.action_taken = action
        report.action_details = form.action_details.data
        report.handled_by_id = current_user.id
        report.handled_at = datetime.utcnow()
        report.status = ReportStatus.RESOLVED

        reported_user = report.reported_user

        # Execute action
        if action == ReportAction.DISMISSED:
            # Just mark as dismissed
            pass

        elif action == ReportAction.WARNING_ISSUED:
            # Send warning alert to user
            send_report_alert(
                reported_user.id,
                'Warning',
                f'You have received a warning for violating our community guidelines. Reason: {report.reason.value.replace("_", " ").title()}'
            )

        elif action == ReportAction.CONTENT_REMOVED:
            # Remove the content
            if report.report_type == ReportType.MESSAGE and report.reported_message:
                # Mark message as admin removed
                report.reported_message.admin_removed = True
            elif report.report_type == ReportType.NEWSPAPER_ARTICLE and report.reported_article:
                report.reported_article.is_deleted = True

            send_report_alert(
                reported_user.id,
                'Content Removed',
                f'Your content has been removed for violating our community guidelines.'
            )

        elif action == ReportAction.USER_MUTED:
            # Mute the user
            mute_hours = int(form.mute_duration_hours.data)
            report.mute_duration_hours = mute_hours

            mute = UserMute(
                user_id=reported_user.id,
                report_id=report.id,
                reason=f'Report: {report.reason.value}',
                muted_by_id=current_user.id,
                expires_at=datetime.utcnow() + timedelta(hours=mute_hours)
            )
            db.session.add(mute)

            send_report_alert(
                reported_user.id,
                'Account Muted',
                f'Your account has been muted for {mute_hours} hours. You cannot post articles or send messages during this time.'
            )

        elif action == ReportAction.TEMPORARY_BAN:
            ban_days = int(form.ban_duration_days.data)
            reported_user.is_banned = True
            reported_user.banned_until = datetime.utcnow() + timedelta(days=ban_days)
            reported_user.ban_reason = f'Report: {report.reason.value}'

            send_report_alert(
                reported_user.id,
                'Account Temporarily Banned',
                f'Your account has been banned for {ban_days} days.'
            )

        elif action == ReportAction.PERMANENT_BAN:
            reported_user.is_banned = True
            reported_user.banned_until = None  # Permanent
            reported_user.ban_reason = f'Report: {report.reason.value}'

        # Notify reporter that action was taken
        send_report_alert(
            report.reporter_id,
            'Report Reviewed',
            f'Your report {report.report_number} has been reviewed and action has been taken. Thank you for helping keep our community safe.'
        )

        db.session.commit()
        flash(f'Action taken: {action.value.replace("_", " ").title()}', 'success')
        return redirect(url_for('support.admin_reports'))

    return redirect(url_for('support.view_report', report_id=report_id))


# ==================== CANNED RESPONSES ====================

@bp.route('/admin/canned-responses')
@login_required
def canned_responses():
    """Manage canned responses."""
    if not is_staff(current_user):
        abort(403)

    responses = CannedResponse.query.filter_by(is_active=True).order_by(
        CannedResponse.category,
        CannedResponse.title
    ).all()

    return render_template('support/admin/canned_responses.html',
                          title='Canned Responses',
                          responses=responses)


@bp.route('/admin/canned-responses/create', methods=['GET', 'POST'])
@login_required
def create_canned_response():
    """Create a new canned response."""
    if not is_staff(current_user):
        abort(403)

    form = CannedResponseForm()

    if form.validate_on_submit():
        category = TicketCategory(form.category.data) if form.category.data else None

        response = CannedResponse(
            category=category,
            title=form.title.data,
            content=form.content.data,
            created_by_id=current_user.id
        )
        db.session.add(response)
        db.session.commit()

        flash('Canned response created.', 'success')
        return redirect(url_for('support.canned_responses'))

    return render_template('support/admin/canned_response_form.html',
                          title='Create Canned Response',
                          form=form)


@bp.route('/admin/canned-responses/<int:response_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_canned_response(response_id):
    """Edit a canned response."""
    if not is_staff(current_user):
        abort(403)

    response = CannedResponse.query.get_or_404(response_id)
    form = CannedResponseForm(obj=response)

    if form.validate_on_submit():
        response.category = TicketCategory(form.category.data) if form.category.data else None
        response.title = form.title.data
        response.content = form.content.data
        db.session.commit()

        flash('Canned response updated.', 'success')
        return redirect(url_for('support.canned_responses'))

    # Populate form
    if response.category:
        form.category.data = response.category.value

    return render_template('support/admin/canned_response_form.html',
                          title='Edit Canned Response',
                          form=form,
                          editing=True)


@bp.route('/admin/canned-responses/<int:response_id>/delete', methods=['POST'])
@login_required
def delete_canned_response(response_id):
    """Delete a canned response."""
    if not is_staff(current_user):
        abort(403)

    response = CannedResponse.query.get_or_404(response_id)
    response.is_active = False
    db.session.commit()

    flash('Canned response deleted.', 'success')
    return redirect(url_for('support.canned_responses'))


@bp.route('/api/canned-response/<int:response_id>')
@login_required
def get_canned_response_content(response_id):
    """API endpoint to get canned response content."""
    if not is_staff(current_user):
        return jsonify({'error': 'Forbidden'}), 403

    response = CannedResponse.query.get_or_404(response_id)
    return jsonify({'content': response.content})


# ==================== STATISTICS ====================

@bp.route('/admin/statistics')
@login_required
def admin_statistics():
    """Admin statistics dashboard."""
    if not is_staff(current_user):
        abort(403)

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    month_start = today_start - timedelta(days=30)

    # Ticket statistics
    ticket_stats = {
        'total': SupportTicket.query.filter_by(is_deleted=False).count(),
        'open': SupportTicket.query.filter_by(status=TicketStatus.OPEN, is_deleted=False).count(),
        'in_progress': SupportTicket.query.filter_by(status=TicketStatus.IN_PROGRESS, is_deleted=False).count(),
        'awaiting_response': SupportTicket.query.filter_by(status=TicketStatus.AWAITING_RESPONSE, is_deleted=False).count(),
        'resolved': SupportTicket.query.filter_by(status=TicketStatus.RESOLVED, is_deleted=False).count(),
        'closed': SupportTicket.query.filter_by(status=TicketStatus.CLOSED, is_deleted=False).count(),
        'today': SupportTicket.query.filter(SupportTicket.created_at >= today_start).count(),
        'this_week': SupportTicket.query.filter(SupportTicket.created_at >= week_start).count(),
        'this_month': SupportTicket.query.filter(SupportTicket.created_at >= month_start).count(),
    }

    # Average resolution time (for resolved tickets)
    resolved_tickets = SupportTicket.query.filter(
        SupportTicket.resolved_at != None,
        SupportTicket.is_deleted == False
    ).all()

    if resolved_tickets:
        total_time = sum(
            (t.resolved_at - t.created_at).total_seconds()
            for t in resolved_tickets
        )
        avg_resolution_hours = (total_time / len(resolved_tickets)) / 3600
        ticket_stats['avg_resolution_hours'] = round(avg_resolution_hours, 1)
    else:
        ticket_stats['avg_resolution_hours'] = 0

    # Average rating
    rated_tickets = SupportTicket.query.filter(
        SupportTicket.rating != None,
        SupportTicket.is_deleted == False
    ).all()

    if rated_tickets:
        ticket_stats['avg_rating'] = round(sum(t.rating for t in rated_tickets) / len(rated_tickets), 1)
        ticket_stats['total_ratings'] = len(rated_tickets)
    else:
        ticket_stats['avg_rating'] = 0
        ticket_stats['total_ratings'] = 0

    # Report statistics
    report_stats = {
        'total': Report.query.filter_by(is_deleted=False).count(),
        'pending': Report.query.filter_by(status=ReportStatus.PENDING, is_deleted=False).count(),
        'under_review': Report.query.filter_by(status=ReportStatus.UNDER_REVIEW, is_deleted=False).count(),
        'resolved': Report.query.filter_by(status=ReportStatus.RESOLVED, is_deleted=False).count(),
        'dismissed': Report.query.filter_by(status=ReportStatus.DISMISSED, is_deleted=False).count(),
        'today': Report.query.filter(Report.created_at >= today_start).count(),
        'this_week': Report.query.filter(Report.created_at >= week_start).count(),
    }

    # Reports by type
    report_by_type = {
        'message': Report.query.filter_by(report_type=ReportType.MESSAGE, is_deleted=False).count(),
        'article': Report.query.filter_by(report_type=ReportType.NEWSPAPER_ARTICLE, is_deleted=False).count(),
        'user': Report.query.filter_by(report_type=ReportType.USER_PROFILE, is_deleted=False).count(),
        'company': Report.query.filter_by(report_type=ReportType.COMPANY, is_deleted=False).count(),
    }

    # Most reported users
    most_reported = db.session.query(
        User,
        func.count(Report.id).label('report_count')
    ).join(Report, Report.reported_user_id == User.id).filter(
        Report.is_deleted == False
    ).group_by(User.id).order_by(
        func.count(Report.id).desc()
    ).limit(10).all()

    # Staff performance
    staff_stats = db.session.query(
        User,
        func.count(SupportTicket.id).label('tickets_handled')
    ).join(TicketResponse, TicketResponse.user_id == User.id).filter(
        TicketResponse.is_staff_response == True
    ).group_by(User.id).order_by(
        func.count(SupportTicket.id).desc()
    ).limit(10).all()

    return render_template('support/admin/statistics.html',
                          title='Support Statistics',
                          ticket_stats=ticket_stats,
                          report_stats=report_stats,
                          report_by_type=report_by_type,
                          most_reported=most_reported,
                          staff_stats=staff_stats)


# ==================== USER HISTORY ====================

@bp.route('/admin/user/<int:user_id>/history')
@login_required
def user_ticket_history(user_id):
    """View all tickets and reports for a user."""
    if not is_staff(current_user):
        abort(403)

    user = User.query.get_or_404(user_id)

    # User's tickets
    tickets = SupportTicket.query.filter_by(
        user_id=user_id,
        is_deleted=False
    ).order_by(SupportTicket.created_at.desc()).all()

    # Reports against user
    reports_against = Report.query.filter_by(
        reported_user_id=user_id,
        is_deleted=False
    ).order_by(Report.created_at.desc()).all()

    # Reports submitted by user
    reports_submitted = Report.query.filter_by(
        reporter_id=user_id,
        is_deleted=False
    ).order_by(Report.created_at.desc()).all()

    # Mute history
    mute_history = UserMute.query.filter_by(user_id=user_id).order_by(
        UserMute.started_at.desc()
    ).all()

    return render_template('support/admin/user_history.html',
                          title=f'History: {user.username}',
                          viewed_user=user,
                          tickets=tickets,
                          reports_against=reports_against,
                          reports_submitted=reports_submitted,
                          mute_history=mute_history)
