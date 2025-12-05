"""add_quality_to_active_residence

Revision ID: 11daea3e2b05
Revises: 3025788cf32a
Create Date: 2025-11-13 18:10:50.731307

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '11daea3e2b05'
down_revision = '3025788cf32a'
branch_labels = None
depends_on = None


def upgrade():
    # Add quality column to active_residence table
    op.add_column('active_residence', sa.Column('quality', sa.Integer(), nullable=False, server_default='1'))


def downgrade():
    # Remove quality column from active_residence table
    op.drop_column('active_residence', 'quality')
