"""Add conquest system fields

Revision ID: add_conquest_system
Revises: 33ead7b1b4e5
Create Date: 2025-12-05

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_conquest_system'
down_revision = '33ead7b1b4e5'
branch_labels = None
depends_on = None


def upgrade():
    # Add conquest fields to country table
    op.add_column('country', sa.Column('is_conquered', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('country', sa.Column('conquered_by_id', sa.Integer(), nullable=True))
    op.add_column('country', sa.Column('conquered_at', sa.DateTime(), nullable=True))

    # Add foreign key for conquered_by_id (self-referential)
    op.create_foreign_key(
        'fk_country_conquered_by',
        'country', 'country',
        ['conquered_by_id'], ['id']
    )

    # Add index for is_conquered
    op.create_index('ix_country_is_conquered', 'country', ['is_conquered'])

    # Add frozen fields to company table
    op.add_column('company', sa.Column('is_frozen', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('company', sa.Column('frozen_at', sa.DateTime(), nullable=True))

    # Add index for is_frozen
    op.create_index('ix_company_is_frozen', 'company', ['is_frozen'])


def downgrade():
    # Remove company frozen fields
    op.drop_index('ix_company_is_frozen', 'company')
    op.drop_column('company', 'frozen_at')
    op.drop_column('company', 'is_frozen')

    # Remove country conquest fields
    op.drop_index('ix_country_is_conquered', 'country')
    op.drop_constraint('fk_country_conquered_by', 'country', type_='foreignkey')
    op.drop_column('country', 'conquered_at')
    op.drop_column('country', 'conquered_by_id')
    op.drop_column('country', 'is_conquered')
