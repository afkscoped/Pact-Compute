"""incident ownership and resolution records

Additive only: one new table.

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('incident_records',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('org_id', sa.String(length=32), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('subject_type', sa.String(length=20), nullable=False),
        sa.Column('subject_id', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=12), nullable=False),
        sa.Column('owner_id', sa.String(length=32), nullable=True),
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.Column('outcome', sa.String(length=20), nullable=True),
        sa.Column('resolved_by', sa.String(length=32), nullable=True),
        sa.Column('resolved_at', sa.Float(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['owner_id'], ['members.id']),
        sa.ForeignKeyConstraint(['resolved_by'], ['members.id']),
        sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_incident_records_org_id', 'incident_records', ['org_id'])
    op.create_index('ix_incident_records_org_status', 'incident_records', ['org_id', 'status', 'created_at'])


def downgrade():
    op.drop_index('ix_incident_records_org_status', table_name='incident_records')
    op.drop_index('ix_incident_records_org_id', table_name='incident_records')
    op.drop_table('incident_records')
