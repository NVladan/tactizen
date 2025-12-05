# app/alert_helpers.py
# Helper functions for creating and sending system alerts

from app.extensions import db
from app.models import Alert, User
from app.models.messaging import AlertType, AlertPriority
from datetime import datetime
from flask import current_app
import logging

logger = logging.getLogger(__name__)


def create_alert(user_id, alert_type, title, content, priority=AlertPriority.NORMAL,
                alert_data=None, link_url=None, link_text=None):
    """
    Core function to create an alert for a user.

    Args:
        user_id: ID of the user to receive the alert
        alert_type: AlertType enum value
        title: Alert title
        content: Alert message content
        priority: AlertPriority enum value (default: NORMAL)
        alert_data: Optional dict with additional data
        link_url: Optional URL for action button
        link_text: Optional text for action button

    Returns:
        bool: True if alert created successfully, False otherwise
    """
    try:
        alert = Alert(
            user_id=user_id,
            alert_type=alert_type,
            priority=priority,
            title=title,
            content=content,
            alert_data=alert_data or {},
            link_url=link_url,
            link_text=link_text,
            is_deleted=False,  # Explicitly set to ensure new alerts are not deleted
            created_at=datetime.utcnow()
        )

        db.session.add(alert)
        db.session.commit()

        logger.info(f"Alert created for user {user_id}: {alert_type.value} - {title}")
        return True

    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create alert for user {user_id}: {e}", exc_info=True)
        return False


def send_level_up_alert(user_id, new_level):
    """
    Send a level up alert to a user.

    Args:
        user_id: The ID of the user who leveled up
        new_level: The new level achieved

    Returns:
        bool: True if alert sent successfully
    """
    title = f"Level Up! You reached Level {new_level}"
    content = f"Congratulations! You've advanced to Level {new_level}. You earned 1 Gold as a reward."

    return create_alert(
        user_id=user_id,
        alert_type=AlertType.LEVEL_UP,
        priority=AlertPriority.NORMAL,
        title=title,
        content=content,
        alert_data={'new_level': new_level, 'gold_reward': 1}
    )


def send_house_expired_alert(user_id, house_name=None):
    """
    Send a house expired alert to a user.

    Args:
        user_id: The ID of the user whose house expired
        house_name: Optional name of the house

    Returns:
        bool: True if alert sent successfully
    """
    house_display = house_name if house_name else "Your house"
    title = "House Expired"
    content = f"{house_display} has expired. You need to activate a new house from your storage."

    from flask import url_for
    return create_alert(
        user_id=user_id,
        alert_type=AlertType.HOUSE_EXPIRED,
        priority=AlertPriority.IMPORTANT,
        title=title,
        content=content,
        alert_data={'house_name': house_name},
        link_url=url_for('main.storage', _external=False),
        link_text="Go to Storage"
    )


def send_election_win_alert(user_id, party_name, vote_count, position="Party President"):
    """
    Send an election win alert to a user.

    Args:
        user_id: The ID of the user who won the election
        party_name: Name of the party
        vote_count: Number of votes received
        position: The position won (default: "Party President")

    Returns:
        bool: True if alert sent successfully
    """
    user = db.session.get(User, user_id)
    if not user:
        logger.error(f"User {user_id} not found for election win alert")
        return False

    title = "Congratulations! You Won the Election!"
    content = f"You have been elected as {position} of {party_name} with {vote_count} votes! Congratulations on your victory."

    # Build link URL manually to avoid url_for issues outside request context
    link_url = f"/party/{user.party_id}" if user.party_id else None

    return create_alert(
        user_id=user_id,
        alert_type=AlertType.ELECTION_WIN,
        priority=AlertPriority.IMPORTANT,
        title=title,
        content=content,
        alert_data={
            'party_name': party_name,
            'vote_count': vote_count,
            'position': position
        },
        link_url=link_url,
        link_text="View Party"
    )


def send_admin_announcement(user_ids, title, content, priority=AlertPriority.NORMAL,
                           link_url=None, link_text=None):
    """
    Send an admin announcement alert to one or multiple users.

    Args:
        user_ids: Single user ID (int) or list of user IDs
        title: Alert title
        content: Alert content/message
        priority: AlertPriority enum (NORMAL, IMPORTANT, URGENT)
        link_url: Optional URL for the alert button
        link_text: Optional text for the link button

    Returns:
        int: Number of users who received the alert
    """
    if isinstance(user_ids, int):
        user_ids = [user_ids]

    success_count = 0

    for user_id in user_ids:
        user = db.session.get(User, user_id)
        if not user:
            logger.warning(f"User {user_id} not found for admin announcement")
            continue

        if create_alert(
            user_id=user_id,
            alert_type=AlertType.ADMIN_ANNOUNCEMENT,
            priority=priority,
            title=title,
            content=content,
            alert_data={'is_admin_announcement': True},
            link_url=link_url,
            link_text=link_text
        ):
            success_count += 1

    logger.info(f"Admin announcement sent to {success_count} users: {title}")
    return success_count


def send_announcement_to_all_users(title, content, priority=AlertPriority.NORMAL,
                                  link_url=None, link_text=None):
    """
    Send an admin announcement to all active users.

    Args:
        title: Alert title
        content: Alert content/message
        priority: AlertPriority enum (NORMAL, IMPORTANT, URGENT)
        link_url: Optional URL for the alert button
        link_text: Optional text for the link button

    Returns:
        int: Number of users who received the alert
    """
    try:
        from sqlalchemy import select

        # Get all active users (not deleted, not banned)
        active_users = db.session.scalars(
            select(User.id).where(
                User.is_deleted == False,
                User.is_banned == False
            )
        ).all()

        return send_admin_announcement(
            user_ids=active_users,
            title=title,
            content=content,
            priority=priority,
            link_url=link_url,
            link_text=link_text
        )

    except Exception as e:
        logger.error(f"Error sending announcement to all users: {e}", exc_info=True)
        return 0


def send_war_declared_alert(defender_country_id, attacker_country_name, war_id):
    """
    Send war declaration alert to the president and ministers of the defending country.

    Args:
        defender_country_id: ID of the country that was declared war upon
        attacker_country_name: Name of the attacking country
        war_id: ID of the war

    Returns:
        int: Number of alerts sent
    """
    from app.models import CountryPresident, Minister

    try:
        recipient_ids = []

        # Get current president of defending country
        current_president = db.session.scalar(
            db.select(CountryPresident)
            .where(CountryPresident.country_id == defender_country_id)
            .where(CountryPresident.is_current == True)
        )

        if current_president:
            recipient_ids.append(current_president.user_id)

        # Get all active ministers of defending country
        active_ministers = db.session.scalars(
            db.select(Minister)
            .where(Minister.country_id == defender_country_id)
            .where(Minister.is_active == True)
        ).all()

        for minister in active_ministers:
            if minister.user_id not in recipient_ids:
                recipient_ids.append(minister.user_id)

        if not recipient_ids:
            logger.warning(f"No president or ministers found for country {defender_country_id} to send war alert")
            return 0

        title = "War Declared!"
        content = f"{attacker_country_name} has declared war on your country! Prepare your defenses and rally your citizens."
        link_url = f"/war/{war_id}"

        success_count = 0
        for user_id in recipient_ids:
            if create_alert(
                user_id=user_id,
                alert_type=AlertType.WAR_DECLARED,
                priority=AlertPriority.URGENT,
                title=title,
                content=content,
                alert_data={
                    'attacker_country_name': attacker_country_name,
                    'war_id': war_id
                },
                link_url=link_url,
                link_text="View War"
            ):
                success_count += 1

        logger.info(f"War declaration alert sent to {success_count} government officials of country {defender_country_id}")
        return success_count

    except Exception as e:
        logger.error(f"Error sending war declaration alert: {e}", exc_info=True)
        return 0
