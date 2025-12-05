"""add blockchain fields

Revision ID: 691b9c00
Revises: 5fb7d5f29f83
Create Date: 2025-11-17 23:04:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '691b9c00'
down_revision = '5fb7d5f29f83'
branch_labels = None
depends_on = None


def upgrade():
    # Add blockchain fields to user table
    op.add_column('user', sa.Column('base_wallet_address', sa.String(length=42), nullable=True))
    op.add_column('user', sa.Column('citizenship_nft_token_id', sa.Integer(), nullable=True))
    op.add_column('user', sa.Column('government_nft_token_id', sa.Integer(), nullable=True))

    # Add index for base_wallet_address
    op.create_index(op.f('ix_user_base_wallet_address'), 'user', ['base_wallet_address'], unique=False)


def downgrade():
    # Remove index
    op.drop_index(op.f('ix_user_base_wallet_address'), table_name='user')

    # Remove columns
    op.drop_column('user', 'government_nft_token_id')
    op.drop_column('user', 'citizenship_nft_token_id')
    op.drop_column('user', 'base_wallet_address')
