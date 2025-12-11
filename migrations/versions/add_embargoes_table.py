"""add_embargoes_table

Revision ID: add_embargoes_table
Revises: b1bca6ea69be
Create Date: 2025-11-30 15:22:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_embargoes_table'
down_revision = 'b1bca6ea69be'
branch_labels = None
depends_on = None


def upgrade():
    # Create embargoes table
    op.create_table('embargoes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('imposing_country_id', sa.Integer(), nullable=False),
        sa.Column('target_country_id', sa.Integer(), nullable=False),
        sa.Column('imposed_by_law_id', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('ended_by_law_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.ForeignKeyConstraint(['imposing_country_id'], ['country.id'], ),
        sa.ForeignKeyConstraint(['target_country_id'], ['country.id'], ),
        sa.ForeignKeyConstraint(['imposed_by_law_id'], ['laws.id'], ),
        sa.ForeignKeyConstraint(['ended_by_law_id'], ['laws.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_embargoes_imposing_country_id', 'embargoes', ['imposing_country_id'], unique=False)
    op.create_index('ix_embargoes_target_country_id', 'embargoes', ['target_country_id'], unique=False)
    op.create_index('ix_embargoes_is_active', 'embargoes', ['is_active'], unique=False)


def downgrade():
    op.drop_index('ix_embargoes_is_active', table_name='embargoes')
    op.drop_index('ix_embargoes_target_country_id', table_name='embargoes')
    op.drop_index('ix_embargoes_imposing_country_id', table_name='embargoes')
    op.drop_table('embargoes')
