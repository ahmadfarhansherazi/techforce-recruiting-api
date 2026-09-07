from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.enums import CandidateStatus, Region
from app.domain.models import CandidateIn


class TestCandidateIn:
    VALID_KWARGS = {
        "legacy_candidate_id": "C-1001",
        "first_name": "Alicia",
        "last_name": "Trent",
        "email": "alicia.trent@gmail.com",
        "region_code": "US-MW",
        "role": "Full-Stack Engineer",
        "status": "Active",
        "applied_date": "2026-05-14",
        "salary": "$95,000",
    }

    def test_happy_path_normalizes_every_field(self) -> None:
        candidate = CandidateIn(**self.VALID_KWARGS)

        assert candidate.legacy_candidate_id == "C-1001"
        assert candidate.email == "alicia.trent@gmail.com"
        assert candidate.region_code is Region.US_MW
        assert candidate.status is CandidateStatus.ACTIVE
        assert candidate.applied_date == date(2026, 5, 14)
        assert candidate.salary == Decimal("95000")
        assert candidate.full_name == "Alicia Trent"

    def test_optional_fields_default_to_none(self) -> None:
        kwargs = self.VALID_KWARGS | {
            "legacy_candidate_id": None,
            "role": None,
            "applied_date": None,
            "salary": None,
        }
        candidate = CandidateIn(**kwargs)

        assert candidate.legacy_candidate_id is None
        assert candidate.role is None
        assert candidate.applied_date is None
        assert candidate.salary is None

    def test_sql_fragment_in_name_passes_through_as_literal_string(self) -> None:
        kwargs = self.VALID_KWARGS | {"last_name": "O'Connor'); DROP TABLE candidates;--"}
        candidate = CandidateIn(**kwargs)

        assert candidate.last_name == "O'Connor'); DROP TABLE candidates;--"
        assert candidate.full_name == "Alicia O'Connor'); DROP TABLE candidates;--"

    def test_invalid_email_raises_validation_error_on_that_field(self) -> None:
        kwargs = self.VALID_KWARGS | {"email": "not-an-email"}
        with pytest.raises(ValidationError) as excinfo:
            CandidateIn(**kwargs)

        errors = excinfo.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("email",)

    def test_multiple_invalid_fields_aggregate_into_one_error(self) -> None:
        kwargs = self.VALID_KWARGS | {"region_code": "ZZ-99", "status": "on hold"}
        with pytest.raises(ValidationError) as excinfo:
            CandidateIn(**kwargs)

        locs = {error["loc"] for error in excinfo.value.errors()}
        assert locs == {("region_code",), ("status",)}

    @pytest.mark.parametrize("field", ["first_name", "last_name"])
    def test_blank_name_is_rejected(self, field: str) -> None:
        kwargs = self.VALID_KWARGS | {field: "   "}
        with pytest.raises(ValidationError):
            CandidateIn(**kwargs)
