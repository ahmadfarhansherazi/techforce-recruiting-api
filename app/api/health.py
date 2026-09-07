from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import Database


class HealthRouter:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.router = APIRouter()
        self.router.add_api_route("/health", self.check, methods=["GET"])

    async def check(self) -> dict[str, str]:
        async with self.database.session() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar_one()
        return {"status": "ok"}
