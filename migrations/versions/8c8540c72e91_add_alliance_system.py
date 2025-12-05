"""add_alliance_system

Revision ID: 8c8540c72e91
Revises: 210fe79d04b8
Create Date: 2025-11-29 11:51:53.454890

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '8c8540c72e91'
down_revision = '210fe79d04b8'
branch_labels = None
depends_on = None


def upgrade():
    # Create alliance tables
    op.create_table('alliances',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('leader_country_id', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('dissolved_at', sa.DateTime(), nullable=True),
    sa.Column('dissolved_reason', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['leader_country_id'], ['country.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_index('ix_alliances_is_active', 'alliances', ['is_active'], unique=False)
    op.create_index('ix_alliances_leader_country_id', 'alliances', ['leader_country_id'], unique=False)

    op.create_table('alliance_memberships',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('alliance_id', sa.Integer(), nullable=False),
    sa.Column('country_id', sa.Integer(), nullable=False),
    sa.Column('is_founder', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('joined_at', sa.DateTime(), nullable=False),
    sa.Column('left_at', sa.DateTime(), nullable=True),
    sa.Column('left_reason', sa.String(length=100), nullable=True),
    sa.Column('can_rejoin_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['alliance_id'], ['alliances.id'], ),
    sa.ForeignKeyConstraint(['country_id'], ['country.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_active_membership', 'alliance_memberships', ['country_id', 'is_active'], unique=False)
    op.create_index('ix_alliance_memberships_alliance_id', 'alliance_memberships', ['alliance_id'], unique=False)
    op.create_index('ix_alliance_memberships_country_id', 'alliance_memberships', ['country_id'], unique=False)
    op.create_index('ix_alliance_memberships_is_active', 'alliance_memberships', ['is_active'], unique=False)

    op.create_table('alliance_invitations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('alliance_id', sa.Integer(), nullable=False),
    sa.Column('inviting_country_id', sa.Integer(), nullable=False),
    sa.Column('invited_country_id', sa.Integer(), nullable=False),
    sa.Column('initiated_by_user_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('PENDING_VOTES', 'ACCEPTED', 'REJECTED', 'EXPIRED', name='allianceinvitationstatus'), nullable=False),
    sa.Column('inviter_law_id', sa.Integer(), nullable=True),
    sa.Column('invited_law_id', sa.Integer(), nullable=True),
    sa.Column('inviter_accepted', sa.Boolean(), nullable=True),
    sa.Column('invited_accepted', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['alliance_id'], ['alliances.id'], ),
    sa.ForeignKeyConstraint(['initiated_by_user_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['invited_country_id'], ['country.id'], ),
    sa.ForeignKeyConstraint(['invited_law_id'], ['laws.id'], ),
    sa.ForeignKeyConstraint(['inviter_law_id'], ['laws.id'], ),
    sa.ForeignKeyConstraint(['inviting_country_id'], ['country.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_alliance_invitations_alliance_id', 'alliance_invitations', ['alliance_id'], unique=False)
    op.create_index('ix_alliance_invitations_invited_country_id', 'alliance_invitations', ['invited_country_id'], unique=False)
    op.create_index('ix_alliance_invitations_inviting_country_id', 'alliance_invitations', ['inviting_country_id'], unique=False)
    op.create_index('ix_alliance_invitations_status', 'alliance_invitations', ['status'], unique=False)

    op.create_table('alliance_kicks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('alliance_id', sa.Integer(), nullable=False),
    sa.Column('target_country_id', sa.Integer(), nullable=False),
    sa.Column('initiated_by_user_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('PENDING_VOTE', 'APPROVED', 'REJECTED', name='alliancekickstatus'), nullable=False),
    sa.Column('law_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['alliance_id'], ['alliances.id'], ),
    sa.ForeignKeyConstraint(['initiated_by_user_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['law_id'], ['laws.id'], ),
    sa.ForeignKeyConstraint(['target_country_id'], ['country.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_alliance_kicks_alliance_id', 'alliance_kicks', ['alliance_id'], unique=False)
    op.create_index('ix_alliance_kicks_status', 'alliance_kicks', ['status'], unique=False)
    op.create_index('ix_alliance_kicks_target_country_id', 'alliance_kicks', ['target_country_id'], unique=False)

    op.create_table('alliance_leaves',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('alliance_id', sa.Integer(), nullable=False),
    sa.Column('country_id', sa.Integer(), nullable=False),
    sa.Column('initiated_by_user_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('law_id', sa.Integer(), nullable=True),
    sa.Column('approved_at', sa.DateTime(), nullable=True),
    sa.Column('execute_at', sa.DateTime(), nullable=True),
    sa.Column('executed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['alliance_id'], ['alliances.id'], ),
    sa.ForeignKeyConstraint(['country_id'], ['country.id'], ),
    sa.ForeignKeyConstraint(['initiated_by_user_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['law_id'], ['laws.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_alliance_leaves_alliance_id', 'alliance_leaves', ['alliance_id'], unique=False)
    op.create_index('ix_alliance_leaves_country_id', 'alliance_leaves', ['country_id'], unique=False)
    op.create_index('ix_alliance_leaves_status', 'alliance_leaves', ['status'], unique=False)

    op.create_table('alliance_dissolutions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('alliance_id', sa.Integer(), nullable=False),
    sa.Column('initiated_by_user_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('member_laws', sa.JSON(), nullable=False),
    sa.Column('member_votes', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['alliance_id'], ['alliances.id'], ),
    sa.ForeignKeyConstraint(['initiated_by_user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_alliance_dissolutions_alliance_id', 'alliance_dissolutions', ['alliance_id'], unique=False)
    op.create_index('ix_alliance_dissolutions_status', 'alliance_dissolutions', ['status'], unique=False)


def downgrade():
    op.drop_index('ix_alliance_dissolutions_status', table_name='alliance_dissolutions')
    op.drop_index('ix_alliance_dissolutions_alliance_id', table_name='alliance_dissolutions')
    op.drop_table('alliance_dissolutions')

    op.drop_index('ix_alliance_leaves_status', table_name='alliance_leaves')
    op.drop_index('ix_alliance_leaves_country_id', table_name='alliance_leaves')
    op.drop_index('ix_alliance_leaves_alliance_id', table_name='alliance_leaves')
    op.drop_table('alliance_leaves')

    op.drop_index('ix_alliance_kicks_target_country_id', table_name='alliance_kicks')
    op.drop_index('ix_alliance_kicks_status', table_name='alliance_kicks')
    op.drop_index('ix_alliance_kicks_alliance_id', table_name='alliance_kicks')
    op.drop_table('alliance_kicks')

    op.drop_index('ix_alliance_invitations_status', table_name='alliance_invitations')
    op.drop_index('ix_alliance_invitations_inviting_country_id', table_name='alliance_invitations')
    op.drop_index('ix_alliance_invitations_invited_country_id', table_name='alliance_invitations')
    op.drop_index('ix_alliance_invitations_alliance_id', table_name='alliance_invitations')
    op.drop_table('alliance_invitations')

    op.drop_index('ix_alliance_memberships_is_active', table_name='alliance_memberships')
    op.drop_index('ix_alliance_memberships_country_id', table_name='alliance_memberships')
    op.drop_index('ix_alliance_memberships_alliance_id', table_name='alliance_memberships')
    op.drop_index('idx_active_membership', table_name='alliance_memberships')
    op.drop_table('alliance_memberships')

    op.drop_index('ix_alliances_leader_country_id', table_name='alliances')
    op.drop_index('ix_alliances_is_active', table_name='alliances')
    op.drop_table('alliances')
