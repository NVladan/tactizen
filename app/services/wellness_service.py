"""
Wellness Service - Handles all wellness and energy restoration operations.

This service encapsulates wellness management logic that was previously in the User model.
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy import select
from app.extensions import db

logger = logging.getLogger(__name__)


class WellnessService:
    """Service for managing user wellness and energy operations."""

    @staticmethod
    def eat_bread(user, quantity='max', quality=1):
        """
        Eat bread from inventory to restore wellness.
        Quality determines restoration amount: Q1=2, Q2=4, Q3=6, Q4=8, Q5=10

        Args:
            user: User instance
            quantity: Either 'max' or an integer number of bread to eat
            quality: Quality level (1-5)

        Returns:
            tuple: (success: bool, message: str, bread_eaten: int, wellness_restored: float)
        """
        from app.models.resource import Resource
        from app.services.inventory_service import InventoryService

        # Quality-based restoration (quality * 2)
        WELLNESS_PER_BREAD = quality * 2.0
        MAX_WELLNESS = user.max_wellness  # Dynamic max based on house/NFTs
        DAILY_BREAD_ITEM_LIMIT = 10  # Max 10 breads per day (any quality)

        # Get bread resource
        bread_resource = db.session.scalar(
            db.select(Resource).where(Resource.slug == 'bread')
        )

        if not bread_resource:
            logger.error("Bread resource not found in database")
            return False, "Bread resource not available.", 0, 0.0

        # Check and reset daily tracker if needed (uses game day, resets at 9 AM CET)
        from app.time_helpers import get_allocation_date
        today = get_allocation_date()
        if not user.last_bread_reset_date or user.last_bread_reset_date < today:
            user.bread_consumed_today = 0
            user.last_bread_reset_date = today
            logger.debug(f"User {user.id} bread tracker reset for new day {today}")

        # Check daily limit (number of items, not wellness points)
        remaining_daily_limit = DAILY_BREAD_ITEM_LIMIT - int(user.bread_consumed_today)
        if remaining_daily_limit <= 0:
            logger.info(f"User {user.id} reached daily bread limit")
            return False, f"You've reached your daily limit of {DAILY_BREAD_ITEM_LIMIT} breads. Try again tomorrow!", 0, 0.0

        # Check how much bread user has for this quality
        bread_in_inventory = InventoryService.get_resource_quantity(user, bread_resource.id, quality)
        if bread_in_inventory <= 0:
            logger.info(f"User {user.id} has no Q{quality} bread in inventory")
            return False, f"You don't have any Q{quality} bread in your inventory.", 0, 0.0

        # Calculate how much wellness can be restored
        wellness_needed = MAX_WELLNESS - user.wellness
        if wellness_needed <= 0:
            logger.info(f"User {user.id} already at max wellness")
            return False, "Your wellness is already at maximum (100).", 0, 0.0

        # Calculate maximum bread that can be eaten based on all constraints
        max_bread_from_wellness = int(wellness_needed / WELLNESS_PER_BREAD)
        max_bread_from_daily_limit = remaining_daily_limit  # Now tracking item count, not wellness
        max_bread_available = min(bread_in_inventory, max_bread_from_wellness, max_bread_from_daily_limit)

        # Determine actual quantity to eat
        if quantity == 'max':
            bread_to_eat = max_bread_available
        else:
            try:
                bread_to_eat = int(quantity)
                if bread_to_eat <= 0:
                    return False, "Invalid quantity. Please specify a positive number.", 0, 0.0
                if bread_to_eat > bread_in_inventory:
                    return False, f"You only have {bread_in_inventory} Q{quality} bread in your inventory.", 0, 0.0
                # Cap at maximum allowed
                if bread_to_eat > max_bread_available:
                    bread_to_eat = max_bread_available
            except (ValueError, TypeError):
                return False, "Invalid quantity specified.", 0, 0.0

        if bread_to_eat <= 0:
            return False, "Cannot eat bread at this time.", 0, 0.0

        # Calculate actual wellness to restore
        wellness_to_restore = bread_to_eat * WELLNESS_PER_BREAD

        # Update user state
        user.wellness = min(MAX_WELLNESS, user.wellness + wellness_to_restore)
        user.bread_consumed_today += bread_to_eat  # Track item count, not wellness points

        # Remove bread from inventory (with quality)
        if not InventoryService.remove_item(user, bread_resource.id, bread_to_eat, quality):
            logger.error(f"Failed to remove Q{quality} bread from inventory for user {user.id}")
            return False, "Error removing bread from inventory.", 0, 0.0

        logger.info(f"User {user.id} ate {bread_to_eat} Q{quality} bread, restored {wellness_to_restore:.1f} wellness")

        # Build success message
        remaining_items = DAILY_BREAD_ITEM_LIMIT - int(user.bread_consumed_today)
        message = f"You ate {bread_to_eat} Q{quality} bread and restored {wellness_to_restore:.1f} wellness! "
        message += f"Current wellness: {user.wellness:.1f}/{MAX_WELLNESS:.0f}. "
        message += f"You can eat {remaining_items} more bread today (max {DAILY_BREAD_ITEM_LIMIT} per day)."

        return True, message, bread_to_eat, wellness_to_restore

    @staticmethod
    def drink_beer(user, quantity='max', quality=1):
        """
        Drink beer from inventory to restore energy.
        Quality determines restoration amount: Q1=2, Q2=4, Q3=6, Q4=8, Q5=10

        Args:
            user: User instance
            quantity: Either 'max' or an integer number of beer to drink
            quality: Quality level (1-5)

        Returns:
            tuple: (success: bool, message: str, beer_drunk: int, energy_restored: float)
        """
        from app.models.resource import Resource
        from app.services.inventory_service import InventoryService

        # Quality-based restoration (quality * 2)
        ENERGY_PER_BEER = quality * 2.0
        MAX_ENERGY = user.max_energy  # Dynamic max based on house/NFTs
        DAILY_BEER_ITEM_LIMIT = 10  # Max 10 beers per day (any quality)

        # Get beer resource
        beer_resource = db.session.scalar(
            db.select(Resource).where(Resource.slug == 'beer')
        )

        if not beer_resource:
            logger.error("Beer resource not found in database")
            return False, "Beer resource not available.", 0, 0.0

        # Check and reset daily tracker if needed (uses game day, resets at 9 AM CET)
        from app.time_helpers import get_allocation_date
        today = get_allocation_date()
        if not user.last_beer_reset_date or user.last_beer_reset_date < today:
            user.beer_consumed_today = 0
            user.last_beer_reset_date = today
            logger.debug(f"User {user.id} beer tracker reset for new day {today}")

        # Check daily limit (number of items, not energy points)
        remaining_daily_limit = DAILY_BEER_ITEM_LIMIT - int(user.beer_consumed_today)
        if remaining_daily_limit <= 0:
            logger.info(f"User {user.id} reached daily beer limit")
            return False, f"You've reached your daily limit of {DAILY_BEER_ITEM_LIMIT} beers. Try again tomorrow!", 0, 0.0

        # Check how much beer user has for this quality
        beer_in_inventory = InventoryService.get_resource_quantity(user, beer_resource.id, quality)
        if beer_in_inventory <= 0:
            logger.info(f"User {user.id} has no Q{quality} beer in inventory")
            return False, f"You don't have any Q{quality} beer in your inventory.", 0, 0.0

        # Calculate how much energy can be restored
        energy_needed = MAX_ENERGY - user.energy
        if energy_needed <= 0:
            logger.info(f"User {user.id} already at max energy")
            return False, "Your energy is already at maximum (100).", 0, 0.0

        # Calculate maximum beer that can be drunk based on all constraints
        max_beer_from_energy = int(energy_needed / ENERGY_PER_BEER)
        max_beer_from_daily_limit = remaining_daily_limit  # Now tracking item count, not energy
        max_beer_available = min(beer_in_inventory, max_beer_from_energy, max_beer_from_daily_limit)

        # Determine actual quantity to drink
        if quantity == 'max':
            beer_to_drink = max_beer_available
        else:
            try:
                beer_to_drink = int(quantity)
                if beer_to_drink <= 0:
                    return False, "Invalid quantity. Please specify a positive number.", 0, 0.0
                if beer_to_drink > beer_in_inventory:
                    return False, f"You only have {beer_in_inventory} Q{quality} beer in your inventory.", 0, 0.0
                # Cap at maximum allowed
                if beer_to_drink > max_beer_available:
                    beer_to_drink = max_beer_available
            except (ValueError, TypeError):
                return False, "Invalid quantity specified.", 0, 0.0

        if beer_to_drink <= 0:
            return False, "Cannot drink beer at this time.", 0, 0.0

        # Calculate actual energy to restore
        energy_to_restore = beer_to_drink * ENERGY_PER_BEER

        # Update user state
        user.energy = min(MAX_ENERGY, user.energy + energy_to_restore)
        user.beer_consumed_today += beer_to_drink  # Track item count, not energy points

        # Remove beer from inventory (with quality)
        if not InventoryService.remove_item(user, beer_resource.id, beer_to_drink, quality):
            logger.error(f"Failed to remove Q{quality} beer from inventory for user {user.id}")
            return False, "Error removing beer from inventory.", 0, 0.0

        logger.info(f"User {user.id} drank {beer_to_drink} Q{quality} beer, restored {energy_to_restore:.1f} energy")

        # Build success message
        remaining_items = DAILY_BEER_ITEM_LIMIT - int(user.beer_consumed_today)
        message = f"You drank {beer_to_drink} Q{quality} beer and restored {energy_to_restore:.1f} energy! "
        message += f"Current energy: {user.energy:.1f}/{MAX_ENERGY:.0f}. "
        message += f"You can drink {remaining_items} more beer today (max {DAILY_BEER_ITEM_LIMIT} per day)."

        return True, message, beer_to_drink, energy_to_restore

    @staticmethod
    def drink_wine(user, quantity='max', quality=1):
        """
        Drink wine from inventory to restore both wellness AND energy.
        Quality determines restoration amount: Q1=1+1, Q2=2+2, Q3=3+3, Q4=4+4, Q5=5+5

        Args:
            user: User instance
            quantity: Either 'max' or an integer number of wine to drink
            quality: Quality level (1-5)

        Returns:
            tuple: (success: bool, message: str, wine_drunk: int, wellness_restored: float, energy_restored: float)
        """
        from app.models.resource import Resource
        from app.services.inventory_service import InventoryService

        # Quality-based restoration (quality * 1 for each stat)
        WELLNESS_PER_WINE = quality * 1.0
        ENERGY_PER_WINE = quality * 1.0
        MAX_WELLNESS = user.max_wellness  # Dynamic max based on house/NFTs
        MAX_ENERGY = user.max_energy  # Dynamic max based on house/NFTs
        DAILY_WINE_ITEM_LIMIT = 10  # Max 10 wines per day (any quality)

        # Get wine resource
        wine_resource = db.session.scalar(
            db.select(Resource).where(Resource.slug == 'wine')
        )

        if not wine_resource:
            logger.error("Wine resource not found in database")
            return False, "Wine resource not available.", 0, 0.0, 0.0

        # Check and reset daily tracker if needed (uses game day, resets at 9 AM CET)
        from app.time_helpers import get_allocation_date
        today = get_allocation_date()
        if not user.last_wine_reset_date or user.last_wine_reset_date < today:
            user.wine_consumed_today = 0
            user.last_wine_reset_date = today
            logger.debug(f"User {user.id} wine tracker reset for new day {today}")

        # Check daily limit
        remaining_daily_limit = DAILY_WINE_ITEM_LIMIT - int(user.wine_consumed_today)
        if remaining_daily_limit <= 0:
            logger.info(f"User {user.id} reached daily wine limit")
            return False, f"You've reached your daily limit of {DAILY_WINE_ITEM_LIMIT} wines. Try again tomorrow!", 0, 0.0, 0.0

        # Check how much wine user has for this quality
        wine_in_inventory = InventoryService.get_resource_quantity(user, wine_resource.id, quality)
        if wine_in_inventory <= 0:
            logger.info(f"User {user.id} has no Q{quality} wine in inventory")
            return False, f"You don't have any Q{quality} wine in your inventory.", 0, 0.0, 0.0

        # Calculate how much wellness and energy can be restored
        wellness_needed = MAX_WELLNESS - user.wellness
        energy_needed = MAX_ENERGY - user.energy

        # Check if already at max for both
        if wellness_needed <= 0 and energy_needed <= 0:
            logger.info(f"User {user.id} already at max wellness and energy")
            return False, f"Your wellness and energy are already at maximum ({MAX_WELLNESS:.0f}).", 0, 0.0, 0.0

        # Calculate maximum wine based on what needs restoring
        max_wine_from_wellness = int(wellness_needed / WELLNESS_PER_WINE) if wellness_needed > 0 else 999
        max_wine_from_energy = int(energy_needed / ENERGY_PER_WINE) if energy_needed > 0 else 999
        max_wine_from_stats = max(max_wine_from_wellness, max_wine_from_energy)  # Use max since it restores both
        max_wine_available = min(wine_in_inventory, max_wine_from_stats, remaining_daily_limit)

        # Determine actual quantity to drink
        if quantity == 'max':
            wine_to_drink = max_wine_available
        else:
            try:
                wine_to_drink = int(quantity)
                if wine_to_drink <= 0:
                    return False, "Invalid quantity. Please specify a positive number.", 0, 0.0, 0.0
                if wine_to_drink > wine_in_inventory:
                    return False, f"You only have {wine_in_inventory} Q{quality} wine in your inventory.", 0, 0.0, 0.0
                # Cap at maximum allowed
                if wine_to_drink > max_wine_available:
                    wine_to_drink = max_wine_available
            except (ValueError, TypeError):
                return False, "Invalid quantity specified.", 0, 0.0, 0.0

        if wine_to_drink <= 0:
            return False, "Cannot drink wine at this time.", 0, 0.0, 0.0

        # Calculate actual restoration amounts
        wellness_to_restore = min(wine_to_drink * WELLNESS_PER_WINE, wellness_needed)
        energy_to_restore = min(wine_to_drink * ENERGY_PER_WINE, energy_needed)

        # Update user state
        user.wellness = min(MAX_WELLNESS, user.wellness + wellness_to_restore)
        user.energy = min(MAX_ENERGY, user.energy + energy_to_restore)
        user.wine_consumed_today += wine_to_drink

        # Remove wine from inventory
        if not InventoryService.remove_item(user, wine_resource.id, wine_to_drink, quality):
            logger.error(f"Failed to remove Q{quality} wine from inventory for user {user.id}")
            return False, "Error removing wine from inventory.", 0, 0.0, 0.0

        logger.info(f"User {user.id} drank {wine_to_drink} Q{quality} wine, restored {wellness_to_restore:.1f} wellness and {energy_to_restore:.1f} energy")

        # Build success message
        remaining_items = DAILY_WINE_ITEM_LIMIT - int(user.wine_consumed_today)
        message = f"You drank {wine_to_drink} Q{quality} wine and restored {wellness_to_restore:.1f} wellness and {energy_to_restore:.1f} energy! "
        message += f"Current wellness: {user.wellness:.1f}/{MAX_WELLNESS:.0f}, energy: {user.energy:.1f}/{MAX_ENERGY:.0f}. "
        message += f"You can drink {remaining_items} more wine today (max {DAILY_WINE_ITEM_LIMIT} per day)."

        return True, message, wine_to_drink, wellness_to_restore, energy_to_restore

    @staticmethod
    def process_residence_restoration(user):
        """
        Process automatic wellness and energy restoration from active residence.
        Quality determines restoration amount: Q1=2+2, Q2=4+4, Q3=6+6, Q4=8+8, Q5=10+10
        Restores every 15 minutes.

        Returns:
            tuple: (restored: bool, wellness_restored: float, energy_restored: float)
        """
        # Check if user has active residence
        if not user.active_residence:
            return False, 0.0, 0.0

        # Check if residence is expired
        if user.active_residence.is_expired:
            # Remove expired residence
            logger.info(f"Removing expired residence for user {user.id}")
            db.session.delete(user.active_residence)
            return False, 0.0, 0.0

        # Quality-based restoration (quality * 2)
        house_quality = user.active_residence.quality
        RESTORE_INTERVAL_MINUTES = 15
        WELLNESS_PER_RESTORE = house_quality * 2.0
        ENERGY_PER_RESTORE = house_quality * 2.0
        MAX_WELLNESS = user.max_wellness  # Dynamic max based on house/NFTs
        MAX_ENERGY = user.max_energy  # Dynamic max based on house/NFTs

        # Calculate time since last restore
        now = datetime.utcnow()
        time_since_restore = now - user.active_residence.last_restore_at
        minutes_passed = time_since_restore.total_seconds() / 60

        # Check if enough time has passed
        if minutes_passed < RESTORE_INTERVAL_MINUTES:
            # Not enough time has passed
            return False, 0.0, 0.0

        # Calculate how many restore cycles have passed
        restore_cycles = int(minutes_passed / RESTORE_INTERVAL_MINUTES)

        # Cap at reasonable amount (e.g., max 96 cycles = 1 day worth)
        restore_cycles = min(restore_cycles, 96)

        # Calculate restoration amounts
        wellness_to_restore = 0.0
        energy_to_restore = 0.0

        # Restore wellness if not at max
        if user.wellness < MAX_WELLNESS:
            wellness_to_restore = min(
                restore_cycles * WELLNESS_PER_RESTORE,
                MAX_WELLNESS - user.wellness
            )
            user.wellness = min(MAX_WELLNESS, user.wellness + wellness_to_restore)

        # Restore energy if not at max
        if user.energy < MAX_ENERGY:
            energy_to_restore = min(
                restore_cycles * ENERGY_PER_RESTORE,
                MAX_ENERGY - user.energy
            )
            user.energy = min(MAX_ENERGY, user.energy + energy_to_restore)

        # Update last restore time - set it to the last complete interval
        # This ensures we don't lose partial progress
        intervals_to_add = restore_cycles * RESTORE_INTERVAL_MINUTES
        user.active_residence.last_restore_at = user.active_residence.last_restore_at + timedelta(minutes=intervals_to_add)

        if wellness_to_restore > 0 or energy_to_restore > 0:
            logger.info(f"User {user.id} Q{house_quality} residence restored {wellness_to_restore:.1f} wellness and {energy_to_restore:.1f} energy ({restore_cycles} cycles)")
            return True, wellness_to_restore, energy_to_restore

        return False, 0.0, 0.0
