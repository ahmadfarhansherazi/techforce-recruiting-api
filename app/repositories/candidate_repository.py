from dataclasses import dataclass

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Candidate
from app.domain.enums import CandidateStatus
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
