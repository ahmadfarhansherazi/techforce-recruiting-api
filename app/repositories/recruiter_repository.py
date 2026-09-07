from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Recruiter, RecruiterRegion
from app.domain.enums import Region
from app.domain.errors import RecruiterNotFound
from app.domain.scope import RecruiterScope


class RecruiterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_scope(self, recruiter_id: str) -> RecruiterScope:
        recruiter = await self.session.get(Recruiter, recruiter_id)
        if recruiter is None:
            raise RecruiterNotFound(recruiter_id)

        regions = frozenset() if recruiter.is_admin else await self._load_regions(recruiter_id)
        return RecruiterScope(recruiter_id=recruiter.id, is_admin=recruiter.is_admin, regions=regions)

    async def _load_regions(self, recruiter_id: str) -> frozenset[Region]:
        result = await self.session.execute(
            select(RecruiterRegion.region_code).where(RecruiterRegion.recruiter_id == recruiter_id)
        )
        return frozenset(Region(code) for code in result.scalars())
