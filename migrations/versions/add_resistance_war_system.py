"""Add resistance war system

Adds resistance war fields to War model and resistance stats to User model.

Revision ID: add_resistance_war
Revises: 6f13f64519ac
Create Date: 2025-12-05
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_resistance_war'
down_revision = '6f13f64519ac'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to wars table (MySQL uses strings for enums)
    op.add_column('wars', sa.Column('war_type', sa.String(20), nullable=True, server_default='normal'))
    op.add_column('wars', sa.Column('is_resistance_war', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('wars', sa.Column('resistance_region_id', sa.Integer(), nullable=True))
    op.add_column('wars', sa.Column('resistance_started_by_user_id', sa.Integer(), nullable=True))
    op.add_column('wars', sa.Column('resistance_country_id', sa.Integer(), nullable=True))

    # Add foreign keys
    op.create_foreign_key('fk_wars_resistance_region', 'wars', 'region', ['resistance_region_id'], ['id'])
    op.create_foreign_key('fk_wars_resistance_started_by', 'wars', 'user', ['resistance_started_by_user_id'], ['id'])
    op.create_foreign_key('fk_wars_resistance_country', 'wars', 'country', ['resistance_country_id'], ['id'])

    # Add indexes for resistance war queries
    op.create_index('ix_wars_is_resistance_war', 'wars', ['is_resistance_war'])
    op.create_index('ix_wars_resistance_country_id', 'wars', ['resistance_country_id'])
    op.create_index('ix_wars_war_type', 'wars', ['war_type'])

    # Add resistance war stats to user table
    op.add_column('user', sa.Column('resistance_wars_started', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('user', sa.Column('resistance_wars_won', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    # Remove user columns
    op.drop_column('user', 'resistance_wars_won')
    op.drop_column('user', 'resistance_wars_started')

    # Remove indexes
    op.drop_index('ix_wars_war_type', table_name='wars')
    op.drop_index('ix_wars_resistance_country_id', table_name='wars')
    op.drop_index('ix_wars_is_resistance_war', table_name='wars')

    # Remove foreign keys
    op.drop_constraint('fk_wars_resistance_country', 'wars', type_='foreignkey')
    op.drop_constraint('fk_wars_resistance_started_by', 'wars', type_='foreignkey')
    op.drop_constraint('fk_wars_resistance_region', 'wars', type_='foreignkey')

    # Remove columns
    op.drop_column('wars', 'resistance_country_id')
    op.drop_column('wars', 'resistance_started_by_user_id')
    op.drop_column('wars', 'resistance_region_id')
    op.drop_column('wars', 'is_resistance_war')
    op.drop_column('wars', 'war_type')
