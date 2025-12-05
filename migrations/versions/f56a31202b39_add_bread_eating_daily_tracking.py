"""add_bread_eating_daily_tracking

Revision ID: f56a31202b39
Revises: c4eb9d63851b
Create Date: 2025-11-06 09:03:43.493692

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f56a31202b39'
down_revision = 'c4eb9d63851b'
branch_labels = None
depends_on = None


def upgrade():
    # Add bread eating daily tracking fields to user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('wellness_from_bread_today', sa.Float(), server_default='0.0', nullable=False))
        batch_op.add_column(sa.Column('last_bread_reset_date', sa.Date(), nullable=True))


def downgrade():
    # Remove bread eating daily tracking fields from user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('last_bread_reset_date')
        batch_op.drop_column('wellness_from_bread_today')
