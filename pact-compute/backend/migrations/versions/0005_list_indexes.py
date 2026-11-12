"""composite indexes for cursor-paginated list queries

Additive only (indexes). Safe on existing data; building them on a large table briefly takes a
write lock, which is negligible at the current scale.

Revision ID: 0005
Revises: 0004
"""
from alembic import op


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

INDEXES = [
    ('ix_jobs_org_created', 'jobs', ['org_id', 'created_at', 'id']),
    ('ix_research_runs_org_created', 'research_runs', ['org_id', 'created_at', 'id']),
    ('ix_bookings_consumer_accepted', 'market_bookings', ['consumer_org_id', 'accepted_at', 'id']),
    ('ix_bookings_producer_accepted', 'market_bookings', ['producer_org_id', 'accepted_at', 'id']),
    ('ix_offers_org_start', 'capacity_offers', ['org_id', 'starts_at', 'id']),
    ('ix_offers_status_ends', 'capacity_offers', ['status', 'ends_at']),
    ('ix_events_type_seq', 'events', ['entity_type', 'seq']),
]


def upgrade():
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade():
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
