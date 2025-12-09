"""Add user_visited_countries tracking table

Revision ID: 28cc0421e7df
Revises: 83b18b03388d
Create Date: 2025-12-08 22:15:04.570254

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '28cc0421e7df'
down_revision = '83b18b03388d'
branch_labels = None
depends_on = None


def upgrade():
    # Create the user_visited_countries tracking table
    op.create_table('user_visited_countries',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('country_id', sa.Integer(), nullable=False),
        sa.Column('first_visited_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['country_id'], ['country.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'country_id')
    )


def downgrade():
    op.drop_table('user_visited_countries')
