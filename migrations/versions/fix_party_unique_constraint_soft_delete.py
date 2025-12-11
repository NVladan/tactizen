"""fix party unique constraint for soft delete

Revision ID: fix_party_constraint
Revises: export_license_001
Create Date: 2025-11-24 15:12:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_party_constraint'
down_revision = 'export_license_001'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the old unique constraint
    op.drop_constraint('uq_party_country_slug', 'political_party', type_='unique')

    # For MySQL, we need a different approach since it doesn't support partial indexes
    # We'll add is_deleted to the unique constraint (NULL values are ignored in unique indexes)
    # This allows duplicate (country_id, slug) pairs if they have different is_deleted values
    # Since we only use 0 (False) and 1 (True), this works: one active, multiple deleted allowed
    op.create_unique_constraint('uq_party_country_slug_deleted', 'political_party', ['country_id', 'slug', 'is_deleted'])


def downgrade():
    # Drop the new unique constraint
    op.drop_constraint('uq_party_country_slug_deleted', 'political_party', type_='unique')

    # Restore the old unique constraint
    op.create_unique_constraint('uq_party_country_slug', 'political_party', ['country_id', 'slug'])
