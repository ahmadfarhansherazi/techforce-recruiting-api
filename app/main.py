from fastapi import FastAPI

from app.api.candidates import CandidatesRouter
from app.api.health import HealthRouter
from app.config import get_settings
from app.db.session import Database


class Application:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.database = Database(self.settings)
        self.fastapi = FastAPI(title="TechForce API")
        self.fastapi.state.database = self.database
        self.fastapi.include_router(HealthRouter(self.database).router)
        self.fastapi.include_router(CandidatesRouter().router)


app = Application().fastapi
