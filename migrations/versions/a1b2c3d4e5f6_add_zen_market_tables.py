"""add zen market tables

Revision ID: a1b2c3d4e5f6
Revises: 691b9c00
Create Date: 2025-11-17 23:21:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '691b9c00'
branch_labels = None
depends_on = None


def upgrade():
    # Create zen_market table
    op.create_table('zen_market',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('initial_exchange_rate', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('price_level', sa.Integer(), nullable=False),
        sa.Column('progress_within_level', sa.Integer(), nullable=False),
        sa.Column('volume_per_level', sa.Integer(), nullable=False),
        sa.Column('price_adjustment_per_level', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_zen_market_price_level'), 'zen_market', ['price_level'], unique=False)

    # Create zen_price_history table
    op.create_table('zen_price_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('market_id', sa.Integer(), nullable=False),
        sa.Column('rate_open', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('rate_high', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('rate_low', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('rate_close', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('recorded_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['market_id'], ['zen_market.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('market_id', 'recorded_date', name='unique_daily_zen_rate')
    )
    op.create_index('idx_zen_history_lookup', 'zen_price_history', ['market_id', 'recorded_date'], unique=False)
    op.create_index(op.f('ix_zen_price_history_market_id'), 'zen_price_history', ['market_id'], unique=False)
    op.create_index(op.f('ix_zen_price_history_recorded_date'), 'zen_price_history', ['recorded_date'], unique=False)

    # Create zen_transaction table
    op.create_table('zen_transaction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('market_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(length=10), nullable=False),
        sa.Column('zen_amount', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('gold_amount', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('exchange_rate', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('blockchain_tx_hash', sa.String(length=66), nullable=True),
        sa.Column('blockchain_status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['market_id'], ['zen_market.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_zen_transaction_blockchain_tx_hash'), 'zen_transaction', ['blockchain_tx_hash'], unique=False)
    op.create_index(op.f('ix_zen_transaction_created_at'), 'zen_transaction', ['created_at'], unique=False)
    op.create_index(op.f('ix_zen_transaction_market_id'), 'zen_transaction', ['market_id'], unique=False)
    op.create_index(op.f('ix_zen_transaction_user_id'), 'zen_transaction', ['user_id'], unique=False)

    # Insert default ZEN market (only one instance needed)
    op.execute("""
        INSERT INTO zen_market (initial_exchange_rate, price_level, progress_within_level, volume_per_level, price_adjustment_per_level, created_at, updated_at)
        VALUES (50.00, 0, 0, 100, 0.50, NOW(), NOW())
    """)


def downgrade():
    op.drop_index(op.f('ix_zen_transaction_user_id'), table_name='zen_transaction')
    op.drop_index(op.f('ix_zen_transaction_market_id'), table_name='zen_transaction')
    op.drop_index(op.f('ix_zen_transaction_created_at'), table_name='zen_transaction')
    op.drop_index(op.f('ix_zen_transaction_blockchain_tx_hash'), table_name='zen_transaction')
    op.drop_table('zen_transaction')

    op.drop_index(op.f('ix_zen_price_history_recorded_date'), table_name='zen_price_history')
    op.drop_index(op.f('ix_zen_price_history_market_id'), table_name='zen_price_history')
    op.drop_index('idx_zen_history_lookup', table_name='zen_price_history')
    op.drop_table('zen_price_history')

    op.drop_index(op.f('ix_zen_market_price_level'), table_name='zen_market')
    op.drop_table('zen_market')
