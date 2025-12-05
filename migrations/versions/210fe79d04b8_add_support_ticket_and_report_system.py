"""add_support_ticket_and_report_system

Revision ID: 210fe79d04b8
Revises: add_battle_system_001
Create Date: 2025-11-27 17:20:57.618507

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '210fe79d04b8'
down_revision = 'add_battle_system_001'
branch_labels = None
depends_on = None


def upgrade():
    # Create support ticket system tables
    op.create_table('canned_response',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('category', sa.Enum('BUG_REPORT', 'SUGGESTION', 'ACCOUNT_ISSUE', 'PAYMENT_ISSUE', 'REPORT_USER', 'OTHER', name='ticketcategory'), nullable=True),
    sa.Column('title', sa.String(length=100), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_by_id', sa.Integer(), nullable=False),
    sa.Column('times_used', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('support_ticket',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ticket_number', sa.String(length=20), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('category', sa.Enum('BUG_REPORT', 'SUGGESTION', 'ACCOUNT_ISSUE', 'PAYMENT_ISSUE', 'REPORT_USER', 'OTHER', name='ticketcategory'), nullable=False),
    sa.Column('subject', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('image_filename', sa.String(length=255), nullable=True),
    sa.Column('status', sa.Enum('OPEN', 'IN_PROGRESS', 'AWAITING_RESPONSE', 'RESOLVED', 'CLOSED', 'ARCHIVED', name='ticketstatus'), nullable=False),
    sa.Column('priority', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='ticketpriority'), nullable=False),
    sa.Column('assigned_to_id', sa.Integer(), nullable=True),
    sa.Column('rating', sa.Integer(), nullable=True),
    sa.Column('rating_comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('closed_at', sa.DateTime(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['assigned_to_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_support_ticket_priority', 'support_ticket', ['priority'], unique=False)
    op.create_index('ix_support_ticket_status', 'support_ticket', ['status'], unique=False)
    op.create_index('ix_support_ticket_ticket_number', 'support_ticket', ['ticket_number'], unique=True)

    op.create_table('ticket_audit_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ticket_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('action_type', sa.Enum('CREATED', 'STATUS_CHANGED', 'PRIORITY_CHANGED', 'ASSIGNED', 'RESPONSE_ADDED', 'INTERNAL_NOTE_ADDED', 'CLOSED', 'ARCHIVED', 'REOPENED', 'RATED', name='auditactiontype'), nullable=False),
    sa.Column('old_value', sa.String(length=100), nullable=True),
    sa.Column('new_value', sa.String(length=100), nullable=True),
    sa.Column('details', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['ticket_id'], ['support_ticket.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('ticket_response',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ticket_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('is_staff_response', sa.Boolean(), nullable=True),
    sa.Column('is_internal_note', sa.Boolean(), nullable=True),
    sa.Column('canned_response_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['canned_response_id'], ['canned_response.id'], ),
    sa.ForeignKeyConstraint(['ticket_id'], ['support_ticket.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('report',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('report_number', sa.String(length=20), nullable=False),
    sa.Column('reporter_id', sa.Integer(), nullable=False),
    sa.Column('reported_user_id', sa.Integer(), nullable=True),
    sa.Column('report_type', sa.Enum('MESSAGE', 'NEWSPAPER_ARTICLE', 'USER_PROFILE', 'COMPANY', name='reporttype'), nullable=False),
    sa.Column('reason', sa.Enum('INAPPROPRIATE_CONTENT', 'HARASSMENT', 'SPAM', 'CHEATING', 'INAPPROPRIATE_NAME_AVATAR', 'OTHER', name='reportreason'), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('reported_message_id', sa.Integer(), nullable=True),
    sa.Column('reported_article_id', sa.Integer(), nullable=True),
    sa.Column('reported_company_id', sa.Integer(), nullable=True),
    sa.Column('content_snapshot', sa.JSON(), nullable=True),
    sa.Column('status', sa.Enum('PENDING', 'UNDER_REVIEW', 'RESOLVED', 'DISMISSED', name='reportstatus'), nullable=False),
    sa.Column('action_taken', sa.Enum('DISMISSED', 'WARNING_ISSUED', 'CONTENT_REMOVED', 'USER_MUTED', 'TEMPORARY_BAN', 'PERMANENT_BAN', name='reportaction'), nullable=True),
    sa.Column('action_details', sa.Text(), nullable=True),
    sa.Column('mute_duration_hours', sa.Integer(), nullable=True),
    sa.Column('handled_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('handled_at', sa.DateTime(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['handled_by_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['reported_article_id'], ['article.id'], ),
    sa.ForeignKeyConstraint(['reported_company_id'], ['company.id'], ),
    sa.ForeignKeyConstraint(['reported_message_id'], ['message.id'], ),
    sa.ForeignKeyConstraint(['reported_user_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['reporter_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_report_report_number', 'report', ['report_number'], unique=True)
    op.create_index('ix_report_report_type', 'report', ['report_type'], unique=False)
    op.create_index('ix_report_status', 'report', ['status'], unique=False)

    op.create_table('user_mute',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('report_id', sa.Integer(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('muted_by_id', sa.Integer(), nullable=False),
    sa.Column('started_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('lifted_at', sa.DateTime(), nullable=True),
    sa.Column('lifted_by_id', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['lifted_by_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['muted_by_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['report_id'], ['report.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('user_mute')
    op.drop_index('ix_report_status', table_name='report')
    op.drop_index('ix_report_report_type', table_name='report')
    op.drop_index('ix_report_report_number', table_name='report')
    op.drop_table('report')
    op.drop_table('ticket_response')
    op.drop_table('ticket_audit_log')
    op.drop_index('ix_support_ticket_ticket_number', table_name='support_ticket')
    op.drop_index('ix_support_ticket_status', table_name='support_ticket')
    op.drop_index('ix_support_ticket_priority', table_name='support_ticket')
    op.drop_table('support_ticket')
    op.drop_table('canned_response')
