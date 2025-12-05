"""Add game update model

Revision ID: 838d3a1769d6
Revises: b7c613f14a39
Create Date: 2025-12-04 19:07:20.675322

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '838d3a1769d6'
down_revision = 'b7c613f14a39'
branch_labels = None
depends_on = None


def upgrade():
    # Create game_update table only
    op.create_table('game_update',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('summary', sa.String(length=500), nullable=True),
    sa.Column('category', sa.Enum('FEATURE', 'BALANCE', 'BUGFIX', 'CONTENT', 'UI', 'PERFORMANCE', 'SECURITY', 'EVENT', 'ANNOUNCEMENT', 'MAINTENANCE', name='updatecategory'), nullable=False),
    sa.Column('version', sa.String(length=20), nullable=True),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('published_at', sa.DateTime(), nullable=True),
    sa.Column('is_published', sa.Boolean(), nullable=False),
    sa.Column('is_pinned', sa.Boolean(), nullable=False),
    sa.Column('is_important', sa.Boolean(), nullable=False),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('game_update')
