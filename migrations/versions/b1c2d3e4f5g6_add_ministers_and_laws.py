"""add ministers and laws

Revision ID: b1c2d3e4f5g6
Revises: a1b2c3d4e5f6
Create Date: 2025-11-18 17:49:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5g6'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Create ministers table
    op.create_table('ministers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('country_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('ministry_type', sa.Enum('FOREIGN_AFFAIRS', 'DEFENCE', 'FINANCE', name='ministrytype'), nullable=False),
    sa.Column('appointed_by_user_id', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('appointed_at', sa.DateTime(), nullable=False),
    sa.Column('resigned_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['appointed_by_user_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['country_id'], ['country.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_country_ministry_active', 'ministers', ['country_id', 'ministry_type', 'is_active'], unique=False)
    op.create_index(op.f('ix_ministers_country_id'), 'ministers', ['country_id'], unique=False)
    op.create_index(op.f('ix_ministers_is_active'), 'ministers', ['is_active'], unique=False)
    op.create_index(op.f('ix_ministers_ministry_type'), 'ministers', ['ministry_type'], unique=False)
    op.create_index(op.f('ix_ministers_user_id'), 'ministers', ['user_id'], unique=False)

    # Create laws table
    op.create_table('laws',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('country_id', sa.Integer(), nullable=False),
    sa.Column('law_type', sa.Enum('DECLARE_WAR', 'MUTUAL_PROTECTION_PACT', 'NON_AGGRESSION_PACT', 'MILITARY_BUDGET', 'PRINT_CURRENCY', 'IMPORT_TAX', 'SALARY_TAX', 'INCOME_TAX', name='lawtype'), nullable=False),
    sa.Column('status', sa.Enum('VOTING', 'PASSED', 'REJECTED', 'EXPIRED', name='lawstatus'), nullable=False),
    sa.Column('proposed_by_user_id', sa.Integer(), nullable=False),
    sa.Column('proposed_by_role', sa.String(length=50), nullable=False),
    sa.Column('law_details', sa.JSON(), nullable=False),
    sa.Column('voting_start', sa.DateTime(), nullable=False),
    sa.Column('voting_end', sa.DateTime(), nullable=False),
    sa.Column('votes_for', sa.Integer(), nullable=False),
    sa.Column('votes_against', sa.Integer(), nullable=False),
    sa.Column('total_votes', sa.Integer(), nullable=False),
    sa.Column('result_calculated_at', sa.DateTime(), nullable=True),
    sa.Column('passed', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['country_id'], ['country.id'], ),
    sa.ForeignKeyConstraint(['proposed_by_user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_laws_country_id'), 'laws', ['country_id'], unique=False)
    op.create_index(op.f('ix_laws_law_type'), 'laws', ['law_type'], unique=False)
    op.create_index(op.f('ix_laws_status'), 'laws', ['status'], unique=False)

    # Create law_votes table
    op.create_table('law_votes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('law_id', sa.Integer(), nullable=False),
    sa.Column('voter_user_id', sa.Integer(), nullable=False),
    sa.Column('vote', sa.Boolean(), nullable=False),
    sa.Column('voter_role', sa.String(length=50), nullable=False),
    sa.Column('voted_at', sa.DateTime(), nullable=False),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.ForeignKeyConstraint(['law_id'], ['laws.id'], ),
    sa.ForeignKeyConstraint(['voter_user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('law_id', 'voter_user_id', name='uq_law_voter')
    )
    op.create_index(op.f('ix_law_votes_law_id'), 'law_votes', ['law_id'], unique=False)
    op.create_index(op.f('ix_law_votes_voter_user_id'), 'law_votes', ['voter_user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_law_votes_voter_user_id'), table_name='law_votes')
    op.drop_index(op.f('ix_law_votes_law_id'), table_name='law_votes')
    op.drop_table('law_votes')

    op.drop_index(op.f('ix_laws_status'), table_name='laws')
    op.drop_index(op.f('ix_laws_law_type'), table_name='laws')
    op.drop_index(op.f('ix_laws_country_id'), table_name='laws')
    op.drop_table('laws')

    op.drop_index(op.f('ix_ministers_user_id'), table_name='ministers')
    op.drop_index(op.f('ix_ministers_ministry_type'), table_name='ministers')
    op.drop_index(op.f('ix_ministers_is_active'), table_name='ministers')
    op.drop_index(op.f('ix_ministers_country_id'), table_name='ministers')
    op.drop_index('idx_country_ministry_active', table_name='ministers')
    op.drop_table('ministers')
