from datetime import date
from decimal import Decimal

import pytest

from app.domain.enums import CandidateStatus, Region
from app.domain.errors import NormalizationError
from app.domain.normalizers import (
    DateNormalizer,
    EmailNormalizer,
    RegionNormalizer,
    SalaryNormalizer,
    StatusNormalizer,
)


class TestEmailNormalizer:
    def test_happy_path(self) -> None:
        assert EmailNormalizer.normalize("alicia.trent@gmail.com") == "alicia.trent@gmail.com"

    def test_case_and_whitespace_variants_collide(self) -> None:
        assert EmailNormalizer.normalize("alicia.trent@gmail.com") == EmailNormalizer.normalize(
            "  Alicia.Trent@Gmail.com "
        )

    def test_plus_addressing_preserved(self) -> None:
        assert EmailNormalizer.normalize("Alicia.Trent+jobs@Gmail.com") == "alicia.trent+jobs@gmail.com"

    def test_dots_in_local_part_preserved(self) -> None:
        assert EmailNormalizer.normalize("m.bellamy@outlook.com") == "m.bellamy@outlook.com"

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "   ",
            "marcus.reed[at]gmail.com",
            "tina.holloway.gmail.com",
            "a@b@c.com",
            "user@nodot",
            "@gmail.com",
            "user@",
        ],
    )
    def test_rejects_invalid_addresses(self, value: str) -> None:
        with pytest.raises(NormalizationError):
            EmailNormalizer.normalize(value)


class TestRegionNormalizer:
    def test_happy_path(self) -> None:
        assert RegionNormalizer.normalize("US-MW") is Region.US_MW

    @pytest.mark.parametrize("raw,expected", list(RegionNormalizer._ALIASES.items()))
    def test_every_alias_maps_correctly(self, raw: str, expected: Region) -> None:
        assert RegionNormalizer.normalize(raw) is expected

    def test_lowercase_variant_normalizes(self) -> None:
        assert RegionNormalizer.normalize("us-mw") is Region.US_MW

    def test_padded_variant_normalizes(self) -> None:
        assert RegionNormalizer.normalize(" CO-BOG ") is Region.CO_BOG

    @pytest.mark.parametrize("value", ["ZZ-99", "US-MIDWEST", "USMW", "", "   "])
    def test_unrecognised_region_is_rejected_not_guessed(self, value: str) -> None:
        with pytest.raises(NormalizationError):
            RegionNormalizer.normalize(value)


class TestStatusNormalizer:
    def test_happy_path(self) -> None:
        assert StatusNormalizer.normalize("Active") is CandidateStatus.ACTIVE

    @pytest.mark.parametrize("raw,expected", list(StatusNormalizer._ALIASES.items()))
    def test_every_alias_maps_correctly(self, raw: str, expected: CandidateStatus) -> None:
        assert StatusNormalizer.normalize(raw) is expected

    def test_misspelling_maps_to_active(self) -> None:
        assert StatusNormalizer.normalize("actve") is CandidateStatus.ACTIVE

    @pytest.mark.parametrize("value", ["on hold", "", "unknown", "pending"])
    def test_rejects_status_outside_enum(self, value: str) -> None:
        with pytest.raises(NormalizationError):
            StatusNormalizer.normalize(value)


class TestDateNormalizer:
    TODAY = date(2026, 9, 7)

    def test_iso_happy_path(self) -> None:
        assert DateNormalizer.normalize("2026-05-14", today=self.TODAY) == date(2026, 5, 14)

    def test_slash_format_unambiguous(self) -> None:
        assert DateNormalizer.normalize("06/30/2026", today=self.TODAY) == date(2026, 6, 30)

    def test_text_month_format(self) -> None:
        assert DateNormalizer.normalize("14-May-2026", today=self.TODAY) == date(2026, 5, 14)

    def test_blank_returns_none(self) -> None:
        assert DateNormalizer.normalize("", today=self.TODAY) is None

    def test_calendar_impossible_date_rejected(self) -> None:
        with pytest.raises(NormalizationError):
            DateNormalizer.normalize("2026-02-30", today=self.TODAY)

    def test_ambiguous_dd_mm_vs_mm_dd_rejected(self) -> None:
        with pytest.raises(NormalizationError):
            DateNormalizer.normalize("05/07/2026", today=self.TODAY)

    def test_same_day_and_month_is_not_ambiguous(self) -> None:
        assert DateNormalizer.normalize("05/05/2026", today=self.TODAY) == date(2026, 5, 5)

    def test_future_date_rejected(self) -> None:
        with pytest.raises(NormalizationError):
            DateNormalizer.normalize("2026-12-31", today=self.TODAY)

    def test_unrecognized_format_rejected(self) -> None:
        with pytest.raises(NormalizationError):
            DateNormalizer.normalize("2026.05.14", today=self.TODAY)


class TestSalaryNormalizer:
    def test_happy_path_plain_integer(self) -> None:
        assert SalaryNormalizer.normalize("88000") == Decimal("88000")

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("$95,000", Decimal("95000")),
            ("97,500", Decimal("97500")),
            ("$102,000", Decimal("102000")),
        ],
    )
    def test_strips_currency_symbol_and_thousands_separator(self, raw: str, expected: Decimal) -> None:
        assert SalaryNormalizer.normalize(raw) == expected

    @pytest.mark.parametrize("raw", ["70000-90000", "70000 to 90000", "$70,000-$90,000"])
    def test_range_takes_lower_bound(self, raw: str) -> None:
        assert SalaryNormalizer.normalize(raw) == Decimal("70000")

    @pytest.mark.parametrize("raw", ["negotiable", "85k", "n/a"])
    def test_unparseable_becomes_none(self, raw: str) -> None:
        assert SalaryNormalizer.normalize(raw) is None

    def test_blank_becomes_none(self) -> None:
        assert SalaryNormalizer.normalize("") is None

    def test_blank_and_unparseable_are_indistinguishable_none(self) -> None:
        # The design carries no sentinel distinguishing "missing" from
        # "present but garbage": both collapse to the same None.
        assert SalaryNormalizer.normalize("") is SalaryNormalizer.normalize("negotiable") is None

    @pytest.mark.parametrize("raw", ["0", "-500"])
    def test_non_positive_amount_becomes_none(self, raw: str) -> None:
        assert SalaryNormalizer.normalize(raw) is None
