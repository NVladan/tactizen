# app/models/zen_market.py
from datetime import datetime, date
from . import db
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, ROUND_UP, InvalidOperation


class ZenMarket(db.Model):
    """Manages the exchange between ZEN tokens and Gold."""
    __tablename__ = 'zen_market'

    id = db.Column(db.Integer, primary_key=True)

    # Pricing mechanism (similar to GoldMarket)
    initial_exchange_rate = db.Column(db.Numeric(10, 4), nullable=False, default=Decimal('50.00'))  # 50 Gold per 1 ZEN
    price_level = db.Column(db.Integer, default=0, nullable=False, index=True)
    progress_within_level = db.Column(db.Integer, default=0, nullable=False)
    volume_per_level = db.Column(db.Integer, default=100, nullable=False)  # 100 ZEN to change level
    price_adjustment_per_level = db.Column(db.Numeric(10, 4), default=Decimal('0.50'), nullable=False)  # +/- 0.50 gold per level

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    price_history = db.relationship('ZenPriceHistory', back_populates='zen_market', lazy='dynamic', cascade='all, delete-orphan')
    transactions = db.relationship('ZenTransaction', back_populates='market', lazy='dynamic', cascade='all, delete-orphan')

    MARKET_SPREAD_PERCENT = Decimal('0.05')  # 5% spread
    MINIMUM_EXCHANGE_RATE_UNIT = Decimal('0.01')

    @property
    def current_base_rate_for_one_zen(self):
        """Calculates the current theoretical base exchange rate (Gold for 1 ZEN)."""
        try:
            initial_r = Decimal(self.initial_exchange_rate)
            adjustment = Decimal(self.price_adjustment_per_level)
            level = int(self.price_level)
        except (TypeError, ValueError, InvalidOperation):
            return self.MINIMUM_EXCHANGE_RATE_UNIT
        calculated_rate = initial_r + (Decimal(level) * adjustment)
        return max(self.MINIMUM_EXCHANGE_RATE_UNIT, calculated_rate)

    @property
    def buy_zen_price(self):
        """Gold player PAYS to buy 1 ZEN (rate + spread)."""
        base_rate = self.current_base_rate_for_one_zen
        spread_amount = max(
            self.MINIMUM_EXCHANGE_RATE_UNIT / 10,
            (base_rate * self.MARKET_SPREAD_PERCENT)
        ).quantize(self.MINIMUM_EXCHANGE_RATE_UNIT / 10, rounding=ROUND_UP)
        price = (base_rate + spread_amount).quantize(self.MINIMUM_EXCHANGE_RATE_UNIT, rounding=ROUND_HALF_UP)
        return max(self.MINIMUM_EXCHANGE_RATE_UNIT * 2, price)

    @property
    def sell_zen_price(self):
        """Gold player GETS for selling 1 ZEN (rate - spread)."""
        base_rate = self.current_base_rate_for_one_zen
        spread_amount = max(
            self.MINIMUM_EXCHANGE_RATE_UNIT / 10,
            (base_rate * self.MARKET_SPREAD_PERCENT)
        ).quantize(self.MINIMUM_EXCHANGE_RATE_UNIT / 10, rounding=ROUND_DOWN)
        price = (base_rate - spread_amount).quantize(self.MINIMUM_EXCHANGE_RATE_UNIT, rounding=ROUND_HALF_UP)
        return max(self.MINIMUM_EXCHANGE_RATE_UNIT, price)

    @property
    def zen_volume_to_next_level(self):
        """ZEN volume needed to be BOUGHT to reach the next price level threshold."""
        try:
            remaining = int(self.volume_per_level) - int(self.progress_within_level)
            return max(0, remaining)
        except (TypeError, ValueError):
            return 0

    @property
    def zen_volume_to_previous_level(self):
        """ZEN volume needed to be SOLD to reach the previous price level threshold."""
        try:
            return max(0, int(self.progress_within_level) + 1)
        except (TypeError, ValueError):
            return 0

    def update_price_level(self, zen_amount, is_buy):
        """
        Updates price level based on transaction volume.

        Args:
            zen_amount (Decimal): Amount of ZEN traded
            is_buy (bool): True if user is buying ZEN, False if selling
        """
        zen_amount_int = int(zen_amount)

        if is_buy:
            # Buying ZEN increases price
            self.progress_within_level += zen_amount_int
            while self.progress_within_level >= self.volume_per_level:
                self.progress_within_level -= self.volume_per_level
                self.price_level += 1
        else:
            # Selling ZEN decreases price
            self.progress_within_level -= zen_amount_int
            while self.progress_within_level < 0:
                if self.price_level > -100:  # Prevent going too negative
                    self.price_level -= 1
                    self.progress_within_level += self.volume_per_level
                else:
                    self.progress_within_level = 0
                    break

        self.updated_at = datetime.utcnow()

    def __repr__(self):
        base_rate = self.current_base_rate_for_one_zen
        return f'<ZenMarket BaseRate(1ZEN):{base_rate:.2f} Gold>'


class ZenPriceHistory(db.Model):
    """Tracks daily historical ZEN/Gold exchange rates (OHLC)."""
    __tablename__ = 'zen_price_history'

    id = db.Column(db.Integer, primary_key=True)
    market_id = db.Column(db.Integer, db.ForeignKey('zen_market.id'), nullable=False, index=True)

    # OHLC (Open, High, Low, Close) exchange rates for the day
    rate_open = db.Column(db.Numeric(10, 4), nullable=False)   # Rate at start of day
    rate_high = db.Column(db.Numeric(10, 4), nullable=False)   # Highest rate during the day
    rate_low = db.Column(db.Numeric(10, 4), nullable=False)    # Lowest rate during the day
    rate_close = db.Column(db.Numeric(10, 4), nullable=False)  # Rate at end of day

    # Date for which this rate is recorded
    recorded_date = db.Column(db.Date, nullable=False, index=True)

    # Timestamp of when the record was created
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Composite unique constraint
    __table_args__ = (
        db.UniqueConstraint('market_id', 'recorded_date', name='unique_daily_zen_rate'),
        db.Index('idx_zen_history_lookup', 'market_id', 'recorded_date'),
    )

    # Relationships
    zen_market = db.relationship('ZenMarket', back_populates='price_history')

    def __repr__(self):
        return f'<ZenPriceHistory Date:{self.recorded_date} Close:{self.rate_close}>'


class ZenTransaction(db.Model):
    """Records ZEN buy/sell transactions for auditing and analytics."""
    __tablename__ = 'zen_transaction'

    id = db.Column(db.Integer, primary_key=True)
    market_id = db.Column(db.Integer, db.ForeignKey('zen_market.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Transaction details
    transaction_type = db.Column(db.String(10), nullable=False)  # 'buy' or 'sell'
    zen_amount = db.Column(db.Numeric(18, 8), nullable=False)  # Amount of ZEN traded
    gold_amount = db.Column(db.Numeric(20, 8), nullable=False)  # Amount of Gold exchanged
    exchange_rate = db.Column(db.Numeric(10, 4), nullable=False)  # Rate at time of transaction

    # Blockchain transaction hash (optional - for on-chain verification)
    blockchain_tx_hash = db.Column(db.String(66), nullable=True, index=True)
    blockchain_status = db.Column(db.String(20), default='pending')  # 'pending', 'confirmed', 'failed'

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    market = db.relationship('ZenMarket', back_populates='transactions')
    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<ZenTransaction U:{self.user_id} {self.transaction_type.upper()} {self.zen_amount}ZEN>'
