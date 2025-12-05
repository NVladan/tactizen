"""add_production_progress_tracking

Revision ID: 69472e4cc4f1
Revises: 012c47ddf8f1
Create Date: 2025-11-13 12:17:44.957611

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '69472e4cc4f1'
down_revision = '012c47ddf8f1'
branch_labels = None
depends_on = None


def upgrade():
    # Create table to track production progress per resource
    op.create_table('company_production_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('progress', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resource_id'], ['resource.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create index for faster lookups
    op.create_index('ix_company_production_progress_company_resource',
                    'company_production_progress',
                    ['company_id', 'resource_id'],
                    unique=True)


def downgrade():
    op.drop_index('ix_company_production_progress_company_resource', table_name='company_production_progress')
    op.drop_table('company_production_progress')
