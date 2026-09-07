from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

from app.domain.errors import ImportFileError
from app.services.import_service import CandidateImportService, ImportReport


class CandidatesRouter:
    def __init__(self) -> None:
        self.router = APIRouter(prefix="/api/v1/candidates")
        self.router.add_api_route(
            "/import", self.import_candidates, methods=["POST"], response_model=ImportReport
        )

    async def import_candidates(self, request: Request, file: UploadFile = File(...)) -> ImportReport:
        content = await file.read()
        async with request.app.state.database.session() as session:
            service = CandidateImportService(session)
            try:
                return await service.import_csv(file.filename or "upload.csv", content)
            except ImportFileError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
