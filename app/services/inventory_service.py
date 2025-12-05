"""
Inventory Service - Handles all user inventory operations.

This service encapsulates inventory management logic that was previously in the User model.
"""

import logging
from sqlalchemy import select, func
from app.extensions import db
from app.models.resource import InventoryItem, Resource
from app.constants import GameConstants

logger = logging.getLogger(__name__)


class InventoryService:
    """Service for managing user inventory operations."""

    BASE_STORAGE_LIMIT = 1000

    @staticmethod
    def get_storage_limit(user):
        """Get user's total storage limit including NFT bonuses."""
        from app.services.bonus_calculator import BonusCalculator
        return BonusCalculator.get_storage_capacity(user.id, InventoryService.BASE_STORAGE_LIMIT)

    @staticmethod
    def get_total_count(user):
        """Get total quantity of all items in user's inventory."""
        total = db.session.scalar(
            select(func.sum(InventoryItem.quantity)).where(
                InventoryItem.user_id == user.id
            )
        )
        return int(total) if total else 0

    @staticmethod
    def get_available_storage(user):
        """Get remaining storage space available (includes NFT bonus)."""
        current_count = InventoryService.get_total_count(user)
        storage_limit = InventoryService.get_storage_limit(user)
        return max(0, storage_limit - current_count)

    @staticmethod
    def get_item(user, resource_id, quality=0):
        """Gets a specific inventory item for this user."""
        return db.session.scalar(
            db.select(InventoryItem).where(
                InventoryItem.user_id == user.id,
                InventoryItem.resource_id == resource_id,
                InventoryItem.quality == quality
            )
        )

    @staticmethod
    def get_resource_quantity(user, resource_id, quality=0):
        """Gets the quantity (Integer) of a specific resource with specific quality."""
        item = InventoryService.get_item(user, resource_id, quality)
        return item.quantity if item else 0

    @staticmethod
    def add_item(user, resource_id, quantity, quality=0):
        """
        Adds an INTEGER quantity of a resource to the user's inventory.
        Respects USER_STORAGE_LIMIT and will add partial quantity if limit is reached.

        Args:
            user: User instance
            resource_id: ID of the resource to add
            quantity: Integer quantity to add
            quality: Quality level (0 for raw materials, 1-5 for manufactured goods)

        Returns:
            tuple: (quantity_added: int, remaining: int)
                - quantity_added: Amount actually added to inventory
                - remaining: Amount that couldn't be added due to storage limit
        """
        try:
            add_qty = int(quantity)
        except (ValueError, TypeError):
            logger.error(f"Invalid quantity '{quantity}' for add_to_inventory for user {user.id}")
            return 0, quantity

        if add_qty <= 0:
            return 0, 0

        available_space = InventoryService.get_available_storage(user)
        if available_space <= 0:
            storage_limit = InventoryService.get_storage_limit(user)
            logger.warning(f"User {user.id} storage full ({InventoryService.get_total_count(user)}/{storage_limit})")
            return 0, add_qty

        quantity_to_add = min(add_qty, available_space)
        remaining = add_qty - quantity_to_add

        inventory_count = user.inventory.count()
        if inventory_count >= GameConstants.MAX_INVENTORY_SLOTS:
            logger.warning(f"User {user.id} inventory full ({inventory_count}/{GameConstants.MAX_INVENTORY_SLOTS})")
            return 0, add_qty

        # Lock the inventory item row to prevent race conditions
        item = db.session.scalar(
            db.select(InventoryItem)
            .where(
                InventoryItem.user_id == user.id,
                InventoryItem.resource_id == resource_id,
                InventoryItem.quality == quality
            )
            .with_for_update()
        )
        if item:
            if item.quantity + quantity_to_add > GameConstants.MAX_RESOURCE_QUANTITY:
                actual_add = GameConstants.MAX_RESOURCE_QUANTITY - item.quantity
                if actual_add <= 0:
                    logger.warning(f"User {user.id} would exceed max resource quantity for resource {resource_id}")
                    return 0, add_qty
                quantity_to_add = min(quantity_to_add, actual_add)
                remaining = add_qty - quantity_to_add

            item.quantity += quantity_to_add
            logger.debug(f"User {user.id} added {quantity_to_add} of resource {resource_id} Q{quality}, new total: {item.quantity}")
        else:
            resource = db.session.get(Resource, resource_id)
            if resource:
                item = InventoryItem(user_id=user.id, resource_id=resource_id, quality=quality, quantity=quantity_to_add)
                db.session.add(item)
                logger.debug(f"User {user.id} added new resource {resource_id} Q{quality} with quantity {quantity_to_add}")
            else:
                logger.error(f"Resource {resource_id} not found for add_to_inventory for user {user.id}")
                return 0, add_qty

        return quantity_to_add, remaining

    @staticmethod
    def remove_item(user, resource_id, quantity, quality=0):
        """
        Removes an INTEGER quantity of a resource from the user's inventory.

        Args:
            user: User instance
            resource_id: ID of the resource to remove
            quantity: Integer quantity to remove
            quality: Quality level (0 for raw materials, 1-5 for manufactured goods)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            remove_qty = int(quantity)
        except (ValueError, TypeError):
            logger.error(f"Invalid quantity '{quantity}' for remove_from_inventory for user {user.id}")
            return False

        if remove_qty <= 0:
            return True

        # Lock the inventory item row to prevent race conditions
        item = db.session.scalar(
            db.select(InventoryItem)
            .where(
                InventoryItem.user_id == user.id,
                InventoryItem.resource_id == resource_id,
                InventoryItem.quality == quality
            )
            .with_for_update()
        )
        current_quantity = item.quantity if item else 0

        if not item or current_quantity < remove_qty:
            logger.warning(f"User {user.id} insufficient inventory for resource {resource_id} Q{quality}: {current_quantity}/{remove_qty}")
            return False

        item.quantity -= remove_qty
        logger.debug(f"User {user.id} removed {remove_qty} of resource {resource_id} Q{quality}, remaining: {item.quantity}")

        if item.quantity <= 0:
            db.session.delete(item)
            logger.debug(f"User {user.id} inventory item {resource_id} Q{quality} removed (quantity reached 0)")

        return True
