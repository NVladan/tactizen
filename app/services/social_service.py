"""
Social Service - Handles all social interaction operations.

This service encapsulates social features logic that was previously in the User model.
"""

import logging
import secrets
import string
from decimal import Decimal
from sqlalchemy import select
from app.extensions import db

logger = logging.getLogger(__name__)


class SocialService:
    """Service for managing user social operations (friendship, referrals)."""

    @staticmethod
    def get_friendship_status(user, other_user_id):
        """
        Get friendship status with another user.

        Returns:
            str: 'friends', 'request_sent', 'request_received', 'none'
        """
        from app.models.friendship import Friendship, FriendshipStatus

        # Check if we sent a request to them
        sent_request = db.session.scalar(
            select(Friendship).where(
                Friendship.requester_id == user.id,
                Friendship.receiver_id == other_user_id
            )
        )

        if sent_request:
            if sent_request.status == FriendshipStatus.ACCEPTED:
                return 'friends'
            else:
                return 'request_sent'

        # Check if they sent a request to us
        received_request = db.session.scalar(
            select(Friendship).where(
                Friendship.requester_id == other_user_id,
                Friendship.receiver_id == user.id
            )
        )

        if received_request:
            if received_request.status == FriendshipStatus.ACCEPTED:
                return 'friends'
            else:
                return 'request_received'

        return 'none'

    @staticmethod
    def are_friends(user, other_user_id):
        """Quick check if users are friends (accepted friendship)."""
        return SocialService.get_friendship_status(user, other_user_id) == 'friends'

    @staticmethod
    def get_friends(user):
        """
        Get list of all accepted friends.

        Returns:
            list: List of User objects who are friends
        """
        from app.models.friendship import Friendship, FriendshipStatus
        from app.models.user import User

        # Get friendships where this user is the requester
        friends_as_requester = db.session.scalars(
            select(User).join(
                Friendship, Friendship.receiver_id == User.id
            ).where(
                Friendship.requester_id == user.id,
                Friendship.status == FriendshipStatus.ACCEPTED
            )
        ).all()

        # Get friendships where this user is the receiver
        friends_as_receiver = db.session.scalars(
            select(User).join(
                Friendship, Friendship.requester_id == User.id
            ).where(
                Friendship.receiver_id == user.id,
                Friendship.status == FriendshipStatus.ACCEPTED
            )
        ).all()

        # Combine and return unique friends
        return list(set(friends_as_requester + friends_as_receiver))

    @staticmethod
    def get_pending_friend_requests(user):
        """
        Get list of pending friend requests received by this user.

        Returns:
            list: List of Friendship objects with pending requests
        """
        from app.models.friendship import Friendship, FriendshipStatus

        return db.session.scalars(
            select(Friendship).where(
                Friendship.receiver_id == user.id,
                Friendship.status == FriendshipStatus.PENDING
            )
        ).all()

    @staticmethod
    def generate_referral_code(user):
        """Generate a unique referral code for the user."""
        from app.models.user import User

        if user.referral_code:
            return user.referral_code  # Already has a code

        # Generate a random 8-character alphanumeric code
        alphabet = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(secrets.choice(alphabet) for _ in range(8))
            # Check if code is unique
            existing = db.session.scalar(select(User).where(User.referral_code == code))
            if not existing:
                user.referral_code = code
                return code

    @staticmethod
    def check_and_award_referral_bonus(user):
        """
        Check if user has reached level 10 and award referral bonus to referrer.
        Should be called when user gains experience.

        Returns:
            bool: True if bonus was awarded
        """
        # Only award at level 10
        if user.level != 10:
            return False

        # Check if user was referred
        if not user.referred_by_relation:
            return False

        referral = user.referred_by_relation

        # Check if referral is still pending
        if not referral.is_pending:
            return False  # Already completed or cancelled

        # Award gold to referrer (increased from 5 to 10) with row-level locking
        referrer = referral.referrer
        gold_amount = Decimal('10.0')
        from app.services.currency_service import CurrencyService
        success, message, _ = CurrencyService.add_gold(
            referrer.id, gold_amount, f'Referral bonus for user {user.id}'
        )
        if not success:
            logger.error(f"Failed to add referral gold to user {referrer.id}: {message}")
            return False

        # Mark referral as completed
        referral.complete_referral(gold_amount)

        # Check recruiter achievements for the referrer
        from app.services.achievement_service import AchievementService
        try:
            AchievementService.check_recruiter(referrer)
        except Exception as e:
            logger.error(f"Error checking recruiter achievement: {e}")

        logger.info(f"Referral bonus awarded: User {referrer.id} received {gold_amount} gold for referring user {user.id}")
        return True

    @staticmethod
    def get_referrer(user):
        """Get the user who referred this user, if any."""
        if user.referred_by_relation:
            return user.referred_by_relation.referrer
        return None

    @staticmethod
    def get_referral_stats(user):
        """Get referral statistics for this user."""
        from app.models.referral import ReferralStatus

        total = user.referrals_made.count()
        pending = user.referrals_made.filter_by(status=ReferralStatus.PENDING).count()
        completed = user.referrals_made.filter_by(status=ReferralStatus.COMPLETED).count()

        return {
            'total': total,
            'pending': pending,
            'completed': completed,
            'gold_earned': sum(r.gold_awarded for r in user.referrals_made.filter_by(status=ReferralStatus.COMPLETED))
        }
