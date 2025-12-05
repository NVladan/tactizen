"""change_bread_beer_limits_to_item_count

Revision ID: 028d691f34ff
Revises: 11daea3e2b05
Create Date: 2025-11-13 20:28:37.321238

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '028d691f34ff'
down_revision = '11daea3e2b05'
branch_labels = None
depends_on = None


def upgrade():
    # Rename wellness_from_bread_today to bread_consumed_today
    # Rename energy_from_beer_today to beer_consumed_today
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('wellness_from_bread_today',
                              new_column_name='bread_consumed_today',
                              existing_type=sa.Float(),
                              existing_nullable=False)
        batch_op.alter_column('energy_from_beer_today',
                              new_column_name='beer_consumed_today',
                              existing_type=sa.Float(),
                              existing_nullable=False)


def downgrade():
    # Rename back to original names
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('bread_consumed_today',
                              new_column_name='wellness_from_bread_today',
                              existing_type=sa.Float(),
                              existing_nullable=False)
        batch_op.alter_column('beer_consumed_today',
                              new_column_name='energy_from_beer_today',
                              existing_type=sa.Float(),
                              existing_nullable=False)
