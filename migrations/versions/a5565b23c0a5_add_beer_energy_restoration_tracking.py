"""add_beer_energy_restoration_tracking

Revision ID: a5565b23c0a5
Revises: b7091f42ea06
Create Date: 2025-11-06 11:57:45.370546

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a5565b23c0a5'
down_revision = 'b7091f42ea06'
branch_labels = None
depends_on = None


def upgrade():
    # Add beer energy restoration tracking fields to user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('energy_from_beer_today', sa.Float(), nullable=False, server_default='0.0'))
        batch_op.add_column(sa.Column('last_beer_reset_date', sa.Date(), nullable=True))


def downgrade():
    # Remove beer energy restoration tracking fields from user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('last_beer_reset_date')
        batch_op.drop_column('energy_from_beer_today')
