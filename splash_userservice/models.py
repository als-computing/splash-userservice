from typing import List, Optional

from pydantic import BaseModel, Field


class UniqueId(BaseModel):
    id: str = Field("globally unique identifier for user")
    source: Optional[str] = Field("indicates source of identifier, e.g. ORCID")


class User(BaseModel):
    uid: str = Field(description="system unique identifier")
    authenticators: Optional[List[UniqueId]] = Field(None, description="list of accounts that user can be known by")
    given_name: Optional[str] = Field(None, description="user's given name", schema="https://schema.org/givenName")
    family_name: Optional[str] = Field(None, description="user's family name")
    current_institution: Optional[str] = Field(None, description="user's currently known institution")
    current_email: Optional[str] = Field(None, description="user's currently known email")
    groups: Optional[List[str]] = Field(None, description="list of groups a user belongs to")
    orcid: str = Field(description="user's ORCID")


class AccessGroup(BaseModel):
    uid: str = Field(description="group's system unique identifier")
    name: str = Field(description="group's name")
    members: Optional[List[UniqueId]] = Field(None, description="list of users in the access group")


class MappedField(BaseModel):
    source: str
    source_name: str
    source_dtype: str


# V2 API Models

# V2UserGroupDetails is the main response model, which inherits the others.

class V2UserBase(BaseModel):
    uid: Optional[int] = Field(description="system unique identifier")
    given_name: Optional[str] = Field(None, description="user's given name")
    family_name: Optional[str] = Field(None, description="user's family name")
    current_institution: Optional[str] = Field(None, description="user's currently known institution")
    current_email: Optional[str] = Field(None, description="user's currently known email")
    orcid: str = Field(description="user's ORCID")


class V2UserGroups(V2UserBase):
    groups: List[str] = Field(description="list of groups, consolidated from Beamlines, Proposals, and ESAFs")


class V2UserEsaf(BaseModel):
    roles: List[str] = Field(description="user's roles in the ESAF: 'pi', 'explead', and/or 'participant'")
    id: str = Field(description="ESAF identifier")
    title: Optional[str] = Field(None, description="title of the ESAF")
    proposal_id: Optional[str] = Field(None, description="associated proposal identifier")
    beamline_id: Optional[str] = Field(None, description="associated beamline identifier")
    earliest_start: Optional[str] = Field(None, description="earliest scheduled start date among all the date ranges in the ESAF")
    latest_end: Optional[str] = Field(None, description="latest scheduled end date for all the date ranges in the ESAF")


class V2UserGroupDetails(V2UserGroups):
    beamlines: List[str] = Field([], description="list of Beamlines for which the user is considered 'staff', by identifier, e.g. '7.3.3'")
    proposals: List[str] = Field([], description="list of Proposal identifiers the user is associated with")
    esafs: List[V2UserEsaf] = Field([], description="list of ESAF the user is associated with, with their roles and some detail of the ESAF")

