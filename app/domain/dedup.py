from dataclasses import dataclass

from app.domain.models import CandidateIn


@dataclass(frozen=True)
class DeduplicatedCandidate:
    # The row a later failure should be reported against. For a merged
    # record this is the last row that contributed to it, matching the
    # "later row wins" tie-break used to build that record.
    row_number: int
    candidate: CandidateIn


@dataclass(frozen=True)
class DeduplicationResult:
    records: list[DeduplicatedCandidate]
    collapsed: int
    merged: int


class DeduplicationEngine:
    def deduplicate(self, rows: list[tuple[int, CandidateIn]]) -> DeduplicationResult:
        survivors, collapsed = self._collapse_exact_duplicates(rows)
        records, merged = self._merge_by_email(survivors)
        return DeduplicationResult(records=records, collapsed=collapsed, merged=merged)

    @staticmethod
    def _collapse_exact_duplicates(
        rows: list[tuple[int, CandidateIn]],
    ) -> tuple[list[tuple[int, CandidateIn]], int]:
        survivors: list[tuple[int, CandidateIn]] = []
        seen: list[CandidateIn] = []
        collapsed = 0
        for row_number, candidate in rows:
            if candidate in seen:
                collapsed += 1
                continue
            seen.append(candidate)
            survivors.append((row_number, candidate))
        return survivors, collapsed

    def _merge_by_email(
        self, rows: list[tuple[int, CandidateIn]]
    ) -> tuple[list[DeduplicatedCandidate], int]:
        groups: dict[str, list[tuple[int, CandidateIn]]] = {}
        order: list[str] = []
        for row_number, candidate in rows:
            # Grouping key is the normalized email only, never legacy_candidate_id:
            # rows sharing a legacy id with different emails are distinct people
            # and must fall into different groups here.
            key = candidate.email
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append((row_number, candidate))

        records: list[DeduplicatedCandidate] = []
        merged = 0
        for key in order:
            group = groups[key]
            if len(group) == 1:
                row_number, candidate = group[0]
                records.append(DeduplicatedCandidate(row_number=row_number, candidate=candidate))
                continue
            merged += len(group) - 1
            row_number, candidate = self._merge_group(group)
            records.append(DeduplicatedCandidate(row_number=row_number, candidate=candidate))
        return records, merged

    @staticmethod
    def _merge_group(group: list[tuple[int, CandidateIn]]) -> tuple[int, CandidateIn]:
        ordered = sorted(group, key=lambda pair: pair[0])
        merged_fields: dict[str, object] = {}
        for field_name in CandidateIn.model_fields:
            value = None
            for _, candidate in ordered:
                current = getattr(candidate, field_name)
                if current is not None:
                    value = current
            merged_fields[field_name] = value

        winning_row_number = ordered[-1][0]
        merged_candidate = CandidateIn.model_construct(**merged_fields)
        return winning_row_number, merged_candidate
