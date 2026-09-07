from sqlalchemy import func, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ImportBatch, ImportRejection


class ImportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_batch(self, filename: str) -> int:
        batch = ImportBatch(filename=filename, imported_count=0, merged_count=0, rejected_count=0)
        self.session.add(batch)
        await self.session.flush()
        return batch.id

    async def finish_batch(self, batch_id: int, imported: int, merged: int, rejected: int) -> None:
        await self.session.execute(
            update(ImportBatch)
            .where(ImportBatch.id == batch_id)
            .values(imported_count=imported, merged_count=merged, rejected_count=rejected, finished_at=func.now())
        )

    async def bulk_insert_rejections(self, batch_id: int, rejections: list[dict]) -> None:
        if not rejections:
            return
        rows = [
            {
                "batch_id": batch_id,
                "row_number": rejection["row_number"],
                "reason": rejection["reason"],
                "raw_row": rejection["raw_row"],
            }
            for rejection in rejections
        ]
        await self.session.execute(insert(ImportRejection), rows)
