"""Add last_hospital_use to User model

Revision ID: 122e71fa3a25
Revises: 4a5c4d3501b5
Create Date: 2025-12-04 21:44:58.907497

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '122e71fa3a25'
down_revision = '4a5c4d3501b5'
branch_labels = None
depends_on = None


def upgrade():
    # Add last_hospital_use column to track hospital usage cooldown
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_hospital_use', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('last_hospital_use')
