"""
Currency Service - Handles all currency/financial operations.

This service encapsulates currency management logic that was previously in the User model.
"""

import logging
from decimal import Decimal
from sqlalchemy import select
from app.extensions import db
from app.constants import GameConstants
from app.exceptions import InvalidAmountError, InsufficientFundsError

logger = logging.getLogger(__name__)


class CurrencyService:
    """Service for managing user currency operations."""

    @staticmethod
    def get_or_create_currency(user, country_id):
        """Get or create user's currency for a specific country."""
        from app.models.currency import UserCurrency

        user_currency = db.session.scalar(
            select(UserCurrency).where(
                UserCurrency.user_id == user.id,
                UserCurrency.country_id == country_id
            )
        )

        if not user_currency:
            user_currency = UserCurrency(
                user_id=user.id,
                country_id=country_id,
                amount=Decimal('0')
            )
            db.session.add(user_currency)
            db.session.flush()

        return user_currency

    @staticmethod
    def get_amount(user, country_id):
        """Get amount of specific country's currency user owns."""
        from app.models.currency import UserCurrency

        currency = db.session.scalar(
            select(UserCurrency).where(
                UserCurrency.user_id == user.id,
                UserCurrency.country_id == country_id
            )
        )
        return currency.amount if currency else Decimal('0.0')

    @staticmethod
    def get_local_currency(user):
        """Get currency amount for the country user is currently in."""
        if not user.current_region or not user.current_region.current_owner:
            return Decimal('0.0')

        current_country_id = user.current_region.current_owner.id
        return CurrencyService.get_amount(user, current_country_id)

    @staticmethod
    def get_local_currency_code(user):
        """Get currency code for the country user is currently in."""
        if not user.current_region or not user.current_region.current_owner:
            return None
        return user.current_region.current_owner.currency_code

    @staticmethod
    def get_all_currencies(user):
        """Get all currencies owned by user with amount > 0."""
        from app.models.currency import UserCurrency

        user_currencies = db.session.scalars(
            select(UserCurrency)
            .where(UserCurrency.user_id == user.id)
            .where(UserCurrency.amount > Decimal('0.0'))
            .join(UserCurrency.country)
            .order_by(UserCurrency.amount.desc())
        ).all()

        return [{
            'country_id': uc.country_id,
            'country_name': uc.country.name,
            'currency_code': uc.country.currency_code,
            'amount': uc.amount
        } for uc in user_currencies]

    @staticmethod
    def add_currency(user, country_id, amount):
        """Add currency to user's wallet with row-level locking."""
        from app.models.currency import UserCurrency

        if amount <= 0:
            return True

        amount = Decimal(str(amount))

        # Use row-level locking to prevent race conditions
        currency = db.session.scalar(
            select(UserCurrency).where(
                UserCurrency.user_id == user.id,
                UserCurrency.country_id == country_id
            ).with_for_update()
        )

        if currency:
            currency.amount += amount
        else:
            currency = UserCurrency(
                user_id=user.id,
                country_id=country_id,
                amount=amount
            )
            db.session.add(currency)

        return True

    @staticmethod
    def remove_currency(user, country_id, amount):
        """Remove currency from user's wallet. Returns False if insufficient funds."""
        from app.models.currency import UserCurrency

        if amount <= 0:
            return True

        amount = Decimal(str(amount))

        currency = db.session.scalar(
            select(UserCurrency).where(
                UserCurrency.user_id == user.id,
                UserCurrency.country_id == country_id
            ).with_for_update()
        )

        if not currency or currency.amount < amount:
            return False

        currency.amount -= amount

        if currency.amount == 0:
            db.session.delete(currency)

        return True

    @staticmethod
    def has_sufficient(user, country_id, amount):
        """Check if user has enough of a specific currency."""
        return CurrencyService.get_amount(user, country_id) >= Decimal(str(amount))

    @staticmethod
    def validate_transaction(user, country_id, amount, action='deduct'):
        """
        Validate currency transaction before attempting.

        Args:
            user: User instance
            country_id: Country ID for the currency
            amount: Amount to validate
            action: 'deduct' or 'add'

        Returns:
            bool: True if valid

        Raises:
            InvalidAmountError: If amount is invalid
            InsufficientFundsError: If user doesn't have enough currency
        """
        amount = Decimal(str(amount))

        if amount <= 0:
            logger.warning(f"User {user.id} attempted transaction with non-positive amount: {amount}")
            raise InvalidAmountError("Amount must be positive")

        if amount > GameConstants.MAX_CURRENCY_AMOUNT:
            logger.warning(f"User {user.id} attempted transaction exceeding max amount: {amount}")
            raise InvalidAmountError(f"Amount exceeds maximum ({GameConstants.MAX_CURRENCY_AMOUNT})")

        if action == 'deduct':
            current_amount = CurrencyService.get_amount(user, country_id)
            if current_amount < amount:
                logger.info(f"User {user.id} insufficient funds for country {country_id}: {current_amount}/{amount}")
                raise InsufficientFundsError(f"Insufficient funds. Have: {current_amount:.2f}, Need: {amount:.2f}")

        return True

    @staticmethod
    def safe_remove(user, country_id, amount):
        """
        Safe currency removal with validation.

        Args:
            user: User instance
            country_id: Country ID for the currency
            amount: Amount to remove

        Returns:
            bool: True if successful

        Raises:
            InvalidAmountError: If amount is invalid
            InsufficientFundsError: If user doesn't have enough currency
        """
        CurrencyService.validate_transaction(user, country_id, amount, 'deduct')
        return CurrencyService.remove_currency(user, country_id, amount)

    # ============== GOLD TRANSACTIONS (with row-level locking) ==============

    @staticmethod
    def deduct_gold(user_id, amount, description=''):
        """
        Safely deduct gold from a user with row-level locking to prevent race conditions.

        Args:
            user_id: User ID
            amount: Amount of gold to deduct (Decimal or convertible)
            description: Optional description for logging

        Returns:
            tuple: (success: bool, message: str, updated_user: User or None)

        Note: This method uses SELECT FOR UPDATE to prevent race conditions.
        The caller should NOT have already loaded the user in the same transaction
        without FOR UPDATE, as that could lead to stale data.
        """
        from app.models import User

        amount = Decimal(str(amount))

        if amount <= 0:
            return False, "Amount must be positive", None

        # Lock the user row for update
        user = db.session.scalar(
            select(User).where(User.id == user_id).with_for_update()
        )

        if not user:
            return False, "User not found", None

        if user.gold < amount:
            return False, f"Insufficient gold. Have: {user.gold}, Need: {amount}", None

        user.gold -= amount

        if description:
            logger.info(f"Gold deducted from user {user_id}: {amount} ({description})")

        return True, "Success", user

    @staticmethod
    def add_gold(user_id, amount, description=''):
        """
        Safely add gold to a user with row-level locking.

        Args:
            user_id: User ID
            amount: Amount of gold to add (Decimal or convertible)
            description: Optional description for logging

        Returns:
            tuple: (success: bool, message: str, updated_user: User or None)
        """
        from app.models import User

        amount = Decimal(str(amount))

        if amount <= 0:
            return False, "Amount must be positive", None

        # Lock the user row for update
        user = db.session.scalar(
            select(User).where(User.id == user_id).with_for_update()
        )

        if not user:
            return False, "User not found", None

        # Check for overflow (max gold limit)
        max_gold = Decimal('999999999999.99999999')
        if user.gold + amount > max_gold:
            return False, "Gold amount would exceed maximum limit", None

        user.gold += amount

        if description:
            logger.info(f"Gold added to user {user_id}: {amount} ({description})")

        return True, "Success", user

    @staticmethod
    def transfer_gold(from_user_id, to_user_id, amount, description=''):
        """
        Safely transfer gold between users with proper locking.

        Args:
            from_user_id: Source user ID
            to_user_id: Destination user ID
            amount: Amount to transfer
            description: Optional description for logging

        Returns:
            tuple: (success: bool, message: str)
        """
        from app.models import User

        amount = Decimal(str(amount))

        if amount <= 0:
            return False, "Amount must be positive"

        if from_user_id == to_user_id:
            return False, "Cannot transfer to yourself"

        # Lock both users in a consistent order to prevent deadlocks
        # Always lock lower ID first
        first_id, second_id = sorted([from_user_id, to_user_id])

        first_user = db.session.scalar(
            select(User).where(User.id == first_id).with_for_update()
        )
        second_user = db.session.scalar(
            select(User).where(User.id == second_id).with_for_update()
        )

        if not first_user or not second_user:
            return False, "One or both users not found"

        # Determine sender and receiver
        sender = first_user if first_user.id == from_user_id else second_user
        receiver = second_user if second_user.id == to_user_id else first_user

        if sender.gold < amount:
            return False, f"Insufficient gold. Have: {sender.gold}, Need: {amount}"

        sender.gold -= amount
        receiver.gold += amount

        if description:
            logger.info(f"Gold transfer from user {from_user_id} to {to_user_id}: {amount} ({description})")

        return True, "Success"

    # ==================== Company Currency Operations ====================

    @staticmethod
    def add_company_currency(company_id, amount, description=''):
        """
        Safely add local currency to a company with row-level locking.

        Args:
            company_id: ID of the company
            amount: Amount of currency to add
            description: Optional description for logging

        Returns:
            tuple: (success: bool, message: str, company: Company or None)
        """
        from app.models import Company

        amount = Decimal(str(amount))
        if amount <= 0:
            return False, "Amount must be positive", None

        # Lock the company row for update
        company = db.session.scalar(
            select(Company).where(Company.id == company_id).with_for_update()
        )

        if not company:
            return False, "Company not found", None

        if company.is_deleted:
            return False, "Company has been deleted", None

        # Check for overflow
        max_currency = Decimal('999999999999.99')
        if company.currency_balance + amount > max_currency:
            return False, "Currency amount would exceed maximum limit", None

        company.currency_balance += amount

        if description:
            logger.info(f"Company {company_id} currency added: {amount} ({description})")

        return True, "Success", company

    @staticmethod
    def deduct_company_currency(company_id, amount, description=''):
        """
        Safely deduct local currency from a company with row-level locking.

        Args:
            company_id: ID of the company
            amount: Amount of currency to deduct
            description: Optional description for logging

        Returns:
            tuple: (success: bool, message: str, company: Company or None)
        """
        from app.models import Company

        amount = Decimal(str(amount))
        if amount <= 0:
            return False, "Amount must be positive", None

        # Lock the company row for update
        company = db.session.scalar(
            select(Company).where(Company.id == company_id).with_for_update()
        )

        if not company:
            return False, "Company not found", None

        if company.is_deleted:
            return False, "Company has been deleted", None

        if company.currency_balance < amount:
            return False, f"Insufficient funds. Have: {company.currency_balance}, Need: {amount}", None

        company.currency_balance -= amount

        if description:
            logger.info(f"Company {company_id} currency deducted: {amount} ({description})")

        return True, "Success", company
