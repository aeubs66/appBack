"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.models import SubscriptionProduct, SubscriptionStatus, ScopeType, TeamRole, DocumentStatus


# PDF Document Schemas
class PDFDocumentBase(BaseModel):
    title: str
    num_pages: int
    storage_path: str


class PDFDocumentCreate(PDFDocumentBase):
    team_id: Optional[UUID] = None


class PDFDocumentResponse(PDFDocumentBase):
    id: UUID
    owner_clerk_user_id: str
    team_id: Optional[UUID]
    status: DocumentStatus
    created_at: datetime

    class Config:
        from_attributes = True


# PDF Chunk Schemas
class PDFChunkBase(BaseModel):
    content: str
    page_from: int
    page_to: int


class PDFChunkCreate(PDFChunkBase):
    doc_id: UUID
    embedding: List[float] = Field(..., min_items=1536, max_items=1536)


class PDFChunkResponse(PDFChunkBase):
    id: UUID
    doc_id: UUID

    class Config:
        from_attributes = True


# Team Schemas
class TeamBase(BaseModel):
    name: str
    seat_limit: int = 3


class TeamCreate(TeamBase):
    pass


class TeamResponse(TeamBase):
    id: UUID
    owner_clerk_user_id: str
    created_at: datetime

    class Config:
        from_attributes = True


# Team Member Schemas
class TeamMemberBase(BaseModel):
    clerk_user_id: str
    role: TeamRole


class TeamMemberCreate(TeamMemberBase):
    team_id: UUID


class TeamMemberResponse(TeamMemberBase):
    team_id: UUID
    joined_at: datetime

    class Config:
        from_attributes = True


# Subscription Schemas
class SubscriptionBase(BaseModel):
    scope_type: ScopeType
    product: SubscriptionProduct
    status: SubscriptionStatus
    seat_limit: int = 3
    extra_seats: int = 0


class SubscriptionCreate(SubscriptionBase):
    owner_clerk_user_id: Optional[str] = None
    team_id: Optional[UUID] = None
    current_period_end: Optional[datetime] = None


class SubscriptionResponse(SubscriptionBase):
    id: UUID
    owner_clerk_user_id: Optional[str]
    team_id: Optional[UUID]
    current_period_end: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Usage Schemas
class UsagePersonalBase(BaseModel):
    clerk_user_id: str
    month_tag: str
    credits_total: int = 0
    credits_used: int = 0


class UsagePersonalResponse(UsagePersonalBase):
    updated_at: datetime

    class Config:
        from_attributes = True


class UsageTeamBase(BaseModel):
    team_id: UUID
    month_tag: str
    credits_total: int = 0
    credits_used: int = 0


class UsageTeamResponse(UsageTeamBase):
    updated_at: datetime

    class Config:
        from_attributes = True

