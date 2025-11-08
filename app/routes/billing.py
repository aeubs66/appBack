"""Billing routes for Clerk Billing webhooks and checkout helpers."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from svix.webhooks import Webhook, WebhookVerificationError
from dotenv import load_dotenv

from app.db import get_db
from app.models import ScopeType, Subscription, Team
from app.services.billing_service import (
    PLAN_BY_PRODUCT,
    get_plan_by_price_id,
    reset_usage_for_subscription,
    sync_subscription_from_event,
)


router = APIRouter()

logger = logging.getLogger(__name__)


load_dotenv()

CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")
CLERK_BILLING_WEBHOOK_SECRET = os.getenv("CLERK_BILLING_WEBHOOK_SECRET")
CLERK_API_BASE = os.getenv("CLERK_API_BASE_URL", "https://api.clerk.com/v1")


def _verify_svix_signature(payload: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
    if not CLERK_BILLING_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Billing webhook secret not configured."
        )

    try:
        webhook = Webhook(CLERK_BILLING_WEBHOOK_SECRET)
        event = webhook.verify(payload, headers)
        return json.loads(event)
    except WebhookVerificationError as exc:
        logger.warning("[BILLING] Webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")


@router.post("/webhook")
async def clerk_billing_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower().startswith("svix-")}

    event = _verify_svix_signature(payload, headers)
    event_type = event.get("type")
    data = event.get("data", {})

    logger.info("[BILLING] Received event %s", event_type)

    if event_type in {"billing.subscription.created", "billing.subscription.updated", "billing.subscription.deleted"}:
        subscription = sync_subscription_from_event(db, event_type, data)
        if not subscription:
            return {"ok": True}

        # Reset usage on create/renewal
        plan = PLAN_BY_PRODUCT[subscription.product]
        reset_usage_for_subscription(db, subscription, plan)
        return {"ok": True}

    if event_type in {"billing.invoice.paid", "billing.invoice.settled"}:
        subscription_id = data.get("subscription_id") or (data.get("subscription") or {}).get("id")
        if not subscription_id:
            logger.warning("[BILLING] Invoice event missing subscription id")
            return {"ok": True}

        subscription = (
            db.query(Subscription)
            .filter(Subscription.clerk_subscription_id == subscription_id)
            .first()
        )
        if not subscription:
            logger.warning("[BILLING] Invoice for unknown subscription %s", subscription_id)
            return {"ok": True}

        plan = PLAN_BY_PRODUCT[subscription.product]
        period_start = data.get("period_start") or data.get("period_start_at")
        reset_usage_for_subscription(db, subscription, plan, month_tag=period_start)
        return {"ok": True}

    logger.info("[BILLING] Ignored event %s", event_type)
    return {"ok": True}


def _require_clerk_secret():
    if not CLERK_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLERK_SECRET_KEY not configured"
        )


async def _create_checkout_session(payload: Dict[str, Any]) -> str:
    _require_clerk_secret()

    url = f"{CLERK_API_BASE}/billing/sessions"
    headers = {
        "Authorization": f"Bearer {CLERK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            logger.error(
                "[BILLING] Failed to create checkout session (%s): %s",
                response.status_code,
                response.text,
            )
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to create billing session")
        data = response.json()
        return data.get("url")


@router.post("/checkout")
async def create_checkout_session(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    plan_id = body.get("price_id")
    scope = body.get("scope", ScopeType.PERSONAL.value)
    team_id = body.get("team_id")
    clerk_user_id = body.get("clerk_user_id")

    plan = get_plan_by_price_id(plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown plan")

    if plan.scope_type == ScopeType.PERSONAL and not clerk_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing clerk_user_id")

    if plan.scope_type == ScopeType.TEAM and not team_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing team_id")

    checkout_payload: Dict[str, Any] = {
        "mode": "subscription",
        "price_id": plan.price_id,
        "success_url": body.get("success_url"),
        "cancel_url": body.get("cancel_url"),
    }

    if plan.scope_type == ScopeType.PERSONAL:
        checkout_payload["customer_id"] = clerk_user_id
        checkout_payload["customer_type"] = "user"
    else:
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team or not team.clerk_organization_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team missing Clerk organization mapping")
        checkout_payload["customer_id"] = team.clerk_organization_id
        checkout_payload["customer_type"] = "organization"

    url = await _create_checkout_session(checkout_payload)
    return {"url": url}


@router.post("/portal")
async def create_billing_portal_session(request: Request):
    body = await request.json()
    entity_id = body.get("entity_id")
    entity_type = body.get("entity_type", "user")

    payload = {
        "mode": "portal",
        "customer_id": entity_id,
        "customer_type": entity_type,
        "return_url": body.get("return_url"),
    }

    url = await _create_checkout_session(payload)
    return {"url": url}


