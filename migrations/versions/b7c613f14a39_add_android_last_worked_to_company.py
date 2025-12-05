"""Add android_last_worked to Company

Revision ID: b7c613f14a39
Revises: 23ba6bf69281
Create Date: 2025-12-03 21:13:13.903187

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b7c613f14a39'
down_revision = '23ba6bf69281'
branch_labels = None
depends_on = None


def upgrade():
    # Add android_last_worked column to company table
    with op.batch_alter_table('company', schema=None) as batch_op:
        batch_op.add_column(sa.Column('android_last_worked', sa.Date(), nullable=True))


def downgrade():
    # Remove android_last_worked column from company table
    with op.batch_alter_table('company', schema=None) as batch_op:
        batch_op.drop_column('android_last_worked')
