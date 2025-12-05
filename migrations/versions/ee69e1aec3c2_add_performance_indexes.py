"""add_performance_indexes

Revision ID: ee69e1aec3c2
Revises: 97037cff1a8f
Create Date: 2025-11-06 00:03:28.422763

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ee69e1aec3c2'
down_revision = '97037cff1a8f'
branch_labels = None
depends_on = None


def upgrade():
    # === User Table Indexes ===
    # Timestamp indexes for "recently joined" queries
    op.create_index('idx_user_created_at', 'user', ['created_at'], unique=False)
    op.create_index('idx_user_updated_at', 'user', ['updated_at'], unique=False)

    # Composite index for "new citizens of country X"
    op.create_index('idx_user_citizenship_created', 'user', ['citizenship_id', 'created_at'], unique=False)

    # Composite index for "active users in region X"
    op.create_index('idx_user_region_updated', 'user', ['current_region_id', 'updated_at'], unique=False)

    # === Country Table Indexes ===
    # Timestamp indexes
    op.create_index('idx_country_created_at', 'country', ['created_at'], unique=False)
    op.create_index('idx_country_updated_at', 'country', ['updated_at'], unique=False)

    # Currency code for lookups
    op.create_index('idx_country_currency_code', 'country', ['currency_code'], unique=False)

    # === Region Table Indexes ===
    # Timestamp indexes
    op.create_index('idx_region_created_at', 'region', ['created_at'], unique=False)
    op.create_index('idx_region_updated_at', 'region', ['updated_at'], unique=False)

    # Foreign key index (frequently joined)
    op.create_index('idx_region_original_owner', 'region', ['original_owner_id'], unique=False)

    # === Resource Table Indexes ===
    # Timestamp indexes
    op.create_index('idx_resource_created_at', 'resource', ['created_at'], unique=False)
    op.create_index('idx_resource_updated_at', 'resource', ['updated_at'], unique=False)

    # === InventoryItem Table Indexes ===
    # Composite primary key is already indexed, but add reverse lookup
    op.create_index('idx_inventory_resource_user', 'inventory_item', ['resource_id', 'user_id'], unique=False)

    # === CountryMarketItem Table Indexes ===
    # Timestamp indexes for "active markets" queries
    op.create_index('idx_market_created_at', 'country_market_item', ['created_at'], unique=False)
    op.create_index('idx_market_updated_at', 'country_market_item', ['updated_at'], unique=False)

    # Composite index for reverse lookups (resource -> markets)
    op.create_index('idx_market_resource_country', 'country_market_item', ['resource_id', 'country_id'], unique=False)

    # Index for finding markets by activity
    op.create_index('idx_market_country_updated', 'country_market_item', ['country_id', 'updated_at'], unique=False)

    # === GoldMarket Table Indexes ===
    # Timestamp indexes
    op.create_index('idx_gold_market_created_at', 'gold_market', ['created_at'], unique=False)
    op.create_index('idx_gold_market_updated_at', 'gold_market', ['updated_at'], unique=False)

    # === UserCurrency Table Indexes ===
    # Timestamp indexes
    op.create_index('idx_user_currency_created_at', 'user_currency', ['created_at'], unique=False)
    op.create_index('idx_user_currency_updated_at', 'user_currency', ['updated_at'], unique=False)

    # Composite index for reverse lookups (country -> holders)
    op.create_index('idx_user_currency_country_user', 'user_currency', ['country_id', 'user_id'], unique=False)

    # === FinancialTransaction Table Indexes ===
    # Composite indexes for common queries
    op.create_index('idx_transaction_type_timestamp', 'financial_transaction', ['transaction_type', 'timestamp'], unique=False)
    op.create_index('idx_transaction_user_timestamp', 'financial_transaction', ['user_id', 'timestamp'], unique=False)
    op.create_index('idx_transaction_country_timestamp', 'financial_transaction', ['country_id', 'timestamp'], unique=False)

    # Index for currency-specific queries
    op.create_index('idx_transaction_currency_type', 'financial_transaction', ['currency_type'], unique=False)


def downgrade():
    # Drop indexes in reverse order

    # FinancialTransaction
    op.drop_index('idx_transaction_currency_type', table_name='financial_transaction')
    op.drop_index('idx_transaction_country_timestamp', table_name='financial_transaction')
    op.drop_index('idx_transaction_user_timestamp', table_name='financial_transaction')
    op.drop_index('idx_transaction_type_timestamp', table_name='financial_transaction')

    # UserCurrency
    op.drop_index('idx_user_currency_country_user', table_name='user_currency')
    op.drop_index('idx_user_currency_updated_at', table_name='user_currency')
    op.drop_index('idx_user_currency_created_at', table_name='user_currency')

    # GoldMarket
    op.drop_index('idx_gold_market_updated_at', table_name='gold_market')
    op.drop_index('idx_gold_market_created_at', table_name='gold_market')

    # CountryMarketItem
    op.drop_index('idx_market_country_updated', table_name='country_market_item')
    op.drop_index('idx_market_resource_country', table_name='country_market_item')
    op.drop_index('idx_market_updated_at', table_name='country_market_item')
    op.drop_index('idx_market_created_at', table_name='country_market_item')

    # InventoryItem
    op.drop_index('idx_inventory_resource_user', table_name='inventory_item')

    # Resource
    op.drop_index('idx_resource_updated_at', table_name='resource')
    op.drop_index('idx_resource_created_at', table_name='resource')

    # Region
    op.drop_index('idx_region_original_owner', table_name='region')
    op.drop_index('idx_region_updated_at', table_name='region')
    op.drop_index('idx_region_created_at', table_name='region')

    # Country
    op.drop_index('idx_country_currency_code', table_name='country')
    op.drop_index('idx_country_updated_at', table_name='country')
    op.drop_index('idx_country_created_at', table_name='country')

    # User
    op.drop_index('idx_user_region_updated', table_name='user')
    op.drop_index('idx_user_citizenship_created', table_name='user')
    op.drop_index('idx_user_updated_at', table_name='user')
    op.drop_index('idx_user_created_at', table_name='user')
