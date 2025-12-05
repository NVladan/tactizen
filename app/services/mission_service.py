"""
Mission Service - Handles mission tracking, progress, and rewards.

This service manages daily missions, weekly challenges, and tutorial quests.
"""

import logging
import random
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, and_, or_
from app.extensions import db
from app.models.mission import Mission, UserMission, MissionType, MissionCategory
from app.models.messaging import Alert, AlertType, AlertPriority
from app.time_helpers import get_allocation_date, get_game_day_start, get_week_start, get_next_week_start

logger = logging.getLogger(__name__)

# Configuration
DAILY_MISSIONS_COUNT = 5
WEEKLY_MISSIONS_COUNT = 3


class MissionService:
    """Service for managing user missions."""

    @staticmethod
    def get_active_missions(user):
        """
        Get all active missions for a user, organized by type.

        Returns:
            dict: {
                'daily': [UserMission, ...],
                'weekly': [UserMission, ...],
                'tutorial': [UserMission, ...]
            }
        """
        now = datetime.utcnow()

        # Get all non-claimed missions that haven't expired
        user_missions = db.session.scalars(
            select(UserMission)
            .where(
                UserMission.user_id == user.id,
                UserMission.is_claimed == False,
                or_(
                    UserMission.expires_at.is_(None),
                    UserMission.expires_at > now
                )
            )
            .join(UserMission.mission)
            .order_by(Mission.mission_type, Mission.name)
        ).all()

        result = {
            'daily': [],
            'weekly': [],
            'tutorial': []
        }

        for um in user_missions:
            mission_type = um.mission.mission_type
            if mission_type == MissionType.DAILY.value:
                result['daily'].append(um)
            elif mission_type == MissionType.WEEKLY.value:
                result['weekly'].append(um)
            elif mission_type == MissionType.TUTORIAL.value:
                result['tutorial'].append(um)

        return result

    @staticmethod
    def get_completed_unclaimed(user):
        """Get all completed missions that haven't been claimed yet."""
        now = datetime.utcnow()

        return db.session.scalars(
            select(UserMission)
            .where(
                UserMission.user_id == user.id,
                UserMission.is_completed == True,
                UserMission.is_claimed == False,
                or_(
                    UserMission.expires_at.is_(None),
                    UserMission.expires_at > now
                )
            )
            .join(UserMission.mission)
            .order_by(Mission.mission_type, UserMission.completed_at)
        ).all()

    @staticmethod
    def assign_daily_missions(user):
        """
        Assign daily missions to a user.
        Randomly selects missions from the daily pool.

        Returns:
            list: List of newly assigned UserMission objects
        """
        now = datetime.utcnow()

        # Check if user already has daily missions for today
        game_day_start = get_game_day_start()
        next_day_start = game_day_start + timedelta(days=1)

        existing_daily = db.session.scalar(
            select(db.func.count(UserMission.id))
            .where(
                UserMission.user_id == user.id,
                UserMission.assigned_at >= game_day_start,
                UserMission.assigned_at < next_day_start
            )
            .join(UserMission.mission)
            .where(Mission.mission_type == MissionType.DAILY.value)
        )

        if existing_daily and existing_daily > 0:
            logger.debug(f"User {user.id} already has daily missions for today")
            return []

        # Get available daily missions
        daily_missions = db.session.scalars(
            select(Mission)
            .where(
                Mission.mission_type == MissionType.DAILY.value,
                Mission.is_active == True
            )
        ).all()

        if not daily_missions:
            logger.warning("No daily missions available in database")
            return []

        # Randomly select missions
        selected = random.sample(
            daily_missions,
            min(DAILY_MISSIONS_COUNT, len(daily_missions))
        )

        # Create UserMission records
        assigned = []
        for mission in selected:
            user_mission = UserMission(
                user_id=user.id,
                mission_id=mission.id,
                current_progress=0,
                is_completed=False,
                is_claimed=False,
                assigned_at=now,
                expires_at=next_day_start  # Expires at next game day reset
            )
            db.session.add(user_mission)
            assigned.append(user_mission)

        db.session.flush()
        logger.info(f"Assigned {len(assigned)} daily missions to user {user.id}")

        return assigned

    @staticmethod
    def assign_weekly_missions(user):
        """
        Assign weekly missions to a user.
        Randomly selects missions from the weekly pool.
        Weekly missions run Monday 9 AM CET to next Monday 9 AM CET.

        Returns:
            list: List of newly assigned UserMission objects
        """
        now = datetime.utcnow()

        # Calculate week boundaries using time_helpers (Monday 9 AM CET)
        week_start = get_week_start()
        next_week_start = get_next_week_start()

        # Check if user already has weekly missions for this week
        existing_weekly = db.session.scalar(
            select(db.func.count(UserMission.id))
            .where(
                UserMission.user_id == user.id,
                UserMission.assigned_at >= week_start,
                UserMission.assigned_at < next_week_start
            )
            .join(UserMission.mission)
            .where(Mission.mission_type == MissionType.WEEKLY.value)
        )

        if existing_weekly and existing_weekly > 0:
            logger.debug(f"User {user.id} already has weekly missions for this week")
            return []

        # Get available weekly missions
        weekly_missions = db.session.scalars(
            select(Mission)
            .where(
                Mission.mission_type == MissionType.WEEKLY.value,
                Mission.is_active == True
            )
        ).all()

        if not weekly_missions:
            logger.warning("No weekly missions available in database")
            return []

        # Randomly select missions
        selected = random.sample(
            weekly_missions,
            min(WEEKLY_MISSIONS_COUNT, len(weekly_missions))
        )

        # Create UserMission records
        assigned = []
        for mission in selected:
            user_mission = UserMission(
                user_id=user.id,
                mission_id=mission.id,
                current_progress=0,
                is_completed=False,
                is_claimed=False,
                assigned_at=now,
                expires_at=next_week_start  # Expires at next Monday 9 AM CET
            )
            db.session.add(user_mission)
            assigned.append(user_mission)

        db.session.flush()
        logger.info(f"Assigned {len(assigned)} weekly missions to user {user.id}")

        return assigned

    @staticmethod
    def get_or_assign_tutorial_missions(user):
        """
        Get tutorial missions for a user, assigning them if needed.
        Tutorial missions are assigned once and persist until completed.

        Returns:
            list: List of UserMission objects for tutorial missions
        """
        # Check existing tutorial missions
        existing_tutorial = db.session.scalars(
            select(UserMission)
            .where(UserMission.user_id == user.id)
            .join(UserMission.mission)
            .where(Mission.mission_type == MissionType.TUTORIAL.value)
            .order_by(Mission.tutorial_order)
        ).all()

        if existing_tutorial:
            return existing_tutorial

        # Get all tutorial missions ordered by tutorial_order
        tutorial_missions = db.session.scalars(
            select(Mission)
            .where(
                Mission.mission_type == MissionType.TUTORIAL.value,
                Mission.is_active == True
            )
            .order_by(Mission.tutorial_order)
        ).all()

        if not tutorial_missions:
            logger.warning("No tutorial missions available in database")
            return []

        # Assign all tutorial missions (they don't expire)
        now = datetime.utcnow()
        assigned = []

        for mission in tutorial_missions:
            user_mission = UserMission(
                user_id=user.id,
                mission_id=mission.id,
                current_progress=0,
                is_completed=False,
                is_claimed=False,
                assigned_at=now,
                expires_at=None  # Tutorial missions never expire
            )
            db.session.add(user_mission)
            assigned.append(user_mission)

        db.session.flush()
        logger.info(f"Assigned {len(assigned)} tutorial missions to user {user.id}")

        return assigned

    @staticmethod
    def ensure_missions_assigned(user):
        """
        Ensure user has all mission types assigned.
        Called on login or dashboard load.

        Returns:
            dict: Summary of missions assigned
        """
        daily = MissionService.assign_daily_missions(user)
        weekly = MissionService.assign_weekly_missions(user)
        tutorial = MissionService.get_or_assign_tutorial_missions(user)

        return {
            'daily_assigned': len(daily),
            'weekly_assigned': len(weekly),
            'tutorial_count': len(tutorial)
        }

    @staticmethod
    def track_progress(user, action_type, count=1):
        """
        Track progress for all active missions matching the action type.

        Args:
            user: User instance
            action_type: The action performed (e.g., 'fight', 'work', 'train')
            count: Number of times the action was performed

        Returns:
            list: List of dicts with mission progress info:
                  [{mission, user_mission, newly_completed}, ...]
        """
        now = datetime.utcnow()
        results = []

        # Get all active (non-completed, non-claimed, non-expired) missions matching action type
        user_missions = db.session.scalars(
            select(UserMission)
            .where(
                UserMission.user_id == user.id,
                UserMission.is_completed == False,
                UserMission.is_claimed == False,
                or_(
                    UserMission.expires_at.is_(None),
                    UserMission.expires_at > now
                )
            )
            .join(UserMission.mission)
            .where(Mission.action_type == action_type)
        ).all()

        for user_mission in user_missions:
            newly_completed = user_mission.add_progress(count)

            results.append({
                'mission': user_mission.mission,
                'user_mission': user_mission,
                'newly_completed': newly_completed,
                'current_progress': user_mission.current_progress,
                'requirement': user_mission.mission.requirement_count
            })

            if newly_completed:
                logger.info(
                    f"User {user.id} completed mission '{user_mission.mission.code}'"
                )

        return results

    @staticmethod
    def claim_reward(user, user_mission_id):
        """
        Claim reward for a completed mission.

        Args:
            user: User instance
            user_mission_id: ID of the UserMission to claim

        Returns:
            dict: {
                'success': bool,
                'message': str,
                'rewards': {gold, xp, items},
                'leveled_up': bool,
                'new_level': int
            }
        """
        from app.services.currency_service import CurrencyService
        from app.services.inventory_service import InventoryService
        from app.alert_helpers import send_level_up_alert

        # Get the user mission with row-level locking
        user_mission = db.session.scalar(
            select(UserMission)
            .where(
                UserMission.id == user_mission_id,
                UserMission.user_id == user.id
            )
            .with_for_update()
        )

        if not user_mission:
            return {
                'success': False,
                'message': 'Mission not found',
                'rewards': None,
                'leveled_up': False,
                'new_level': user.level
            }

        if user_mission.is_claimed:
            return {
                'success': False,
                'message': 'Reward already claimed',
                'rewards': None,
                'leveled_up': False,
                'new_level': user.level
            }

        if not user_mission.is_completed:
            return {
                'success': False,
                'message': 'Mission not yet completed',
                'rewards': None,
                'leveled_up': False,
                'new_level': user.level
            }

        if user_mission.is_expired:
            return {
                'success': False,
                'message': 'Mission has expired',
                'rewards': None,
                'leveled_up': False,
                'new_level': user.level
            }

        mission = user_mission.mission
        rewards = {
            'gold': 0,
            'xp': 0,
            'items': []
        }
        leveled_up = False
        new_level = user.level

        # Award gold
        if mission.gold_reward and mission.gold_reward > 0:
            gold_amount = Decimal(str(mission.gold_reward))
            success, msg, _ = CurrencyService.add_gold(
                user.id,
                gold_amount,
                f'Mission reward: {mission.code}'
            )
            if success:
                rewards['gold'] = float(mission.gold_reward)
            else:
                logger.error(f"Failed to add gold for mission {mission.code}: {msg}")

        # Award XP and check for level up
        if mission.xp_reward and mission.xp_reward > 0:
            leveled_up, new_level = user.add_experience(mission.xp_reward)
            rewards['xp'] = mission.xp_reward

            if leveled_up:
                # Send level up alert
                send_level_up_alert(user.id, new_level)
                logger.info(f"User {user.id} leveled up to {new_level} from mission reward")

        # Award resource items
        if mission.resource_reward_id and mission.resource_reward_quantity > 0:
            added, remaining = InventoryService.add_item(
                user,
                mission.resource_reward_id,
                mission.resource_reward_quantity,
                mission.resource_reward_quality
            )
            if added > 0:
                rewards['items'].append({
                    'resource_id': mission.resource_reward_id,
                    'resource_name': mission.resource_reward.name if mission.resource_reward else 'Unknown',
                    'quantity': added,
                    'quality': mission.resource_reward_quality
                })

        # Mark as claimed
        user_mission.is_claimed = True
        user_mission.claimed_at = datetime.utcnow()

        # Create reward alert
        reward_text = []
        if rewards['gold'] > 0:
            reward_text.append(f"{rewards['gold']:.2f} gold")
        if rewards['xp'] > 0:
            reward_text.append(f"{rewards['xp']} XP")
        for item in rewards['items']:
            reward_text.append(f"{item['quantity']}x {item['resource_name']}")

        if reward_text:
            alert = Alert(
                user_id=user.id,
                alert_type=AlertType.MISSION_COMPLETE.value,
                priority=AlertPriority.NORMAL.value,
                title=f'Mission Complete: {mission.name}',
                content=f'You earned: {", ".join(reward_text)}',
                link_url='/missions',
                link_text='View Missions'
            )
            db.session.add(alert)

        logger.info(f"User {user.id} claimed mission '{mission.code}' rewards: {rewards}")

        return {
            'success': True,
            'message': 'Rewards claimed successfully',
            'rewards': rewards,
            'leveled_up': leveled_up,
            'new_level': new_level
        }

    @staticmethod
    def expire_old_missions():
        """
        Mark expired missions. Called by scheduler.
        Unclaimed rewards are lost on expiration.
        """
        now = datetime.utcnow()

        # Get expired unclaimed missions
        expired_missions = db.session.scalars(
            select(UserMission)
            .where(
                UserMission.is_claimed == False,
                UserMission.expires_at.isnot(None),
                UserMission.expires_at <= now
            )
        ).all()

        count = 0
        for um in expired_missions:
            # Just mark as claimed to prevent future claims
            # The mission reward is lost
            um.is_claimed = True
            um.claimed_at = now
            count += 1

        if count > 0:
            logger.info(f"Expired {count} unclaimed missions")

        return count

    @staticmethod
    def get_mission_stats(user):
        """Get mission completion statistics for a user."""
        # Total completed missions (all time)
        total_completed = db.session.scalar(
            select(db.func.count(UserMission.id))
            .where(
                UserMission.user_id == user.id,
                UserMission.is_completed == True
            )
        ) or 0

        # Today's completed daily missions
        game_day_start = get_game_day_start()
        daily_completed_today = db.session.scalar(
            select(db.func.count(UserMission.id))
            .where(
                UserMission.user_id == user.id,
                UserMission.is_completed == True,
                UserMission.assigned_at >= game_day_start
            )
            .join(UserMission.mission)
            .where(Mission.mission_type == MissionType.DAILY.value)
        ) or 0

        # This week's completed weekly missions
        week_start = get_week_start()

        weekly_completed = db.session.scalar(
            select(db.func.count(UserMission.id))
            .where(
                UserMission.user_id == user.id,
                UserMission.is_completed == True,
                UserMission.assigned_at >= week_start
            )
            .join(UserMission.mission)
            .where(Mission.mission_type == MissionType.WEEKLY.value)
        ) or 0

        # Tutorial progress
        tutorial_total = db.session.scalar(
            select(db.func.count(Mission.id))
            .where(
                Mission.mission_type == MissionType.TUTORIAL.value,
                Mission.is_active == True
            )
        ) or 0

        tutorial_completed = db.session.scalar(
            select(db.func.count(UserMission.id))
            .where(
                UserMission.user_id == user.id,
                UserMission.is_completed == True
            )
            .join(UserMission.mission)
            .where(Mission.mission_type == MissionType.TUTORIAL.value)
        ) or 0

        return {
            'total_completed': total_completed,
            'daily_completed_today': daily_completed_today,
            'daily_total': DAILY_MISSIONS_COUNT,
            'weekly_completed': weekly_completed,
            'weekly_total': WEEKLY_MISSIONS_COUNT,
            'tutorial_completed': tutorial_completed,
            'tutorial_total': tutorial_total
        }
