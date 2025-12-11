"""add_export_license_table

Revision ID: export_license_001
Revises: treasury_tax_001
Create Date: 2025-11-21 19:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'export_license_001'
down_revision = 'treasury_tax_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add cost_gold column to export_license table if it doesn't exist
    # (table may already exist from previous migrations)
    try:
        op.add_column('export_license', sa.Column('cost_gold', mysql.DECIMAL(precision=20, scale=8), nullable=False, server_default='20.00000000'))
    except Exception:
        # Column might already exist or table might not exist, skip
        pass


def downgrade():
    # Remove cost_gold column
    try:
        op.drop_column('export_license', 'cost_gold')
    except Exception:
        pass
