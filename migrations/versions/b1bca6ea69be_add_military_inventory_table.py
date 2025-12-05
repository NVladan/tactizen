"""add_military_inventory_table

Revision ID: b1bca6ea69be
Revises: 425f686cede2
Create Date: 2025-11-29 23:16:42.218921

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b1bca6ea69be'
down_revision = '425f686cede2'
branch_labels = None
depends_on = None


def upgrade():
    # Create military_inventory table only
    op.create_table('military_inventory',
        sa.Column('country_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('quality', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['country_id'], ['country.id'], ),
        sa.ForeignKeyConstraint(['resource_id'], ['resource.id'], ),
        sa.PrimaryKeyConstraint('country_id', 'resource_id', 'quality')
    )


def downgrade():
    op.drop_table('military_inventory')
