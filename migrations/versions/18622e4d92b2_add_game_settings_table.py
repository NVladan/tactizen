"""Add game_settings table

Revision ID: 18622e4d92b2
Revises: add_conquest_system
Create Date: 2025-12-05 21:46:20.851453

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '18622e4d92b2'
down_revision = 'add_conquest_system'
branch_labels = None
depends_on = None


def upgrade():
    # Create game_settings table for dynamic game configuration
    op.create_table('game_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('game_settings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_game_settings_key'), ['key'], unique=True)


def downgrade():
    with op.batch_alter_table('game_settings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_game_settings_key'))

    op.drop_table('game_settings')
