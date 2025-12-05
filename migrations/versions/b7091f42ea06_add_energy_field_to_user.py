"""add_energy_field_to_user

Revision ID: b7091f42ea06
Revises: 8235cd30dc44
Create Date: 2025-11-06 11:40:52.768637

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7091f42ea06'
down_revision = '8235cd30dc44'
branch_labels = None
depends_on = None


def upgrade():
    # Add energy field to user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('energy', sa.Float(), nullable=False, server_default='100.0'))


def downgrade():
    # Remove energy field from user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('energy')
