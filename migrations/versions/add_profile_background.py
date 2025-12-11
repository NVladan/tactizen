"""Add profile_background to User model

Revision ID: add_profile_bg001
Revises:
Create Date: 2025-12-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_profile_bg001'
down_revision = '28cc0421e7df'
branch_labels = None
depends_on = None


def upgrade():
    # Add profile_background column to user table
    op.add_column('user', sa.Column('profile_background', sa.String(20), nullable=False, server_default='default'))


def downgrade():
    op.drop_column('user', 'profile_background')
