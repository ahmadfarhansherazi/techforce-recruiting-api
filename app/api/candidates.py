from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel

from app.api.dependencies import get_recruiter_scope
from app.db.models import Candidate
from app.domain.enums import CandidateStatus, Region
from app.domain.errors import ImportFileError
from app.domain.scope import RecruiterScope
from app.repositories.candidate_repository import CandidateRepository
from app.services.import_service import CandidateImportService, ImportReport


class CandidateOut(BaseModel):
    # id is not in the brief's field list but is included, a list a UI can't
    # link into or key rows by is not usable.
    id: int
    name: str
    email: str
    region: Region
    role: str | None
    status: CandidateStatus
    applied_date: date | None

    @classmethod
    def from_candidate(cls, candidate: Candidate) -> "CandidateOut":
        return cls(
            id=candidate.id,
            name=candidate.full_name,
            email=candidate.email,
            region=Region(candidate.region_code),
            role=candidate.role,
            status=CandidateStatus(candidate.status),
            applied_date=candidate.applied_date,
        )


class CandidateListResponse(BaseModel):
    items: list[CandidateOut]
    total: int
    limit: int
    offset: int


class CandidatesRouter:
    def __init__(self) -> None:
        self.router = APIRouter(prefix="/api/v1/candidates")
        self.router.add_api_route(
            "/import", self.import_candidates, methods=["POST"], response_model=ImportReport
        )
        self.router.add_api_route(
            "", self.list_candidates, methods=["GET"], response_model=CandidateListResponse
        )
        self.router.add_api_route(
            "/{candidate_id}", self.get_candidate, methods=["GET"], response_model=CandidateOut
        )

    async def import_candidates(self, request: Request, file: UploadFile = File(...)) -> ImportReport:
        content = await file.read()
        async with request.app.state.database.session() as session:
            service = CandidateImportService(session)
            try:
                return await service.import_csv(file.filename or "upload.csv", content)
            except ImportFileError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    async def list_candidates(
        self,
        request: Request,
        scope: RecruiterScope = Depends(get_recruiter_scope),
        search: str | None = Query(default=None),
        status: CandidateStatus | None = Query(default=None),
        limit: int = Query(default=CandidateRepository.DEFAULT_LIMIT, ge=1, le=CandidateRepository.MAX_LIMIT),
        offset: int = Query(default=0, ge=0),
    ) -> CandidateListResponse:
        async with request.app.state.database.session() as session:
            page = await CandidateRepository(session).list_candidates(
                scope=scope, search=search, status=status, limit=limit, offset=offset
            )
        return CandidateListResponse(
            items=[CandidateOut.from_candidate(candidate) for candidate in page.items],
            total=page.total,
            limit=limit,
            offset=offset,
        )

    async def get_candidate(
        self,
        candidate_id: int,
        request: Request,
        scope: RecruiterScope = Depends(get_recruiter_scope),
    ) -> CandidateOut:
        async with request.app.state.database.session() as session:
            candidate = await CandidateRepository(session).get_by_id(scope, candidate_id)
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="candidate not found")
        return CandidateOut.from_candidate(candidate)
