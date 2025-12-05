"""add_employment_alert_type

Revision ID: c8b6acbcf3ce
Revises: 69472e4cc4f1
Create Date: 2025-11-13 14:18:30.204697

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8b6acbcf3ce'
down_revision = '69472e4cc4f1'
branch_labels = None
depends_on = None


def upgrade():
    # Add new enum values for AlertType
    op.execute("ALTER TABLE alert MODIFY COLUMN alert_type ENUM('level_up', 'house_expired', 'election_win', 'admin_announcement', 'employment')")

    # Add new enum values for AlertPriority
    op.execute("ALTER TABLE alert MODIFY COLUMN priority ENUM('low', 'normal', 'medium', 'important', 'urgent')")


def downgrade():
    # Remove the new enum values
    op.execute("ALTER TABLE alert MODIFY COLUMN alert_type ENUM('level_up', 'house_expired', 'election_win', 'admin_announcement')")

    # Remove the new priority values
    op.execute("ALTER TABLE alert MODIFY COLUMN priority ENUM('normal', 'important', 'urgent')")
