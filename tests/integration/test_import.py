from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Candidate, ImportRejection


class TestImport:
    # Hermetic fixture CSV, not the real Data/candidates_import.csv which is
    # gitignored and must not be a test dependency.
    CSV_CONTENT = (
        b"candidate_id,first_name,last_name,email,region_code,desired_role,salary_expectation,applied_date,status\r\n"
        b"C-9001,Jamie,Rivera,jamie.rivera@example.com,US-MW,Backend Engineer,,2026-05-01,Active\r\n"
        b"C-9002,Jamie,Rivera,jamie.rivera@example.com,US-MW,,95000,2026-05-02,Active\r\n"
        b"C-9003,Taylor,Kim,not-an-email,US-MW,QA Engineer,80000,2026-05-03,Active\r\n"
        b"C-9004,Robert,O'Brien'); DROP TABLE candidates;--,robert.injection@example.com,US-NE,Full-Stack Engineer,90000,2026-05-04,Active\r\n"
    )

    async def _import(self, client: AsyncClient) -> dict:
        files = {"file": ("candidates.csv", self.CSV_CONTENT, "text/csv")}
        response = await client.post("/api/v1/candidates/import", files=files)
        assert response.status_code == 200
        return response.json()

    async def test_same_email_different_details_merge_per_rule(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        report = await self._import(client)
        assert report["merged"] >= 1

        candidate = (
            await db_session.execute(select(Candidate).where(Candidate.email == "jamie.rivera@example.com"))
        ).scalar_one()

        assert candidate.role == "Backend Engineer"  # non-null from row 1 beats row 2's null
        assert candidate.salary == Decimal("95000.00")  # non-null from row 2 beats row 1's null
        assert candidate.applied_date == date(2026, 5, 2)  # both non-null, later row (row 2) wins
        assert candidate.legacy_candidate_id == "C-9002"  # both non-null, later row (row 2) wins

    async def test_invalid_email_rejected_with_correct_row_number(self, client: AsyncClient) -> None:
        report = await self._import(client)
        rejected = {row["row"]: row["reason"] for row in report["rejected"]}

        assert 3 in rejected
        assert "email" in rejected[3]

    async def test_injection_rows_import_as_literal_text(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await self._import(client)

        candidate = (
            await db_session.execute(
                select(Candidate).where(Candidate.email == "robert.injection@example.com")
            )
        ).scalar_one()
        assert candidate.full_name == "Robert O'Brien'); DROP TABLE candidates;--"

        # The table was not dropped, it is still queryable.
        count = await db_session.scalar(select(func.count()).select_from(Candidate))
        assert count is not None and count > 0

    async def test_reimporting_same_file_yields_zero_imported(self, client: AsyncClient) -> None:
        first = await self._import(client)
        assert first["imported"] > 0

        second = await self._import(client)
        assert second["imported"] == 0
        assert second["merged"] > 0
        assert second["rejected"] == first["rejected"]

    async def test_rejected_row_persisted_with_raw_row(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await self._import(client)

        rejection = (
            await db_session.execute(select(ImportRejection).where(ImportRejection.row_number == 3))
        ).scalar_one()

        assert rejection.raw_row["candidate_id"] == "C-9003"
        assert rejection.raw_row["email"] == "not-an-email"
