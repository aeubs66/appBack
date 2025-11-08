"""Billing service helpers for Clerk Billing integration."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Union
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    ScopeType,
    Subscription,
    SubscriptionProduct,
    SubscriptionStatus,
    Team,
    TeamMember,
    UsagePersonal,
    UsageTeam,
)


logger = logging.getLogger(__name__)


STARTER_PRICE_ID = os.getenv("CLERK_PRICE_STARTER_MONTHLY", "starter_monthly")
PRO_PRICE_ID = os.getenv("CLERK_PRICE_PRO_MONTHLY", "pro_monthly")
TEAM_BASE_PRICE_ID = os.getenv("CLERK_PRICE_TEAM_BASE_MONTHLY", "team_base_monthly")
TEAM_EXTRA_SEAT_PRICE_ID = os.getenv("CLERK_PRICE_TEAM_EXTRA_SEAT", "team_extra_seat")


@dataclass
class PlanDefinition:
    price_id: str
    product: SubscriptionProduct
    scope_type: ScopeType
    monthly_credits: int
    base_seats: int
    extra_seat_credit: int = 0


PLAN_BY_PRICE: Dict[str, PlanDefinition] = {
    STARTER_PRICE_ID: PlanDefinition(
        price_id=STARTER_PRICE_ID,
        product=SubscriptionProduct.STARTER,
        scope_type=ScopeType.PERSONAL,
        monthly_credits=100,
        base_seats=1,
    ),
    PRO_PRICE_ID: PlanDefinition(
        price_id=PRO_PRICE_ID,
        product=SubscriptionProduct.PRO,
        scope_type=ScopeType.PERSONAL,
        monthly_credits=400,
        base_seats=1,
    ),
    TEAM_BASE_PRICE_ID: PlanDefinition(
        price_id=TEAM_BASE_PRICE_ID,
        product=SubscriptionProduct.TEAM,
        scope_type=ScopeType.TEAM,
        monthly_credits=200,
        base_seats=3,
        extra_seat_credit=50,
    ),
}


PLAN_BY_PRODUCT: Dict[SubscriptionProduct, PlanDefinition] = {
    value.product: value for value in PLAN_BY_PRICE.values()
}


def _get_month_tag(dt: Optional[datetime] = None) -> str:
    timestamp = dt or datetime.now(timezone.utc)
    return timestamp.strftime("%Y-%m")


def get_plan_by_price_id(price_id: Optional[str]) -> Optional[PlanDefinition]:
    if not price_id:
        return None
    return PLAN_BY_PRICE.get(price_id)


def get_plan_by_product(product: SubscriptionProduct) -> PlanDefinition:
    return PLAN_BY_PRODUCT[product]


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except Exception:
        logger.warning("[BILLING] Unable to parse datetime: %s", value)
        return None


def _extract_extra_seats(data: dict) -> int:
    extra_seats = 0

    for item in data.get("items", []) or data.get("line_items", []):
        price_id = item.get("price_id") or (item.get("price") or {}).get("id")
        if price_id == TEAM_EXTRA_SEAT_PRICE_ID:
            extra_seats += int(item.get("quantity", 0))

    for entitlement in data.get("entitlements", []):
        price_id = entitlement.get("price_id")
        if price_id == TEAM_EXTRA_SEAT_PRICE_ID:
            extra_seats += int(entitlement.get("limit", 0))

    add_ons = data.get("add_ons", [])
    for add_on in add_ons:
        if add_on.get("price_id") == TEAM_EXTRA_SEAT_PRICE_ID:
            extra_seats += int(add_on.get("quantity", 0))

    return extra_seats


def _map_status(status: Optional[str]) -> SubscriptionStatus:
    if not status:
        return SubscriptionStatus.ACTIVE
    normalized = status.lower()
    for member in SubscriptionStatus:
        if member.value == normalized:
            return member
    return SubscriptionStatus.ACTIVE


def _find_team_by_clerk_id(db: Session, clerk_org_id: Optional[str]) -> Optional[Team]:
    if not clerk_org_id:
        return None
    return db.query(Team).filter(Team.clerk_organization_id == clerk_org_id).first()


def sync_subscription_from_event(db: Session, event_type: str, data: dict) -> Optional[Subscription]:
    """Upsert subscription information from Clerk Billing events."""

    subscription_id = data.get("id") or data.get("subscription_id")
    if not subscription_id:
        logger.warning("[BILLING] Subscription event missing id")
        return None

    price_info = data.get("price") or {}
    price_id = data.get("price_id") or price_info.get("id")
    plan = get_plan_by_price_id(price_id)

    if not plan:
        logger.warning("[BILLING] Unknown price id '%s'", price_id)
        return None

    scope = data.get("scope") or data.get("subscriber") or {}
    scope_type_raw = scope.get("type")
    scope_id = scope.get("id")

    owner_clerk_user_id: Optional[str] = None
    team: Optional[Team] = None

    if plan.scope_type == ScopeType.PERSONAL:
        owner_clerk_user_id = scope_id or data.get("customer_id")
    else:
        team = _find_team_by_clerk_id(db, scope_id)
        if not team:
            logger.warning(
                "[BILLING] Team subscription for organization '%s' but no team record found.",
                scope_id,
            )

    extra_seats = _extract_extra_seats(data)
    seat_limit = plan.base_seats + (extra_seats if plan.scope_type == ScopeType.TEAM else 0)

    current_period_end = parse_datetime(
        data.get("current_period_end") or data.get("current_period_end_at")
    )

    subscription = (
        db.query(Subscription)
        .filter(Subscription.clerk_subscription_id == subscription_id)
        .first()
    )

    if not subscription:
        subscription = Subscription(
            clerk_subscription_id=subscription_id,
            scope_type=plan.scope_type,
        )
        db.add(subscription)

    subscription.product = plan.product
    subscription.status = _map_status(data.get("status"))
    subscription.owner_clerk_user_id = owner_clerk_user_id
    subscription.team_id = team.id if team else None
    subscription.current_period_end = current_period_end
    subscription.extra_seats = extra_seats
    subscription.seat_limit = seat_limit

    if team:
        team.seat_limit = seat_limit

    db.commit()

    return subscription


def reset_usage_for_subscription(
    db: Session,
    subscription: Subscription,
    plan: PlanDefinition,
    month_tag: Optional[Union[str, datetime]] = None,
) -> None:
    if isinstance(month_tag, datetime):
        month_tag_value = _get_month_tag(month_tag)
    elif isinstance(month_tag, str):
        month_tag_value = _get_month_tag(parse_datetime(month_tag))
    else:
        month_tag_value = _get_month_tag()

    if subscription.scope_type == ScopeType.PERSONAL:
        if not subscription.owner_clerk_user_id:
            logger.warning("[BILLING] Personal subscription missing owner id.")
            return

        usage = (
            db.query(UsagePersonal)
            .filter(
                UsagePersonal.clerk_user_id == subscription.owner_clerk_user_id,
                UsagePersonal.month_tag == month_tag_value,
            )
            .first()
        )

        if not usage:
            usage = UsagePersonal(
                clerk_user_id=subscription.owner_clerk_user_id,
                month_tag=month_tag_value,
                credits_total=plan.monthly_credits,
                credits_used=0,
            )
            db.add(usage)
        else:
            usage.credits_total = plan.monthly_credits
            usage.credits_used = 0

    else:
        if not subscription.team_id:
            logger.warning("[BILLING] Team subscription missing team reference.")
            return

        usage = (
            db.query(UsageTeam)
            .filter(
                UsageTeam.team_id == subscription.team_id,
                UsageTeam.month_tag == month_tag_value,
            )
            .first()
        )

        total_credits = plan.monthly_credits + subscription.extra_seats * plan.extra_seat_credit

        if not usage:
            usage = UsageTeam(
                team_id=subscription.team_id,
                month_tag=month_tag_value,
                credits_total=total_credits,
                credits_used=0,
            )
            db.add(usage)
        else:
            usage.credits_total = total_credits
            usage.credits_used = 0

    db.commit()


@dataclass
class UsageContext:
    scope_type: ScopeType
    subscription: Optional[Subscription]
    plan: PlanDefinition
    month_tag: str
    credits_total: int
    credits_used: int
    subject_id: str
    usage_record: UsagePersonal | UsageTeam


def prepare_usage_context(
    db: Session, *, clerk_user_id: str, team_id: Optional[str] = None
) -> UsageContext:
    month_tag = _get_month_tag()

    team_uuid: Optional[uuid.UUID] = None
    if team_id:
        try:
            team_uuid = uuid.UUID(str(team_id))
        except (ValueError, TypeError):
            logger.warning("[BILLING] Invalid team_id supplied for usage context: %s", team_id)

    if team_uuid:
        subscription = (
            db.query(Subscription)
            .filter(
                Subscription.scope_type == ScopeType.TEAM,
                Subscription.team_id == team_uuid,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .order_by(Subscription.created_at.desc())
            .first()
        )
        plan = PLAN_BY_PRODUCT.get(
            subscription.product if subscription else SubscriptionProduct.TEAM
        )
        total_credits = plan.monthly_credits
        extra = subscription.extra_seats if subscription else 0
        total_credits += extra * plan.extra_seat_credit

        usage = (
            db.query(UsageTeam)
            .filter(UsageTeam.team_id == team_uuid, UsageTeam.month_tag == month_tag)
            .first()
        )

        if not usage:
            usage = UsageTeam(
                team_id=team_uuid,
                month_tag=month_tag,
                credits_total=total_credits,
                credits_used=0,
            )
            db.add(usage)
            db.commit()

        credits_total = usage.credits_total or total_credits
        credits_used = usage.credits_used

        return UsageContext(
            scope_type=ScopeType.TEAM,
            subscription=subscription,
            plan=plan,
            month_tag=month_tag,
            credits_total=credits_total,
            credits_used=credits_used,
            subject_id=str(team_uuid),
            usage_record=usage,
        )

    # Personal usage path
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.scope_type == ScopeType.PERSONAL,
            Subscription.owner_clerk_user_id == clerk_user_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .order_by(Subscription.created_at.desc())
        .first()
    )

    plan = PLAN_BY_PRODUCT.get(
        subscription.product if subscription else SubscriptionProduct.STARTER
    )
    total_credits = plan.monthly_credits

    usage = (
        db.query(UsagePersonal)
        .filter(UsagePersonal.clerk_user_id == clerk_user_id, UsagePersonal.month_tag == month_tag)
        .first()
    )

    if not usage:
        usage = UsagePersonal(
            clerk_user_id=clerk_user_id,
            month_tag=month_tag,
            credits_total=total_credits,
            credits_used=0,
        )
        db.add(usage)
        db.commit()

    credits_total = usage.credits_total or total_credits
    credits_used = usage.credits_used

    return UsageContext(
        scope_type=ScopeType.PERSONAL,
        subscription=subscription,
        plan=plan,
        month_tag=month_tag,
        credits_total=credits_total,
        credits_used=credits_used,
        subject_id=clerk_user_id,
        usage_record=usage,
    )


def usage_remaining(context: UsageContext) -> int:
    return max(0, context.credits_total - context.credits_used)


def increment_usage(db: Session, context: UsageContext, amount: int = 1) -> None:
    context.usage_record.credits_used += amount
    db.commit()


def can_invite_member(db: Session, team: Team) -> bool:
    members = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
    limit = team.seat_limit or 0
    return members < limit


def subscription_to_dict(subscription: Subscription) -> dict:
    plan = PLAN_BY_PRODUCT[subscription.product]
    return {
        "subscription_id": subscription.clerk_subscription_id,
        "scope_type": subscription.scope_type.value,
        "product": subscription.product.value,
        "status": subscription.status.value,
        "seat_limit": subscription.seat_limit,
        "extra_seats": subscription.extra_seats,
        "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        "monthly_credits": plan.monthly_credits,
        "extra_seat_credit": plan.extra_seat_credit,
    }


