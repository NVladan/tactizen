"""add_mission_system

Revision ID: add_mission_system
Revises: add_resistance_war
Create Date: 2025-12-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_mission_system'
down_revision = 'add_resistance_war'
branch_labels = None
depends_on = None


def upgrade():
    # Create mission table
    op.create_table('mission',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('mission_type', sa.String(length=20), nullable=False),
        sa.Column('category', sa.String(length=20), nullable=False),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('requirement_count', sa.Integer(), nullable=False, default=1),
        sa.Column('gold_reward', sa.Numeric(precision=10, scale=2), nullable=False, default=0),
        sa.Column('xp_reward', sa.Integer(), nullable=False, default=0),
        sa.Column('resource_reward_id', sa.Integer(), nullable=True),
        sa.Column('resource_reward_quantity', sa.Integer(), nullable=False, default=0),
        sa.Column('resource_reward_quality', sa.Integer(), nullable=False, default=1),
        sa.Column('tutorial_order', sa.Integer(), nullable=True),
        sa.Column('prerequisite_mission_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['resource_reward_id'], ['resource.id'], ),
        sa.ForeignKeyConstraint(['prerequisite_mission_id'], ['mission.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('mission', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_mission_code'), ['code'], unique=True)
        batch_op.create_index(batch_op.f('ix_mission_mission_type'), ['mission_type'], unique=False)

    # Create user_mission table
    op.create_table('user_mission',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('mission_id', sa.Integer(), nullable=False),
        sa.Column('current_progress', sa.Integer(), nullable=False, default=0),
        sa.Column('is_completed', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_claimed', sa.Boolean(), nullable=False, default=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('claimed_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['mission_id'], ['mission.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('user_mission', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_mission_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_mission_mission_id'), ['mission_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_mission_is_completed'), ['is_completed'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_mission_expires_at'), ['expires_at'], unique=False)
        batch_op.create_index('idx_user_mission_lookup', ['user_id', 'mission_id'], unique=False)
        batch_op.create_index('idx_user_active_missions', ['user_id', 'is_completed', 'is_claimed'], unique=False)


def downgrade():
    with op.batch_alter_table('user_mission', schema=None) as batch_op:
        batch_op.drop_index('idx_user_active_missions')
        batch_op.drop_index('idx_user_mission_lookup')
        batch_op.drop_index(batch_op.f('ix_user_mission_expires_at'))
        batch_op.drop_index(batch_op.f('ix_user_mission_is_completed'))
        batch_op.drop_index(batch_op.f('ix_user_mission_mission_id'))
        batch_op.drop_index(batch_op.f('ix_user_mission_user_id'))

    op.drop_table('user_mission')

    with op.batch_alter_table('mission', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_mission_mission_type'))
        batch_op.drop_index(batch_op.f('ix_mission_code'))

    op.drop_table('mission')
