"""add_positions_to_job_offer

Revision ID: 39cdaa708f77
Revises: 15da41f579e6
Create Date: 2025-11-07 14:46:36.924649

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '39cdaa708f77'
down_revision = '15da41f579e6'
branch_labels = None
depends_on = None


def upgrade():
    # Add positions field to job_offer table
    with op.batch_alter_table('job_offer', schema=None) as batch_op:
        batch_op.add_column(sa.Column('positions', sa.Integer(), nullable=False, server_default='1'))


def downgrade():
    # Remove positions field from job_offer table
    with op.batch_alter_table('job_offer', schema=None) as batch_op:
        batch_op.drop_column('positions')
