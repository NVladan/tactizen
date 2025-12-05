"""
Achievement Service - Handles achievement tracking and unlocking.

This service checks user progress and awards achievements when milestones are reached.
"""

import logging
from datetime import date, timedelta
from app.time_helpers import get_allocation_date
from decimal import Decimal
from sqlalchemy import select
from app.extensions import db
from app.models.achievement import Achievement, UserAchievement, AchievementProgress, AchievementCategory
from app.models.messaging import Alert, AlertType, AlertPriority

logger = logging.getLogger(__name__)


class AchievementService:
    """Service for managing user achievements."""

    ACHIEVEMENT_CODES = {
        'HARD_WORKER': 'hard_worker_30',
        'TRAINING_HARD': 'training_hard_30',
        'QUICK_LEARNER': 'quick_learner_30',
        'ENTREPRENEUR': 'entrepreneur_5',
        'EXPLORER': 'explorer_all_countries',
    }

    @staticmethod
    def has_achievement(user, achievement_code):
        """Check if user has already unlocked an achievement."""
        achievement = db.session.scalar(
            select(Achievement).where(Achievement.code == achievement_code)
        )
        if not achievement:
            return False

        user_achievement = db.session.scalar(
            select(UserAchievement).where(
                UserAchievement.user_id == user.id,
                UserAchievement.achievement_id == achievement.id
            )
        )
        return user_achievement is not None

    @staticmethod
    def get_or_create_progress(user, achievement_code):
        """Get or create achievement progress tracker for user."""
        progress = db.session.scalar(
            select(AchievementProgress).where(
                AchievementProgress.user_id == user.id,
                AchievementProgress.achievement_code == achievement_code
            )
        )

        if not progress:
            progress = AchievementProgress(
                user_id=user.id,
                achievement_code=achievement_code,
                current_value=0,
                current_streak=0,
                best_streak=0
            )
            db.session.add(progress)
            db.session.flush()

        return progress

    @staticmethod
    def update_streak(user, achievement_code, activity_date=None):
        """
        Update streak for daily activities.

        Args:
            user: User instance
            achievement_code: Code of the achievement to track
            activity_date: Date of activity (defaults to today)

        Returns:
            tuple: (current_streak, achievement_unlocked)
        """
        if activity_date is None:
            activity_date = get_allocation_date()

        progress = AchievementService.get_or_create_progress(user, achievement_code)

        if progress.last_activity_date:
            days_diff = (activity_date - progress.last_activity_date).days

            if days_diff == 0:
                return progress.current_streak, False
            elif days_diff == 1:
                progress.current_streak += 1
            else:
                progress.current_streak = 1
        else:
            progress.current_streak = 1

        progress.last_activity_date = activity_date
        progress.current_value = progress.current_streak

        if progress.current_streak > progress.best_streak:
            progress.best_streak = progress.current_streak

        achievement_unlocked = AchievementService._check_and_unlock(user, achievement_code, progress.current_streak)

        return progress.current_streak, achievement_unlocked

    @staticmethod
    def increment_count(user, achievement_code, increment=1):
        """
        Increment a counter-based achievement.

        Args:
            user: User instance
            achievement_code: Code of the achievement to track
            increment: Amount to increment by

        Returns:
            tuple: (current_value, achievement_unlocked)
        """
        progress = AchievementService.get_or_create_progress(user, achievement_code)

        progress.current_value += increment

        achievement_unlocked = AchievementService._check_and_unlock(user, achievement_code, progress.current_value)

        return progress.current_value, achievement_unlocked

    @staticmethod
    def _check_and_unlock(user, achievement_code, current_value):
        """
        Check if achievement should be unlocked and unlock it.

        Args:
            user: User instance
            achievement_code: Code of the achievement
            current_value: Current progress value

        Returns:
            bool: True if achievement was unlocked, False otherwise
        """
        if AchievementService.has_achievement(user, achievement_code):
            return False

        achievement = db.session.scalar(
            select(Achievement).where(
                Achievement.code == achievement_code,
                Achievement.is_active == True
            )
        )

        if not achievement:
            logger.warning(f"Achievement {achievement_code} not found or inactive")
            return False

        if current_value >= achievement.requirement_value:
            return AchievementService.unlock_achievement(user, achievement)

        return False

    @staticmethod
    def unlock_achievement(user, achievement):
        """
        Unlock an achievement for a user and award gold + free NFT mints.

        Args:
            user: User instance
            achievement: Achievement instance

        Returns:
            bool: True if unlocked successfully
        """
        existing = db.session.scalar(
            select(UserAchievement).where(
                UserAchievement.user_id == user.id,
                UserAchievement.achievement_id == achievement.id
            )
        )

        if existing:
            logger.warning(f"User {user.id} already has achievement {achievement.code}")
            return False

        user_achievement = UserAchievement(
            user_id=user.id,
            achievement_id=achievement.id,
            gold_awarded=achievement.gold_reward
        )
        db.session.add(user_achievement)

        # Award gold with row-level locking
        from app.services.currency_service import CurrencyService
        success, message, _ = CurrencyService.add_gold(
            user.id, Decimal(str(achievement.gold_reward)), f'Achievement reward: {achievement.code}'
        )
        if not success:
            logger.error(f"Failed to add achievement gold to user {user.id}: {message}")
            return False

        # Award free NFT mints if achievement has them
        nft_reward = getattr(achievement, 'free_nft_reward', 0) or 0
        if nft_reward > 0:
            user.free_nft_mints += nft_reward

        # Build reward message
        rewards = [f'{achievement.gold_reward} gold']
        if nft_reward > 0:
            rewards.append(f'{nft_reward} free NFT mint{"s" if nft_reward > 1 else ""}')
        reward_text = ' and '.join(rewards)

        alert = Alert(
            user_id=user.id,
            alert_type=AlertType.LEVEL_UP.value,
            priority=AlertPriority.IMPORTANT.value,
            title=f'Achievement Unlocked: {achievement.name}!',
            content=f'You earned the "{achievement.name}" achievement and received {reward_text}!',
            link_url='/profile/achievements',
            link_text='View Achievements'
        )
        db.session.add(alert)

        logger.info(f"User {user.id} unlocked achievement {achievement.code}, awarded {achievement.gold_reward} gold, {nft_reward} free NFT mints")

        return True

    @staticmethod
    def get_user_achievements(user):
        """Get all achievements unlocked by user."""
        user_achievements = db.session.scalars(
            select(UserAchievement)
            .where(UserAchievement.user_id == user.id)
            .join(UserAchievement.achievement)
            .order_by(UserAchievement.unlocked_at.desc())
        ).all()

        return user_achievements

    @staticmethod
    def get_achievement_stats(user):
        """Get achievement statistics for user."""
        total_achievements = db.session.scalar(
            select(db.func.count(Achievement.id)).where(Achievement.is_active == True)
        )

        unlocked_count = db.session.scalar(
            select(db.func.count(UserAchievement.id)).where(UserAchievement.user_id == user.id)
        )

        total_gold_earned = db.session.scalar(
            select(db.func.sum(UserAchievement.gold_awarded)).where(UserAchievement.user_id == user.id)
        ) or 0

        return {
            'total': total_achievements,
            'unlocked': unlocked_count or 0,
            'locked': (total_achievements or 0) - (unlocked_count or 0),
            'total_gold_earned': total_gold_earned,
            'completion_percentage': round((unlocked_count or 0) / (total_achievements or 1) * 100, 1)
        }

    @staticmethod
    def get_all_achievements_with_progress(user):
        """Get all achievements with user's progress."""
        achievements = db.session.scalars(
            select(Achievement)
            .where(Achievement.is_active == True)
            .order_by(Achievement.category, Achievement.name)
        ).all()

        # Pre-calculate live values for achievements that don't store progress
        live_values = AchievementService._get_live_progress_values(user)

        result = []
        for achievement in achievements:
            user_achievement = db.session.scalar(
                select(UserAchievement).where(
                    UserAchievement.user_id == user.id,
                    UserAchievement.achievement_id == achievement.id
                )
            )

            progress = db.session.scalar(
                select(AchievementProgress).where(
                    AchievementProgress.user_id == user.id,
                    AchievementProgress.achievement_code == achievement.code
                )
            )

            # Use live value if available, otherwise use stored progress
            current_value = live_values.get(achievement.code, progress.current_value if progress else 0)

            result.append({
                'achievement': achievement,
                'unlocked': user_achievement is not None,
                'unlocked_at': user_achievement.unlocked_at if user_achievement else None,
                'current_value': current_value,
                'requirement': achievement.requirement_value,
                'progress_percentage': min(100, round(current_value / achievement.requirement_value * 100, 1))
            })

        return result

    @staticmethod
    def _get_live_progress_values(user):
        """Get live progress values for achievements that query real data instead of stored progress."""
        from app.models.friendship import Friendship, FriendshipStatus
        from app.models.referral import Referral, ReferralStatus
        from app.models.company import Company
        from app.models import Country
        from sqlalchemy import or_

        live_values = {}

        # Company count for entrepreneur achievements
        company_count = db.session.scalar(
            select(db.func.count(Company.id)).where(
                Company.owner_id == user.id,
                Company.is_deleted == False
            )
        ) or 0
        live_values['entrepreneur_1'] = company_count
        live_values['entrepreneur_5'] = company_count
        live_values['entrepreneur_10'] = company_count

        # Friend count for social_butterfly achievements
        friend_count = db.session.scalar(
            select(db.func.count(Friendship.id)).where(
                or_(
                    Friendship.requester_id == user.id,
                    Friendship.receiver_id == user.id
                ),
                Friendship.status == FriendshipStatus.ACCEPTED
            )
        ) or 0
        live_values['social_butterfly_10'] = friend_count
        live_values['social_butterfly_50'] = friend_count

        # Completed referrals for recruiter achievements
        completed_referrals = db.session.scalar(
            select(db.func.count(Referral.id)).where(
                Referral.referrer_id == user.id,
                Referral.status == ReferralStatus.COMPLETED
            )
        ) or 0
        live_values['recruiter_10'] = completed_referrals
        live_values['recruiter_100'] = completed_referrals
        live_values['recruiter_1000'] = completed_referrals

        # Countries visited for explorer achievement
        total_countries = db.session.scalar(
            select(db.func.count(Country.id)).where(Country.is_deleted == False)
        ) or 1
        countries_visited = len(user.visited_countries) if hasattr(user, 'visited_countries') else 0
        live_values['explorer'] = countries_visited
        live_values['explorer_all_countries'] = countries_visited

        # Streak achievements - all tiers share the same streak from base achievement
        # Work streak (stored under hard_worker_7)
        work_progress = db.session.scalar(
            select(AchievementProgress).where(
                AchievementProgress.user_id == user.id,
                AchievementProgress.achievement_code == 'hard_worker_7'
            )
        )
        work_streak = work_progress.current_streak if work_progress else 0
        live_values['hard_worker_7'] = work_streak
        live_values['hard_worker_30'] = work_streak
        live_values['hard_worker_100'] = work_streak

        # Training streak (stored under training_hard_7)
        training_progress = db.session.scalar(
            select(AchievementProgress).where(
                AchievementProgress.user_id == user.id,
                AchievementProgress.achievement_code == 'training_hard_7'
            )
        )
        training_streak = training_progress.current_streak if training_progress else 0
        live_values['training_hard_7'] = training_streak
        live_values['training_hard_30'] = training_streak
        live_values['training_hard_100'] = training_streak

        # Study streak (stored under quick_learner_7)
        study_progress = db.session.scalar(
            select(AchievementProgress).where(
                AchievementProgress.user_id == user.id,
                AchievementProgress.achievement_code == 'quick_learner_7'
            )
        )
        study_streak = study_progress.current_streak if study_progress else 0
        live_values['quick_learner_7'] = study_streak
        live_values['quick_learner_30'] = study_streak
        live_values['quick_learner_100'] = study_streak

        # Battle Hero count for combat achievements
        from app.models.battle import BattleHero
        battle_hero_count = db.session.scalar(
            select(db.func.count(BattleHero.id)).where(
                BattleHero.user_id == user.id
            )
        ) or 0
        live_values['battle_hero_10'] = battle_hero_count
        live_values['battle_hero_100'] = battle_hero_count

        return live_values

    @staticmethod
    def track_work_streak(user):
        """Track daily work streak and check for all Hard Worker achievements (7, 30, 100 days)."""
        # Update streak using any work achievement code (they all track same streak)
        current_streak, _ = AchievementService.update_streak(user, 'hard_worker_7')

        # Check all work achievement tiers
        achievement_unlocked = False
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'hard_worker_7', current_streak)
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'hard_worker_30', current_streak)
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'hard_worker_100', current_streak)

        return current_streak, achievement_unlocked

    @staticmethod
    def track_training_streak(user):
        """Track daily training streak and check for all Training Hard achievements (7, 30, 100 days)."""
        # Update streak using any training achievement code (they all track same streak)
        current_streak, _ = AchievementService.update_streak(user, 'training_hard_7')

        # Check all training achievement tiers
        achievement_unlocked = False
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'training_hard_7', current_streak)
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'training_hard_30', current_streak)
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'training_hard_100', current_streak)

        return current_streak, achievement_unlocked

    @staticmethod
    def track_study_streak(user):
        """Track daily study streak and check for all Quick Learner achievements (7, 30, 100 days)."""
        # Update streak using any study achievement code (they all track same streak)
        current_streak, _ = AchievementService.update_streak(user, 'quick_learner_7')

        # Check all study achievement tiers
        achievement_unlocked = False
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'quick_learner_7', current_streak)
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'quick_learner_30', current_streak)
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'quick_learner_100', current_streak)

        return current_streak, achievement_unlocked

    @staticmethod
    def check_entrepreneur(user):
        """Check if user has unlocked Entrepreneur achievements (own 1, 5, or 10 companies)."""
        from app.models.company import Company

        company_count = db.session.scalar(
            select(db.func.count(Company.id)).where(
                Company.owner_id == user.id,
                Company.is_deleted == False
            )
        )

        # Check all entrepreneur achievement tiers
        achievement_unlocked = False
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'entrepreneur_1', company_count)
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'entrepreneur_5', company_count)
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'entrepreneur_10', company_count)

        return achievement_unlocked

    @staticmethod
    def check_social_butterfly(user):
        """Check if user has unlocked Social Butterfly achievements (10 or 50 friends)."""
        from app.models.friendship import Friendship, FriendshipStatus

        # Count accepted friendships (where user is either requester or receiver)
        friend_count = db.session.scalar(
            select(db.func.count(Friendship.id)).where(
                db.or_(
                    Friendship.requester_id == user.id,
                    Friendship.receiver_id == user.id
                ),
                Friendship.status == FriendshipStatus.ACCEPTED
            )
        )

        # Check all social achievement tiers
        achievement_unlocked = False
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'social_butterfly_10', friend_count)
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'social_butterfly_50', friend_count)

        return achievement_unlocked

    @staticmethod
    def check_recruiter(user):
        """Check if user has unlocked Recruiter achievements (10, 100, 1000 referrals at level 10)."""
        from app.models.referral import Referral, ReferralStatus

        # Count completed referrals (referees who reached level 10)
        completed_referrals = db.session.scalar(
            select(db.func.count(Referral.id)).where(
                Referral.referrer_id == user.id,
                Referral.status == ReferralStatus.COMPLETED
            )
        )

        # Check all recruiter achievement tiers
        achievement_unlocked = False
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'recruiter_10', completed_referrals)
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'recruiter_100', completed_referrals)
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'recruiter_1000', completed_referrals)

        return achievement_unlocked

    @staticmethod
    def check_explorer(user):
        """Check if user has visited all countries."""
        from app.models.location import Country

        total_countries = db.session.scalar(
            select(db.func.count(Country.id))
        )

        # TODO: Track countries visited (would need new table)
        # For now, this is a placeholder
        return False

    @staticmethod
    def check_battle_hero(user):
        """Check if user has unlocked Battle Hero achievements (10 or 100 medals)."""
        from app.models.battle import BattleHero

        # Count battle hero awards
        battle_hero_count = db.session.scalar(
            select(db.func.count(BattleHero.id)).where(
                BattleHero.user_id == user.id
            )
        ) or 0

        # Check all battle hero achievement tiers
        achievement_unlocked = False
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'battle_hero_10', battle_hero_count)
        achievement_unlocked |= AchievementService._check_and_unlock(user, 'battle_hero_100', battle_hero_count)

        return achievement_unlocked
