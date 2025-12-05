"""add_activity_tracking

Revision ID: c4eb9d63851b
Revises: abc123456789
Create Date: 2025-11-06 01:17:20.395934

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'c4eb9d63851b'
down_revision = 'abc123456789'
branch_labels = None
depends_on = None


def upgrade():
    # Add activity tracking columns to user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_login', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_seen', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('login_count', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('page_views', sa.Integer(), nullable=False, server_default='0'))
        batch_op.create_index('ix_user_last_login', ['last_login'])
        batch_op.create_index('ix_user_last_seen', ['last_seen'])

    # Create activity_log table
    op.create_table('activity_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('activity_type', sa.Enum('LOGIN', 'LOGOUT', 'PAGE_VIEW', 'MARKET_BUY', 'MARKET_SELL',
                                          'CURRENCY_EXCHANGE', 'TRAVEL', 'TRAIN', 'STUDY',
                                          'PROFILE_UPDATE', 'ADMIN_ACTION', 'CACHE_CLEAR',
                                          'PROFILE_VIEW', 'ERROR_403', 'ERROR_404', 'ERROR_500',
                                          name='activitytype'), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('endpoint', sa.String(length=255), nullable=True),
        sa.Column('method', sa.String(length=10), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('activity_log', schema=None) as batch_op:
        batch_op.create_index('idx_activity_created', ['created_at'])
        batch_op.create_index('idx_activity_user_created', ['user_id', 'created_at'])
        batch_op.create_index('idx_activity_user_type', ['user_id', 'activity_type'])
        batch_op.create_index('ix_activity_log_activity_type', ['activity_type'])
        batch_op.create_index('ix_activity_log_endpoint', ['endpoint'])
        batch_op.create_index('ix_activity_log_user_id', ['user_id'])

    # Create user_session table
    op.create_table('user_session',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_token', sa.String(length=255), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('login_at', sa.DateTime(), nullable=False),
        sa.Column('logout_at', sa.DateTime(), nullable=True),
        sa.Column('last_activity', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('user_session', schema=None) as batch_op:
        batch_op.create_index('idx_session_login', ['login_at'])
        batch_op.create_index('idx_session_user_active', ['user_id', 'is_active'])
        batch_op.create_index('ix_user_session_is_active', ['is_active'])
        batch_op.create_index('ix_user_session_session_token', ['session_token'], unique=True)
        batch_op.create_index('ix_user_session_user_id', ['user_id'])


def downgrade():
    # Drop user_session table
    op.drop_table('user_session')

    # Drop activity_log table
    op.drop_table('activity_log')

    # Remove activity tracking columns from user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_index('ix_user_last_seen')
        batch_op.drop_index('ix_user_last_login')
        batch_op.drop_column('page_views')
        batch_op.drop_column('login_count')
        batch_op.drop_column('last_seen')
        batch_op.drop_column('last_login')
