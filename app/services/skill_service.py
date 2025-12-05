"""
Skill Service - Handles all skill training and studying operations.

This service encapsulates skill management logic that was previously in the User model.
"""

import logging
from datetime import datetime
from sqlalchemy import select
from app.extensions import db
from app.constants import GameConstants

logger = logging.getLogger(__name__)


class SkillService:
    """Service for managing user skill operations."""

    @staticmethod
    def train_skill(user, skill_type):
        """
        Train a military skill (infantry, armoured, aviation).

        Args:
            user: User instance
            skill_type: Type of military skill to train

        Returns:
            tuple: (success: bool, message: str, leveled_up: bool, new_level: int)

        Raises:
            DailyCooldownError: If training cooldown hasn't expired
            InsufficientWellnessError: If user doesn't have enough wellness
            InvalidSkillTypeError: If skill type is not valid
        """
        # Validate skill type
        try:
            GameConstants.validate_skill_type(skill_type, 'military')
        except ValueError as e:
            logger.warning(f"User {user.id} attempted invalid military skill: {skill_type}")
            return False, str(e), False, user.level

        # Check cooldown
        if not user.can_train_today:
            logger.info(f"User {user.id} attempted training on cooldown")
            return False, f"You can only train once per {GameConstants.MILITARY_TRAINING_COOLDOWN_HOURS} hours.", False, user.level

        energy_cost = 10.0
        if user.energy < energy_cost:
            logger.info(f"User {user.id} insufficient energy for training: {user.energy}/{energy_cost}")
            return False, f"Not enough energy (need {energy_cost}).", False, user.level

        # Perform training
        user.energy -= energy_cost
        leveled_up, new_level = user.add_experience(GameConstants.MILITARY_TRAINING_XP_GAIN)
        user.last_trained = datetime.utcnow()

        skill_gain = float(GameConstants.MILITARY_TRAINING_SKILL_GAIN)
        if skill_type == 'infantry':
            user.skill_infantry += skill_gain
        elif skill_type == 'armoured':
            user.skill_armoured += skill_gain
        elif skill_type == 'aviation':
            user.skill_aviation += skill_gain

        logger.info(f"User {user.id} trained {skill_type}, gained {skill_gain} skill and {GameConstants.MILITARY_TRAINING_XP_GAIN} XP")
        return True, f"Successfully trained {skill_type.capitalize()}! Gained {skill_gain} skill and {GameConstants.MILITARY_TRAINING_XP_GAIN} XP.", leveled_up, new_level

    @staticmethod
    def study_skill(user, skill_type):
        """
        Study a work skill (resource_extraction, manufacture, construction).

        Args:
            user: User instance
            skill_type: Type of work skill to study

        Returns:
            tuple: (success: bool, message: str, leveled_up: bool, new_level: int)

        Raises:
            DailyCooldownError: If study cooldown hasn't expired
            InsufficientWellnessError: If user doesn't have enough wellness
            InvalidSkillTypeError: If skill type is not valid
        """
        # Validate skill type
        try:
            GameConstants.validate_skill_type(skill_type, 'work')
        except ValueError as e:
            logger.warning(f"User {user.id} attempted invalid work skill: {skill_type}")
            return False, str(e), False, user.level

        # Check cooldown
        if not user.can_study_today:
            logger.info(f"User {user.id} attempted study on cooldown")
            return False, f"You can only study once per {GameConstants.WORK_TRAINING_COOLDOWN_HOURS} hours.", False, user.level

        energy_cost = 10.0
        if user.energy < energy_cost:
            logger.info(f"User {user.id} insufficient energy for study: {user.energy}/{energy_cost}")
            return False, f"Not enough energy (need {energy_cost}).", False, user.level

        # Perform study
        user.energy -= energy_cost
        leveled_up, new_level = user.add_experience(GameConstants.WORK_TRAINING_XP_GAIN)
        user.last_studied = datetime.utcnow()

        skill_gain = float(GameConstants.WORK_TRAINING_SKILL_GAIN)
        skill_name_display = GameConstants.get_skill_display_name(skill_type)

        if skill_type == 'resource_extraction':
            user.skill_resource_extraction += skill_gain
        elif skill_type == 'manufacture':
            user.skill_manufacture += skill_gain
        elif skill_type == 'construction':
            user.skill_construction += skill_gain

        logger.info(f"User {user.id} studied {skill_type}, gained {skill_gain} skill and {GameConstants.WORK_TRAINING_XP_GAIN} XP")
        return True, f"Successfully studied {skill_name_display}! Gained {skill_gain} skill and {GameConstants.WORK_TRAINING_XP_GAIN} XP.", leveled_up, new_level

    @staticmethod
    def get_skill_for_company_type(user, company_type):
        """Get user's skill level for a specific company type."""
        from app.models.company import CompanyType

        skill_mapping = {
            # Resource extraction
            CompanyType.MINING: user.skill_resource_extraction,
            CompanyType.RESOURCE_EXTRACTION: user.skill_resource_extraction,
            CompanyType.FARMING: user.skill_resource_extraction,
            # Weapon manufacturing (split)
            CompanyType.RIFLE_MANUFACTURING: user.skill_manufacture,
            CompanyType.TANK_MANUFACTURING: user.skill_manufacture,
            CompanyType.HELICOPTER_MANUFACTURING: user.skill_manufacture,
            # Consumer goods (split)
            CompanyType.BREAD_MANUFACTURING: user.skill_manufacture,
            CompanyType.BEER_MANUFACTURING: user.skill_manufacture,
            CompanyType.WINE_MANUFACTURING: user.skill_manufacture,
            # Semi-products
            CompanyType.SEMI_PRODUCT: user.skill_manufacture,
            # Construction
            CompanyType.CONSTRUCTION: user.skill_construction,
        }
        return skill_mapping.get(company_type, 0.0)

    @staticmethod
    def allocate_training_hours(user, skill_type, hours):
        """
        Allocate hours to training a military skill.

        Args:
            user: User instance
            skill_type: 'infantry', 'armoured', or 'aviation'
            hours: Number of hours to train (1-12)

        Returns:
            tuple: (success: bool, message: str, skill_gain: float, energy_cost: int, leveled_up: bool, new_level: int)
        """
        # Validate hours
        can_allocate, reason = user.can_allocate_hours('training', hours)
        if not can_allocate:
            return False, reason, 0.0, 0, False, user.level

        # Validate skill type
        if skill_type not in ['infantry', 'armoured', 'aviation']:
            return False, "Invalid skill type", 0.0, 0, False, user.level

        # Calculate base costs
        base_energy_cost = hours * 2  # 2 energy per hour

        # Apply NFT efficiency bonuses (training only uses energy, not wellness)
        from app.services.bonus_calculator import BonusCalculator
        energy_cost = BonusCalculator.get_energy_cost(user.id, base_energy_cost)

        # Check energy
        if user.energy < energy_cost:
            return False, f"Insufficient energy. Need {energy_cost}, have {user.energy:.1f}", 0.0, 0, False, user.level

        # Calculate skill gain (0.01 per hour)
        skill_gain = hours * 0.01

        # Apply skill gain
        if skill_type == 'infantry':
            user.skill_infantry += skill_gain
        elif skill_type == 'armoured':
            user.skill_armoured += skill_gain
        elif skill_type == 'aviation':
            user.skill_aviation += skill_gain

        # Deduct energy
        user.energy = max(0, user.energy - energy_cost)

        # Update time allocation
        allocation = user.get_today_allocation()
        allocation.hours_training += hours
        allocation.training_skill = skill_type

        # Add experience and check for level up
        xp_gain = GameConstants.MILITARY_TRAINING_XP_GAIN * hours
        leveled_up, new_level = user.add_experience(xp_gain)

        # Track training streak for achievements
        from app.services.achievement_service import AchievementService
        try:
            current_streak, achievement_unlocked = AchievementService.track_training_streak(user)
            if achievement_unlocked:
                logger.info(f"User {user.id} unlocked training-related achievement with {current_streak}-day streak")
        except Exception as e:
            logger.error(f"Error tracking training achievement for user {user.id}: {e}")

        # Track mission progress for training
        from app.services.mission_service import MissionService
        try:
            MissionService.track_progress(user, 'train', 1)
        except Exception as e:
            logger.error(f"Error tracking train mission for user {user.id}: {e}")

        message = f"Trained {skill_type} for {hours} hours. Gained {skill_gain:.2f} skill and {xp_gain} XP. Energy: -{energy_cost}"

        return True, message, skill_gain, energy_cost, leveled_up, new_level

    @staticmethod
    def allocate_studying_hours(user, skill_type, hours):
        """
        Allocate hours to studying a work skill.

        Args:
            user: User instance
            skill_type: 'resource_extraction', 'manufacture', or 'construction'
            hours: Number of hours to study (1-12)

        Returns:
            tuple: (success: bool, message: str, skill_gain: float, energy_cost: int, leveled_up: bool, new_level: int)
        """
        # Validate hours
        can_allocate, reason = user.can_allocate_hours('studying', hours)
        if not can_allocate:
            return False, reason, 0.0, 0, False, user.level

        # Validate skill type
        if skill_type not in ['resource_extraction', 'manufacture', 'construction']:
            return False, "Invalid skill type", 0.0, 0, False, user.level

        # Calculate base costs
        base_energy_cost = hours * 2  # 2 energy per hour

        # Apply NFT efficiency bonuses (studying only uses energy, not wellness)
        from app.services.bonus_calculator import BonusCalculator
        energy_cost = BonusCalculator.get_energy_cost(user.id, base_energy_cost)

        # Check energy
        if user.energy < energy_cost:
            return False, f"Insufficient energy. Need {energy_cost}, have {user.energy:.1f}", 0.0, 0, False, user.level

        # Calculate skill gain (0.01 per hour)
        skill_gain = hours * 0.01

        # Apply skill gain
        if skill_type == 'resource_extraction':
            user.skill_resource_extraction += skill_gain
        elif skill_type == 'manufacture':
            user.skill_manufacture += skill_gain
        elif skill_type == 'construction':
            user.skill_construction += skill_gain

        # Deduct energy
        user.energy = max(0, user.energy - energy_cost)

        # Update time allocation
        allocation = user.get_today_allocation()
        allocation.hours_studying += hours
        allocation.studying_skill = skill_type

        # Add experience and check for level up
        xp_gain = GameConstants.WORK_TRAINING_XP_GAIN * hours
        leveled_up, new_level = user.add_experience(xp_gain)

        # Track study streak for achievements
        from app.services.achievement_service import AchievementService
        try:
            current_streak, achievement_unlocked = AchievementService.track_study_streak(user)
            if achievement_unlocked:
                logger.info(f"User {user.id} unlocked study-related achievement with {current_streak}-day streak")
        except Exception as e:
            logger.error(f"Error tracking study achievement for user {user.id}: {e}")

        # Track mission progress for studying
        from app.services.mission_service import MissionService
        try:
            MissionService.track_progress(user, 'study', 1)
        except Exception as e:
            logger.error(f"Error tracking study mission for user {user.id}: {e}")

        message = f"Studied {skill_type.replace('_', ' ')} for {hours} hours. Gained {skill_gain:.2f} skill and {xp_gain} XP. Energy: -{energy_cost}"

        return True, message, skill_gain, energy_cost, leveled_up, new_level
