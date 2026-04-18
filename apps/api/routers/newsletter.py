"""
MOD-19: Newsletter Integration (Listmonk + Brevo)
POST /api/v1/newsletter/subscribe — Public signup
GET  /api/v1/newsletter/lists     — Public list of available lists
POST /api/v1/newsletter/send      — Admin-only: trigger campaign via Brevo HTTP API
"""
import os
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import httpx

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/newsletter", tags=["MOD-19 Newsletter"])

# ── Config ────────────────────────────────────────────────────────────────────

LISTMONK_URL = os.getenv("LISTMONK_URL", "http://172.18.0.7:9000")
LISTMONK_USER = os.getenv("LISTMONK_ADMIN_USER", "admin")
LISTMONK_PW = os.getenv("LISTMONK_ADMIN_PASSWORD", "")
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")

# List ID mapping (from Listmonk)
LIST_IDS = {
    "citizens": 3,
    "press": 4,
    "parties": 5,
    "public_bodies": 6,
    "ngos": 7,
    "government": 8,
}

VALID_FREQUENCIES = {"weekly", "monthly"}
VALID_LANGUAGES = {"el", "en"}
VALID_TYPES = set(LIST_IDS.keys())


# ── Schemas ───────────────────────────────────────────────────────────────────

class SubscribeRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    subscriber_type: str = "citizens"
    frequency: str = "weekly"
    language: str = "el"
    topic_new_proposals: bool = False
    topic_active_votes: bool = True
    topic_vote_results: bool = True
    topic_system_news: bool = False
    topic_breaking_news: bool = False


# ── Listmonk API helper ──────────────────────────────────────────────────────

async def _listmonk_request(method: str, path: str, json_data: dict = None) -> dict:
    if not LISTMONK_PW:
        raise HTTPException(status_code=503, detail="Newsletter system not configured")
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.request(
            method,
            f"{LISTMONK_URL}{path}",
            json=json_data,
            auth=(LISTMONK_USER, LISTMONK_PW),
        )
        if r.status_code >= 400:
            logger.error(f"[MOD-19] Listmonk {method} {path}: {r.status_code} {r.text[:200]}")
        return r.json()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/lists")
async def get_lists():
    """Public: available newsletter lists."""
    return {
        "lists": [
            {"id": "citizens", "name_el": "Πολίτες", "name_en": "Citizens"},
            {"id": "press", "name_el": "Τύπος", "name_en": "Press"},
            {"id": "parties", "name_el": "Κόμματα", "name_en": "Parties"},
            {"id": "public_bodies", "name_el": "Δημόσιοι Φορείς", "name_en": "Public Bodies"},
            {"id": "ngos", "name_el": "ΜΚΟ / Σύλλογοι", "name_en": "NGOs"},
            {"id": "government", "name_el": "Κυβέρνηση", "name_en": "Government"},
        ]
    }


@router.post("/subscribe")
async def subscribe(req: SubscribeRequest):
    """
    Public: subscribe to newsletter.
    Creates subscriber in Listmonk with double opt-in.
    """
    if req.subscriber_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of: {VALID_TYPES}")
    if req.frequency not in VALID_FREQUENCIES:
        raise HTTPException(status_code=400, detail="Frequency must be 'weekly' or 'monthly'")
    if req.language not in VALID_LANGUAGES:
        raise HTTPException(status_code=400, detail="Language must be 'el' or 'en'")

    list_id = LIST_IDS.get(req.subscriber_type, LIST_IDS["citizens"])

    # Create subscriber in Listmonk with list assignment
    payload = {
        "email": req.email,
        "name": req.name or "",
        "status": "enabled",
        "lists": [list_id],
        "preconfirm_subscriptions": False,  # Double opt-in
        "attribs": {
            "frequency": req.frequency,
            "language": req.language,
            "subscriber_type": req.subscriber_type,
            "topic_new_proposals": req.topic_new_proposals,
            "topic_active_votes": req.topic_active_votes,
            "topic_vote_results": req.topic_vote_results,
            "topic_system_news": req.topic_system_news,
            "topic_breaking_news": req.topic_breaking_news,
        },
    }

    result = await _listmonk_request("POST", "/api/subscribers", payload)

    if "data" in result:
        logger.info(f"[MOD-19] New subscriber: {req.email} → list {req.subscriber_type}")
        return {"success": True, "message": "Confirmation email sent. Please check your inbox."}
    elif "subscriber exists" in str(result.get("message", "")).lower():
        return {"success": True, "message": "Already subscribed."}
    else:
        raise HTTPException(status_code=400, detail=result.get("message", "Subscription failed"))
