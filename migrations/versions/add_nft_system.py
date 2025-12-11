"""add nft system

Revision ID: nft_system_001
Revises: a1b2c3d4e5f6
Create Date: 2025-11-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'nft_system_001'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # NFT inventory table
    op.create_table(
        'nft_inventory',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('nft_type', sa.String(length=50), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('tier', sa.Integer(), nullable=False),
        sa.Column('bonus_value', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.BigInteger(), nullable=False),
        sa.Column('contract_address', sa.String(length=42), nullable=False),
        sa.Column('is_equipped', sa.Boolean(), server_default='false'),
        sa.Column('equipped_to_profile', sa.Boolean(), server_default='false'),
        sa.Column('equipped_to_company_id', sa.Integer(), nullable=True),
        sa.Column('acquired_via', sa.String(length=20), nullable=False),
        sa.Column('acquired_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('metadata_uri', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('tier >= 1 AND tier <= 5', name='check_tier_range'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['equipped_to_company_id'], ['company.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_id')
    )

    # Create indexes
    op.create_index('idx_nft_inventory_user_id', 'nft_inventory', ['user_id'])
    op.create_index('idx_nft_inventory_token_id', 'nft_inventory', ['token_id'])
    op.create_index('idx_nft_inventory_tier', 'nft_inventory', ['tier'])
    op.create_index('idx_nft_inventory_equipped', 'nft_inventory', ['is_equipped'])
    op.create_index('idx_nft_inventory_company', 'nft_inventory', ['equipped_to_company_id'])

    # Player NFT slots table
    op.create_table(
        'player_nft_slots',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('slot_1_nft_id', sa.Integer(), nullable=True),
        sa.Column('slot_2_nft_id', sa.Integer(), nullable=True),
        sa.Column('slot_3_nft_id', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['slot_1_nft_id'], ['nft_inventory.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['slot_2_nft_id'], ['nft_inventory.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['slot_3_nft_id'], ['nft_inventory.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('user_id')
    )

    # Company NFT slots table
    op.create_table(
        'company_nft_slots',
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('slot_1_nft_id', sa.Integer(), nullable=True),
        sa.Column('slot_2_nft_id', sa.Integer(), nullable=True),
        sa.Column('slot_3_nft_id', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['slot_1_nft_id'], ['nft_inventory.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['slot_2_nft_id'], ['nft_inventory.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['slot_3_nft_id'], ['nft_inventory.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('company_id')
    )

    # NFT burn history table
    op.create_table(
        'nft_burn_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('burned_nft_ids', sa.Text(), nullable=False),  # Store as JSON in MySQL
        sa.Column('minted_nft_id', sa.BigInteger(), nullable=True),
        sa.Column('tier_from', sa.Integer(), nullable=False),
        sa.Column('tier_to', sa.Integer(), nullable=True),
        sa.Column('transaction_hash', sa.String(length=66), nullable=True),
        sa.Column('burned_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('tier_from >= 1 AND tier_from <= 5', name='check_tier_from_range'),
        sa.CheckConstraint('tier_to >= 1 AND tier_to <= 5', name='check_tier_to_range'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('idx_nft_burn_history_user_id', 'nft_burn_history', ['user_id'])
    op.create_index('idx_nft_burn_history_minted_nft_id', 'nft_burn_history', ['minted_nft_id'])

    # NFT drop history table
    op.create_table(
        'nft_drop_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('nft_id', sa.Integer(), nullable=False),
        sa.Column('drop_source', sa.String(length=50), nullable=False),
        sa.Column('tier', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('dropped_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('tier >= 1 AND tier <= 3', name='check_drop_tier_range'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['nft_id'], ['nft_inventory.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('idx_nft_drop_history_user_id', 'nft_drop_history', ['user_id'])
    op.create_index('idx_nft_drop_history_drop_source', 'nft_drop_history', ['drop_source'])
    op.create_index('idx_nft_drop_history_tier', 'nft_drop_history', ['tier'])
    op.create_index('idx_nft_drop_history_dropped_at', 'nft_drop_history', ['dropped_at'])

    # NFT marketplace table
    op.create_table(
        'nft_marketplace',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nft_id', sa.Integer(), nullable=False),
        sa.Column('seller_id', sa.Integer(), nullable=False),
        sa.Column('price_zen', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('price_gold', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('listed_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('sold_at', sa.DateTime(), nullable=True),
        sa.Column('buyer_id', sa.Integer(), nullable=True),
        sa.CheckConstraint('price_zen > 0', name='check_price_zen_positive'),
        sa.ForeignKeyConstraint(['nft_id'], ['nft_inventory.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['seller_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['buyer_id'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nft_id', 'is_active', name='unique_active_listing')
    )

    op.create_index('idx_nft_marketplace_seller_id', 'nft_marketplace', ['seller_id'])
    op.create_index('idx_nft_marketplace_is_active', 'nft_marketplace', ['is_active'])

    # NFT trade history table
    op.create_table(
        'nft_trade_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nft_id', sa.Integer(), nullable=False),
        sa.Column('from_user_id', sa.Integer(), nullable=False),
        sa.Column('to_user_id', sa.Integer(), nullable=False),
        sa.Column('price_zen', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('price_gold', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('trade_type', sa.String(length=20), nullable=False),
        sa.Column('transaction_hash', sa.String(length=66), nullable=True),
        sa.Column('traded_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['nft_id'], ['nft_inventory.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['from_user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('idx_nft_trade_history_from_user_id', 'nft_trade_history', ['from_user_id'])
    op.create_index('idx_nft_trade_history_to_user_id', 'nft_trade_history', ['to_user_id'])
    op.create_index('idx_nft_trade_history_nft_id', 'nft_trade_history', ['nft_id'])


def downgrade():
    # Drop tables in reverse order
    op.drop_table('nft_trade_history')
    op.drop_table('nft_marketplace')
    op.drop_table('nft_drop_history')
    op.drop_table('nft_burn_history')
    op.drop_table('company_nft_slots')
    op.drop_table('player_nft_slots')
    op.drop_table('nft_inventory')
