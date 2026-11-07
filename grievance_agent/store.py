"""MySQL case store (SQLAlchemy 2.x).

Production target is MySQL 8 (``mysql+pymysql://...``). SQLite is supported for local
development and tests only. Only PII-redacted text is ever written here.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text,
                        create_engine, delete, select)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id() -> str:
    return uuid.uuid4().hex[:12].upper()


class Base(DeclarativeBase):
    pass


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    source: Mapped[str] = mapped_column(String(16), default="live")           # live | eval
    status: Mapped[str] = mapped_column(String(24), default="intake", index=True)
    # intake | crisis | submitted | in_review | closed | withdrawn
    student_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)  # salted hash, never a raw ID
    route: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    urgency_level: Mapped[str] = mapped_column(String(16), default="routine")
    urgency_score: Mapped[float] = mapped_column(Float, default=0.0)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewer_outcome: Mapped[str | None] = mapped_column(String(96), nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    turns: Mapped[list["Turn"]] = relationship(back_populates="case", cascade="all, delete-orphan", order_by="Turn.idx")
    records: Mapped[list["Record"]] = relationship(back_populates="case", cascade="all, delete-orphan", order_by="Record.version")


class Turn(Base):
    __tablename__ = "turns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))   # student | assistant | system
    text_redacted: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    case: Mapped[Case] = relationship(back_populates="turns")


class Record(Base):
    __tablename__ = "records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    record_json: Mapped[dict] = mapped_column(JSON)
    verification_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(32), default="ai")  # ai | reviewer
    student_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    case: Mapped[Case] = relationship(back_populates="records")


class ConsentLog(Base):
    __tablename__ = "consent_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(32), index=True)  # kept after deletion, as proof of the request
    event: Mapped[str] = mapped_column(String(32))  # given | withdrawn | deleted
    notice_version: Mapped[str] = mapped_column(String(16), default="v1")
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Escalation(Base):
    __tablename__ = "escalations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    route: Mapped[str] = mapped_column(String(32))
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    acknowledged_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    actor: Mapped[str] = mapped_column(String(64))   # system | student | reviewer:<name>
    action: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Precedent(Base):
    """Anonymised, labelled example statements used for urgency kNN / precedent search."""
    __tablename__ = "precedents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text_redacted: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(String(16))   # routine | sensitive | high
    embedding: Mapped[bytes] = mapped_column(LargeBinary)
    embed_model: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RubricRating(Base):
    __tablename__ = "rubric_ratings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    item_id: Mapped[str] = mapped_column(String(32), index=True)   # blinded dialogue id
    rater: Mapped[str] = mapped_column(String(64))
    scores: Mapped[dict] = mapped_column(JSON)                     # {"E1": 4, ...}
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


def student_pseudonym(raw_student_id: str, salt: str) -> str:
    return hashlib.sha256((salt + "|" + raw_student_id.strip().lower()).encode()).hexdigest()[:32]


class Store:
    def __init__(self, database_url: str, echo: bool = False):
        kwargs: dict[str, Any] = {"echo": echo, "future": True}
        if database_url.startswith("mysql"):
            kwargs.update(pool_pre_ping=True, pool_recycle=3600)
        if database_url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if database_url in ("sqlite://", "sqlite:///:memory:"):
                from sqlalchemy.pool import StaticPool
                kwargs["poolclass"] = StaticPool
        self.engine = create_engine(database_url, **kwargs)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Any]:
        s = self.Session()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    # ---------- cases ----------
    def create_case(self, source: str = "live", student_ref: str | None = None) -> str:
        with self.session() as s:
            c = Case(source=source, student_ref=student_ref)
            s.add(c)
            s.flush()
            s.add(ConsentLog(case_id=c.id, event="given"))
            s.add(AuditLog(case_id=c.id, actor="student", action="consent_given", detail={}))
            return c.id

    def get_case(self, case_id: str) -> Case | None:
        with self.session() as s:
            c = s.get(Case, case_id)
            if c is not None:
                _ = list(c.turns), list(c.records)  # eager-load for detached use
            return c

    def update_case(self, case_id: str, **fields: Any) -> None:
        with self.session() as s:
            c = s.get(Case, case_id)
            for k, v in fields.items():
                setattr(c, k, v)

    def list_cases(self, statuses: tuple[str, ...] | None = None, source: str | None = "live") -> list[Case]:
        with self.session() as s:
            q = select(Case)
            if statuses:
                q = q.where(Case.status.in_(statuses))
            if source:
                q = q.where(Case.source == source)
            return list(s.scalars(q.order_by(Case.created_at.desc())))

    # ---------- turns ----------
    def add_turn(self, case_id: str, role: str, text_redacted: str, meta: dict | None = None) -> int:
        with self.session() as s:
            n = len(s.scalars(select(Turn.id).where(Turn.case_id == case_id)).all())
            s.add(Turn(case_id=case_id, idx=n, role=role, text_redacted=text_redacted, meta=meta or {}))
            return n

    def get_turns(self, case_id: str) -> list[Turn]:
        with self.session() as s:
            return list(s.scalars(select(Turn).where(Turn.case_id == case_id).order_by(Turn.idx)))

    # ---------- records ----------
    def add_record(self, case_id: str, record: dict, verification: dict, created_by: str = "ai") -> int:
        with self.session() as s:
            n = len(s.scalars(select(Record.id).where(Record.case_id == case_id)).all())
            r = Record(case_id=case_id, version=n + 1, record_json=record, verification_json=verification,
                       created_by=created_by)
            s.add(r)
            s.flush()
            return r.version

    def latest_record(self, case_id: str) -> Record | None:
        with self.session() as s:
            return s.scalars(select(Record).where(Record.case_id == case_id).order_by(Record.version.desc())).first()

    def confirm_latest_record(self, case_id: str) -> None:
        with self.session() as s:
            r = s.scalars(select(Record).where(Record.case_id == case_id).order_by(Record.version.desc())).first()
            if r:
                r.student_confirmed = True

    # ---------- escalations / audit ----------
    def add_escalation(self, case_id: str, route: str, reasons: list[str]) -> None:
        with self.session() as s:
            s.add(Escalation(case_id=case_id, route=route, reasons=reasons))

    def escalations(self, case_id: str) -> list[Escalation]:
        with self.session() as s:
            return list(s.scalars(select(Escalation).where(Escalation.case_id == case_id)))

    def acknowledge_escalations(self, case_id: str, reviewer: str) -> None:
        with self.session() as s:
            for e in s.scalars(select(Escalation).where(Escalation.case_id == case_id, Escalation.acknowledged_at.is_(None))):
                e.acknowledged_by, e.acknowledged_at = reviewer, utcnow()

    def audit(self, case_id: str | None, actor: str, action: str, detail: dict | None = None) -> None:
        with self.session() as s:
            s.add(AuditLog(case_id=case_id, actor=actor, action=action, detail=detail or {}))

    def audit_log(self, case_id: str) -> list[AuditLog]:
        with self.session() as s:
            return list(s.scalars(select(AuditLog).where(AuditLog.case_id == case_id).order_by(AuditLog.at)))

    # ---------- consent, deletion, retention ----------
    def delete_case_data(self, case_id: str, actor: str = "student") -> None:
        """DPDP-style erasure: remove transcript, records and escalations; keep a minimal audit trace."""
        with self.session() as s:
            c = s.get(Case, case_id)
            if c is not None:
                s.delete(c)
            s.add(ConsentLog(case_id=case_id, event="deleted"))
            s.add(AuditLog(case_id=case_id, actor=actor, action="data_deleted", detail={}))

    def purge_expired(self, retention_days: int) -> int:
        cutoff = utcnow() - timedelta(days=retention_days)
        with self.session() as s:
            ids = list(s.scalars(select(Case.id).where(Case.status == "closed", Case.closed_at < cutoff)))
            for cid in ids:
                s.delete(s.get(Case, cid))
                s.add(AuditLog(case_id=cid, actor="system", action="retention_purge", detail={"days": retention_days}))
            return len(ids)

    def consent_events(self, case_id: str) -> list[ConsentLog]:
        with self.session() as s:
            return list(s.scalars(select(ConsentLog).where(ConsentLog.case_id == case_id).order_by(ConsentLog.at)))

    # ---------- admin views ----------
    def recent_audit(self, limit: int = 200) -> list[AuditLog]:
        with self.session() as s:
            return list(s.scalars(select(AuditLog).order_by(AuditLog.at.desc()).limit(limit)))

    def unacknowledged_alerts(self) -> int:
        with self.session() as s:
            q = select(Escalation.id).join(Case, Case.id == Escalation.case_id).where(
                Escalation.acknowledged_at.is_(None), Escalation.route == "URGENT_ALERT", Case.source == "live")
            return len(s.scalars(q).all())

    def delete_cases_by_ref(self, student_ref: str, actor: str = "admin") -> int:
        """Remove every case with this student_ref (used to clear demo data)."""
        with self.session() as s:
            ids = list(s.scalars(select(Case.id).where(Case.student_ref == student_ref)))
            for cid in ids:
                s.delete(s.get(Case, cid))
                s.add(AuditLog(case_id=cid, actor=actor, action="demo_case_removed", detail={}))
            return len(ids)

    # ---------- precedents ----------
    def precedent_count(self, embed_model: str) -> int:
        with self.session() as s:
            return len(s.scalars(select(Precedent.id).where(Precedent.embed_model == embed_model)).all())

    def replace_precedents(self, rows: list[tuple[str, str, bytes]], embed_model: str) -> None:
        with self.session() as s:
            s.execute(delete(Precedent).where(Precedent.embed_model == embed_model))
            for text, label, emb in rows:
                s.add(Precedent(text_redacted=text, label=label, embedding=emb, embed_model=embed_model))

    def load_precedents(self, embed_model: str) -> list[Precedent]:
        with self.session() as s:
            return list(s.scalars(select(Precedent).where(Precedent.embed_model == embed_model)))

    # ---------- rubric ----------
    def add_rating(self, run_id: str, item_id: str, rater: str, scores: dict, comment: str | None) -> None:
        with self.session() as s:
            s.add(RubricRating(run_id=run_id, item_id=item_id, rater=rater, scores=scores, comment=comment))

    def ratings(self, run_id: str) -> list[RubricRating]:
        with self.session() as s:
            return list(s.scalars(select(RubricRating).where(RubricRating.run_id == run_id)))

    # ---------- leakage inspection (used by the evaluation) ----------
    def dump_case_text(self, case_id: str) -> str:
        """Every stored string tied to a case, for privacy-leakage checks."""
        with self.session() as s:
            parts: list[str] = []
            for t in s.scalars(select(Turn).where(Turn.case_id == case_id)):
                parts += [t.text_redacted, json.dumps(t.meta, ensure_ascii=False)]
            for r in s.scalars(select(Record).where(Record.case_id == case_id)):
                parts += [json.dumps(r.record_json, ensure_ascii=False), json.dumps(r.verification_json, ensure_ascii=False)]
            for a in s.scalars(select(AuditLog).where(AuditLog.case_id == case_id)):
                parts.append(json.dumps(a.detail, ensure_ascii=False))
            for e in s.scalars(select(Escalation).where(Escalation.case_id == case_id)):
                parts.append(json.dumps(e.reasons, ensure_ascii=False))
            return "\n".join(parts)


def mysql_schema_sql() -> str:
    """Render the MySQL 8 DDL for every table (used to write db/schema.sql)."""
    from sqlalchemy.dialects import mysql
    from sqlalchemy.schema import CreateIndex, CreateTable

    out = []
    for table in Base.metadata.sorted_tables:
        out.append(str(CreateTable(table).compile(dialect=mysql.dialect())).strip() + " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
        for idx in table.indexes:
            out.append(str(CreateIndex(idx).compile(dialect=mysql.dialect())).strip() + ";")
    return "\n\n".join(out) + "\n"
