"""Add GameEvent model for timed events

Revision ID: 83b18b03388d
Revises: 7e0b8dea92c1
Create Date: 2025-12-08 21:51:35.408880

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '83b18b03388d'
down_revision = '7e0b8dea92c1'
branch_labels = None
depends_on = None


def upgrade():
    # Create the game_events table
    op.create_table('game_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('multiplier', sa.Float(), nullable=False),
        sa.Column('affects_setting', sa.String(length=100), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_announced', sa.Boolean(), nullable=False),
        sa.Column('banner_color', sa.String(length=7), nullable=False),
        sa.Column('icon', sa.String(length=50), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for game_events
    op.create_index('ix_game_events_end_time', 'game_events', ['end_time'], unique=False)
    op.create_index('ix_game_events_event_type', 'game_events', ['event_type'], unique=False)
    op.create_index('ix_game_events_start_time', 'game_events', ['start_time'], unique=False)


def downgrade():
    # Drop indexes first
    op.drop_index('ix_game_events_start_time', table_name='game_events')
    op.drop_index('ix_game_events_event_type', table_name='game_events')
    op.drop_index('ix_game_events_end_time', table_name='game_events')

    # Drop the table
    op.drop_table('game_events')
