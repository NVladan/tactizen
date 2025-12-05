"""merge military rank with ministers branch

Revision ID: 6f1e24494970
Revises: b1c2d3e4f5g6, military_rank_001
Create Date: 2025-11-24 21:40:29.200612

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6f1e24494970'
down_revision = ('b1c2d3e4f5g6', 'military_rank_001')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
