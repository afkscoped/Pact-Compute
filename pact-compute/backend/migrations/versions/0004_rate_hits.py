"""shared rate-limit table

Additive only: one new table.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('rate_hits',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('bucket', sa.String(length=160), nullable=False),
        sa.Column('until', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_rate_hits_bucket_until', 'rate_hits', ['bucket', 'until'])


def downgrade():
    op.drop_index('ix_rate_hits_bucket_until', table_name='rate_hits')
    op.drop_table('rate_hits')
