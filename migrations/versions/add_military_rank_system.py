"""add military rank system

Revision ID: military_rank_001
Revises: fix_party_constraint
Create Date: 2025-11-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'military_rank_001'
down_revision = 'fix_party_constraint'
branch_labels = None
depends_on = None


def upgrade():
    # Create military_ranks table
    op.create_table(
        'military_ranks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('xp_required', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('damage_bonus', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Add military rank fields to user table
    op.add_column('user', sa.Column('military_rank_id', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('user', sa.Column('military_rank_xp', mysql.DECIMAL(precision=20, scale=2), nullable=False, server_default='0.00'))

    # Create foreign key constraint
    op.create_foreign_key('fk_user_military_rank', 'user', 'military_ranks', ['military_rank_id'], ['id'])

    # Create index on military_rank_id
    op.create_index('idx_user_military_rank_id', 'user', ['military_rank_id'])

    # Populate military_ranks table with all 60 ranks
    # XP progression: exponential growth starting at 100, with 12% increase per rank
    # This ensures each rank requires progressively more XP (not easier as you advance)
    ranks_data = [
        (1, 'Recruit', 0, 2),
        (2, 'Apprentice', 100, 4),
        (3, 'Private III', 212, 6),
        (4, 'Private II', 337, 8),
        (5, 'Private I', 477, 10),
        (6, 'Specialist III', 634, 12),
        (7, 'Specialist II', 810, 14),
        (8, 'Specialist I', 1007, 16),
        (9, 'Lance Corporal', 1228, 18),
        (10, 'Corporal', 1475, 20),
        (11, 'Senior Corporal', 1752, 22),
        (12, 'Master Corporal', 2062, 24),
        (13, 'Sergeant III', 2409, 26),
        (14, 'Sergeant II', 2798, 28),
        (15, 'Sergeant I', 3234, 30),
        (16, 'Staff Sergeant III', 3722, 32),
        (17, 'Staff Sergeant II', 4269, 34),
        (18, 'Staff Sergeant I', 4882, 36),
        (19, 'Technical Sergeant', 5568, 38),
        (20, 'Senior Sergeant', 6336, 40),
        (21, 'First Sergeant', 7197, 42),
        (22, 'Master Sergeant III', 8161, 44),
        (23, 'Master Sergeant II', 9241, 46),
        (24, 'Master Sergeant I', 10451, 48),
        (25, 'Sergeant Major', 11806, 50),
        (26, 'Command Sergeant Major', 13323, 52),
        (27, 'Sergeant Major of the Guard', 15023, 54),
        (28, 'Warrant Officer III', 16927, 56),
        (29, 'Warrant Officer II', 19059, 58),
        (30, 'Warrant Officer I', 21447, 60),
        (31, 'Chief Warrant Officer', 24121, 62),
        (32, 'Master Warrant Officer', 27116, 64),
        (33, '2nd Lieutenant', 30471, 66),
        (34, '1st Lieutenant', 34229, 68),
        (35, 'Captain III', 38438, 70),
        (36, 'Captain II', 43152, 72),
        (37, 'Captain I', 48431, 74),
        (38, 'Major III', 54344, 76),
        (39, 'Major II', 60967, 78),
        (40, 'Major I', 68384, 80),
        (41, 'Lieutenant Colonel III', 76692, 82),
        (42, 'Lieutenant Colonel II', 85997, 84),
        (43, 'Lieutenant Colonel I', 96418, 86),
        (44, 'Colonel III', 108090, 88),
        (45, 'Colonel II', 121162, 90),
        (46, 'Colonel I', 135803, 92),
        (47, 'Senior Colonel', 152201, 94),
        (48, 'Brigadier General III', 170567, 96),
        (49, 'Brigadier General II', 191137, 98),
        (50, 'Brigadier General I', 214176, 100),
        (51, 'Major General III', 239979, 102),
        (52, 'Major General II', 268879, 104),
        (53, 'Major General I', 301247, 106),
        (54, 'Lieutenant General III', 337499, 108),
        (55, 'Lieutenant General II', 378101, 110),
        (56, 'Lieutenant General I', 423576, 112),
        (57, 'General III', 474508, 114),
        (58, 'General II', 531551, 116),
        (59, 'General I', 595440, 118),
        (60, 'Field Marshal', 666995, 120),
    ]

    # Insert all ranks
    op.bulk_insert(
        sa.table('military_ranks',
                 sa.column('id', sa.Integer),
                 sa.column('name', sa.String),
                 sa.column('xp_required', sa.Integer),
                 sa.column('damage_bonus', sa.Integer)),
        [{'id': id, 'name': name, 'xp_required': xp, 'damage_bonus': bonus}
         for id, name, xp, bonus in ranks_data]
    )


def downgrade():
    # Remove foreign key and index
    op.drop_constraint('fk_user_military_rank', 'user', type_='foreignkey')
    op.drop_index('idx_user_military_rank_id', table_name='user')

    # Remove columns from user table
    op.drop_column('user', 'military_rank_xp')
    op.drop_column('user', 'military_rank_id')

    # Drop military_ranks table
    op.drop_table('military_ranks')
