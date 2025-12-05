# app/models/currency.py

from datetime import datetime
from decimal import Decimal
from sqlalchemy import Numeric, CheckConstraint, Index
from . import db
from app.logging_config import log_transaction as log_transaction_to_file

class UserCurrency(db.Model):
    """Tracks how much of each country's currency a user owns."""
    __tablename__ = 'user_currency'

    # Composite primary key
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True, nullable=False)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), primary_key=True, nullable=False)

    # Amount of this currency the user owns
    # Numeric(20, 8) = 20 total digits, 8 decimal places for precision
    # Allows for: 999,999,999,999.99999999
    amount = db.Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)

    # Timestamps for tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = db.relationship('User', back_populates='currencies')
    country = db.relationship('Country', back_populates='user_holdings')

    # Add CHECK constraint to prevent negative balances
    __table_args__ = (
        CheckConstraint('amount >= 0', name='currency_amount_non_negative'),
        # Index for fast lookup of user's currencies
        Index('idx_user_currencies', 'user_id'),
    )

    def __repr__(self):
        return f'<UserCurrency User:{self.user_id} Country:{self.country_id} Amount:{self.amount}>'


class FinancialTransaction(db.Model):
    """Immutable audit log of all financial transactions."""
    __tablename__ = 'financial_transaction'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Transaction type
    transaction_type = db.Column(db.String(30), nullable=False, index=True)
    # Types: CURRENCY_GAIN, CURRENCY_LOSS, GOLD_GAIN, GOLD_LOSS,
    #        MARKET_BUY, MARKET_SELL, CURRENCY_EXCHANGE, TRAVEL, ADMIN_ADJUSTMENT

    # Amounts (always positive, type indicates gain/loss)
    amount = db.Column(Numeric(20, 8), nullable=False)
    currency_type = db.Column(db.String(10), nullable=False)  # 'GOLD', 'USD', 'MXN', etc.

    # Balances AFTER transaction (for verification)
    balance_after = db.Column(Numeric(20, 8), nullable=False)

    # Context
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=True, index=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=True)
    related_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # For P2P trades

    description = db.Column(db.String(255))
    metadata_json = db.Column(db.JSON)  # Store additional data

    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='transactions')
    country = db.relationship('Country', backref='transactions')
    resource = db.relationship('Resource', backref='transactions')

    def __repr__(self):
        return f'<Transaction {self.transaction_type} {self.amount} {self.currency_type} @{self.timestamp}>'


# Helper function to log transactions
def log_transaction(user, transaction_type, amount, currency_type, balance_after, **kwargs):
    """
    Helper to log all financial transactions.

    Logs to both:
    1. Database (FinancialTransaction table) for permanent audit trail
    2. Log files (transactions.log) for easy monitoring and analysis
    """
    # Create database record
    transaction = FinancialTransaction(
        user_id=user.id,
        transaction_type=transaction_type,
        amount=Decimal(str(amount)),
        currency_type=currency_type,
        balance_after=Decimal(str(balance_after)),
        **kwargs
    )
    db.session.add(transaction)

    # Also log to file for easy access
    description = kwargs.get('description', '')
    country_id = kwargs.get('country_id')
    resource_id = kwargs.get('resource_id')

    log_transaction_to_file(
        user_id=user.id,
        transaction_type=transaction_type,
        amount=str(amount),
        currency=currency_type,
        description=description,
        balance_after=str(balance_after),
        country_id=country_id,
        resource_id=resource_id
    )

    return transaction
