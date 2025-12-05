# app/models/resource.py

import enum
import math
from datetime import datetime
# *** CORRECTED IMPORT LINE ***
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, ROUND_UP, InvalidOperation, getcontext
# *** END CORRECTION ***
from slugify import slugify
from sqlalchemy import Numeric, Integer # Import Integer

# Assuming db is initialized in extensions and imported in models/__init__
from . import db # Use relative import
from .location import Country # Import Country if needed for relationships defined here
from app.mixins import SoftDeleteMixin

# --- Resource Category Enum ---
class ResourceCategory(enum.Enum):
    RAW_MATERIAL = 'Raw Material'
    MANUFACTURED_GOOD = 'Semi Products'
    FOOD = 'Food'
    WEAPON = 'Weapon'
    CONSTRUCTION = 'Construction'
    ENERGY = 'Energy'
    HOUSE = 'House'
    # Add other categories as needed


# --- Models ---

class Resource(SoftDeleteMixin, db.Model):
    """Represents an item resource in the game."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True, index=True, nullable=False)
    category = db.Column(db.Enum(ResourceCategory), nullable=False, index=True)
    icon_path = db.Column(db.String(100), nullable=True) # Path relative to static folder

    # Market Parameters
    market_volume_threshold = db.Column(db.Integer, default=200, nullable=False) # Default volume per level
    market_price_adjustment = db.Column(Numeric(10, 4), default=Decimal('0.1'), nullable=False)

    # Quality System
    can_have_quality = db.Column(db.Boolean, default=False, nullable=False) # True for manufactured goods

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships (using strings)
    inventory_items = db.relationship('InventoryItem', back_populates='resource', lazy='dynamic')
    market_items = db.relationship('CountryMarketItem', back_populates='resource', lazy='dynamic')

    def __init__(self, name, category, icon_path=None, threshold=200, adjustment=Decimal('0.1'), can_have_quality=False): # Default threshold 200
        """Initializes a new Resource."""
        self.name = name
        self.slug = slugify(name)
        self.category = category
        self.icon_path = icon_path
        self.market_volume_threshold = threshold
        self.market_price_adjustment = adjustment # Store as Decimal
        self.can_have_quality = can_have_quality

    def __repr__(self):
        """String representation of the Resource object."""
        return f'<Resource {self.name}>'


class InventoryItem(db.Model):
    """Represents a user's holding of a specific resource."""
    # Composite primary key
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), primary_key=True)
    quality = db.Column(db.Integer, primary_key=True, default=0, nullable=False) # 0 for non-quality items, 1-5 for quality items

    # *** CHANGED TO INTEGER ***
    quantity = db.Column(db.Integer, default=0, nullable=False)

    # Relationships (using strings)
    user = db.relationship('User', back_populates='inventory')
    resource = db.relationship('Resource', back_populates='inventory_items')

    def __repr__(self):
        """String representation of the InventoryItem object."""
        # Display as integer
        return f'<InventoryItem User:{self.user_id} Res:{self.resource_id} Qty:{self.quantity}>'


class ActiveResidence(db.Model):
    """Represents a user's currently active house/residence."""
    __tablename__ = 'active_residence'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=False)
    quality = db.Column(db.Integer, nullable=False, default=1)  # Q1-Q5 for houses

    # Timestamps
    activated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)  # activated_at + 30 days
    last_restore_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = db.relationship('User', back_populates='active_residence')
    resource = db.relationship('Resource')

    def __repr__(self):
        return f'<ActiveResidence User:{self.user_id} Resource:{self.resource_id}>'

    @property
    def is_expired(self):
        """Check if the residence has expired."""
        return datetime.utcnow() >= self.expires_at

    @property
    def time_remaining(self):
        """Get time remaining until expiration."""
        if self.is_expired:
            return None
        return self.expires_at - datetime.utcnow()

    @property
    def next_restore_at(self):
        """Calculate when the next restore will happen (every 15 minutes)."""
        from datetime import timedelta
        return self.last_restore_at + timedelta(minutes=15)


class CountryMarketItem(db.Model):
    """Represents a resource on a specific country's market using Price Levels."""
    # Composite primary key
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), primary_key=True)
    quality = db.Column(db.Integer, primary_key=True, default=0, nullable=False) # 0 for non-quality items, 1-5 for quality items

    # Market State
    initial_price = db.Column(Numeric(10, 4), nullable=False) # Base price when level is 0
    price_level = db.Column(db.Integer, default=0, nullable=False, index=True) # Current price level (can be negative)
    # *** CHANGED TO INTEGER ***
    progress_within_level = db.Column(db.Integer, default=0, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships (using strings)
    country = db.relationship('Country', back_populates='market_items')
    resource = db.relationship('Resource', back_populates='market_items')
    price_history = db.relationship('MarketPriceHistory', back_populates='market_item', lazy='dynamic', cascade='all, delete-orphan')

    # --- Constants ---
    MARKET_SPREAD_PERCENT = Decimal('0.10') # 10% spread
    MINIMUM_PRICE = Decimal('0.01') # Minimum allowed price
    # FLOAT_TOLERANCE no longer needed for integer comparisons

    # --- Helper for safe Integer conversion ---
    def _get_valid_vol_prog_int(self):
        """Helper to safely get Integer volume_per_level and progress, returns None if invalid."""
        res = self.resource
        if not res and hasattr(self, 'resource_id') and self.resource_id:
             try: res = db.session.get(Resource, self.resource_id)
             except Exception: return None, None
        elif not res: return None, None

        try:
            vol = int(res.market_volume_threshold)
            if vol <= 0: return None, None
        except (TypeError, ValueError, AttributeError): return None, None

        try:
            prog_val = self.progress_within_level if self.progress_within_level is not None else 0
            prog = int(prog_val)
        except (TypeError, ValueError, AttributeError): return None, None

        return vol, prog

    # --- Calculated Market Properties ---
    @property
    def volume_per_level(self):
        """Safely returns the resource's volume threshold per level as Integer."""
        vol, _ = self._get_valid_vol_prog_int()
        return vol if vol is not None else 200 # Default

    @property
    def price_adjustment_per_level(self):
        """Safely returns the resource's price adjustment per level as Decimal."""
        res = self.resource
        if not res and hasattr(self, 'resource_id') and self.resource_id:
             try: res = db.session.get(Resource, self.resource_id)
             except Exception: res = None
        elif not res: res = None

        if res and hasattr(res, 'market_price_adjustment'):
            try:
                adj = Decimal(res.market_price_adjustment)
                return adj if adj >= 0 else Decimal('0.1')
            except Exception: return Decimal('0.1')
        return Decimal('0.1')

    @property
    def current_base_price(self):
        """Calculates the current theoretical base price based on price_level."""
        try:
            initial_p = Decimal(self.initial_price)
            adjustment = self.price_adjustment_per_level
            level = int(self.price_level)
        except (TypeError, ValueError, InvalidOperation):
             return self.MINIMUM_PRICE
        calculated_price = initial_p + (Decimal(level) * adjustment)
        return max(self.MINIMUM_PRICE, calculated_price)

    @property
    def buy_price(self):
        """Calculates the price users buy at (base + spread)."""
        base_price = self.current_base_price
        # Use ROUND_UP for buy price spread calculation
        spread_amount = max(Decimal('0.0001'), (base_price * self.MARKET_SPREAD_PERCENT)).quantize(Decimal('0.0001'), rounding=ROUND_UP)
        buy_p = (base_price + spread_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return max(self.MINIMUM_PRICE + Decimal('0.01'), buy_p)

    @property
    def sell_price(self):
        """Calculates the price users sell at (base - spread)."""
        base_price = self.current_base_price
        # Use ROUND_DOWN for sell price spread calculation
        spread_amount = max(Decimal('0.0001'), (base_price * self.MARKET_SPREAD_PERCENT)).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
        sell_p = (base_price - spread_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return max(self.MINIMUM_PRICE, sell_p)

    # --- Properties for Transaction Limits & Display (INTEGER LOGIC) ---
    @property
    def volume_to_next_level(self):
        """Volume needed to purchase to reach the next price level threshold (Integer)."""
        vol_per_lvl, progress = self._get_valid_vol_prog_int()
        if vol_per_lvl is None: return 0 # Fallback

        remaining = vol_per_lvl - progress
        return max(0, remaining)


    @property
    def volume_to_previous_level(self):
        """Volume needed to sell to reach the previous price level threshold (Integer)."""
        vol_per_lvl, progress = self._get_valid_vol_prog_int()
        if vol_per_lvl is None: return 0 # Fallback

        # Amount needed to sell to hit 0 progress is the current progress.
        # If progress is 0, returns 0. Route logic handles the "sell 1" limit.
        return max(0, progress)


    def __repr__(self):
        """String representation of the CountryMarketItem object."""
        country_id = getattr(self, 'country_id', 'N/A')
        resource_id = getattr(self, 'resource_id', 'N/A')
        level = getattr(self, 'price_level', 'N/A')
        progress = getattr(self, 'progress_within_level', 'N/A')

        return f'<MarketItem C:{country_id} R:{resource_id} Lvl:{level} Prog:{progress}>' # Show integer progress


class MarketPriceHistory(db.Model):
    """Tracks daily historical prices for market items (recorded at 9 AM CET)."""
    __tablename__ = 'market_price_history'

    id = db.Column(db.Integer, primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=False)
    quality = db.Column(db.Integer, default=0, nullable=False)

    # OHLC (Open, High, Low, Close) prices for the day
    price_open = db.Column(Numeric(10, 4), nullable=False)   # Price at start of day (9 AM CET)
    price_high = db.Column(Numeric(10, 4), nullable=False)   # Highest price during the day
    price_low = db.Column(Numeric(10, 4), nullable=False)    # Lowest price during the day
    price_close = db.Column(Numeric(10, 4), nullable=False)  # Price at end of day (next 9 AM CET)

    # Legacy field for backwards compatibility
    price = db.Column(Numeric(10, 4), nullable=True)  # Can be null now

    # Date for which this price is recorded (date only, normalized to midnight UTC)
    recorded_date = db.Column(db.Date, nullable=False, index=True)

    # Timestamp of when the record was created
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Composite foreign key to CountryMarketItem
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['country_id', 'resource_id', 'quality'],
            ['country_market_item.country_id', 'country_market_item.resource_id', 'country_market_item.quality']
        ),
        db.UniqueConstraint('country_id', 'resource_id', 'quality', 'recorded_date', name='unique_daily_price'),
        db.Index('idx_price_history_lookup', 'country_id', 'resource_id', 'quality', 'recorded_date'),
    )

    # Relationships
    market_item = db.relationship('CountryMarketItem', back_populates='price_history')
    country = db.relationship('Country', overlaps="market_item,price_history")
    resource = db.relationship('Resource', overlaps="market_item,price_history")

    def __repr__(self):
        return f'<MarketPriceHistory C:{self.country_id} R:{self.resource_id} Date:{self.recorded_date} Price:{self.price}>'