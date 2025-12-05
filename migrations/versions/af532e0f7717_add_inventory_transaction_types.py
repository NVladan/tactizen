"""add_inventory_transaction_types

Revision ID: af532e0f7717
Revises: 79ab7f34d521
Create Date: 2025-11-07 20:15:12.783229

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'af532e0f7717'
down_revision = '79ab7f34d521'
branch_labels = None
depends_on = None


def upgrade():
    # Add new transaction types to the enum (using enum names, not values)
    op.execute("ALTER TABLE company_transaction MODIFY COLUMN transaction_type ENUM('OWNER_DEPOSIT_GOLD', 'OWNER_DEPOSIT_CURRENCY', 'PRODUCT_SALE', 'CURRENCY_EXCHANGE', 'INVENTORY_SALE', 'OWNER_WITHDRAWAL_GOLD', 'OWNER_WITHDRAWAL_CURRENCY', 'WAGE_PAYMENT', 'RESOURCE_PURCHASE', 'UPGRADE', 'EXPORT_LICENSE', 'RELOCATION', 'CURRENCY_EXCHANGE_SELL', 'INVENTORY_PURCHASE') NOT NULL")


def downgrade():
    # Remove inventory transaction types from the enum
    op.execute("ALTER TABLE company_transaction MODIFY COLUMN transaction_type ENUM('OWNER_DEPOSIT_GOLD', 'OWNER_DEPOSIT_CURRENCY', 'PRODUCT_SALE', 'CURRENCY_EXCHANGE', 'OWNER_WITHDRAWAL_GOLD', 'OWNER_WITHDRAWAL_CURRENCY', 'WAGE_PAYMENT', 'RESOURCE_PURCHASE', 'UPGRADE', 'EXPORT_LICENSE', 'RELOCATION', 'CURRENCY_EXCHANGE_SELL') NOT NULL")
