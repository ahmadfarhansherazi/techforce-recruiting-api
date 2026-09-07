from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.domain.enums import CandidateStatus, Region
from app.domain.errors import NormalizationError
from app.domain.normalizers import (
    DateNormalizer,
    EmailNormalizer,
    RegionNormalizer,
    SalaryNormalizer,
    StatusNormalizer,
)


class CandidateIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    legacy_candidate_id: str | None = None
    first_name: str
    last_name: str
    email: str
    region_code: Region
    role: str | None = None
    status: CandidateStatus
    applied_date: date | None = None
    salary: Decimal | None = None

    @field_validator("legacy_candidate_id", "role", mode="before")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise NormalizationError("name is required")
        return cleaned

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return EmailNormalizer.normalize(value)

    @field_validator("region_code", mode="before")
    @classmethod
    def _normalize_region(cls, value: str) -> Region:
        return RegionNormalizer.normalize(value)

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: str) -> CandidateStatus:
        return StatusNormalizer.normalize(value)

    @field_validator("applied_date", mode="before")
    @classmethod
    def _normalize_applied_date(cls, value: str | date | None) -> date | None:
        if value is None or isinstance(value, date):
            return value
        return DateNormalizer.normalize(value)

    @field_validator("salary", mode="before")
    @classmethod
    def _normalize_salary(cls, value: str | Decimal | None) -> Decimal | None:
        if value is None or isinstance(value, Decimal):
            return value
        return SalaryNormalizer.normalize(value)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class RawRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    row_number: int = Field(ge=1)
    raw: dict[str, str | None]
