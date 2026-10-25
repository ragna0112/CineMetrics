"""Initial schema; frozen independently of application models."""
from alembic import op
import sqlalchemy as sa
revision = '001'
down_revision = None

def upgrade():
    op.create_table('genres', sa.Column('id', sa.Integer, primary_key=True), sa.Column('name', sa.String(100), nullable=False))
    op.create_table('movies', sa.Column('id', sa.Integer, primary_key=True), sa.Column('title', sa.String(500), nullable=False), sa.Column('overview', sa.Text), sa.Column('poster_url', sa.Text), sa.Column('release_date', sa.Date), sa.Column('original_language', sa.String(20)))
    op.create_index('ix_movies_title', 'movies', ['title'])
    op.create_index('ix_movies_release_date', 'movies', ['release_date'])
    op.create_table('movie_genres', sa.Column('movie_id', sa.Integer, sa.ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True), sa.Column('genre_id', sa.Integer, sa.ForeignKey('genres.id'), primary_key=True))
    op.create_index('ix_movie_genres_genre_id', 'movie_genres', ['genre_id'])
    op.create_table('movie_snapshots', sa.Column('movie_id', sa.Integer, sa.ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True), sa.Column('day', sa.Date, primary_key=True), sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False), sa.Column('popularity', sa.Float), sa.Column('rating', sa.Float), sa.Column('vote_count', sa.Integer), sa.CheckConstraint('popularity >= 0'), sa.CheckConstraint('rating >= 0 AND rating <= 10'), sa.CheckConstraint('vote_count >= 0'))
    op.create_index('ix_snapshot_day', 'movie_snapshots', ['day'])
    op.create_table('pipeline_runs', sa.Column('id', sa.Integer, primary_key=True), sa.Column('started_at', sa.DateTime(timezone=True), nullable=False), sa.Column('finished_at', sa.DateTime(timezone=True)), sa.Column('status', sa.String(20), nullable=False), sa.Column('movie_count', sa.Integer, nullable=False), sa.Column('error', sa.Text))
    op.create_index('ix_pipeline_runs_status', 'pipeline_runs', ['status'])

def downgrade():
    for name in ['pipeline_runs', 'movie_snapshots', 'movie_genres', 'movies', 'genres']:
        op.drop_table(name)
