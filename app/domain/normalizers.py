import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.domain.enums import CandidateStatus, Region
from app.domain.errors import NormalizationError


class EmailNormalizer:
    _PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    @classmethod
    def normalize(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise NormalizationError("email is required")
        if cleaned.count("@") != 1 or not cls._PATTERN.match(cleaned):
            raise NormalizationError(f"'{value.strip()}' is not a valid email address")
        return cleaned


class RegionNormalizer:
    # Explicit aliases, one entry per raw value actually seen in the source file.
    # "USW" is the missing-hyphen typo for US-W. "ZZ-99" has no target and is
    # deliberately absent, so it falls through to rejection.
    _ALIASES: dict[str, Region] = {
        "US-MW": Region.US_MW,
        "US-NE": Region.US_NE,
        "US-SE": Region.US_SE,
        "US-W": Region.US_W,
        "PH-MNL": Region.PH_MNL,
        "CO-BOG": Region.CO_BOG,
        "USW": Region.US_W,
    }

    @classmethod
    def normalize(cls, value: str) -> Region:
        cleaned = value.strip().upper()
        if not cleaned:
            raise NormalizationError("region is required")
        try:
            return cls._ALIASES[cleaned]
        except KeyError:
            raise NormalizationError(f"unrecognized region code '{value.strip()}'") from None


class StatusNormalizer:
    # "ACTVE" is the misspelling seen in the source file. "on hold" is
    # deliberately absent: the source file's own note calls it out as a
    # status outside the enum, so it must be rejected, not accepted.
    _ALIASES: dict[str, CandidateStatus] = {
        "ACTIVE": CandidateStatus.ACTIVE,
        "ACTVE": CandidateStatus.ACTIVE,
        "SCREENING": CandidateStatus.SCREENING,
        "INTERVIEWING": CandidateStatus.INTERVIEWING,
        "WITHDRAWN": CandidateStatus.WITHDRAWN,
    }

    @classmethod
    def normalize(cls, value: str) -> CandidateStatus:
        cleaned = value.strip().upper()
        try:
            return cls._ALIASES[cleaned]
        except KeyError:
            raise NormalizationError(f"unrecognized status '{value.strip()}'") from None


class DateNormalizer:
    _ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    _SLASH_PATTERN = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
    _TEXT_PATTERN = re.compile(r"^\d{1,2}-[A-Za-z]{3,9}-\d{4}$")
    _TEXT_FORMAT = "%d-%b-%Y"

    @classmethod
    def normalize(cls, value: str, today: date | None = None) -> date | None:
        cleaned = value.strip()
        if not cleaned:
            return None
        parsed = cls._parse_iso(cleaned) or cls._parse_slash(cleaned) or cls._parse_text(cleaned)
        if parsed is None:
            raise NormalizationError(f"unrecognized date format '{cleaned}'")
        if parsed > (today or date.today()):
            raise NormalizationError(f"'{cleaned}' is in the future")
        return parsed

    @classmethod
    def _parse_iso(cls, cleaned: str) -> date | None:
        if not cls._ISO_PATTERN.match(cleaned):
            return None
        try:
            return date.fromisoformat(cleaned)
        except ValueError:
            raise NormalizationError(f"'{cleaned}' is not a real calendar date") from None

    @classmethod
    def _parse_slash(cls, cleaned: str) -> date | None:
        match = cls._SLASH_PATTERN.match(cleaned)
        if not match:
            return None
        first, second, year = (int(group) for group in match.groups())
        month, day = cls._resolve_month_day(first, second, cleaned)
        try:
            return date(year, month, day)
        except ValueError:
            raise NormalizationError(f"'{cleaned}' is not a real calendar date") from None

    @classmethod
    def _parse_text(cls, cleaned: str) -> date | None:
        if not cls._TEXT_PATTERN.match(cleaned):
            return None
        try:
            return datetime.strptime(cleaned, cls._TEXT_FORMAT).date()
        except ValueError:
            raise NormalizationError(f"'{cleaned}' is not a real calendar date") from None

    @staticmethod
    def _resolve_month_day(first: int, second: int, raw: str) -> tuple[int, int]:
        first_could_be_month = first <= 12
        second_could_be_month = second <= 12
        if first_could_be_month and second_could_be_month:
            if first != second:
                raise NormalizationError(f"'{raw}' is ambiguous between DD/MM and MM/DD")
            return first, second
        if second_could_be_month:
            return second, first
        if first_could_be_month:
            return first, second
        raise NormalizationError(f"'{raw}' has no valid month/day reading")


class SalaryNormalizer:
    _CURRENCY_CHARS = str.maketrans("", "", "$,")
    _RANGE_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:-|to)\s*\d+(?:\.\d+)?$")
    _NUMBER_PATTERN = re.compile(r"^\d+(?:\.\d+)?$")

    @classmethod
    def normalize(cls, value: str) -> Decimal | None:
        cleaned = value.strip()
        if not cleaned:
            return None
        stripped = cleaned.translate(cls._CURRENCY_CHARS).strip()
        range_match = cls._RANGE_PATTERN.match(stripped)
        candidate = range_match.group(1) if range_match else stripped
        if not cls._NUMBER_PATTERN.match(candidate):
            return None
        try:
            amount = Decimal(candidate)
        except InvalidOperation:
            return None
        return amount if amount > 0 else None
