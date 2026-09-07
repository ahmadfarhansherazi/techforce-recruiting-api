# CLAUDE.md

Working context for the TechForce take-home. Read this fully before writing code. When something here conflicts with a general best practice you would otherwise reach for, this file wins.

## What we are building

A vertical slice of a recruiting operations platform:

1. A CSV ingestion endpoint that loads a deliberately messy legacy candidate export into PostgreSQL, rejecting bad rows with an explicit report rather than dropping them.
2. A read API where a recruiter, identified only by an `X-Recruiter-Id` header, can see candidates in their assigned regions and nothing else.
3. A minimal React table on top of that API with a recruiter switcher, so the scoping is visible by flipping between users.
4. A pytest suite proving dedup, validation, injection safety, and authorization.

Stack: Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 16, React + TypeScript, Vite. Postgres runs via docker-compose. Tests run against real Postgres, never SQLite.



The brief states it openly, so treat these as the acceptance criteria:

- Did you define what "valid" means and apply it consistently, rather than coercing everything into passing.
- Is authorization enforced somewhere it cannot be bypassed by a future endpoint.
- Do you write to the database like someone who has run one in production: batched writes, parameterized queries, correct conflict handling.
- Are decisions documented. Ambiguity in the brief is intentional. Making a reasonable call and writing it down is the task.

Anything that does not serve one of those four gets cut when time is short.

## Code style

These are hard rules for this repository.

**Everything lives on a class.** No module-level functions anywhere except `__init__.py` and pytest fixtures in `conftest.py`. If a piece of logic does not obviously belong to an existing class, that is a signal it needs its own class, not a loose helper. Pure helpers that take no state become `@staticmethod` on the class that uses them. Router endpoints are methods on a class that registers its own routes.

**Short code.** Prefer 10 clear lines over 30 defensive ones. If a method is longer than roughly 20 lines it is doing two jobs, split it. Small classes with narrow responsibilities beat large ones with sections.

**Comments and docstrings are the exception, not the default.** No docstrings on classes or methods whose names already say what they do. No parameter tables, no type restatements in prose, no section banners. Write a comment only when the code cannot explain a decision on its own: a non-obvious constraint, a deliberate deviation, a rule from the brief. Those comments are one line.

**Naming carries the meaning.** `CandidateNormalizer.region()` needs no docstring. If you feel the urge to write one, the name is wrong.

**Type hints everywhere**, on parameters and returns. They replace most of the documentation you would otherwise write. Modern syntax: `str | None`, `list[Candidate]`, no `typing.Optional`, no `typing.List`.

**No em dashes in any prose, code comment, commit message, or NOTES.md content.** Use commas, colons, or restructure the sentence.

**Style specifics:** f-strings only. `pathlib` over `os.path`. Dataclasses or Pydantic models over dicts for anything structured. Custom exception classes over returning error tuples or `None` sentinels. No bare `except`. No mutable default arguments. Constants as class attributes on the class that owns them, not module-level globals.

**Write it the way a senior engineer writes when they know a reviewer is watching:** obvious, boring, small, correct. No cleverness, no premature abstraction, no config layers for things that have one value.

## Layering

Strict dependency direction, each layer only imports downward:

```
api/          routers, request and response schemas, dependency wiring
services/     orchestration, transaction boundaries
repositories/ all SQL, the only layer touching a Session
domain/       Pydantic models, enums, normalizers, validators, pure logic
db/           engine, session factory, ORM models, migrations
```

Routers contain no business logic and no SQL. Repositories contain no HTTP concepts. The domain layer imports nothing from the other four and is testable with no database.

## The scoping chokepoint

This is the highest-value piece of the exercise. The brief explicitly rejects filtering that "could be bypassed by another endpoint," so make bypass structurally impossible rather than merely absent.

A `RecruiterScope` object is resolved once by a FastAPI dependency: it looks up the recruiter, raises 403 on an unknown ID, and carries `recruiter_id`, `is_admin`, and `regions`. Every method on `CandidateRepository` that reads candidates takes `scope: RecruiterScope` as its first argument, and the scope predicate is applied inside the repository, not by the caller. There is no unscoped read method on that class. A new endpoint physically cannot query candidates without a scope, because there is no function to call.

Admins are `is_admin=True` with no region rows. Never store `*` as a region value, that forces an `OR` into every predicate and will eventually be got wrong.

Add PostgreSQL Row-Level Security as a second layer, and only then. Two gotchas if you do: the table owner bypasses RLS unless you set `FORCE ROW LEVEL SECURITY`, and the recruiter must be set with `SET LOCAL` inside the request transaction so it cannot leak across pooled connections. The payoff is a test that issues a raw unscoped `SELECT *` as the application role and still gets only in-scope rows.

## Schema

Canonical regions: `US-MW`, `US-NE`, `US-SE`, `US-W`, `PH-MNL`, `CO-BOG`.

```
regions            code PK, label

candidates         id                   PK, surrogate
                   legacy_candidate_id  TEXT NULL, indexed, NOT unique
                   email                CITEXT NOT NULL UNIQUE
                   full_name            TEXT NOT NULL
                   region_code          FK -> regions.code, NOT NULL
                   role                 TEXT NULL
                   status               ENUM NOT NULL
                   applied_date         DATE NULL
                   salary               NUMERIC(12,2) NULL
                   created_at, updated_at TIMESTAMPTZ

recruiters         id PK (matches X-Recruiter-Id), name, is_admin BOOL

recruiter_regions  recruiter_id FK, region_code FK, PK(both)

import_batches     id, filename, started_at, finished_at,
                   imported_count, merged_count, rejected_count

import_rejections  batch_id FK, row_number INT, reason TEXT, raw_row JSONB
```


**`legacy_candidate_id` is not the primary key and carries no unique constraint.** The source file contains a `candidate_id` collision between two different people. Keying on it silently destroys a record. Identity is the normalized email; the legacy ID is descriptive metadata.

**Status is a Postgres enum, region is a lookup table.** Status is a closed set we control, so the database enforces it for free. Regions change when the business opens an office, and a table avoids an `ALTER TYPE` migration. The asymmetry is deliberate.

**Uniqueness on email lives in the database.** In-memory dedup handles duplicates within one file. The unique constraint handles duplicates across separate imports. Both are needed; neither substitutes for the other.

**Rejections are persisted, not just returned.** "Rejected, not silently dropped" is really a request for an audit trail someone in recruiting ops can act on. The table costs almost nothing and is the strongest schema-level signal in the project.

Indexes: unique on email, plus `region_code`, `status`, and a composite `(region_code, applied_date DESC, id)` for the list query. Plain `ILIKE` for search is honest at this data size; mention `pg_trgm` in NOTES.md as the answer at scale rather than building it.

## Ingestion rules

Read the file with `utf-8-sig`. A legacy export very likely carries a BOM, and Unicode names are called out explicitly in the brief.

Attach the 1-based file row number at read time and carry it through both validation and dedup. Rejection reports are worthless without it.

**Email:** lowercase and trim. Do not strip plus-addressing or dots, those are distinct identities and collapsing them merges different people.

**Region:** explicit alias map to the six canonical codes. No fuzzy matching. "Cannot be confidently normalized" means unrecognized values are rejected, not guessed.

**Status:** map known variants to the canonical enum, reject unknown values.

**Date:** try ISO first, then a short explicit ordered list of formats. Reject ambiguous `DD/MM` versus `MM/DD` values rather than guessing, reject impossible dates, decide and document what happens to future dates.

**Salary:** strip currency symbols and thousands separators, accept a single positive number, take the lower bound of a range, everything else becomes null. Document the rule in NOTES.md.

**Dedup precedence,** applied in this order and stated in NOTES.md:
1. Exact duplicate rows collapse silently.
2. Same normalized email with differing details: merge field by field, non-null beats null, later row wins ties. Counts as `merged`.
3. Same `legacy_candidate_id` with different emails: two distinct people, keep both.

**Idempotency:** importing the same file twice yields `imported: 0, merged: N`. This is worth a test and it is a cheap one.

**Writes are batched.** A single `INSERT ... ON CONFLICT (email) DO UPDATE` over a list of dicts. Never a per-row insert inside a loop, they are watching for exactly that.

**All SQL is parameterized or ORM-built.** The file contains hostile rows. Never build a query with string interpolation, including in the search filter. Escape `%` and `_` in user-supplied search text.

## API contract

```
POST /api/v1/candidates/import
  -> 200 {imported, merged, rejected: [{row, reason}]}
  -> 400 only when the file itself is unparseable or the wrong shape

GET /api/v1/candidates?search=&status=&limit=&offset=
  -> 200 {items, total, limit, offset}
```

Rejections are a business outcome of a successful batch, so a partially rejected import is a 200, not a 400.

Unknown recruiter ID gets 403. Missing header gets 422. A valid recruiter with no matching candidates gets 200 and an empty list.

`total` must come from the same scoped query as `items`. A global count next to a scoped page leaks the size of the pool outside the recruiter's regions.

Cap `limit`. If a candidate detail endpoint is added for the authorization test, an out-of-scope candidate returns 404 rather than 403, since 403 confirms the record exists.

Import stays synchronous. Note in NOTES.md that a real system queues it; do not build that here.

## Tests

Real PostgreSQL via docker-compose or testcontainers, function-scoped transactional rollback between tests. Fixtures live in `conftest.py` and are the only functions permitted outside a class. Test bodies group into classes by subject: `TestDeduplication`, `TestScoping`, and so on.

Minimum coverage required by the brief:
- A dedup case, ideally one per precedence rule.
- Invalid email rejection.
- The injection rows landing as inert literal data.
- A recruiter cannot retrieve a candidate outside their regions.
- An admin can retrieve everything.

Add the idempotency test if time allows. The suite must run and pass on camera before recording stops.


## NOTES.md

Write it incrementally as decisions are made, not reconstructed at the end. It must cover:

- Dedup and merge rules, and the normalization decisions for email, region, status, date, and salary.
- The AI usage log: what was delegated, what was deliberately kept manual, and at least one concrete thing an AI tool produced that was caught and corrected during the exercise.
- What comes next with more time: RLS if not built, queued imports, keyset pagination, `pg_trgm` search, CSV formula injection escaping on any future export path.

The AI usage log needs a specific incident, not a general statement. Note it down the moment it happens.