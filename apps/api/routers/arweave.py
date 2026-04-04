"""
MOD-08: Arweave Integration
Publiziert Full Audit Trail bei PARLIAMENT_VOTED → Arweave Network.
NIEMALS: Individual Votes, Nullifier Hashes, persönliche Daten.

@ai-anchor MOD08_ARWEAVE
@update-hint TX-ID wird in parliament_bills.arweave_tx_id gespeichert
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import ParliamentBill, BillStatusLog
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/arweave", tags=["MOD-08 Arweave"])


def build_audit_trail(snapshot_timestamp: str = None, 
    bill: ParliamentBill,
    status_logs: list,
    vote_results: dict,
    divergence_score: Optional[float],
) -> dict:
    """
    Baut den vollständigen Audit Trail für Arweave.
    Enthält: Bill Metadata, Lifecycle, Citizen Votes (aggregiert), Divergence Score.
    NIEMALS: Individual Votes, Nullifier Hashes.
    """
    return {
        "schema_version": "1.0",
        "published_by":   "ekklesia.gr",
        "published_at":   datetime.now(timezone.utc).isoformat(),
        "bill": {
            "id":              bill.id,
            "title_el":        bill.title_el,
            "title_en":        bill.title_en,
            "pill_el":         bill.pill_el,
            "pill_en":         bill.pill_en,
            "categories":      bill.categories,
            "snapshot_timestamp": snapshot_timestamp,
        "governance_level": "NATIONAL",
            "parliament_vote_date": bill.parliament_vote_date.isoformat()
                if bill.parliament_vote_date else None,
        },
        "lifecycle": [
            {
                "from_status": log.from_status,
                "to_status":   log.to_status,
                "changed_at":  log.changed_at.isoformat() if log.changed_at else None,
            }
            for log in status_logs
        ],
        "parliament_votes": bill.party_votes_parliament or {},
        "citizen_votes": {
            "yes":     vote_results.get("yes",     0),
            "no":      vote_results.get("no",      0),
            "abstain": vote_results.get("abstain", 0),
            "total":   vote_results.get("total",   0),
        },
        "divergence_score": divergence_score,
        "parliament_result": _parliament_result(bill.party_votes_parliament),
    }


def _parliament_result(party_votes: Optional[dict]) -> Optional[str]:
    """Berechnet das Parlamentsergebnis aus den Parteistimmen."""
    if not party_votes:
        return None
    yes = sum(1 for v in party_votes.values() if v in ("ΝΑΙ", "YES"))
    no  = sum(1 for v in party_votes.values() if v in ("ΟΧΙ", "NO"))
    return "APPROVED" if yes >= no else "REJECTED"


async def publish_to_arweave(audit_trail: dict, bill_id: str) -> Optional[str]:
    """
    Publiziert Audit Trail auf Arweave.
    Gibt TX-ID zurück oder None wenn Wallet nicht konfiguriert.
    """
    wallet_path = settings.arweave_wallet_path

    if not wallet_path:
        logger.info(f"[MOD-08] Arweave wallet nicht konfiguriert — Dry Run für Bill {bill_id}")
        return f"DRY_RUN_{bill_id}_{int(datetime.now().timestamp())}"

    try:
        import arweave
        wallet = arweave.Wallet(wallet_path)
        tx = arweave.Transaction(
            wallet,
            data=json.dumps(audit_trail, ensure_ascii=False)
        )
        tx.add_tag("App-Name",         "ekklesia.gr")
        tx.add_tag("App-Version",      "1.0")
        tx.add_tag("Bill-ID",          bill_id)
        tx.add_tag("Content-Type",     "application/json")
        tx.add_tag("Governance-Level", "NATIONAL")
        tx.add_tag("Schema-Version",   "1.0")
        tx.sign()
        tx.send()
        logger.info(f"[MOD-08] Arweave TX published: {tx.id} für Bill {bill_id}")
        return tx.id

    except Exception as e:
        logger.error(f"[MOD-08] Arweave publish failed für {bill_id}: {e}")
        return None


@router.get("/status")
async def arweave_status():
    """
    Status des Arweave Moduls.
    Zeigt ob Wallet konfiguriert ist und Wallet-Adresse (öffentlich).
    """
    wallet_path = settings.arweave_wallet_path

    if not wallet_path:
        return {
            "status":            "dry_run",
            "wallet_configured": False,
            "message":           "Arweave wallet nicht konfiguriert — Dry Run Modus",
            "wallet_address":    None,
        }

    try:
        import arweave
        wallet = arweave.Wallet(wallet_path)
        balance = wallet.balance
        return {
            "status":            "active",
            "wallet_configured": True,
            "wallet_address":    wallet.address,
            "balance_ar":        float(balance),
            "message":           "Arweave wallet aktiv",
        }
    except Exception as e:
        return {
            "status":            "error",
            "wallet_configured": True,
            "message":           str(e),
            "wallet_address":    None,
        }


@router.get("/bill/{bill_id}")
async def get_arweave_record(bill_id: str, db: AsyncSession = Depends(get_db)):
    """Gibt TX-ID und Arweave URL für ein Bill zurück."""
    result = await db.execute(
        select(ParliamentBill).where(ParliamentBill.id == bill_id)
    )
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(404, "Bill nicht gefunden")

    tx_id = bill.arweave_tx_id
    if not tx_id:
        return {"bill_id": bill_id, "arweave_tx_id": None, "arweave_url": None}

    return {
        "bill_id":       bill_id,
        "arweave_tx_id": tx_id,
        "arweave_url":   f"https://arweave.net/{tx_id}",
        "gateway_url":   f"https://viewblock.io/arweave/tx/{tx_id}",
    }
