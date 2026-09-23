# teluvane/teluvane/routes/billing.py
"""Plan/usage reads and LemonSqueezy checkout/portal/webhook."""

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request

from ..auth import current_org
from ..billing import create_checkout_session, create_portal_session, handle_webhook, org_plan
from ..usage import hosted_audit_count, hosted_audit_limit_for_plan

router = APIRouter()


@router.get("/billing/plan")
def billing_plan(org_id: str = Depends(current_org)) -> dict:
    return {"plan": org_plan(org_id)}


@router.get("/billing/usage")
def billing_usage(org_id: str = Depends(current_org)) -> dict:
    plan = org_plan(org_id)
    return {
        "hosted_audits_used": hosted_audit_count(org_id),
        "limit": hosted_audit_limit_for_plan(plan),
    }


@router.post("/billing/checkout")
def billing_checkout(
    email: str = Body(embed=True),
    plan: str = Body(embed=True, default="pro"),
    org_id: str = Depends(current_org),
) -> dict:
    if plan not in ("starter", "pro"):
        raise HTTPException(status_code=400, detail="plan must be 'starter' or 'pro'")
    return {"url": create_checkout_session(org_id, email, plan)}


@router.post("/billing/portal")
def billing_portal(org_id: str = Depends(current_org)) -> dict:
    url = create_portal_session(org_id)
    if not url:
        raise HTTPException(status_code=404, detail="no active subscription")
    return {"url": url}


@router.post("/billing/webhook")
async def billing_webhook(request: Request, x_signature: str = Header(default=None)) -> dict:
    raw = await request.body()
    try:
        handle_webhook(raw, x_signature)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid webhook signature")
    return {"ok": True}
