# app/main/friendship_routes.py

from flask import Blueprint, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app.models import db, User, Friendship, FriendshipStatus, Alert, AlertType, AlertPriority
from app.extensions import limiter
from sqlalchemy import or_

bp = Blueprint('friendship', __name__, url_prefix='/friendship')

@bp.route('/send_request/<int:user_id>', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_FRIEND_REQUEST", "15 per hour"))
def send_request(user_id):
    """Send a friend request to another user."""
    # Can't friend yourself
    if user_id == current_user.id:
        flash('You cannot send a friend request to yourself.', 'error')
        return redirect(request.referrer or url_for('main.index'))

    # Check if user exists
    target_user = db.session.get(User, user_id)
    if not target_user:
        flash('User not found.', 'error')
        return redirect(request.referrer or url_for('main.index'))

    # Check if friendship already exists (either direction)
    existing_friendship = db.session.scalar(
        db.select(Friendship).where(
            or_(
                (Friendship.requester_id == current_user.id) & (Friendship.receiver_id == user_id),
                (Friendship.requester_id == user_id) & (Friendship.receiver_id == current_user.id)
            )
        )
    )

    if existing_friendship:
        if existing_friendship.status == FriendshipStatus.ACCEPTED:
            flash('You are already friends with this user.', 'info')
        else:
            flash('A friend request is already pending.', 'info')
        return redirect(request.referrer or url_for('main.index'))

    # Create new friend request
    friendship = Friendship(
        requester_id=current_user.id,
        receiver_id=user_id,
        status=FriendshipStatus.PENDING
    )
    db.session.add(friendship)

    # Create alert for the receiver
    alert = Alert(
        user_id=user_id,
        alert_type=AlertType.FRIEND_REQUEST,
        priority=AlertPriority.NORMAL,
        title='New Friend Request',
        content=f'{current_user.username or current_user.wallet_address[:10]} wants to be your friend.',
        link_url=url_for('main.view_profile', username=current_user.username or current_user.wallet_address),
        link_text='View Profile',
        alert_data={'friendship_id': friendship.id, 'requester_id': current_user.id}
    )
    db.session.add(alert)

    db.session.commit()

    flash(f'Friend request sent to {target_user.username or target_user.wallet_address[:10]}.', 'success')
    return redirect(request.referrer or url_for('main.profile', username=target_user.username or target_user.wallet_address))


@bp.route('/accept/<int:friendship_id>', methods=['POST'])
@login_required
def accept_request(friendship_id):
    """Accept a friend request."""
    friendship = db.session.get(Friendship, friendship_id)

    if not friendship:
        flash('Friend request not found.', 'error')
        return redirect(request.referrer or url_for('main.index'))

    # Verify this user is the receiver
    if friendship.receiver_id != current_user.id:
        flash('You cannot accept this friend request.', 'error')
        return redirect(request.referrer or url_for('main.index'))

    # Check if already accepted
    if friendship.status == FriendshipStatus.ACCEPTED:
        flash('You are already friends with this user.', 'info')
        return redirect(request.referrer or url_for('main.index'))

    # Accept the friendship
    friendship.accept()

    # Create alert for the requester
    alert = Alert(
        user_id=friendship.requester_id,
        alert_type=AlertType.FRIEND_REQUEST_ACCEPTED,
        priority=AlertPriority.NORMAL,
        title='Friend Request Accepted',
        content=f'{current_user.username or current_user.wallet_address[:10]} accepted your friend request.',
        link_url=url_for('main.view_profile', username=current_user.username or current_user.wallet_address),
        link_text='View Profile'
    )
    db.session.add(alert)

    db.session.commit()

    # Check social achievements for both users
    from app.services.achievement_service import AchievementService
    try:
        AchievementService.check_social_butterfly(current_user)
        AchievementService.check_social_butterfly(friendship.requester)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Error checking social achievement: {e}")

    requester = friendship.requester
    flash(f'You are now friends with {requester.username or requester.wallet_address[:10]}.', 'success')
    return redirect(request.referrer or url_for('main.index'))


@bp.route('/deny/<int:friendship_id>', methods=['POST'])
@login_required
def deny_request(friendship_id):
    """Deny/reject a friend request."""
    friendship = db.session.get(Friendship, friendship_id)

    if not friendship:
        flash('Friend request not found.', 'error')
        return redirect(request.referrer or url_for('main.index'))

    # Verify this user is the receiver
    if friendship.receiver_id != current_user.id:
        flash('You cannot deny this friend request.', 'error')
        return redirect(request.referrer or url_for('main.index'))

    # Delete the friend request
    db.session.delete(friendship)
    db.session.commit()

    flash('Friend request denied.', 'info')
    return redirect(request.referrer or url_for('main.index'))


@bp.route('/unfriend/<int:user_id>', methods=['POST'])
@login_required
def unfriend(user_id):
    """Remove a friendship."""
    # Find the friendship (either direction)
    friendship = db.session.scalar(
        db.select(Friendship).where(
            or_(
                (Friendship.requester_id == current_user.id) & (Friendship.receiver_id == user_id),
                (Friendship.requester_id == user_id) & (Friendship.receiver_id == current_user.id)
            ),
            Friendship.status == FriendshipStatus.ACCEPTED
        )
    )

    if not friendship:
        flash('Friendship not found.', 'error')
        return redirect(request.referrer or url_for('main.index'))

    # Get the other user for the flash message
    other_user_id = user_id
    other_user = db.session.get(User, other_user_id)

    # Delete the friendship
    db.session.delete(friendship)
    db.session.commit()

    flash(f'You are no longer friends with {other_user.username or other_user.wallet_address[:10]}.', 'info')
    return redirect(request.referrer or url_for('main.index'))


@bp.route('/cancel/<int:friendship_id>', methods=['POST'])
@login_required
def cancel_request(friendship_id):
    """Cancel a sent friend request."""
    friendship = db.session.get(Friendship, friendship_id)

    if not friendship:
        flash('Friend request not found.', 'error')
        return redirect(request.referrer or url_for('main.index'))

    # Verify this user is the requester
    if friendship.requester_id != current_user.id:
        flash('You cannot cancel this friend request.', 'error')
        return redirect(request.referrer or url_for('main.index'))

    # Delete the friend request
    db.session.delete(friendship)
    db.session.commit()

    flash('Friend request cancelled.', 'info')
    return redirect(request.referrer or url_for('main.index'))
