"""Split weapon and consumer companies into individual product companies

Revision ID: split_company_types_001
Revises: 6f1e24494970
Create Date: 2025-11-25

This migration:
1. Deletes all existing company-related data (companies, job offers, employments, etc.)
2. Updates the CompanyType enum to replace WEAPON_MANUFACTURING and CONSUMER_GOODS
   with individual product-specific company types
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'split_company_types_001'
down_revision = '6f1e24494970'
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Delete all company-related data
    # Order matters due to foreign key constraints

    # Delete work sessions first (references employment)
    op.execute("DELETE FROM work_session")

    # Delete company production progress
    op.execute("DELETE FROM company_production_progress")

    # Delete export licenses
    op.execute("DELETE FROM export_license")

    # Delete company transactions
    op.execute("DELETE FROM company_transaction")

    # Delete company inventory
    op.execute("DELETE FROM company_inventory")

    # Delete employments
    op.execute("DELETE FROM employment")

    # Delete job offers
    op.execute("DELETE FROM job_offer")

    # Delete companies
    op.execute("DELETE FROM company")

    # Step 2: Update the CompanyType enum
    # For MySQL, we need to alter the enum column

    # New enum values
    new_enum = (
        "ENUM('MINING', 'RESOURCE_EXTRACTION', 'FARMING', "
        "'RIFLE_MANUFACTURING', 'TANK_MANUFACTURING', 'HELICOPTER_MANUFACTURING', "
        "'BREAD_MANUFACTURING', 'BEER_MANUFACTURING', 'WINE_MANUFACTURING', "
        "'SEMI_PRODUCT', 'CONSTRUCTION')"
    )

    # Alter the company_type column with new enum values
    op.execute(f"ALTER TABLE company MODIFY company_type {new_enum} NOT NULL")


def downgrade():
    # Restore old enum (but data is lost)
    old_enum = (
        "ENUM('MINING', 'RESOURCE_EXTRACTION', 'FARMING', "
        "'WEAPON_MANUFACTURING', 'CONSUMER_GOODS', "
        "'SEMI_PRODUCT', 'CONSTRUCTION')"
    )

    op.execute(f"ALTER TABLE company MODIFY company_type {old_enum} NOT NULL")
