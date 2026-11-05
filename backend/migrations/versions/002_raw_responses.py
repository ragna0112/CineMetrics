"""Add durable compressed raw JSON archive without changing existing data."""
from alembic import op
import sqlalchemy as sa
revision = '002'
down_revision = '001'

def upgrade():
    op.create_table('raw_responses',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('run_id', sa.Integer, sa.ForeignKey('pipeline_runs.id'), nullable=False),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resource', sa.String(200), nullable=False),
        sa.Column('payload_gzip', sa.LargeBinary, nullable=False))
    op.create_index('ix_raw_responses_run_id', 'raw_responses', ['run_id'])

def downgrade():
    op.drop_table('raw_responses')
