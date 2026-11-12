"""memberships, invitations and session workspace override

Additive only: new tables and one nullable column; safe on existing data and
compatible with the previous application version.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('memberships',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('member_id', sa.String(length=32), nullable=False),
        sa.Column('org_id', sa.String(length=32), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['member_id'], ['members.id']),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('member_id', 'org_id'))
    op.create_index('ix_memberships_member_id', 'memberships', ['member_id'])
    op.create_index('ix_memberships_org_id', 'memberships', ['org_id'])
    op.create_table('invitations',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('org_id', sa.String(length=32), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('token_digest', sa.String(length=64), nullable=False),
        sa.Column('created_by', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('expires_at', sa.Float(), nullable=False),
        sa.Column('accepted_by', sa.String(length=32), nullable=True),
        sa.Column('accepted_at', sa.Float(), nullable=True),
        sa.Column('revoked_at', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['members.id']),
        sa.ForeignKeyConstraint(['accepted_by'], ['members.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_digest'))
    op.create_index('ix_invitations_org_id', 'invitations', ['org_id'])
    with op.batch_alter_table('sessions') as batch:
        batch.add_column(sa.Column('org_id', sa.String(length=32), nullable=True))
        batch.create_foreign_key('fk_sessions_org_id', 'organizations', ['org_id'], ['id'])


def downgrade():
    with op.batch_alter_table('sessions') as batch:
        batch.drop_constraint('fk_sessions_org_id', type_='foreignkey')
        batch.drop_column('org_id')
    op.drop_table('invitations')
    op.drop_table('memberships')
