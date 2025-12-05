"""Add regional resources model

Revision ID: 6f13f64519ac
Revises: aeb79092c60f
Create Date: 2025-12-05 02:04:36.027453

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6f13f64519ac'
down_revision = 'aeb79092c60f'
branch_labels = None
depends_on = None


def upgrade():
    # Create regional_resources table for storing natural resource deposits in regions
    op.create_table('regional_resources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('region_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('initial_amount', sa.Integer(), nullable=False),
        sa.Column('added_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['added_by_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['region_id'], ['region.id'], ),
        sa.ForeignKeyConstraint(['resource_id'], ['resource.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('region_id', 'resource_id', name='uq_region_resource')
    )
    with op.batch_alter_table('regional_resources', schema=None) as batch_op:
        batch_op.create_index('idx_regional_resource_lookup', ['region_id', 'resource_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_regional_resources_region_id'), ['region_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_regional_resources_resource_id'), ['resource_id'], unique=False)


def downgrade():
    with op.batch_alter_table('regional_resources', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_regional_resources_resource_id'))
        batch_op.drop_index(batch_op.f('ix_regional_resources_region_id'))
        batch_op.drop_index('idx_regional_resource_lookup')

    op.drop_table('regional_resources')
