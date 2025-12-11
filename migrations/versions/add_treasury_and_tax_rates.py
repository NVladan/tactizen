"""add_treasury_and_tax_rates

Revision ID: treasury_tax_001
Revises: nft_cooldown_001
Create Date: 2025-11-21 19:06:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'treasury_tax_001'
down_revision = 'nft_cooldown_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add treasury fields to country table
    op.add_column('country', sa.Column('treasury_gold', mysql.DECIMAL(precision=20, scale=8), nullable=False, server_default='0.00000000'))
    op.add_column('country', sa.Column('treasury_currency', mysql.DECIMAL(precision=20, scale=8), nullable=False, server_default='0.00000000'))

    # Add tax rate fields to country table
    op.add_column('country', sa.Column('vat_tax_rate', mysql.DECIMAL(precision=5, scale=2), nullable=False, server_default='5.00'))
    op.add_column('country', sa.Column('import_tax_rate', mysql.DECIMAL(precision=5, scale=2), nullable=False, server_default='10.00'))
    op.add_column('country', sa.Column('work_tax_rate', mysql.DECIMAL(precision=5, scale=2), nullable=False, server_default='10.00'))


def downgrade():
    # Remove tax rate fields from country table
    op.drop_column('country', 'work_tax_rate')
    op.drop_column('country', 'import_tax_rate')
    op.drop_column('country', 'vat_tax_rate')

    # Remove treasury fields from country table
    op.drop_column('country', 'treasury_currency')
    op.drop_column('country', 'treasury_gold')
