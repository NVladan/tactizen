"""add_quality_to_inventory_items

Revision ID: 3025788cf32a
Revises: 6a664a866bca
Create Date: 2025-11-13 16:37:06.580398

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '3025788cf32a'
down_revision = '6a664a866bca'
branch_labels = None
depends_on = None


def upgrade():
    # Create a new table with the updated schema
    op.create_table('inventory_item_new',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('quality', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['resource_id'], ['resource.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'resource_id', 'quality')
    )

    # Copy data from old table to new (all existing items get quality=0)
    op.execute('''
        INSERT INTO inventory_item_new
        (user_id, resource_id, quality, quantity)
        SELECT user_id, resource_id, 0, quantity
        FROM inventory_item
    ''')

    # Drop old table
    op.drop_table('inventory_item')

    # Rename new table to original name
    op.rename_table('inventory_item_new', 'inventory_item')


def downgrade():
    # Create old table structure
    op.create_table('inventory_item_old',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['resource_id'], ['resource.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'resource_id')
    )

    # Copy data back, grouping by user_id and resource_id, summing quantities
    op.execute('''
        INSERT INTO inventory_item_old
        (user_id, resource_id, quantity)
        SELECT user_id, resource_id, SUM(quantity)
        FROM inventory_item
        GROUP BY user_id, resource_id
    ''')

    # Drop new table
    op.drop_table('inventory_item')

    # Rename old table back
    op.rename_table('inventory_item_old', 'inventory_item')
