from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import Candidate, Recruiter, RecruiterRegion, Region
from app.main import Application

# No SQLite anywhere in this package: every fixture below talks to a real,
# throwaway Postgres database created and dropped for the test session.


class TestDatabaseUrls:
    NAME = "techforce_test"

    def __init__(self) -> None:
        settings = get_settings()
        self.app_url = self._with_database(settings.database_url)
        self.owner_url = self._with_database(settings.alembic_database_url)
        self.maintenance_url = self._with_database(settings.alembic_database_url, database="postgres")

    def _with_database(self, url: str, database: str | None = None) -> str:
        base, _, _ = url.rpartition("/")
        return f"{base}/{database or self.NAME}"


class TestDatabaseManager:
    ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

    def __init__(self, urls: TestDatabaseUrls) -> None:
        self.urls = urls

    async def recreate(self) -> None:
        engine = create_async_engine(self.urls.maintenance_url, isolation_level="AUTOCOMMIT")
        async with engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{self.urls.NAME}" WITH (FORCE)'))
            await connection.execute(text(f'CREATE DATABASE "{self.urls.NAME}"'))
        await engine.dispose()

    def migrate(self) -> None:
        config = Config(str(self.ALEMBIC_INI))
        config.set_main_option("sqlalchemy.url", self.urls.owner_url)
        command.upgrade(config, "head")

    async def grant_app_privileges(self) -> None:
        # Default privileges granted to the app role in docker-compose's init
        # script are set per-database at container init, they do not carry
        # over to a freshly created database, so this database needs its own.
        app_role = make_url(self.urls.app_url).username
        engine = create_async_engine(self.urls.owner_url)
        async with engine.begin() as connection:
            await connection.execute(text(f'GRANT USAGE ON SCHEMA public TO "{app_role}"'))
            await connection.execute(
                text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{app_role}"')
            )
            await connection.execute(text(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{app_role}"'))
        await engine.dispose()

    async def drop(self) -> None:
        engine = create_async_engine(self.urls.maintenance_url, isolation_level="AUTOCOMMIT")
        async with engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{self.urls.NAME}" WITH (FORCE)'))
        await engine.dispose()


class ReferenceDataSeeder:
    # Fixed, hermetic reference data. Not the real recruiters.csv, which is
    # gitignored source data and must never be a test dependency.
    REGIONS = {
        "US-MW": "US Midwest",
        "US-NE": "US Northeast",
        "US-SE": "US Southeast",
        "US-W": "US West",
        "PH-MNL": "Philippines, Manila",
        "CO-BOG": "Colombia, Bogota",
    }
    RECRUITERS = (
        {"id": "R-ADMIN", "name": "Admin Recruiter", "is_admin": True, "regions": ()},
        {"id": "R-SCOPED", "name": "Scoped Recruiter", "is_admin": False, "regions": ("US-MW", "US-NE")},
        {"id": "R-OTHER", "name": "Other Recruiter", "is_admin": False, "regions": ("PH-MNL",)},
    )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def seed(self) -> None:
        for code, label in self.REGIONS.items():
            self.session.add(Region(code=code, label=label))
        await self.session.flush()

        for recruiter in self.RECRUITERS:
            self.session.add(
                Recruiter(id=recruiter["id"], name=recruiter["name"], is_admin=recruiter["is_admin"])
            )
        await self.session.flush()

        for recruiter in self.RECRUITERS:
            for region_code in recruiter["regions"]:
                self.session.add(RecruiterRegion(recruiter_id=recruiter["id"], region_code=region_code))
        await self.session.flush()


class SingleSessionDatabase:
    # Test double for app.db.session.Database: every caller that opens "a
    # session" gets the same function-scoped, transactional one, so the whole
    # request lifecycle rolls back with everything else after the test.
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        yield self._session


@pytest_asyncio.fixture(scope="session")
async def prepared_database() -> AsyncIterator[TestDatabaseUrls]:
    urls = TestDatabaseUrls()
    manager = TestDatabaseManager(urls)
    await manager.recreate()
    manager.migrate()
    await manager.grant_app_privileges()

    engine = create_async_engine(urls.owner_url)
    async with AsyncSession(engine) as session:
        await ReferenceDataSeeder(session).seed()
        await session.commit()
    await engine.dispose()

    yield urls

    await manager.drop()


@pytest_asyncio.fixture(scope="session")
async def test_engine(prepared_database: TestDatabaseUrls) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(prepared_database.app_url)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    connection: AsyncConnection
    async with test_engine.connect() as connection:
        await connection.begin()
        session_factory = async_sessionmaker(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        session = session_factory()
        yield session
        await session.close()
        await connection.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    application = Application()
    application.fastapi.state.database = SingleSessionDatabase(db_session)
    transport = ASGITransport(app=application.fastapi)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    await application.database.dispose()


@pytest_asyncio.fixture
async def seeded_candidates(db_session: AsyncSession) -> dict[str, Candidate]:
    candidates = {
        "ada": Candidate(
            email="ada.lovelace@example.com",
            full_name="Ada Lovelace",
            region_code="US-MW",
            role="Backend Engineer",
            status="active",
            applied_date=date(2026, 5, 1),
            salary=Decimal("95000"),
        ),
        "grace": Candidate(
            email="grace.hopper@example.com",
            full_name="Grace Hopper",
            region_code="US-NE",
            role="Data Engineer",
            status="screening",
            applied_date=date(2026, 5, 2),
            salary=Decimal("88000"),
        ),
        "alan": Candidate(
            email="alan.turing@example.com",
            full_name="Alan Turing",
            region_code="PH-MNL",
            role="QA Engineer",
            status="active",
            applied_date=date(2026, 5, 3),
            salary=None,
        ),
        "percent": Candidate(
            email="candidate.percent@example.com",
            full_name="100% Ready",
            region_code="US-MW",
            role="Frontend Engineer",
            status="active",
            applied_date=date(2026, 5, 4),
            salary=Decimal("70000"),
        ),
        "underscore": Candidate(
            email="candidate.underscore@example.com",
            full_name="Under_Score Candidate",
            region_code="US-NE",
            role="DevOps Engineer",
            status="active",
            applied_date=date(2026, 5, 5),
            salary=Decimal("72000"),
        ),
    }
    # This inserts directly through the ORM, bypassing CandidateRepository
    # and the app.recruiter_id it would normally set. RETURNING (used here
    # to read back generated ids) is checked against the same RLS SELECT
    # policy as a plain read, so without this the insert itself would fail.
    await db_session.execute(text("SELECT set_config('app.bypass_rls', 'true', true)"))
    for candidate in candidates.values():
        db_session.add(candidate)
    await db_session.flush()
    # SET LOCAL lasts for the rest of this transaction, not just this insert,
    # and db_session's transaction spans the whole test. Reset it so a test
    # body that never sets a recruiter still sees RLS's real default-deny.
    await db_session.execute(text("SELECT set_config('app.bypass_rls', 'false', true)"))
    return candidates
