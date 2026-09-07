from httpx import AsyncClient

from app.db.models import Candidate


class TestScoping:
    async def test_region_limited_recruiter_receives_only_their_regions(
        self, client: AsyncClient, seeded_candidates: dict[str, Candidate]
    ) -> None:
        response = await client.get(
            "/api/v1/candidates", headers={"X-Recruiter-Id": "R-SCOPED"}, params={"limit": 50}
        )
        assert response.status_code == 200

        names = {item["name"] for item in response.json()["items"]}
        assert names == {"Ada Lovelace", "Grace Hopper", "100% Ready", "Under_Score Candidate"}

    async def test_scoped_recruiter_gets_404_for_candidate_outside_their_regions(
        self, client: AsyncClient, seeded_candidates: dict[str, Candidate]
    ) -> None:
        alan_id = seeded_candidates["alan"].id  # region PH-MNL, outside R-SCOPED's US-MW/US-NE

        response = await client.get(f"/api/v1/candidates/{alan_id}", headers={"X-Recruiter-Id": "R-SCOPED"})

        assert response.status_code == 404

    async def test_admin_receives_every_candidate_and_can_fetch_by_id(
        self, client: AsyncClient, seeded_candidates: dict[str, Candidate]
    ) -> None:
        response = await client.get(
            "/api/v1/candidates", headers={"X-Recruiter-Id": "R-ADMIN"}, params={"limit": 50}
        )
        assert response.status_code == 200
        assert response.json()["total"] == len(seeded_candidates)

        alan_id = seeded_candidates["alan"].id
        detail = await client.get(f"/api/v1/candidates/{alan_id}", headers={"X-Recruiter-Id": "R-ADMIN"})

        assert detail.status_code == 200
        assert detail.json()["name"] == "Alan Turing"

    async def test_unknown_recruiter_id_receives_403_not_empty_200(
        self, client: AsyncClient, seeded_candidates: dict[str, Candidate]
    ) -> None:
        response = await client.get("/api/v1/candidates", headers={"X-Recruiter-Id": "R-GHOST"})

        assert response.status_code == 403

    async def test_missing_header_receives_422(
        self, client: AsyncClient, seeded_candidates: dict[str, Candidate]
    ) -> None:
        response = await client.get("/api/v1/candidates")

        assert response.status_code == 422

    async def test_total_equals_scoped_count_not_global_count(
        self, client: AsyncClient, seeded_candidates: dict[str, Candidate]
    ) -> None:
        response = await client.get(
            "/api/v1/candidates", headers={"X-Recruiter-Id": "R-SCOPED"}, params={"limit": 1}
        )
        body = response.json()

        assert body["total"] == 4  # R-SCOPED's US-MW + US-NE count, not the global 5
        assert len(body["items"]) == 1  # limit still applied
