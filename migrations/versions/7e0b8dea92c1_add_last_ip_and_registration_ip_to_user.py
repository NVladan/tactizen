"""add last_ip and registration_ip to user

Revision ID: 7e0b8dea92c1
Revises: 6c65a7c03146
Create Date: 2025-12-08 20:40:21.863574

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '7e0b8dea92c1'
down_revision = '6c65a7c03146'
branch_labels = None
depends_on = None


def upgrade():
    # Add IP tracking columns to user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_ip', sa.String(length=45), nullable=True))
        batch_op.add_column(sa.Column('registration_ip', sa.String(length=45), nullable=True))
        batch_op.create_index(batch_op.f('ix_user_last_ip'), ['last_ip'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_registration_ip'), ['registration_ip'], unique=False)


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_registration_ip'))
        batch_op.drop_index(batch_op.f('ix_user_last_ip'))
        batch_op.drop_column('registration_ip')
        batch_op.drop_column('last_ip')
