from httpx import AsyncClient

from app.db.models import Candidate


class TestSearch:
    async def test_percent_is_treated_as_a_literal_not_a_wildcard(
        self, client: AsyncClient, seeded_candidates: dict[str, Candidate]
    ) -> None:
        response = await client.get(
            "/api/v1/candidates", headers={"X-Recruiter-Id": "R-ADMIN"}, params={"search": "%"}
        )
        body = response.json()

        assert body["total"] == 1  # not every candidate
        assert {item["name"] for item in body["items"]} == {"100% Ready"}

    async def test_underscore_is_treated_as_a_literal_not_a_wildcard(
        self, client: AsyncClient, seeded_candidates: dict[str, Candidate]
    ) -> None:
        response = await client.get(
            "/api/v1/candidates", headers={"X-Recruiter-Id": "R-ADMIN"}, params={"search": "_"}
        )
        body = response.json()

        assert body["total"] == 1  # not every candidate
        assert {item["name"] for item in body["items"]} == {"Under_Score Candidate"}

    async def test_search_results_stay_within_caller_scope(
        self, client: AsyncClient, seeded_candidates: dict[str, Candidate]
    ) -> None:
        # "Turing" only exists on Alan Turing, region PH-MNL, outside
        # R-SCOPED's US-MW/US-NE.
        scoped = await client.get(
            "/api/v1/candidates", headers={"X-Recruiter-Id": "R-SCOPED"}, params={"search": "Turing"}
        )
        assert scoped.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}

        admin = await client.get(
            "/api/v1/candidates", headers={"X-Recruiter-Id": "R-ADMIN"}, params={"search": "Turing"}
        )
        assert admin.json()["total"] == 1
