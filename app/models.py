"""
SQLAlchemy database models.
"""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid
import enum
from app.db import Base


class SubscriptionProduct(str, enum.Enum):
    STARTER = "starter"
    PRO = "pro"
    TEAM = "team"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"


class ScopeType(str, enum.Enum):
    PERSONAL = "personal"
    TEAM = "team"


class TeamRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class DocumentStatus(str, enum.Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    
    def __str__(self):
        return self.value


class PDFDocument(Base):
    """PDF document model."""
    __tablename__ = "pdf_document"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_clerk_user_id = Column(String, nullable=False, index=True)
    team_id = Column(UUID(as_uuid=True), ForeignKey("team.id"), nullable=True, index=True)
    title = Column(String, nullable=False)
    num_pages = Column(Integer, nullable=False, default=0)
    storage_path = Column(String, nullable=False)  # Path in Supabase Storage
    status = Column(String, nullable=False, default=DocumentStatus.PROCESSING.value, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    chunks = relationship("PDFChunk", back_populates="document", cascade="all, delete-orphan")
    team = relationship("Team", back_populates="documents")


class PDFChunk(Base):
    """PDF chunk with embedding for vector search."""
    __tablename__ = "pdf_chunk"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID(as_uuid=True), ForeignKey("pdf_document.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    page_from = Column(Integer, nullable=False)
    page_to = Column(Integer, nullable=False)
    embedding = Column(Vector(1536), nullable=False)  # OpenAI text-embedding-3-small dimension

    # Relationships
    document = relationship("PDFDocument", back_populates="chunks")


class Team(Base):
    """Team model."""
    __tablename__ = "team"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_clerk_user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    seat_limit = Column(Integer, nullable=False, default=3)
    clerk_organization_id = Column(String, nullable=True, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    documents = relationship("PDFDocument", back_populates="team")
    subscriptions = relationship("Subscription", back_populates="team")
    usage_records = relationship("UsageTeam", back_populates="team")


class TeamMember(Base):
    """Team member model."""
    __tablename__ = "team_member"

    team_id = Column(UUID(as_uuid=True), ForeignKey("team.id"), primary_key=True)
    clerk_user_id = Column(String, primary_key=True)
    role = Column(Enum(TeamRole), nullable=False, default=TeamRole.MEMBER)
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    team = relationship("Team", back_populates="members")


class Subscription(Base):
    """Subscription model for personal or team plans."""
    __tablename__ = "subscription"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clerk_subscription_id = Column(String, nullable=False, unique=True, index=True)
    scope_type = Column(Enum(ScopeType), nullable=False, index=True)
    owner_clerk_user_id = Column(String, nullable=True, index=True)  # For personal subscriptions
    team_id = Column(UUID(as_uuid=True), ForeignKey("team.id"), nullable=True, index=True)  # For team subscriptions
    product = Column(Enum(SubscriptionProduct), nullable=False)
    status = Column(Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.ACTIVE)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    seat_limit = Column(Integer, nullable=False, default=3)  # For team plans
    extra_seats = Column(Integer, nullable=False, default=0)  # Additional seats beyond base
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    team = relationship("Team", back_populates="subscriptions")


class UsagePersonal(Base):
    """Personal usage tracking (monthly)."""
    __tablename__ = "usage_personal"

    clerk_user_id = Column(String, primary_key=True)
    month_tag = Column(String, primary_key=True)  # Format: "YYYY-MM"
    credits_total = Column(Integer, nullable=False, default=0)
    credits_used = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class UsageTeam(Base):
    """Team usage tracking (monthly)."""
    __tablename__ = "usage_team"

    team_id = Column(UUID(as_uuid=True), ForeignKey("team.id"), primary_key=True)
    month_tag = Column(String, primary_key=True)  # Format: "YYYY-MM"
    credits_total = Column(Integer, nullable=False, default=0)
    credits_used = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    team = relationship("Team", back_populates="usage_records")

