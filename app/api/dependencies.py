from fastapi import Header, HTTPException, Request, status

from app.domain.errors import RecruiterNotFound
from app.domain.scope import RecruiterScope
from app.repositories.recruiter_repository import RecruiterRepository


class RecruiterScopeDependency:
    async def __call__(
        self,
        request: Request,
        x_recruiter_id: str = Header(..., alias="X-Recruiter-Id"),
    ) -> RecruiterScope:
        async with request.app.state.database.session() as session:
            try:
                return await RecruiterRepository(session).get_scope(x_recruiter_id)
            except RecruiterNotFound as exc:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


get_recruiter_scope = RecruiterScopeDependency()
