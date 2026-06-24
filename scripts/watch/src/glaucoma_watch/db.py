"""Observability database schema.

Five append-only tables form the audit trail:

* ``runs`` records every invocation of the watcher.
* ``fetch_events`` records every HTTP request the fetcher made.
* ``snapshots`` records the per-source parsed link list captured this run.
* ``candidates`` records documents that survived deduplication (i.e., truly new).
* ``triage_decisions`` records each AI or human decision about a candidate.

The tables are append-only by convention: callers should never UPDATE or DELETE
rows. Corrections are added as new rows that supersede prior ones (e.g., a human
override of an AI decision is a new ``triage_decisions`` row that references the
same ``candidate_id``).
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .paths import db_path


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"
    run_id = Column(String, primary_key=True, default=_new_id)
    trigger = Column(String, nullable=False)
    git_sha = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=False, default="running")
    error_summary = Column(Text, nullable=True)
    stats = Column(JSON, nullable=True)


class FetchEvent(Base):
    __tablename__ = "fetch_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("runs.run_id"), nullable=False, index=True)
    source_id = Column(String, nullable=False, index=True)
    url = Column(String, nullable=False)
    method = Column(String, nullable=False, default="GET")
    http_status = Column(Integer, nullable=True)
    bytes = Column(Integer, nullable=True)
    sha256_head = Column(String, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    retries = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
    fetched_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class Snapshot(Base):
    __tablename__ = "snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("runs.run_id"), nullable=False, index=True)
    source_id = Column(String, nullable=False, index=True)
    link_count = Column(Integer, nullable=False, default=0)
    snapshot_path = Column(String, nullable=True)
    diff_vs_prior = Column(JSON, nullable=True)
    captured_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class Candidate(Base):
    __tablename__ = "candidates"
    candidate_id = Column(String, primary_key=True, default=_new_id)
    run_id = Column(String, ForeignKey("runs.run_id"), nullable=False, index=True)
    source_id = Column(String, nullable=False, index=True)
    url = Column(String, nullable=False)
    normalized_title = Column(String, nullable=True)
    dedupe_decision = Column(String, nullable=False)
    confidence_features = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class TriageDecision(Base):
    __tablename__ = "triage_decisions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String, ForeignKey("candidates.candidate_id"), nullable=False, index=True)
    model = Column(String, nullable=False)
    prompt_sha256 = Column(String, nullable=True)
    response_json = Column(JSON, nullable=True)
    include = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=True)
    rationale = Column(Text, nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    decided_by = Column(String, nullable=False)
    reviewer_action = Column(String, nullable=True)


_engine: Any = None
_SessionFactory: Any = None


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            f"sqlite:///{db_path()}",
            future=True,
            json_serializer=lambda obj: __import__("json").dumps(obj, default=str),
        )

        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return _engine


def session() -> Session:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=engine(), expire_on_commit=False, future=True)
    return _SessionFactory()


def init_db() -> None:
    Base.metadata.create_all(engine())
