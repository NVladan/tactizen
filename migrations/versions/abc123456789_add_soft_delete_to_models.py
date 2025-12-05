"""add_soft_delete_to_models

Revision ID: abc123456789
Revises: ee69e1aec3c2
Create Date: 2025-11-06 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'abc123456789'
down_revision = 'ee69e1aec3c2'
branch_labels = None
depends_on = None


def upgrade():
    # Add soft delete columns to User table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_user_is_deleted', ['is_deleted'])
        batch_op.create_index('ix_user_deleted_at', ['deleted_at'])

    # Add soft delete columns to Country table
    with op.batch_alter_table('country', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_country_is_deleted', ['is_deleted'])
        batch_op.create_index('ix_country_deleted_at', ['deleted_at'])

    # Add soft delete columns to Region table
    with op.batch_alter_table('region', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_region_is_deleted', ['is_deleted'])
        batch_op.create_index('ix_region_deleted_at', ['deleted_at'])

    # Add soft delete columns to Resource table
    with op.batch_alter_table('resource', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_resource_is_deleted', ['is_deleted'])
        batch_op.create_index('ix_resource_deleted_at', ['deleted_at'])


def downgrade():
    # Remove soft delete columns from Resource table
    with op.batch_alter_table('resource', schema=None) as batch_op:
        batch_op.drop_index('ix_resource_deleted_at')
        batch_op.drop_index('ix_resource_is_deleted')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('is_deleted')

    # Remove soft delete columns from Region table
    with op.batch_alter_table('region', schema=None) as batch_op:
        batch_op.drop_index('ix_region_deleted_at')
        batch_op.drop_index('ix_region_is_deleted')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('is_deleted')

    # Remove soft delete columns from Country table
    with op.batch_alter_table('country', schema=None) as batch_op:
        batch_op.drop_index('ix_country_deleted_at')
        batch_op.drop_index('ix_country_is_deleted')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('is_deleted')

    # Remove soft delete columns from User table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_index('ix_user_deleted_at')
        batch_op.drop_index('ix_user_is_deleted')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('is_deleted')
