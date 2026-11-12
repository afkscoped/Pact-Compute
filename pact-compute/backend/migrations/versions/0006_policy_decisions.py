"""policy rejection and decision notes

Additive only: three nullable columns on policies.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('policies') as batch:
        batch.add_column(sa.Column('rejected_at', sa.Float(), nullable=True))
        batch.add_column(sa.Column('rejected_by', sa.String(length=32), nullable=True))
        batch.add_column(sa.Column('decision_note', sa.Text(), nullable=True))
        batch.create_foreign_key('fk_policies_rejected_by', 'members', ['rejected_by'], ['id'])


def downgrade():
    with op.batch_alter_table('policies') as batch:
        batch.drop_constraint('fk_policies_rejected_by', type_='foreignkey')
        batch.drop_column('decision_note')
        batch.drop_column('rejected_by')
        batch.drop_column('rejected_at')
