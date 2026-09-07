# TechForce API

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Run Postgres

```bash
docker compose up -d
```

This starts Postgres 16 with two roles: an owner role (`techforce_owner`,
used for migrations) and a non-superuser application role
(`techforce_app`, used by the API at runtime).

## Migrations

```bash
alembic upgrade head
```

## Run the API

```bash
uvicorn app.main:app --reload
```

```bash
curl http://localhost:8000/health
```

## Tests

```bash
pytest
```
