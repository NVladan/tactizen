"""Add blockchain signature fields to vote models

Revision ID: e41dc688ed79
Revises: 122e71fa3a25
Create Date: 2025-12-04 23:12:50.396937

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e41dc688ed79'
down_revision = '122e71fa3a25'
branch_labels = None
depends_on = None


def upgrade():
    # Add blockchain signature fields to election_votes
    with op.batch_alter_table('election_votes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('wallet_address', sa.String(length=42), nullable=True))
        batch_op.add_column(sa.Column('vote_message', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('vote_signature', sa.String(length=132), nullable=True))
        batch_op.create_index(batch_op.f('ix_election_votes_wallet_address'), ['wallet_address'], unique=False)

    # Add blockchain signature fields to party_vote
    with op.batch_alter_table('party_vote', schema=None) as batch_op:
        batch_op.add_column(sa.Column('wallet_address', sa.String(length=42), nullable=True))
        batch_op.add_column(sa.Column('vote_message', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('vote_signature', sa.String(length=132), nullable=True))
        batch_op.create_index(batch_op.f('ix_party_vote_wallet_address'), ['wallet_address'], unique=False)


def downgrade():
    # Remove blockchain signature fields from party_vote
    with op.batch_alter_table('party_vote', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_party_vote_wallet_address'))
        batch_op.drop_column('vote_signature')
        batch_op.drop_column('vote_message')
        batch_op.drop_column('wallet_address')

    # Remove blockchain signature fields from election_votes
    with op.batch_alter_table('election_votes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_election_votes_wallet_address'))
        batch_op.drop_column('vote_signature')
        batch_op.drop_column('vote_message')
        batch_op.drop_column('wallet_address')
