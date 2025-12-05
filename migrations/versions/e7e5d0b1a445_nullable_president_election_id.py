"""nullable_president_election_id

Revision ID: e7e5d0b1a445
Revises: 8c8540c72e91
Create Date: 2025-11-29 20:54:03.428135

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'e7e5d0b1a445'
down_revision = '8c8540c72e91'
branch_labels = None
depends_on = None


def upgrade():
    # Make election_id nullable in country_presidents table for impeachment cases
    with op.batch_alter_table('country_presidents', schema=None) as batch_op:
        batch_op.alter_column('election_id',
               existing_type=mysql.INTEGER(display_width=11),
               nullable=True)


def downgrade():
    with op.batch_alter_table('country_presidents', schema=None) as batch_op:
        batch_op.alter_column('election_id',
               existing_type=mysql.INTEGER(display_width=11),
               nullable=False)
