# app/utils.py
import math
from decimal import Decimal, ROUND_HALF_UP

# --- Leveling Constants ---
# XP needed to go from level 1 to level 2 is BASE_XP_INCREMENT.
# XP needed doubles for each subsequent level.
# Level 1->2: 20 XP (Total: 20)
# Level 2->3: 40 XP (Total: 60)
# Level 3->4: 80 XP (Total: 140)
BASE_XP_INCREMENT = 20

def get_total_xp_for_level(level):
    """Calculates the total cumulative XP required to reach the start of a given level."""
    if level <= 1:
        return 0
    # Formula: BASE_XP_INCREMENT * (2^(level - 1) - 1)
    return BASE_XP_INCREMENT * (pow(2, level - 1) - 1)

def get_level_from_xp(xp):
    """Calculates the current level based on total XP."""
    # Convert to float to handle Decimal types from database queries
    xp = float(xp)

    if xp < 0:
        return 1 # Default to 1

    # Handle xp=0 case to avoid log2(0) or log2(1) issues depending on formula use
    if xp < BASE_XP_INCREMENT: # If less than XP needed for level 2
        return 1

    # Formula: level = floor(log2(xp / BASE_XP_INCREMENT + 1) + 1)
    # Use math.log2 for base-2 logarithm
    try:
        # Add a small epsilon to handle potential floating point inaccuracies near level boundaries
        epsilon = 1e-9
        level_float = math.log2(xp / BASE_XP_INCREMENT + 1 + epsilon) + 1
        current_level = math.floor(level_float)
    except ValueError:
        # Handle potential math domain errors if xp is negative (already checked, but safe)
        current_level = 1

    return max(1, current_level) # Ensure level is at least 1

def get_xp_for_next_level_increment(level):
    """Calculates the amount of XP needed to get FROM the start of level TO the start of level+1."""
    # Formula: BASE_XP_INCREMENT * 2^(level - 1)
    # Example: To get from Level 1 (0 XP) to Level 2 (20 XP) needs 20 * 2^0 = 20 XP.
    # Example: To get from Level 2 (20 XP) to Level 3 (60 XP) needs 20 * 2^1 = 40 XP.
    # Example: To get from Level 3 (60 XP) to Level 4 (140 XP) needs 20 * 2^2 = 80 XP.
    if level < 1:
        level = 1 # Ensure level is at least 1 for calculation
    return BASE_XP_INCREMENT * pow(2, level - 1)


# --- Currency Display Utilities ---
def format_currency(amount, decimals=2):
    """
    Format a Decimal currency amount for display with specified decimal places.

    Args:
        amount: Decimal or numeric value
        decimals: Number of decimal places (default: 2)

    Returns:
        str: Formatted currency string (e.g., "123.45")

    Example:
        >>> format_currency(Decimal('123.456789'))
        '123.46'
        >>> format_currency(Decimal('0.00000001'), decimals=8)
        '0.00000001'
    """
    if amount is None:
        amount = Decimal('0.0')

    # Convert to Decimal if not already
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))

    # Create quantize pattern (e.g., '0.01' for 2 decimals)
    quantize_pattern = Decimal('0.' + '0' * decimals) if decimals > 0 else Decimal('1')

    # Round using ROUND_HALF_UP (banker's rounding)
    rounded = amount.quantize(quantize_pattern, rounding=ROUND_HALF_UP)

    return str(rounded)


def format_currency_with_code(amount, currency_code, decimals=2):
    """
    Format currency with currency code.

    Args:
        amount: Decimal or numeric value
        currency_code: Currency code (e.g., 'USD', 'MXN', 'GOLD')
        decimals: Number of decimal places (default: 2)

    Returns:
        str: Formatted string (e.g., "123.45 USD")

    Example:
        >>> format_currency_with_code(Decimal('123.45'), 'USD')
        '123.45 USD'
    """
    formatted_amount = format_currency(amount, decimals)
    if currency_code:
        return f"{formatted_amount} {currency_code}"
    return formatted_amount


def format_gold(amount, decimals=2):
    """
    Format gold amount for display.

    Args:
        amount: Decimal or numeric value
        decimals: Number of decimal places (default: 2)

    Returns:
        str: Formatted gold string with icon (e.g., "123.45 ⚜")
    """
    formatted_amount = format_currency(amount, decimals)
    return f"{formatted_amount} ⚜"  # Using fleur-de-lis as gold icon


def format_percentage(value, decimals=2):
    """
    Format a percentage for display.

    Args:
        value: Decimal or numeric percentage value (e.g., 0.15 for 15%)
        decimals: Number of decimal places (default: 2)

    Returns:
        str: Formatted percentage (e.g., "15.00%")
    """
    if value is None:
        value = Decimal('0.0')

    if not isinstance(value, Decimal):
        value = Decimal(str(value))

    percentage = value * 100
    formatted = format_currency(percentage, decimals)
    return f"{formatted}%"


# --- Price Tracking Utilities ---
def update_market_price_ohlc(country_id, resource_id, quality, new_price):
    """
    Update or create today's OHLC price record for a market item.

    Args:
        country_id: Country ID
        resource_id: Resource ID
        quality: Quality level
        new_price: New price from a trade (as Decimal)
    """
    from datetime import date, datetime
    from app.extensions import db
    from app.models.resource import MarketPriceHistory
    import logging

    logger = logging.getLogger(__name__)

    try:
        today = date.today()
        new_price = Decimal(str(new_price))

        # Check if record exists for today
        existing = db.session.scalar(
            db.select(MarketPriceHistory)
            .where(MarketPriceHistory.country_id == country_id)
            .where(MarketPriceHistory.resource_id == resource_id)
            .where(MarketPriceHistory.quality == quality)
            .where(MarketPriceHistory.recorded_date == today)
        )

        if existing:
            # Update existing record
            # High = max of current high and new price
            if new_price > existing.price_high:
                existing.price_high = new_price

            # Low = min of current low and new price
            if new_price < existing.price_low:
                existing.price_low = new_price

            # Close = most recent price (this one)
            existing.price_close = new_price

            logger.debug(
                f"Updated OHLC for resource {resource_id} Q{quality} in country {country_id}: "
                f"O={existing.price_open}, H={existing.price_high}, L={existing.price_low}, C={existing.price_close}"
            )
        else:
            # Create new record with open = high = low = close = new_price
            price_history = MarketPriceHistory(
                country_id=country_id,
                resource_id=resource_id,
                quality=quality,
                price_open=new_price,
                price_high=new_price,
                price_low=new_price,
                price_close=new_price,
                price=new_price,  # Keep legacy field updated
                recorded_date=today,
                created_at=datetime.utcnow()
            )
            db.session.add(price_history)

            logger.debug(
                f"Created OHLC record for resource {resource_id} Q{quality} in country {country_id}: "
                f"price={new_price}"
            )

        # Commit handled by caller

    except Exception as e:
        logger.error(f"Error updating market price OHLC: {e}", exc_info=True)
        raise


def update_zen_rate_ohlc(market_id, new_rate):
    """
    Update or create today's OHLC rate record for ZEN market.

    Args:
        market_id: ZEN Market ID
        new_rate: New exchange rate from a trade (as Decimal, Gold per 1 ZEN)
    """
    from datetime import date, datetime
    from app.extensions import db
    from app.models.zen_market import ZenPriceHistory
    import logging

    logger = logging.getLogger(__name__)

    try:
        today = date.today()
        new_rate = Decimal(str(new_rate))

        # Check if record exists for today
        existing = db.session.scalar(
            db.select(ZenPriceHistory)
            .where(ZenPriceHistory.market_id == market_id)
            .where(ZenPriceHistory.recorded_date == today)
        )

        if existing:
            # Update existing record
            # High = max of current high and new rate
            if new_rate > existing.rate_high:
                existing.rate_high = new_rate

            # Low = min of current low and new rate
            if new_rate < existing.rate_low:
                existing.rate_low = new_rate

            # Close = most recent rate (this one)
            existing.rate_close = new_rate

            logger.debug(
                f"Updated ZEN OHLC for market {market_id}: "
                f"O={existing.rate_open}, H={existing.rate_high}, L={existing.rate_low}, C={existing.rate_close}"
            )
        else:
            # Create new record with open = high = low = close = new_rate
            zen_history = ZenPriceHistory(
                market_id=market_id,
                rate_open=new_rate,
                rate_high=new_rate,
                rate_low=new_rate,
                rate_close=new_rate,
                recorded_date=today,
                created_at=datetime.utcnow()
            )
            db.session.add(zen_history)

            logger.debug(
                f"Created ZEN OHLC record for market {market_id}: "
                f"rate={new_rate}"
            )

        # Commit handled by caller

    except Exception as e:
        logger.error(f"Error updating ZEN rate OHLC: {e}", exc_info=True)
        raise


def update_currency_rate_ohlc(country_id, new_rate):
    """
    Update or create today's OHLC rate record for a country's gold market.

    Args:
        country_id: Country ID
        new_rate: New exchange rate from a trade (as Decimal)
    """
    from datetime import date, datetime
    from app.extensions import db
    from app.models.currency_market import CurrencyPriceHistory
    import logging

    logger = logging.getLogger(__name__)

    try:
        today = date.today()
        new_rate = Decimal(str(new_rate))

        # Check if record exists for today
        existing = db.session.scalar(
            db.select(CurrencyPriceHistory)
            .where(CurrencyPriceHistory.country_id == country_id)
            .where(CurrencyPriceHistory.recorded_date == today)
        )

        if existing:
            # Update existing record
            # High = max of current high and new rate
            if new_rate > existing.rate_high:
                existing.rate_high = new_rate

            # Low = min of current low and new rate
            if new_rate < existing.rate_low:
                existing.rate_low = new_rate

            # Close = most recent rate (this one)
            existing.rate_close = new_rate

            logger.debug(
                f"Updated currency OHLC for country {country_id}: "
                f"O={existing.rate_open}, H={existing.rate_high}, L={existing.rate_low}, C={existing.rate_close}"
            )
        else:
            # Create new record with open = high = low = close = new_rate
            rate_history = CurrencyPriceHistory(
                country_id=country_id,
                rate_open=new_rate,
                rate_high=new_rate,
                rate_low=new_rate,
                rate_close=new_rate,
                exchange_rate=new_rate,  # Keep legacy field updated
                recorded_date=today,
                created_at=datetime.utcnow()
            )
            db.session.add(rate_history)

            logger.debug(
                f"Created currency OHLC record for country {country_id}: "
                f"rate={new_rate}"
            )

        # Commit handled by caller

    except Exception as e:
        logger.error(f"Error updating currency rate OHLC: {e}", exc_info=True)
        raise