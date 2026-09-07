from enum import Enum


class CandidateStatus(str, Enum):
    ACTIVE = "active"
    SCREENING = "screening"
    INTERVIEWING = "interviewing"
    WITHDRAWN = "withdrawn"


class Region(str, Enum):
    US_MW = "US-MW"
    US_NE = "US-NE"
    US_SE = "US-SE"
    US_W = "US-W"
    PH_MNL = "PH-MNL"
    CO_BOG = "CO-BOG"
