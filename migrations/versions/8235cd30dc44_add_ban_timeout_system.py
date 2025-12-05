"""add_ban_timeout_system

Revision ID: 8235cd30dc44
Revises: 5cf3589cbba6
Create Date: 2025-11-06 11:13:58.775167

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8235cd30dc44'
down_revision = '5cf3589cbba6'
branch_labels = None
depends_on = None


def upgrade():
    # Add ban/timeout system fields to user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_banned', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('ban_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('banned_until', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('banned_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('banned_by_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_user_banned_until'), ['banned_until'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_is_banned'), ['is_banned'], unique=False)
        batch_op.create_foreign_key('fk_user_banned_by', 'user', ['banned_by_id'], ['id'])


def downgrade():
    # Remove ban/timeout system fields from user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_constraint('fk_user_banned_by', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_user_is_banned'))
        batch_op.drop_index(batch_op.f('ix_user_banned_until'))
        batch_op.drop_column('banned_by_id')
        batch_op.drop_column('banned_at')
        batch_op.drop_column('banned_until')
        batch_op.drop_column('ban_reason')
        batch_op.drop_column('is_banned')
