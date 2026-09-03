# teluvane/teluvane/routes/policy.py
"""Framework selection, custom policy rules, scheduled runs, BYOK key, webhooks."""
from fastapi import APIRouter, Depends, Body, HTTPException

from ..appstate import FRAMEWORK_PACKS, base_pack_for_org
from ..auth import current_org
from ..orgs import get_policy_framework, set_policy_framework
from ..policy import Rule
from ..custom_rules import list_custom_rules, upsert_custom_rule, delete_custom_rule
from ..billing import org_plan
from ..scheduler import get_schedule, set_schedule
from ..byok import set_byok, get_byok, clear_byok, has_byok
from ..webhooks import set_webhook, get_webhook, delete_webhook

router = APIRouter()

# ---- policy framework selection (human auth: JWT) -------------------------------------------
@router.get("/orgs/framework")
def get_framework_ep(org_id: str = Depends(current_org)) -> dict:
    return {"framework": get_policy_framework(org_id), "available": list(FRAMEWORK_PACKS)}

@router.put("/orgs/framework")
def put_framework_ep(framework: str = Body(embed=True), org_id: str = Depends(current_org)) -> dict:
    if framework not in FRAMEWORK_PACKS:
        raise HTTPException(status_code=400, detail=f"unknown framework, choose one of {list(FRAMEWORK_PACKS)}")
    set_policy_framework(org_id, framework)
    return {"framework": framework}

# ---- custom policy rules (human auth: JWT, Pro plan to write) ------------------------------
@router.get("/policy/rules")
def get_policy_rules(org_id: str = Depends(current_org)) -> list[dict]:
    base_pack = base_pack_for_org(org_id)
    custom_ids = {r.id for r in list_custom_rules(org_id)}
    base = [{**r.model_dump(), "custom": r.id in custom_ids} for r in base_pack.rules if r.id not in custom_ids]
    custom = [{**r.model_dump(), "custom": True} for r in list_custom_rules(org_id)]
    return base + custom

@router.put("/policy/rules/{rule_id}")
def put_policy_rule(rule_id: str, description: str = Body(...), severity: str = Body(...),
                    keywords: list[str] = Body(default=[]), framework_ref: str = Body(default="Custom"),
                    detector_hint: str = Body(default=""), org_id: str = Depends(current_org)) -> dict:
    if org_plan(org_id) != "pro":
        raise HTTPException(status_code=402, detail="Custom policy rules require the Pro plan")
    upsert_custom_rule(org_id, Rule(id=rule_id, description=description, severity=severity,
                                    framework_ref=framework_ref, detector_hint=detector_hint,
                                    keywords=keywords))
    return {"id": rule_id}

@router.delete("/policy/rules/{rule_id}")
def delete_policy_rule(rule_id: str, org_id: str = Depends(current_org)) -> dict:
    delete_custom_rule(org_id, rule_id)
    return {"deleted": rule_id}

@router.get("/schedule")
def get_schedule_ep(org_id: str = Depends(current_org)) -> dict:
    return get_schedule(org_id)

@router.put("/schedule")
def put_schedule_ep(enabled: bool = Body(...), interval_minutes: int = Body(60),
                    org_id: str = Depends(current_org)) -> dict:
    if org_plan(org_id) != "pro":
        raise HTTPException(status_code=402, detail="Automated tribunal runs require the Pro plan")
    set_schedule(org_id, enabled, interval_minutes)
    return get_schedule(org_id)

@router.put("/byok")
def put_byok(key: str = Body(embed=True), org_id: str = Depends(current_org)) -> dict:
    set_byok(org_id, "anthropic", key)
    return {"configured": True}

@router.get("/byok")
def get_byok_status(org_id: str = Depends(current_org)) -> dict:
    return {"configured": has_byok(org_id, "anthropic")}   # never returns the key itself

@router.delete("/byok")
def delete_byok(org_id: str = Depends(current_org)) -> dict:
    clear_byok(org_id, "anthropic")
    return {"configured": False}

# ---- webhook (human auth: JWT) ----------------------------------------------------------------
@router.get("/webhooks")
def get_webhook_ep(org_id: str = Depends(current_org)) -> dict:
    hook = get_webhook(org_id)
    return hook if hook else {"url": None, "secret": None}

@router.put("/webhooks")
def put_webhook_ep(url: str = Body(embed=True), org_id: str = Depends(current_org)) -> dict:
    if not url.startswith("https://") and not url.startswith("http://"):
        raise HTTPException(status_code=400, detail="webhook url must be http(s)")
    secret = set_webhook(org_id, url)
    return {"url": url, "secret": secret}

@router.delete("/webhooks")
def delete_webhook_ep(org_id: str = Depends(current_org)) -> dict:
    delete_webhook(org_id)
    return {"url": None, "secret": None}
