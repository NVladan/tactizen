"""add_quality_to_market_items

Revision ID: 6a664a866bca
Revises: c8b6acbcf3ce
Create Date: 2025-11-13 16:18:03.657131

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '6a664a866bca'
down_revision = 'c8b6acbcf3ce'
branch_labels = None
depends_on = None


def upgrade():
    # Create a new table with the updated schema
    op.create_table('country_market_item_new',
        sa.Column('country_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('quality', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('initial_price', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('price_level', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('progress_within_level', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['country_id'], ['country.id'], ),
        sa.ForeignKeyConstraint(['resource_id'], ['resource.id'], ),
        sa.PrimaryKeyConstraint('country_id', 'resource_id', 'quality')
    )

    # Copy data from old table to new (all existing items get quality=0)
    op.execute('''
        INSERT INTO country_market_item_new
        (country_id, resource_id, quality, initial_price, price_level, progress_within_level, created_at, updated_at)
        SELECT country_id, resource_id, 0, initial_price, price_level, progress_within_level, created_at, updated_at
        FROM country_market_item
    ''')

    # Drop old table
    op.drop_table('country_market_item')

    # Rename new table to original name
    op.rename_table('country_market_item_new', 'country_market_item')

    # Re-create indexes
    op.create_index('ix_country_market_item_price_level', 'country_market_item', ['price_level'])


def downgrade():
    # Create old table structure
    op.create_table('country_market_item_old',
        sa.Column('country_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('initial_price', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('price_level', sa.Integer(), nullable=False),
        sa.Column('progress_within_level', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['country_id'], ['country.id'], ),
        sa.ForeignKeyConstraint(['resource_id'], ['resource.id'], ),
        sa.PrimaryKeyConstraint('country_id', 'resource_id')
    )

    # Copy data back (only quality=0 items)
    op.execute('''
        INSERT INTO country_market_item_old
        (country_id, resource_id, initial_price, price_level, progress_within_level, created_at, updated_at)
        SELECT country_id, resource_id, initial_price, price_level, progress_within_level, created_at, updated_at
        FROM country_market_item
        WHERE quality = 0
    ''')

    # Drop new table
    op.drop_table('country_market_item')

    # Rename old table back
    op.rename_table('country_market_item_old', 'country_market_item')

    # Re-create indexes
    op.create_index('ix_country_market_item_price_level', 'country_market_item', ['price_level'])
