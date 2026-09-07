# TechForce Recruiting API

## Prerequisites

- Python 3.11+
- Node 20.19+ (or 22.12+)
- Docker and Docker Compose
- `psql` (optional, for inspecting the database directly)

## 0. Add the source data files

`Data/` is gitignored and not pushed to this repository. Create it and add the two source files yourself before running the seed script or importing candidates:

```bash
mkdir -p Data
# copy recruiters.csv and candidates_import.csv into Data/
```

`scripts/seed_reference_data.py` needs `Data/recruiters.csv`. The import endpoint needs `Data/candidates_import.csv` (or any CSV with the same columns) as the file you upload.

## 1. Clone and configure environment variables

```bash
cp .env.example .env
```

The defaults in `.env.example` work as-is against the `docker-compose.yml` in this repo. `DATABASE_URL` connects as the non-superuser app role, `ALEMBIC_DATABASE_URL` connects as the owner role for migrations.

## 2. Start Postgres

```bash
docker compose up -d
```

This starts Postgres 16 on `localhost:5433`, creates the `techforce_owner` (superuser bootstrap, used for migrations) and `techforce_app` (non-superuser, used by the API at runtime) roles, and grants `techforce_app` default privileges on future tables.

Wait for it to report healthy:

```bash
docker compose ps
```

## 3. Install backend dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 4. Run migrations

```bash
alembic upgrade head
```

This creates the schema (six tables, the `citext` extension, the `candidate_status` enum, all indexes) and enables row-level security on `candidates`.

## 5. Seed reference data

```bash
python3 scripts/seed_reference_data.py
```

Inserts the six canonical regions and loads `recruiters.csv` into `recruiters` and `recruiter_regions`. Safe to re-run.

## 6. Run the API

```bash
uvicorn app.main:app --reload
```

```bash
curl http://localhost:8000/health
```

Import the candidate CSV:

```bash
curl -X POST http://localhost:8000/api/v1/candidates/import \
  -F "file=@Data/candidates_import.csv;type=text/csv"
```

List candidates as a recruiter:

```bash
curl http://localhost:8000/api/v1/candidates -H "X-Recruiter-Id: R-101"
```

## 7. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api` to `http://127.0.0.1:8000`, so the backend from step 6 must be running.

## 8. Run the test suite

```bash
pytest
```

Runs both unit tests (`tests/unit`, no database) and integration tests (`tests/integration`, real Postgres). Integration tests create and drop their own `techforce_test` database each run, they do not touch the `techforce` database from step 2.

Unit tests only:

```bash
pytest tests/unit
```

Integration tests only:

```bash
pytest tests/integration
```
