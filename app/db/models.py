from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, Text, desc, func
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Region(Base):
    __tablename__ = "regions"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)


class Candidate(Base):
    __tablename__ = "candidates"

    # Native postgres enum values. Duplicated from app.domain.enums.CandidateStatus
    # rather than imported: db imports nothing from other app packages, same as domain.
    STATUSES = ("active", "screening", "interviewing", "withdrawn")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # No unique constraint: the source file has one legacy id shared by two people.
    legacy_candidate_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    region_code: Mapped[str] = mapped_column(ForeignKey("regions.code"), nullable=False)
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(PGEnum(*STATUSES, name="candidate_status"), nullable=False)
    applied_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_candidates_region_code", "region_code"),
        Index("ix_candidates_status", "status"),
        Index("ix_candidates_region_applied_date_id", "region_code", desc("applied_date"), "id"),
    )


class Recruiter(Base):
    __tablename__ = "recruiters"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RecruiterRegion(Base):
    __tablename__ = "recruiter_regions"

    recruiter_id: Mapped[str] = mapped_column(ForeignKey("recruiters.id"), primary_key=True)
    region_code: Mapped[str] = mapped_column(ForeignKey("regions.code"), primary_key=True)


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    imported_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    merged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ImportRejection(Base):
    __tablename__ = "import_rejections"

    # Schema does not name a PK for this table, a surrogate id is added here.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    raw_row: Mapped[dict] = mapped_column(JSONB, nullable=False)
