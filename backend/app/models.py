from datetime import date, datetime
from sqlalchemy import String, Text, ForeignKey, DateTime, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class MovieGenre(Base):
    __tablename__ = 'movie_genres'
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True)
    genre_id: Mapped[int] = mapped_column(ForeignKey('genres.id'), primary_key=True, index=True)

class Genre(Base):
    __tablename__ = 'genres'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))

class Movie(Base):
    __tablename__ = 'movies'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    overview: Mapped[str | None] = mapped_column(Text)
    poster_url: Mapped[str | None] = mapped_column(Text)
    release_date: Mapped[date | None] = mapped_column(index=True)
    original_language: Mapped[str | None] = mapped_column(String(20))
    genres: Mapped[list[Genre]] = relationship(secondary='movie_genres', lazy='selectin')

class Snapshot(Base):
    __tablename__ = 'movie_snapshots'
    movie_id: Mapped[int] = mapped_column(ForeignKey('movies.id', ondelete='CASCADE'), primary_key=True)
    day: Mapped[date] = mapped_column(primary_key=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    popularity: Mapped[float | None]
    rating: Mapped[float | None]
    vote_count: Mapped[int | None]
    __table_args__ = (CheckConstraint('popularity >= 0'), CheckConstraint('rating >= 0 AND rating <= 10'), CheckConstraint('vote_count >= 0'), Index('ix_snapshot_day', 'day'))

class PipelineRun(Base):
    __tablename__ = 'pipeline_runs'
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), index=True)
    movie_count: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text)
