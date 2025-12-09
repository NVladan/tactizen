# app/constants.py
"""Game constants and configuration values."""

from decimal import Decimal


class GameConstants:
    """Centralized game constants and configuration values."""

    # --- Travel Costs ---
    TRAVEL_COST_GOLD = Decimal('1.0')

    # --- Training (Military Skills) ---
    MILITARY_TRAINING_WELLNESS_COST = 10
    MILITARY_TRAINING_XP_GAIN = 2
    MILITARY_TRAINING_SKILL_GAIN = Decimal('0.5')
    MILITARY_TRAINING_COOLDOWN_HOURS = 23

    # --- Studying (Work Skills) ---
    WORK_TRAINING_WELLNESS_COST = 10
    WORK_TRAINING_XP_GAIN = 1
    WORK_TRAINING_SKILL_GAIN = Decimal('0.5')
    WORK_TRAINING_COOLDOWN_HOURS = 23

    # --- Wellness ---
    MAX_WELLNESS = 100.0
    MIN_WELLNESS = 0.0
    INITIAL_WELLNESS = 100.0  # Starting wellness for new users

    # --- New User Defaults ---
    INITIAL_GOLD = Decimal('0.0')  # Starting gold for new users
    INITIAL_LOCAL_CURRENCY = Decimal('100.0')  # Starting local currency for new citizens

    # --- Avatar Settings ---
    AVATAR_SIZE = (100, 100)  # Avatar dimensions in pixels
    ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    # --- Inventory ---
    MAX_INVENTORY_SLOTS = 1000  # Maximum number of different resource types
    MAX_RESOURCE_QUANTITY = 999999  # Maximum quantity per resource

    # --- Currency Limits ---
    MAX_CURRENCY_AMOUNT = Decimal('999999999999.99999999')  # Max balance
    MIN_CURRENCY_AMOUNT = Decimal('0.0')

    # --- Market ---
    DEFAULT_MARKET_VOLUME_THRESHOLD = 200  # Default volume per price level
    DEFAULT_MARKET_PRICE_ADJUSTMENT = Decimal('0.1')
    MARKET_BUY_SPREAD_PERCENT = Decimal('0.10')  # 10% spread
    MARKET_SELL_SPREAD_PERCENT = Decimal('0.10')  # 10% spread
    MINIMUM_MARKET_PRICE = Decimal('0.01')

    # --- Gold Market ---
    DEFAULT_GOLD_EXCHANGE_RATE = Decimal('100.00')
    GOLD_MARKET_SPREAD_PERCENT = Decimal('0.05')  # 5% spread
    DEFAULT_GOLD_VOLUME_PER_LEVEL = 1000
    DEFAULT_GOLD_PRICE_ADJUSTMENT = Decimal('1.00')

    # --- Experience & Leveling ---
    BASE_XP_INCREMENT = 20  # XP needed to go from level 1 to 2

    # --- Skill Types ---
    MILITARY_SKILL_TYPES = ['infantry', 'armoured', 'aviation']
    WORK_SKILL_TYPES = ['resource_extraction', 'manufacture', 'construction']

    # --- Display Formatting ---
    CURRENCY_DISPLAY_DECIMALS = 2  # Show 2 decimals in UI
    GOLD_DISPLAY_DECIMALS = 2
    SKILL_DISPLAY_DECIMALS = 2
    PRICE_DISPLAY_DECIMALS = 2

    # --- Transaction Types ---
    TRANSACTION_TYPES = {
        'CURRENCY_GAIN': 'Currency Gain',
        'CURRENCY_LOSS': 'Currency Loss',
        'GOLD_GAIN': 'Gold Gain',
        'GOLD_LOSS': 'Gold Loss',
        'MARKET_BUY': 'Market Purchase',
        'MARKET_SELL': 'Market Sale',
        'CURRENCY_EXCHANGE': 'Currency Exchange',
        'TRAVEL': 'Travel',
        'ADMIN_ADJUSTMENT': 'Admin Adjustment',
    }

    # --- User Status ---
    USER_STATUS_ACTIVE = 0
    USER_STATUS_BANNED = 1
    USER_STATUS_SUSPENDED = 2
    USER_STATUS_DELETED = 3

    @classmethod
    def validate_skill_type(cls, skill_type, category='military'):
        """
        Validate if skill type is valid.

        Args:
            skill_type: The skill type to validate
            category: 'military' or 'work'

        Returns:
            bool: True if valid

        Raises:
            ValueError: If skill type is invalid
        """
        if category == 'military':
            if skill_type not in cls.MILITARY_SKILL_TYPES:
                raise ValueError(f"Invalid military skill type: {skill_type}")
        elif category == 'work':
            if skill_type not in cls.WORK_SKILL_TYPES:
                raise ValueError(f"Invalid work skill type: {skill_type}")
        else:
            raise ValueError(f"Invalid skill category: {category}")
        return True

    @classmethod
    def get_skill_display_name(cls, skill_type):
        """Get human-readable skill name."""
        return skill_type.replace('_', ' ').title()
