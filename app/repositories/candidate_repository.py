from dataclasses import dataclass

from sqlalchemy import Select, func, literal_column, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Candidate
from app.domain.enums import CandidateStatus
from app.domain.models import CandidateIn
from app.domain.scope import RecruiterScope


@dataclass(frozen=True)
class CandidatePage:
    items: list[Candidate]
    total: int


class CandidateRepository:
    DEFAULT_LIMIT = 50
    MAX_LIMIT = 200

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_candidates(
        self,
        scope: RecruiterScope,
        search: str | None = None,
        status: CandidateStatus | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> CandidatePage:
        limit = max(1, min(limit, self.MAX_LIMIT))
        offset = max(0, offset)

        statement = self._scoped_statement(scope)
        if status is not None:
            statement = statement.where(Candidate.status == status.value)
        if search:
            statement = statement.where(self._search_predicate(search))

        total = await self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0

        paged = statement.order_by(
            Candidate.region_code, Candidate.applied_date.desc(), Candidate.id
        ).limit(limit).offset(offset)
        items = list((await self.session.scalars(paged)).all())

        return CandidatePage(items=items, total=total)

    async def get_by_id(self, scope: RecruiterScope, candidate_id: int) -> Candidate | None:
        statement = self._scoped_statement(scope).where(Candidate.id == candidate_id)
        return await self.session.scalar(statement)

    async def bulk_upsert(self, candidates: list[CandidateIn]) -> dict[str, bool]:
        # A write, not a read: intentionally takes no scope. One statement,
        # never a per-row insert in a loop.
        if not candidates:
            return {}

        statement = pg_insert(Candidate).values([self._to_row(candidate) for candidate in candidates])
        statement = statement.on_conflict_do_update(
            index_elements=[Candidate.email],
            set_={
                "legacy_candidate_id": statement.excluded.legacy_candidate_id,
                "full_name": statement.excluded.full_name,
                "region_code": statement.excluded.region_code,
                "role": statement.excluded.role,
                "status": statement.excluded.status,
                "applied_date": statement.excluded.applied_date,
                "salary": statement.excluded.salary,
                "updated_at": func.now(),
            },
        ).returning(Candidate.email, (literal_column("xmax") == 0).label("inserted"))

        result = await self.session.execute(statement)
        return {row.email: row.inserted for row in result}

    @staticmethod
    def _to_row(candidate: CandidateIn) -> dict[str, object]:
        return {
            "legacy_candidate_id": candidate.legacy_candidate_id,
            "email": candidate.email,
            "full_name": candidate.full_name,
            "region_code": candidate.region_code.value,
            "role": candidate.role,
            "status": candidate.status.value,
            "applied_date": candidate.applied_date,
            "salary": candidate.salary,
        }

    def _scoped_statement(self, scope: RecruiterScope) -> Select:
        # The only place the region predicate is applied. There is no unscoped
        # read method on this class for a caller to reach for instead.
        statement = select(Candidate)
        if not scope.is_admin:
            region_values = [region.value for region in scope.regions]
            statement = statement.where(Candidate.region_code.in_(region_values))
        return statement

    @staticmethod
    def _search_predicate(search: str):
        pattern = f"%{CandidateRepository._escape_like(search)}%"
        return or_(
            Candidate.full_name.ilike(pattern, escape="\\"),
            Candidate.email.ilike(pattern, escape="\\"),
        )

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
