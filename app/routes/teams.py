"""Team routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Team
from app.services.billing_service import can_invite_member


router = APIRouter()


@router.get("/")
async def list_teams(
    clerk_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List teams owned by the user."""
    teams = (
        db.query(Team)
        .filter(Team.owner_clerk_user_id == clerk_user_id)
        .all()
    )
    return {
        "teams": [
            {
                "id": str(team.id),
                "name": team.name,
                "seat_limit": team.seat_limit,
                "clerk_organization_id": team.clerk_organization_id,
            }
            for team in teams
        ]
    }


@router.get("/{team_id}")
async def get_team(
    team_id: str,
    clerk_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get details for a specific team."""
    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid team id")

    team = db.query(Team).filter(Team.id == team_uuid).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    return {
        "id": str(team.id),
        "name": team.name,
        "seat_limit": team.seat_limit,
        "clerk_organization_id": team.clerk_organization_id,
    }


class InviteRequest(BaseModel):
    email: EmailStr


@router.post("/{team_id}/invite")
async def invite_team_member(
    team_id: str,
    payload: InviteRequest,
    clerk_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Invite a member to the team, enforcing seat limits."""
    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid team id")

    team = db.query(Team).filter(Team.id == team_uuid).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    if team.owner_clerk_user_id != clerk_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only team owners can invite members")

    if not can_invite_member(db, team):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seat limit reached. Upgrade your plan to add more members.",
        )

    # NOTE: Actual invitation sending (email) is handled elsewhere / future phase.
    return {
        "status": "pending",
        "email": payload.email,
        "message": "Seat available. Invitation workflow not implemented yet.",
    }

