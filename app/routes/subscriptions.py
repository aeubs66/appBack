"""Subscription routes."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import (
    ScopeType,
    Subscription,
    SubscriptionStatus,
    Team,
    TeamMember,
)
from app.services.billing_service import (
    prepare_usage_context,
    subscription_to_dict,
    usage_remaining,
)


router = APIRouter()


@router.get("/")
async def get_subscription(
    clerk_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return active subscriptions and usage info for the current user."""

    personal_subscription = (
        db.query(Subscription)
        .filter(
            Subscription.scope_type == ScopeType.PERSONAL,
            Subscription.owner_clerk_user_id == clerk_user_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .order_by(Subscription.created_at.desc())
        .first()
    )

    personal_usage = prepare_usage_context(db, clerk_user_id=clerk_user_id)

    personal_payload = {
        "subscription": subscription_to_dict(personal_subscription) if personal_subscription else None,
        "credits_remaining": usage_remaining(personal_usage),
        "credits_total": personal_usage.credits_total,
        "month_tag": personal_usage.month_tag,
    }

    memberships = (
        db.query(TeamMember)
        .filter(TeamMember.clerk_user_id == clerk_user_id)
        .all()
    )

    team_payload = []
    for membership in memberships:
        team = db.query(Team).filter(Team.id == membership.team_id).first()
        if not team:
            continue

        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.scope_type == ScopeType.TEAM,
                Subscription.team_id == team.id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .order_by(Subscription.created_at.desc())
            .first()
        )

        usage = prepare_usage_context(db, clerk_user_id=clerk_user_id, team_id=str(team.id))

        team_payload.append(
            {
                "team": {
                    "id": str(team.id),
                    "name": team.name,
                    "seat_limit": team.seat_limit,
                },
                "subscription": subscription_to_dict(subscription) if subscription else None,
                "credits_remaining": usage_remaining(usage),
                "credits_total": usage.credits_total,
                "month_tag": usage.month_tag,
            }
        )

    return {
        "personal": personal_payload,
        "teams": team_payload,
    }

