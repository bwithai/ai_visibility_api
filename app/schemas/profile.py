import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DOMAIN_PATTERN = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
    re.IGNORECASE,
)


class BusinessProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    domain: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    competitors: list[str] = Field(default_factory=list)

    @field_validator("name", "industry", "description")
    @classmethod
    def strip_and_validate_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        domain = value.strip().lower().removeprefix("https://").removeprefix("http://")
        domain = domain.split("/")[0].removeprefix("www.")
        if not _DOMAIN_PATTERN.fullmatch(domain):
            raise ValueError("invalid domain format")
        return domain

    @field_validator("competitors")
    @classmethod
    def normalize_competitors(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for competitor in values:
            competitor = competitor.strip().lower().removeprefix("https://").removeprefix("http://")
            competitor = competitor.split("/")[0].removeprefix("www.")
            if not competitor:
                continue
            if not _DOMAIN_PATTERN.fullmatch(competitor):
                raise ValueError(f"invalid competitor domain: {competitor}")
            normalized.append(competitor)
        return normalized


class BusinessProfileCreatedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_uuid: UUID
    name: str
    domain: str
    status: str
    created_at: datetime

    @classmethod
    def from_profile(cls, profile) -> "BusinessProfileCreatedResponse":
        return cls(
            profile_uuid=profile.uuid,
            name=profile.name,
            domain=profile.domain,
            status=profile.status,
            created_at=profile.created_at,
        )


class BusinessProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_uuid: UUID
    name: str
    domain: str
    industry: str
    description: str
    competitors: list[str]
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_profile(cls, profile) -> "BusinessProfileResponse":
        return cls(
            profile_uuid=profile.uuid,
            name=profile.name,
            domain=profile.domain,
            industry=profile.industry,
            description=profile.description,
            competitors=profile.competitors,
            status=profile.status,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
