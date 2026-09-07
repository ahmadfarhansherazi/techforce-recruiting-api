from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Candidate


class TestRowLevelSecurity:
    # This class deliberately never touches CandidateRepository. The point
    # is that the database itself enforces the boundary, independent of
    # whether application code remembered to scope its query.

    async def _set_recruiter(self, session: AsyncSession, recruiter_id: str) -> None:
        await session.execute(
            text("SELECT set_config('app.recruiter_id', :recruiter_id, true)"),
            {"recruiter_id": recruiter_id},
        )

    async def test_unscoped_select_star_only_returns_in_scope_rows(
        self, db_session: AsyncSession, seeded_candidates: dict[str, Candidate]
    ) -> None:
        await self._set_recruiter(db_session, "R-SCOPED")  # assigned US-MW, US-NE

        rows = (await db_session.execute(text("SELECT * FROM candidates"))).mappings().all()

        assert {row["region_code"] for row in rows} <= {"US-MW", "US-NE"}
        emails = {row["email"] for row in rows}
        assert emails == {
            seeded_candidates["ada"].email,
            seeded_candidates["grace"].email,
            seeded_candidates["percent"].email,
            seeded_candidates["underscore"].email,
        }
        assert seeded_candidates["alan"].email not in emails  # PH-MNL, outside R-SCOPED

    async def test_unscoped_select_star_returns_everything_for_an_admin(
        self, db_session: AsyncSession, seeded_candidates: dict[str, Candidate]
    ) -> None:
        await self._set_recruiter(db_session, "R-ADMIN")

        rows = (await db_session.execute(text("SELECT email FROM candidates"))).all()

        assert {row.email for row in rows} == {c.email for c in seeded_candidates.values()}

    async def test_no_recruiter_context_set_returns_nothing(
        self, db_session: AsyncSession, seeded_candidates: dict[str, Candidate]
    ) -> None:
        # app.recruiter_id was never set on this transaction: fail closed,
        # not fail open.
        rows = (await db_session.execute(text("SELECT email FROM candidates"))).all()

        assert rows == []
