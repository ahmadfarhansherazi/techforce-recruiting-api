"""Seeds the six canonical regions and recruiters.csv into Postgres.

Run: python3 scripts/seed_reference_data.py
Safe to re-run: regions and recruiters upsert, recruiter_regions rows are
replaced per recruiter on every run so the database always matches the file.
"""

import csv
from pathlib import Path

from sqlalchemy import create_engine, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Recruiter, RecruiterRegion, Region


class RegionSeeder:
    # No source file for this, the six canonical codes are fixed by the brief.
    REGIONS = {
        "US-MW": "US Midwest",
        "US-NE": "US Northeast",
        "US-SE": "US Southeast",
        "US-W": "US West",
        "PH-MNL": "Philippines, Manila",
        "CO-BOG": "Colombia, Bogota",
    }

    def __init__(self, session: Session) -> None:
        self.session = session

    def seed(self) -> None:
        for code, label in self.REGIONS.items():
            statement = insert(Region).values(code=code, label=label)
            statement = statement.on_conflict_do_update(
                index_elements=["code"], set_={"label": statement.excluded.label}
            )
            self.session.execute(statement)


class RecruiterSeeder:
    def __init__(self, session: Session, csv_path: Path) -> None:
        self.session = session
        self.csv_path = csv_path

    def seed(self) -> None:
        with self.csv_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                self._seed_row(row)

    def _seed_row(self, row: dict[str, str]) -> None:
        recruiter_id = row["recruiter_id"].strip()
        is_admin = row["role"].strip().lower() == "admin"

        statement = insert(Recruiter).values(
            id=recruiter_id, name=row["full_name"].strip(), is_admin=is_admin
        )
        statement = statement.on_conflict_do_update(
            index_elements=["id"],
            set_={"name": statement.excluded.name, "is_admin": statement.excluded.is_admin},
        )
        self.session.execute(statement)

        self.session.execute(delete(RecruiterRegion).where(RecruiterRegion.recruiter_id == recruiter_id))
        for region_code in self._parse_regions(row["assigned_regions"]):
            self.session.execute(
                insert(RecruiterRegion).values(recruiter_id=recruiter_id, region_code=region_code)
            )

    @staticmethod
    def _parse_regions(raw: str) -> list[str]:
        # "*" means unrestricted (admins). It is never persisted as a region row,
        # admins are is_admin=True with zero recruiter_regions rows.
        return [code.strip() for code in raw.split("|") if code.strip() and code.strip() != "*"]


class DatabaseSeeder:
    def __init__(self, session: Session, recruiters_csv: Path) -> None:
        self.session = session
        self.recruiters_csv = recruiters_csv

    def run(self) -> None:
        RegionSeeder(self.session).seed()
        self.session.flush()
        RecruiterSeeder(self.session, self.recruiters_csv).seed()
        self.session.commit()


class SeedRunner:
    RECRUITERS_CSV = Path(__file__).resolve().parent.parent / "Data" / "recruiters.csv"

    @classmethod
    def main(cls) -> None:
        settings = get_settings()
        engine = create_engine(settings.database_url)
        with Session(engine) as session:
            DatabaseSeeder(session, cls.RECRUITERS_CSV).run()
        print("Seed complete.")


if __name__ == "__main__":
    SeedRunner.main()
