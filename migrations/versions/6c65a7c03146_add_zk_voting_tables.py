"""Add ZK voting tables

Revision ID: 6c65a7c03146
Revises: 18622e4d92b2
Create Date: 2025-12-07 16:57:18.162679

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6c65a7c03146'
down_revision = '18622e4d92b2'
branch_labels = None
depends_on = None


def upgrade():
    # Create ZK voting tables
    op.create_table('merkle_tree',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('election_type', sa.String(length=50), nullable=False),
        sa.Column('scope_id', sa.Integer(), nullable=False),
        sa.Column('root', sa.String(length=66), nullable=False),
        sa.Column('num_leaves', sa.Integer(), nullable=True),
        sa.Column('tree_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('election_type', 'scope_id', name='unique_merkle_tree')
    )

    op.create_table('zk_election_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('election_type', sa.String(length=50), nullable=False),
        sa.Column('election_id', sa.Integer(), nullable=False),
        sa.Column('zk_enabled', sa.Boolean(), nullable=True),
        sa.Column('registration_deadline', sa.DateTime(), nullable=True),
        sa.Column('voting_start', sa.DateTime(), nullable=True),
        sa.Column('voting_end', sa.DateTime(), nullable=True),
        sa.Column('frozen_merkle_root', sa.String(length=66), nullable=True),
        sa.Column('num_candidates', sa.Integer(), nullable=True),
        sa.Column('results_finalized', sa.Boolean(), nullable=True),
        sa.Column('results_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('election_type', 'election_id', name='unique_zk_election')
    )

    op.create_table('zk_vote',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('election_type', sa.String(length=50), nullable=False),
        sa.Column('election_id', sa.Integer(), nullable=False),
        sa.Column('nullifier', sa.String(length=66), nullable=False),
        sa.Column('vote_choice', sa.Integer(), nullable=False),
        sa.Column('merkle_root', sa.String(length=66), nullable=False),
        sa.Column('zkverify_tx_hash', sa.String(length=128), nullable=True),
        sa.Column('zkverify_block', sa.Integer(), nullable=True),
        sa.Column('proof_verified', sa.Boolean(), nullable=True),
        sa.Column('proof_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nullifier')
    )
    with op.batch_alter_table('zk_vote', schema=None) as batch_op:
        batch_op.create_index('idx_zkvote_election', ['election_type', 'election_id'], unique=False)
        batch_op.create_index('idx_zkvote_verified', ['proof_verified'], unique=False)

    op.create_table('voter_commitment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('election_type', sa.String(length=50), nullable=False),
        sa.Column('scope_id', sa.Integer(), nullable=False),
        sa.Column('commitment', sa.String(length=66), nullable=False),
        sa.Column('leaf_index', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'election_type', 'scope_id', name='unique_voter_commitment')
    )
    with op.batch_alter_table('voter_commitment', schema=None) as batch_op:
        batch_op.create_index('idx_commitment_scope', ['election_type', 'scope_id'], unique=False)


def downgrade():
    with op.batch_alter_table('voter_commitment', schema=None) as batch_op:
        batch_op.drop_index('idx_commitment_scope')
    op.drop_table('voter_commitment')

    with op.batch_alter_table('zk_vote', schema=None) as batch_op:
        batch_op.drop_index('idx_zkvote_verified')
        batch_op.drop_index('idx_zkvote_election')
    op.drop_table('zk_vote')

    op.drop_table('zk_election_config')
    op.drop_table('merkle_tree')
