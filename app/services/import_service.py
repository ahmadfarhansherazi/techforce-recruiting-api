import csv
import io

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dedup import DeduplicationEngine
from app.domain.errors import ImportFileError
from app.domain.models import CandidateIn, RawRow
from app.repositories.candidate_repository import CandidateRepository
from app.repositories.import_repository import ImportRepository


class RejectedRow(BaseModel):
    row: int
    reason: str


class ImportReport(BaseModel):
    imported: int
    merged: int
    rejected: list[RejectedRow]


class CandidateImportService:
    # CSV column -> CandidateIn field. phone/source/notes are read but not
    # modeled, the candidates table has no columns for them.
    COLUMN_MAP = {
        "candidate_id": "legacy_candidate_id",
        "first_name": "first_name",
        "last_name": "last_name",
        "email": "email",
        "region_code": "region_code",
        "desired_role": "role",
        "salary_expectation": "salary",
        "applied_date": "applied_date",
        "status": "status",
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.candidates = CandidateRepository(session)
        self.imports = ImportRepository(session)

    async def import_csv(self, filename: str, content: bytes) -> ImportReport:
        rows = self._read_rows(content)
        survivors, rejections = self._validate_rows(rows)
        dedup_result = DeduplicationEngine().deduplicate(survivors)

        batch_id = await self.imports.create_batch(filename)
        inserted_by_email = await self.candidates.bulk_upsert(
            [record.candidate for record in dedup_result.records]
        )
        imported = sum(1 for was_inserted in inserted_by_email.values() if was_inserted)
        # A cross-batch conflict (email already existed from a prior import)
        # is a merge too, same as an in-file email collision.
        merged = dedup_result.merged + sum(1 for was_inserted in inserted_by_email.values() if not was_inserted)

        await self.imports.bulk_insert_rejections(batch_id, rejections)
        await self.imports.finish_batch(batch_id, imported, merged, len(rejections))
        await self.session.commit()

        return ImportReport(
            imported=imported,
            merged=merged,
            rejected=[RejectedRow(row=r["row_number"], reason=r["reason"]) for r in rejections],
        )

    def _read_rows(self, content: bytes) -> list[RawRow]:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ImportFileError("file is not valid UTF-8") from exc

        reader = csv.reader(io.StringIO(text, newline=""))
        try:
            header = next(reader)
        except StopIteration:
            raise ImportFileError("file is empty") from None

        missing = [column for column in self.COLUMN_MAP if column not in header]
        if missing:
            raise ImportFileError(f"missing required columns: {', '.join(missing)}")

        return [RawRow(row_number=index, raw=dict(zip(header, record))) for index, record in enumerate(reader, start=1)]

    def _validate_rows(self, rows: list[RawRow]) -> tuple[list[tuple[int, CandidateIn]], list[dict]]:
        survivors: list[tuple[int, CandidateIn]] = []
        rejections: list[dict] = []
        for row in rows:
            kwargs = {field: row.raw.get(column) for column, field in self.COLUMN_MAP.items()}
            try:
                candidate = CandidateIn(**kwargs)
            except ValidationError as exc:
                rejections.append(
                    {"row_number": row.row_number, "reason": self._format_errors(exc), "raw_row": row.raw}
                )
                continue
            survivors.append((row.row_number, candidate))
        return survivors, rejections

    @staticmethod
    def _format_errors(exc: ValidationError) -> str:
        return "; ".join(
            f"{error['loc'][0]}: {str(error['msg']).removeprefix('Value error, ')}" for error in exc.errors()
        )
