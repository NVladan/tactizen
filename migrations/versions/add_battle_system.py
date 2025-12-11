"""add battle system

Revision ID: add_battle_system_001
Revises: split_company_types_001
Create Date: 2025-11-27 13:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_battle_system_001'
down_revision = 'split_company_types_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add initiative tracking columns to wars table
    op.add_column('wars', sa.Column('initiative_holder_id', sa.Integer(), nullable=True))
    op.add_column('wars', sa.Column('initiative_expires_at', sa.DateTime(), nullable=True))
    op.add_column('wars', sa.Column('initiative_lost', sa.Boolean(), nullable=False, server_default='0'))
    op.create_foreign_key('fk_wars_initiative_holder', 'wars', 'country', ['initiative_holder_id'], ['id'])

    # Create mutual_protection_pacts table
    op.create_table('mutual_protection_pacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('country_a_id', sa.Integer(), nullable=False),
        sa.Column('country_b_id', sa.Integer(), nullable=False),
        sa.Column('created_by_law_id', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('ended_early', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('ended_reason', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['country_a_id'], ['country.id'], ),
        sa.ForeignKeyConstraint(['country_b_id'], ['country.id'], ),
        sa.ForeignKeyConstraint(['created_by_law_id'], ['laws.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_active_pact', 'mutual_protection_pacts', ['country_a_id', 'country_b_id', 'is_active'], unique=False)

    # Create battles table
    op.create_table('battles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('war_id', sa.Integer(), nullable=False),
        sa.Column('region_id', sa.Integer(), nullable=False),
        sa.Column('started_by_country_id', sa.Integer(), nullable=False),
        sa.Column('started_by_user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'ATTACKER_WON', 'DEFENDER_WON', name='battlestatus'), nullable=False),
        sa.Column('attacker_rounds_won', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('defender_rounds_won', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('current_round', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('ends_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['region_id'], ['region.id'], ),
        sa.ForeignKeyConstraint(['started_by_country_id'], ['country.id'], ),
        sa.ForeignKeyConstraint(['started_by_user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['war_id'], ['wars.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_battles_region_id'), 'battles', ['region_id'], unique=False)
    op.create_index(op.f('ix_battles_status'), 'battles', ['status'], unique=False)
    op.create_index(op.f('ix_battles_war_id'), 'battles', ['war_id'], unique=False)

    # Create battle_rounds table
    op.create_table('battle_rounds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('battle_id', sa.Integer(), nullable=False),
        sa.Column('round_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'COMPLETED', name='roundstatus'), nullable=False),
        sa.Column('infantry_damage_diff', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('armoured_damage_diff', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('aviation_damage_diff', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('infantry_winner_is_attacker', sa.Boolean(), nullable=True),
        sa.Column('armoured_winner_is_attacker', sa.Boolean(), nullable=True),
        sa.Column('aviation_winner_is_attacker', sa.Boolean(), nullable=True),
        sa.Column('winner_is_attacker', sa.Boolean(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('ends_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['battle_id'], ['battles.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('battle_id', 'round_number', name='unique_battle_round')
    )
    op.create_index(op.f('ix_battle_rounds_battle_id'), 'battle_rounds', ['battle_id'], unique=False)
    op.create_index(op.f('ix_battle_rounds_status'), 'battle_rounds', ['status'], unique=False)

    # Create battle_participations table
    op.create_table('battle_participations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('battle_id', sa.Integer(), nullable=False),
        sa.Column('round_number', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('is_attacker', sa.Boolean(), nullable=False),
        sa.Column('wall_type', sa.Enum('INFANTRY', 'ARMOURED', 'AVIATION', name='walltype'), nullable=False),
        sa.Column('total_damage', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fight_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_fight_at', sa.DateTime(), nullable=True),
        sa.Column('joined_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['battle_id'], ['battles.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('battle_id', 'round_number', 'user_id', name='unique_battle_round_user')
    )
    op.create_index(op.f('ix_battle_participations_battle_id'), 'battle_participations', ['battle_id'], unique=False)
    op.create_index(op.f('ix_battle_participations_user_id'), 'battle_participations', ['user_id'], unique=False)

    # Create battle_damages table
    op.create_table('battle_damages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('battle_id', sa.Integer(), nullable=False),
        sa.Column('round_number', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('is_attacker', sa.Boolean(), nullable=False),
        sa.Column('wall_type', sa.Enum('INFANTRY', 'ARMOURED', 'AVIATION', name='walltype'), nullable=False),
        sa.Column('damage', sa.Integer(), nullable=False),
        sa.Column('weapon_resource_id', sa.Integer(), nullable=True),
        sa.Column('weapon_quality', sa.Integer(), nullable=True),
        sa.Column('player_level', sa.Integer(), nullable=False),
        sa.Column('player_skill', sa.Float(), nullable=False),
        sa.Column('military_rank_id', sa.Integer(), nullable=False),
        sa.Column('rank_damage_bonus', sa.Integer(), nullable=False),
        sa.Column('nft_damage_bonus', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('dealt_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['battle_id'], ['battles.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['weapon_resource_id'], ['resource.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_battle_damages_battle_id'), 'battle_damages', ['battle_id'], unique=False)
    op.create_index(op.f('ix_battle_damages_dealt_at'), 'battle_damages', ['dealt_at'], unique=False)
    op.create_index(op.f('ix_battle_damages_is_attacker'), 'battle_damages', ['is_attacker'], unique=False)
    op.create_index(op.f('ix_battle_damages_user_id'), 'battle_damages', ['user_id'], unique=False)
    op.create_index(op.f('ix_battle_damages_wall_type'), 'battle_damages', ['wall_type'], unique=False)
    op.create_index('idx_battle_wall_side', 'battle_damages', ['battle_id', 'wall_type', 'is_attacker'], unique=False)
    op.create_index('idx_battle_user', 'battle_damages', ['battle_id', 'user_id'], unique=False)

    # Create battle_heroes table
    op.create_table('battle_heroes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('battle_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('wall_type', sa.Enum('INFANTRY', 'ARMOURED', 'AVIATION', name='walltype'), nullable=False),
        sa.Column('is_attacker', sa.Boolean(), nullable=False),
        sa.Column('total_damage', sa.Integer(), nullable=False),
        sa.Column('gold_reward', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('awarded_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['battle_id'], ['battles.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('battle_id', 'wall_type', 'is_attacker', name='unique_battle_wall_side_hero')
    )
    op.create_index(op.f('ix_battle_heroes_battle_id'), 'battle_heroes', ['battle_id'], unique=False)
    op.create_index(op.f('ix_battle_heroes_user_id'), 'battle_heroes', ['user_id'], unique=False)


def downgrade():
    # Drop battle_heroes table
    op.drop_index(op.f('ix_battle_heroes_user_id'), table_name='battle_heroes')
    op.drop_index(op.f('ix_battle_heroes_battle_id'), table_name='battle_heroes')
    op.drop_table('battle_heroes')

    # Drop battle_damages table
    op.drop_index('idx_battle_user', table_name='battle_damages')
    op.drop_index('idx_battle_wall_side', table_name='battle_damages')
    op.drop_index(op.f('ix_battle_damages_wall_type'), table_name='battle_damages')
    op.drop_index(op.f('ix_battle_damages_user_id'), table_name='battle_damages')
    op.drop_index(op.f('ix_battle_damages_is_attacker'), table_name='battle_damages')
    op.drop_index(op.f('ix_battle_damages_dealt_at'), table_name='battle_damages')
    op.drop_index(op.f('ix_battle_damages_battle_id'), table_name='battle_damages')
    op.drop_table('battle_damages')

    # Drop battle_participations table
    op.drop_index(op.f('ix_battle_participations_user_id'), table_name='battle_participations')
    op.drop_index(op.f('ix_battle_participations_battle_id'), table_name='battle_participations')
    op.drop_table('battle_participations')

    # Drop battle_rounds table
    op.drop_index(op.f('ix_battle_rounds_status'), table_name='battle_rounds')
    op.drop_index(op.f('ix_battle_rounds_battle_id'), table_name='battle_rounds')
    op.drop_table('battle_rounds')

    # Drop battles table
    op.drop_index(op.f('ix_battles_war_id'), table_name='battles')
    op.drop_index(op.f('ix_battles_status'), table_name='battles')
    op.drop_index(op.f('ix_battles_region_id'), table_name='battles')
    op.drop_table('battles')

    # Drop mutual_protection_pacts table
    op.drop_index('idx_active_pact', table_name='mutual_protection_pacts')
    op.drop_table('mutual_protection_pacts')

    # Remove initiative tracking columns from wars table
    op.drop_constraint('fk_wars_initiative_holder', 'wars', type_='foreignkey')
    op.drop_column('wars', 'initiative_lost')
    op.drop_column('wars', 'initiative_expires_at')
    op.drop_column('wars', 'initiative_holder_id')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS battlestatus")
    op.execute("DROP TYPE IF EXISTS roundstatus")
    op.execute("DROP TYPE IF EXISTS walltype")
