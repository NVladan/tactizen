"""Add admin_removed field to message

Revision ID: 33ead7b1b4e5
Revises: add_mission_system
Create Date: 2025-12-05 20:31:10.611353

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '33ead7b1b4e5'
down_revision = 'add_mission_system'
branch_labels = None
depends_on = None


def upgrade():
    # Add admin_removed column to message table
    op.add_column('message', sa.Column('admin_removed', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    # Remove admin_removed column from message table
    op.drop_column('message', 'admin_removed')
