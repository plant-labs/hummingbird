from enum import Enum


class EventType(str, Enum):
    KIDNAP = "kidnap"
    ROBBERY = "robbery"
    TERRORISM = "terrorism"
    PROTEST = "protest"
    SCAM = "scam"
    BATTLE = "battle"
    EXPLOSION = "explosion"
    OTHER = "other"


class VerificationStatus(str, Enum):
    UNCONFIRMED = "unconfirmed"
    REPORTED = "reported"
    VERIFIED = "verified"
    OFFICIAL_CONFIRMATION = "official_confirmation"


class IncidentStatus(str, Enum):
    ONGOING = "ongoing"
    IN_NEGOTIATION = "in_negotiation"
    RELEASED = "released"
    RESCUED = "rescued"
    CASUALTY_CONFIRMED = "casualty_confirmed"
    UNRESOLVED = "unresolved"


class LocationPrecision(str, Enum):
    EXACT = "exact"
    LGA = "lga"
    STATE = "state"


class SourceType(str, Enum):
    NEWS = "news"
    SOCIAL = "social"
    OFFICIAL = "official"
    CROWD = "crowd"


class SourceRole(str, Enum):
    PRIMARY = "primary"
    CORROBORATING = "corroborating"
