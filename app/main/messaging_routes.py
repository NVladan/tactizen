# app/main/messaging_routes.py
# Routes for Messages and Alerts

from flask import render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import current_user, login_required
from app.main import bp
from app.extensions import db, limiter
from app.models import User, Message, Alert, BlockedUser
from sqlalchemy import or_, and_, select, func
from datetime import datetime
from app.security import InputSanitizer


# --- Main Messages Page (with tabs) ---
@bp.route('/messages')
@login_required
def messages():
    """Main messages page with tabs for Messages and Alerts."""
    tab = request.args.get('tab', 'messages')  # Default to messages tab

    if tab == 'alerts':
        # Get all non-deleted alerts for user, ordered by most recent
        alerts = db.session.scalars(
            select(Alert)
            .where(Alert.user_id == current_user.id, Alert.is_deleted == False)
            .order_by(Alert.created_at.desc())
        ).all()

        return render_template('messages.html',
                             title='Alerts',
                             tab='alerts',
                             alerts=alerts)
    else:
        # Get message threads (group by conversation partner)
        # Find all unique conversation partners
        sent_to = db.session.scalars(
            select(Message.recipient_id)
            .where(
                Message.sender_id == current_user.id,
                Message.sender_deleted == False
            )
            .distinct()
        ).all()

        received_from = db.session.scalars(
            select(Message.sender_id)
            .where(
                Message.recipient_id == current_user.id,
                Message.recipient_deleted == False
            )
            .distinct()
        ).all()

        # Combine and get unique user IDs
        partner_ids = list(set(sent_to + received_from))

        # Get user objects and latest message for each conversation
        conversations = []
        for partner_id in partner_ids:
            partner = db.session.get(User, partner_id)
            if not partner:
                continue

            # Get latest message in this conversation
            latest_msg = db.session.scalar(
                select(Message)
                .where(
                    or_(
                        and_(Message.sender_id == current_user.id, Message.recipient_id == partner_id, Message.sender_deleted == False),
                        and_(Message.sender_id == partner_id, Message.recipient_id == current_user.id, Message.recipient_deleted == False)
                    )
                )
                .order_by(Message.created_at.desc())
            )

            if latest_msg:
                # Count unread messages from this partner
                unread_count = db.session.scalar(
                    select(func.count(Message.id))
                    .where(
                        Message.sender_id == partner_id,
                        Message.recipient_id == current_user.id,
                        Message.is_read == False,
                        Message.recipient_deleted == False
                    )
                ) or 0

                conversations.append({
                    'partner': partner,
                    'latest_message': latest_msg,
                    'unread_count': unread_count
                })

        # Sort by latest message date
        conversations.sort(key=lambda x: x['latest_message'].created_at, reverse=True)

        return render_template('messages.html',
                             title='Messages',
                             tab='messages',
                             conversations=conversations)


# --- View Message Thread ---
@bp.route('/messages/thread/<int:user_id>')
@login_required
def message_thread(user_id):
    """View full message thread with a specific user."""
    partner = db.session.get(User, user_id)
    if not partner:
        flash("User not found.", "danger")
        return redirect(url_for('main.messages'))

    # Get all messages between these two users
    messages_list = db.session.scalars(
        select(Message)
        .where(
            or_(
                and_(Message.sender_id == current_user.id, Message.recipient_id == user_id, Message.sender_deleted == False),
                and_(Message.sender_id == user_id, Message.recipient_id == current_user.id, Message.recipient_deleted == False)
            )
        )
        .order_by(Message.created_at.asc())
    ).all()

    # Mark all messages from partner as read
    unread_messages = db.session.scalars(
        select(Message)
        .where(
            Message.sender_id == user_id,
            Message.recipient_id == current_user.id,
            Message.is_read == False
        )
    ).all()

    for msg in unread_messages:
        msg.is_read = True

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking messages as read: {e}", exc_info=True)

    return render_template('message_thread.html',
                         title=f'Messages with {partner.username}',
                         partner=partner,
                         messages=messages_list)


# --- Send Message ---
@bp.route('/messages/send/<int:recipient_id>', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_SEND_MESSAGE", "20 per minute"))
def send_message(recipient_id):
    """Send a message to another user."""
    recipient = db.session.get(User, recipient_id)
    if not recipient:
        flash("User not found.", "danger")
        return redirect(url_for('main.messages'))

    # Check if user is blocked
    is_blocked = db.session.scalar(
        select(BlockedUser.id)
        .where(
            BlockedUser.user_id == recipient_id,
            BlockedUser.blocked_user_id == current_user.id
        )
    )

    if is_blocked:
        flash("You cannot send messages to this user.", "warning")
        return redirect(url_for('main.message_thread', user_id=recipient_id))

    # Validate message content
    content = request.form.get('content', '').strip()
    if not content:
        flash("Message cannot be empty.", "warning")
        return redirect(url_for('main.message_thread', user_id=recipient_id))

    # Sanitize and validate content
    try:
        sanitized_content = InputSanitizer.sanitize_description(content, max_length=2000)
        if not sanitized_content:
            flash("Message content is invalid.", "warning")
            return redirect(url_for('main.message_thread', user_id=recipient_id))
    except Exception as e:
        current_app.logger.error(f"Error sanitizing message content: {e}")
        flash("Invalid message content.", "error")
        return redirect(url_for('main.message_thread', user_id=recipient_id))

    # Validate parent message ID (for replies)
    parent_message_id = None
    parent_id_raw = request.form.get('parent_id')
    if parent_id_raw:
        try:
            parent_message_id = InputSanitizer.sanitize_positive_integer(parent_id_raw)
        except ValueError:
            flash("Invalid reply reference.", "error")
            return redirect(url_for('main.message_thread', user_id=recipient_id))

    # Create message
    new_message = Message(
        sender_id=current_user.id,
        recipient_id=recipient_id,
        content=sanitized_content,
        parent_message_id=parent_message_id,
        created_at=datetime.utcnow()
    )

    db.session.add(new_message)

    try:
        db.session.commit()
        flash("Message sent successfully!", "success")
        current_app.logger.info(f"User {current_user.id} sent message to user {recipient_id}")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error sending message: {e}", exc_info=True)
        flash("Error sending message. Please try again.", "danger")

    return redirect(url_for('main.message_thread', user_id=recipient_id))


# --- Compose New Message (to any user) ---
@bp.route('/messages/compose', methods=['GET', 'POST'])
@login_required
def compose_message():
    """Compose a new message to any user."""
    if request.method == 'POST':
        username = request.form.get('recipient_username', '').strip()
        content = request.form.get('content', '').strip()

        if not username or not content:
            flash("Recipient and message content are required.", "warning")
            return redirect(url_for('main.compose_message'))

        # Find recipient by username
        recipient = db.session.scalar(
            select(User).where(User.username == username, User.is_deleted == False)
        )

        if not recipient:
            flash(f"User '{username}' not found.", "danger")
            return redirect(url_for('main.compose_message'))

        if recipient.id == current_user.id:
            flash("You cannot send messages to yourself.", "warning")
            return redirect(url_for('main.compose_message'))

        # Check if user is blocked
        is_blocked = db.session.scalar(
            select(BlockedUser.id)
            .where(
                BlockedUser.user_id == recipient.id,
                BlockedUser.blocked_user_id == current_user.id
            )
        )

        if is_blocked:
            flash("You cannot send messages to this user.", "warning")
            return redirect(url_for('main.compose_message'))

        # Create message
        new_message = Message(
            sender_id=current_user.id,
            recipient_id=recipient.id,
            content=InputSanitizer.sanitize_description(content, max_length=2000),
            created_at=datetime.utcnow()
        )

        db.session.add(new_message)

        try:
            db.session.commit()
            flash(f"Message sent to {recipient.username}!", "success")
            return redirect(url_for('main.message_thread', user_id=recipient.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error sending message: {e}", exc_info=True)
            flash("Error sending message. Please try again.", "danger")

    # GET - show compose form
    return render_template('compose_message.html', title='Compose Message')


# --- Delete Message (Soft Delete) ---
@bp.route('/messages/delete/<int:message_id>', methods=['POST'])
@login_required
def delete_message(message_id):
    """Soft delete a message (hide it for current user only)."""
    message = db.session.get(Message, message_id)

    if not message:
        flash("Message not found.", "danger")
        return redirect(url_for('main.messages'))

    # Check if user is sender or recipient
    if message.sender_id == current_user.id:
        message.sender_deleted = True
    elif message.recipient_id == current_user.id:
        message.recipient_deleted = True
    else:
        flash("You cannot delete this message.", "danger")
        return redirect(url_for('main.messages'))

    try:
        db.session.commit()
        flash("Message deleted.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting message: {e}", exc_info=True)
        flash("Error deleting message.", "danger")

    # Get the partner ID to redirect back to thread
    partner_id = message.recipient_id if message.sender_id == current_user.id else message.sender_id
    return redirect(url_for('main.message_thread', user_id=partner_id))


# --- Delete Message Thread (Soft Delete) ---
@bp.route('/messages/delete-thread/<int:partner_id>', methods=['POST'])
@login_required
def delete_message_thread(partner_id):
    """Soft delete entire message thread with a user (hide it for current user only)."""
    partner = db.session.get(User, partner_id)
    if not partner:
        flash("User not found.", "danger")
        return redirect(url_for('main.messages'))

    # Get all messages between these two users
    messages_to_delete = db.session.scalars(
        select(Message)
        .where(
            or_(
                and_(Message.sender_id == current_user.id, Message.recipient_id == partner_id),
                and_(Message.sender_id == partner_id, Message.recipient_id == current_user.id)
            )
        )
    ).all()

    # Mark messages as deleted for current user
    for message in messages_to_delete:
        if message.sender_id == current_user.id:
            message.sender_deleted = True
        elif message.recipient_id == current_user.id:
            message.recipient_deleted = True

    try:
        db.session.commit()
        flash(f"Conversation with {partner.username} deleted.", "success")
        current_app.logger.info(f"User {current_user.id} deleted thread with user {partner_id}")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting message thread: {e}", exc_info=True)
        flash("Error deleting conversation.", "danger")

    return redirect(url_for('main.messages'))


# --- Mark Alert as Read ---
@bp.route('/alerts/mark-read/<int:alert_id>', methods=['POST'])
@login_required
def mark_alert_read(alert_id):
    """Mark an alert as read."""
    alert = db.session.get(Alert, alert_id)

    if not alert or alert.user_id != current_user.id:
        return jsonify({'error': 'Alert not found'}), 404

    alert.is_read = True

    try:
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking alert as read: {e}", exc_info=True)
        return jsonify({'error': 'Server error'}), 500


# --- Mark All Alerts as Read ---
@bp.route('/alerts/mark-all-read', methods=['POST'])
@login_required
def mark_all_alerts_read():
    """Mark all alerts as read for current user."""
    db.session.execute(
        Alert.__table__.update()
        .where(Alert.user_id == current_user.id, Alert.is_read == False, Alert.is_deleted == False)
        .values(is_read=True)
    )

    try:
        db.session.commit()
        flash("All alerts marked as read.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking all alerts as read: {e}", exc_info=True)
        flash("Error marking alerts as read.", "danger")

    return redirect(url_for('main.messages', tab='alerts'))


# --- Delete Alert (Soft Delete) ---
@bp.route('/alerts/delete/<int:alert_id>', methods=['POST'])
@login_required
def delete_alert(alert_id):
    """Soft delete an alert (hide it for user)."""
    alert = db.session.get(Alert, alert_id)

    if not alert or alert.user_id != current_user.id:
        flash("Alert not found.", "danger")
        return redirect(url_for('main.messages', tab='alerts'))

    alert.is_deleted = True

    try:
        db.session.commit()
        # Clear session cache to prevent stale data on next request
        db.session.expire_all()
        flash("Alert deleted.", "success")
        current_app.logger.info(f"User {current_user.id} deleted alert {alert_id}")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting alert: {e}", exc_info=True)
        flash("Error deleting alert.", "danger")

    return redirect(url_for('main.messages', tab='alerts'))


# --- Delete All Alerts (Soft Delete) ---
@bp.route('/alerts/delete-all', methods=['POST'])
@login_required
def delete_all_alerts():
    """Soft delete all alerts for current user."""
    db.session.execute(
        Alert.__table__.update()
        .where(Alert.user_id == current_user.id, Alert.is_deleted == False)
        .values(is_deleted=True)
    )

    try:
        db.session.commit()
        # Clear session cache to prevent stale data on next request
        db.session.expire_all()
        flash("All alerts deleted.", "success")
        current_app.logger.info(f"User {current_user.id} deleted all alerts")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting all alerts: {e}", exc_info=True)
        flash("Error deleting alerts.", "danger")

    return redirect(url_for('main.messages', tab='alerts'))


# --- Block User ---
@bp.route('/user/block/<int:user_id>', methods=['POST'])
@login_required
def block_user(user_id):
    """Block a user from sending messages."""
    if user_id == current_user.id:
        flash("You cannot block yourself.", "warning")
        return redirect(url_for('main.messages'))

    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('main.messages'))

    # Check if already blocked
    existing_block = db.session.scalar(
        select(BlockedUser)
        .where(
            BlockedUser.user_id == current_user.id,
            BlockedUser.blocked_user_id == user_id
        )
    )

    if existing_block:
        flash(f"{user.username} is already blocked.", "info")
        return redirect(url_for('main.message_thread', user_id=user_id))

    # Create block
    new_block = BlockedUser(
        user_id=current_user.id,
        blocked_user_id=user_id
    )

    db.session.add(new_block)

    try:
        db.session.commit()
        flash(f"You have blocked {user.username}.", "success")
        current_app.logger.info(f"User {current_user.id} blocked user {user_id}")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error blocking user: {e}", exc_info=True)
        flash("Error blocking user.", "danger")

    return redirect(url_for('main.messages'))


# --- Unblock User ---
@bp.route('/user/unblock/<int:user_id>', methods=['POST'])
@login_required
def unblock_user(user_id):
    """Unblock a user."""
    block = db.session.scalar(
        select(BlockedUser)
        .where(
            BlockedUser.user_id == current_user.id,
            BlockedUser.blocked_user_id == user_id
        )
    )

    if not block:
        flash("User is not blocked.", "info")
        return redirect(url_for('main.messages'))

    user = db.session.get(User, user_id)

    db.session.delete(block)

    try:
        db.session.commit()
        flash(f"You have unblocked {user.username if user else 'this user'}.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error unblocking user: {e}", exc_info=True)
        flash("Error unblocking user.", "danger")

    return redirect(url_for('main.messages'))


# --- Search Users for Autocomplete ---
@bp.route('/api/search-users')
@login_required
def search_users():
    """Search for users by username for autocomplete."""
    query = request.args.get('q', '').strip()

    if not query or len(query) < 2:
        return jsonify([])

    # Search for users whose username starts with the query (case-insensitive)
    users = db.session.scalars(
        select(User)
        .where(
            User.username.ilike(f'{query}%'),
            User.is_deleted == False,
            User.id != current_user.id  # Exclude current user
        )
        .limit(10)
    ).all()

    # Return list of usernames
    results = [{'username': user.username, 'level': user.level} for user in users if user.username]

    return jsonify(results)
