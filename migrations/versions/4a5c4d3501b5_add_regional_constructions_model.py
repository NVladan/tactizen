"""Add regional constructions model

Revision ID: 4a5c4d3501b5
Revises: 838d3a1769d6
Create Date: 2025-12-04 20:47:02.438012

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '4a5c4d3501b5'
down_revision = '838d3a1769d6'
branch_labels = None
depends_on = None


def upgrade():
    # Create regional_constructions table
    op.create_table('regional_constructions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('region_id', sa.Integer(), nullable=False),
        sa.Column('country_id', sa.Integer(), nullable=False),
        sa.Column('construction_type', sa.String(length=20), nullable=False),
        sa.Column('quality', sa.Integer(), nullable=False),
        sa.Column('placed_by_user_id', sa.Integer(), nullable=False),
        sa.Column('placed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['country_id'], ['country.id'], ),
        sa.ForeignKeyConstraint(['placed_by_user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['region_id'], ['region.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('region_id', 'construction_type', name='uq_region_construction_type')
    )
    with op.batch_alter_table('regional_constructions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_regional_constructions_construction_type'), ['construction_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_regional_constructions_country_id'), ['country_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_regional_constructions_region_id'), ['region_id'], unique=False)


def downgrade():
    with op.batch_alter_table('regional_constructions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_regional_constructions_region_id'))
        batch_op.drop_index(batch_op.f('ix_regional_constructions_country_id'))
        batch_op.drop_index(batch_op.f('ix_regional_constructions_construction_type'))

    op.drop_table('regional_constructions')
