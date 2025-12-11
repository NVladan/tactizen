"""add_nft_slot_cooldown_timestamps

Revision ID: nft_cooldown_001
Revises: nft_system_001
Create Date: 2025-11-19 23:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'nft_cooldown_001'
down_revision = 'nft_system_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add timestamp columns to player_nft_slots
    op.add_column('player_nft_slots', sa.Column('slot_1_last_modified', sa.DateTime(), nullable=True))
    op.add_column('player_nft_slots', sa.Column('slot_2_last_modified', sa.DateTime(), nullable=True))
    op.add_column('player_nft_slots', sa.Column('slot_3_last_modified', sa.DateTime(), nullable=True))

    # Add timestamp columns to company_nft_slots
    op.add_column('company_nft_slots', sa.Column('slot_1_last_modified', sa.DateTime(), nullable=True))
    op.add_column('company_nft_slots', sa.Column('slot_2_last_modified', sa.DateTime(), nullable=True))
    op.add_column('company_nft_slots', sa.Column('slot_3_last_modified', sa.DateTime(), nullable=True))


def downgrade():
    # Remove timestamp columns from company_nft_slots
    op.drop_column('company_nft_slots', 'slot_3_last_modified')
    op.drop_column('company_nft_slots', 'slot_2_last_modified')
    op.drop_column('company_nft_slots', 'slot_1_last_modified')

    # Remove timestamp columns from player_nft_slots
    op.drop_column('player_nft_slots', 'slot_3_last_modified')
    op.drop_column('player_nft_slots', 'slot_2_last_modified')
    op.drop_column('player_nft_slots', 'slot_1_last_modified')
