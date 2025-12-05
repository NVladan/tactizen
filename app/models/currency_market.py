# tactizen/app/models/currency_market.py
from datetime import datetime, date
from . import db
# Note: No direct import of Country needed here for the relationship string
# --- CORRECTED DECIMAL IMPORT ---
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, ROUND_UP, InvalidOperation
# --- END CORRECTION ---

class GoldMarket(db.Model):
    """Manages the exchange between Gold and a specific country's local currency."""
    __tablename__ = 'gold_market'

    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), primary_key=True)

    initial_exchange_rate = db.Column(db.Numeric(10, 4), nullable=False, default=Decimal('100.00'))
    price_level = db.Column(db.Integer, default=0, nullable=False, index=True)
    progress_within_level = db.Column(db.Integer, default=0, nullable=False)
    volume_per_level = db.Column(db.Integer, default=1000, nullable=False)
    price_adjustment_per_level = db.Column(db.Numeric(10, 4), default=Decimal('1.00'), nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    country = db.relationship("Country", back_populates="gold_market")
    price_history = db.relationship('CurrencyPriceHistory', back_populates='gold_market', lazy='dynamic', cascade='all, delete-orphan', primaryjoin="GoldMarket.country_id==foreign(CurrencyPriceHistory.country_id)")

    MARKET_SPREAD_PERCENT = Decimal('0.05')
    MINIMUM_EXCHANGE_RATE_UNIT = Decimal('0.01')

    @property
    def current_base_rate_for_one_gold(self):
        """Calculates the current theoretical base exchange rate (local currency for 1 Gold)."""
        try:
            initial_r = Decimal(self.initial_exchange_rate)
            adjustment = Decimal(self.price_adjustment_per_level)
            level = int(self.price_level)
        except (TypeError, ValueError, InvalidOperation):
            return self.MINIMUM_EXCHANGE_RATE_UNIT
        calculated_rate = initial_r + (Decimal(level) * adjustment)
        return max(self.MINIMUM_EXCHANGE_RATE_UNIT, calculated_rate)

    @property
    def buy_gold_price(self):
        """Local currency player PAYS to buy 1 Gold (rate + spread)."""
        base_rate = self.current_base_rate_for_one_gold
        # Use ROUND_UP here
        spread_amount = max(self.MINIMUM_EXCHANGE_RATE_UNIT / 10, (base_rate * self.MARKET_SPREAD_PERCENT)).quantize(
            self.MINIMUM_EXCHANGE_RATE_UNIT / 10, rounding=ROUND_UP # Uses ROUND_UP
        )
        price = (base_rate + spread_amount).quantize(self.MINIMUM_EXCHANGE_RATE_UNIT, rounding=ROUND_HALF_UP)
        return max(self.MINIMUM_EXCHANGE_RATE_UNIT * 2, price)

    @property
    def sell_gold_price(self):
        """Local currency player GETS for selling 1 Gold (rate - spread)."""
        base_rate = self.current_base_rate_for_one_gold
        # Use ROUND_DOWN here
        spread_amount = max(self.MINIMUM_EXCHANGE_RATE_UNIT / 10, (base_rate * self.MARKET_SPREAD_PERCENT)).quantize(
            self.MINIMUM_EXCHANGE_RATE_UNIT / 10, rounding=ROUND_DOWN # Uses ROUND_DOWN
        )
        price = (base_rate - spread_amount).quantize(self.MINIMUM_EXCHANGE_RATE_UNIT, rounding=ROUND_HALF_UP)
        return max(self.MINIMUM_EXCHANGE_RATE_UNIT, price)

    @property
    def gold_volume_to_next_level(self):
        """Gold volume needed to be BOUGHT to reach the next price level threshold."""
        try:
            remaining = int(self.volume_per_level) - int(self.progress_within_level)
            return max(0, remaining)
        except (TypeError, ValueError):
            return 0

    @property
    def gold_volume_to_previous_level(self):
        """Gold volume needed to be SOLD to reach the previous price level threshold."""
        try:
            return max(0, int(self.progress_within_level) + 1)
        except (TypeError, ValueError):
             return 0

    def __repr__(self):
        """String representation of the GoldMarket object."""
        country_id = getattr(self, 'country_id', 'N/A')
        base_rate = self.current_base_rate_for_one_gold
        return f'<GoldMarket C:{country_id} BaseRate(1G):{base_rate:.2f}>'


class CurrencyPriceHistory(db.Model):
    """Tracks daily historical exchange rates for currencies (recorded at 9 AM CET)."""
    __tablename__ = 'currency_price_history'

    id = db.Column(db.Integer, primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, unique=False, index=True)

    # OHLC (Open, High, Low, Close) exchange rates for the day
    rate_open = db.Column(db.Numeric(10, 4), nullable=False)   # Rate at start of day (9 AM CET)
    rate_high = db.Column(db.Numeric(10, 4), nullable=False)   # Highest rate during the day
    rate_low = db.Column(db.Numeric(10, 4), nullable=False)    # Lowest rate during the day
    rate_close = db.Column(db.Numeric(10, 4), nullable=False)  # Rate at end of day (next 9 AM CET)

    # Legacy field for backwards compatibility
    exchange_rate = db.Column(db.Numeric(10, 4), nullable=True)  # Can be null now

    # Date for which this rate is recorded (date only, normalized to midnight UTC)
    recorded_date = db.Column(db.Date, nullable=False, index=True)

    # Timestamp of when the record was created
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Composite unique constraint
    __table_args__ = (
        db.UniqueConstraint('country_id', 'recorded_date', name='unique_daily_currency_rate'),
        db.Index('idx_currency_history_lookup', 'country_id', 'recorded_date'),
    )

    # Relationships
    gold_market = db.relationship('GoldMarket', back_populates='price_history', foreign_keys=[country_id], primaryjoin="CurrencyPriceHistory.country_id==GoldMarket.country_id")
    country = db.relationship('Country', overlaps="gold_market,price_history")

    def __repr__(self):
        return f'<CurrencyPriceHistory C:{self.country_id} Date:{self.recorded_date} Rate:{self.exchange_rate}>'