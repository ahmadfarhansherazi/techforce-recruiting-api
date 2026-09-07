from dataclasses import dataclass

from app.domain.enums import Region


@dataclass(frozen=True)
class RecruiterScope:
    recruiter_id: str
    is_admin: bool
    regions: frozenset[Region]

    def permits(self, region: Region) -> bool:
        return self.is_admin or region in self.regions
