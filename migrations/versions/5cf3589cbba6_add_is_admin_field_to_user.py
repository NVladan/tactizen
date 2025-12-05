"""add_is_admin_field_to_user

Revision ID: 5cf3589cbba6
Revises: f56a31202b39
Create Date: 2025-11-06 11:08:35.946260

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5cf3589cbba6'
down_revision = 'f56a31202b39'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_admin field to user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.create_index(batch_op.f('ix_user_is_admin'), ['is_admin'], unique=False)


def downgrade():
    # Remove is_admin field from user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_is_admin'))
        batch_op.drop_column('is_admin')
