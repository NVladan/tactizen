"""add_military_budget_fields

Revision ID: 425f686cede2
Revises: e7e5d0b1a445
Create Date: 2025-11-29 21:24:23.638219

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '425f686cede2'
down_revision = 'e7e5d0b1a445'
branch_labels = None
depends_on = None


def upgrade():
    # Add military budget fields to country table
    with op.batch_alter_table('country', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reserved_currency', sa.Numeric(precision=20, scale=8), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('military_budget_gold', sa.Numeric(precision=20, scale=8), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('military_budget_currency', sa.Numeric(precision=20, scale=8), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('country', schema=None) as batch_op:
        batch_op.drop_column('military_budget_currency')
        batch_op.drop_column('military_budget_gold')
        batch_op.drop_column('reserved_currency')
