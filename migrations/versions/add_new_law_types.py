"""add new law types to enum

Revision ID: add_new_law_types
Revises: add_embargoes_table
Create Date: 2025-12-01 00:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_new_law_types'
down_revision = 'add_embargoes_table'
branch_labels = None
depends_on = None


def upgrade():
    # For MySQL, we need to modify the ENUM column to add new values
    # The new values to add: ALLIANCE_INVITE, ALLIANCE_JOIN, ALLIANCE_KICK, ALLIANCE_LEAVE, ALLIANCE_DISSOLVE, IMPEACHMENT, EMBARGO, REMOVE_EMBARGO
    op.execute("""
        ALTER TABLE laws
        MODIFY COLUMN law_type ENUM(
            'DECLARE_WAR',
            'MUTUAL_PROTECTION_PACT',
            'NON_AGGRESSION_PACT',
            'MILITARY_BUDGET',
            'PRINT_CURRENCY',
            'IMPORT_TAX',
            'SALARY_TAX',
            'INCOME_TAX',
            'ALLIANCE_INVITE',
            'ALLIANCE_JOIN',
            'ALLIANCE_KICK',
            'ALLIANCE_LEAVE',
            'ALLIANCE_DISSOLVE',
            'IMPEACHMENT',
            'EMBARGO',
            'REMOVE_EMBARGO'
        ) NOT NULL
    """)


def downgrade():
    # Revert to original enum values
    # WARNING: This will fail if any rows have the new enum values
    op.execute("""
        ALTER TABLE laws
        MODIFY COLUMN law_type ENUM(
            'DECLARE_WAR',
            'MUTUAL_PROTECTION_PACT',
            'NON_AGGRESSION_PACT',
            'MILITARY_BUDGET',
            'PRINT_CURRENCY',
            'IMPORT_TAX',
            'SALARY_TAX',
            'INCOME_TAX'
        ) NOT NULL
    """)
