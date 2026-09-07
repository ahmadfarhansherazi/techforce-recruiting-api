# Notes

## 1. Deduplication and merge rules

Applied in this order:

1. Rows byte-identical to an earlier row collapse silently. Not counted as merged or rejected, they just disappear from the batch.
2. Rows sharing a normalized email but differing in other fields merge into one record, field by field. A non-null value beats a null value. When both are non-null, the later row in the file wins. Counts as merged.
3. Rows sharing a legacy candidate id but having different emails are two distinct people. Both are kept, this is not a conflict.

Identity is the normalized email, not the legacy candidate id, because the source file proves the legacy id is not unique: `C-1010` appears twice for two different people (Sofia Cardenas and Becca Storm). Keying on it would silently destroy one of them. Email survives normalization to one canonical value per person and is what a recruiter actually recognizes a candidate by.

## 2. Normalization decisions

- **Email**: lowercase and trim, require exactly one `@` and a dot in the domain. Plus-addressing and dots in the local part are preserved, not stripped, they are distinct identities. Empty or malformed addresses (no `@`, more than one `@`) are rejected.
- **Region**: explicit alias map to the six canonical codes, no fuzzy matching. `USW` (missing hyphen) is aliased to `US-W`, a plausible real-world typo. A code with no match in the canonical directory at all, like `ZZ-99`, is rejected outright rather than guessed at.
- **Status**: explicit alias map (`ACTIVE`, `ACTVE` both map to active, etc). `on hold` is rejected rather than added to the enum, the source file's own note on that row calls it out as a status outside the enum.
- **Date**: ISO first, then a short explicit list of other formats. Calendar-impossible dates are rejected. A value ambiguous between `DD/MM` and `MM/DD` is rejected rather than guessed. Future dates are rejected.
- **Salary**: strip currency symbols and thousands separators, accept a single positive number, take the lower bound of a range. Blank and unparseable both become null, the design does not distinguish the two cases.

## 3. Authorization

Enforced in `CandidateRepository`, the only class that touches a database session for candidate reads. Every read method takes `scope` as its first argument and applies the region predicate inside the method itself. There is no unscoped read method on the class, so a new endpoint cannot query candidates without going through this class and supplying a scope, there is nothing else to call.

A second, independent layer sits underneath it: Postgres row-level security on `candidates`, with `FORCE ROW LEVEL SECURITY` so even the table owner is subject to it. The recruiter is set with `SET LOCAL` inside the request transaction, so it cannot leak across a pooled connection. A raw, deliberately unscoped `SELECT * FROM candidates` as the application role still only returns in-scope rows, verified directly in `TestRowLevelSecurity`.

## 4. AI usage

- A database schema diagram was produced as an artifact during the persistence layer work: https://claude.ai/code/artifact/76474d4d-2d10-4673-bc2f-294d50d212ca
- Planned with Claude desktop, created the execution sequence and individual tailored prompts for claude code to work efficiently and in a structured way.
- Asked Claude to walk through the exact decision logic for treating a date as calendar-invalid before writing tests for it. That led to confirming a multi-layer check rather than a single regex pass: format-shape detection first, then month/day disambiguation for ambiguous numeric formats, then actual calendar validity via a real date constructor.
- Asked Claude directly why `USW` is accepted while `ZZ-99` is rejected in region normalization. Confirmed the decision: `USW` keeps its alias to `US-W` since a missing hyphen is a plausible real-world typo, codes with no match in the canonical directory at all are rejected outright.
- Caught and corrected: Claude's default commit messages and PR descriptions included an AI-attribution line. Had to reject it and correct it more than once before it stopped.
- Row-level security: the first RLS migration blocked legitimate application writes. Only a `SELECT` policy existed, so Postgres's default-deny applied to `INSERT` as well, and to the `RETURNING` clause the app relies on to report which rows were new versus updated. Caught by the test suite, fixed with separate permissive `INSERT`/`UPDATE` policies and an explicit bypass flag for the one write path that is intentionally scope-free.

## 5. What I would do next

- Fuzzy matching for region codes, accepting a match above 90% confidence instead of rejecting anything outside the explicit alias map.
- Concurrent ingestion for multiple files at once: an SQS-driven architecture with worker processes, each spawning multiple threads to process CSVs in parallel.
- CI/CD pipelines to support pushing this to production.
