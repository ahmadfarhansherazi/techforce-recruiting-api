from app.domain.dedup import DeduplicationEngine
from app.domain.models import CandidateIn


class TestDeduplicationEngine:
    BASE_KWARGS = {
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

    def _make(self, **overrides: object) -> CandidateIn:
        return CandidateIn(**(self.BASE_KWARGS | overrides))

    def test_rule_1_byte_identical_rows_collapse_silently(self) -> None:
        # C-1004 / Daniel Okafor appears twice in the source file as a
        # literal byte-for-byte duplicate row (row 4 and row 31).
        first = CandidateIn(
            legacy_candidate_id="C-1004",
            first_name="Daniel",
            last_name="Okafor",
            email="daniel.okafor@gmail.com",
            region_code="US-MW",
            role="Full-Stack Engineer",
            status="Active",
            applied_date="2026-05-19",
            salary="97,500",
        )
        second = CandidateIn(
            legacy_candidate_id="C-1004",
            first_name="Daniel",
            last_name="Okafor",
            email="daniel.okafor@gmail.com",
            region_code="US-MW",
            role="Full-Stack Engineer",
            status="Active",
            applied_date="2026-05-19",
            salary="97,500",
        )

        result = DeduplicationEngine().deduplicate([(4, first), (31, second)])

        assert result.collapsed == 1
        assert result.merged == 0
        assert len(result.records) == 1
        # The first occurrence survives, its row number is kept as-is.
        assert result.records[0].row_number == 4

    def test_rule_2_same_email_merges_non_null_over_null_and_later_wins_ties(self) -> None:
        earlier = self._make(role="Engineer", salary=None, legacy_candidate_id="C-100")
        later = self._make(
            role=None,
            salary="100000",
            legacy_candidate_id="C-200",
            email="  Alicia.Trent@Gmail.com ",
        )

        result = DeduplicationEngine().deduplicate([(5, earlier), (12, later)])

        assert result.collapsed == 0
        assert result.merged == 1
        assert len(result.records) == 1

        merged = result.records[0].candidate
        assert merged.role == "Engineer"  # non-null from the earlier row beats later's null
        assert merged.salary == 100000  # non-null from the later row beats earlier's null
        assert merged.legacy_candidate_id == "C-200"  # both non-null, later row wins
        assert result.records[0].row_number == 12  # last contributing row

    def test_rule_3_shared_legacy_id_different_emails_are_kept_distinct(self) -> None:
        # The real C-1010 collision: Sofia Cardenas and Becca Storm share a
        # legacy_candidate_id but are two different people.
        sofia = CandidateIn(
            legacy_candidate_id="C-1010",
            first_name="Sofia",
            last_name="Cardenas",
            email="sofia.cardenas@hotmail.com",
            region_code="CO-BOG",
            role="Backend Engineer",
            status="Screening",
            applied_date="2026-05-27",
            salary="70000",
        )
        becca = CandidateIn(
            legacy_candidate_id="C-1010",
            first_name="Becca",
            last_name="Storm",
            email="becca.storm@gmail.com",
            region_code="US-MW",
            role="QA Engineer",
            status="Active",
            applied_date="2026-07-14",
            salary="74000",
        )

        result = DeduplicationEngine().deduplicate([(10, sofia), (52, becca)])

        assert result.collapsed == 0
        assert result.merged == 0
        assert len(result.records) == 2
        emails = {record.candidate.email for record in result.records}
        assert emails == {"sofia.cardenas@hotmail.com", "becca.storm@gmail.com"}
        row_numbers = {record.row_number for record in result.records}
        assert row_numbers == {10, 52}

    def test_rules_2_and_3_do_not_interfere_in_the_same_batch(self) -> None:
        # Same legacy id, different emails (rule 3, C-1010 collision).
        sofia = CandidateIn(
            legacy_candidate_id="C-1010",
            first_name="Sofia",
            last_name="Cardenas",
            email="sofia.cardenas@hotmail.com",
            region_code="CO-BOG",
            role="Backend Engineer",
            status="Screening",
            applied_date="2026-05-27",
            salary="70000",
        )
        becca = CandidateIn(
            legacy_candidate_id="C-1010",
            first_name="Becca",
            last_name="Storm",
            email="becca.storm@gmail.com",
            region_code="US-MW",
            role="QA Engineer",
            status="Active",
            applied_date="2026-07-14",
            salary="74000",
        )
        # Same email, differing details (rule 2), unrelated legacy ids.
        alicia_first = self._make(legacy_candidate_id="C-1001", role=None)
        alicia_again = self._make(
            legacy_candidate_id="C-1031",
            role="Full-Stack Engineer",
            email="  Alicia.Trent@Gmail.com ",
        )

        result = DeduplicationEngine().deduplicate(
            [(10, sofia), (52, becca), (1, alicia_first), (32, alicia_again)]
        )

        assert result.collapsed == 0
        assert result.merged == 1  # only the Alicia pair merged
        assert len(result.records) == 3  # sofia, becca, merged alicia

        by_email = {record.candidate.email: record for record in result.records}
        assert set(by_email) == {
            "sofia.cardenas@hotmail.com",
            "becca.storm@gmail.com",
            "alicia.trent@gmail.com",
        }
        assert by_email["sofia.cardenas@hotmail.com"].candidate.legacy_candidate_id == "C-1010"
        assert by_email["becca.storm@gmail.com"].candidate.legacy_candidate_id == "C-1010"
        assert by_email["alicia.trent@gmail.com"].candidate.role == "Full-Stack Engineer"
