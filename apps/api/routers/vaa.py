"""
MOD-02: VAA (Voting Advice Application) Router
GET  /api/v1/vaa/statements        — Alle Thesen (el/en)
GET  /api/v1/vaa/parties           — Alle Parteien
POST /api/v1/vaa/match             — Matching-Algorithmus
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Party, Statement, PartyPosition

router = APIRouter(prefix="/api/v1/vaa", tags=["MOD-02 VAA"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class StatementOut(BaseModel):
    id:             int
    text_el:        str
    text_en:        str | None
    explanation_el: str | None
    explanation_en: str | None
    category:       str | None
    display_order:  int

class PartyOut(BaseModel):
    id:             int
    name_el:        str
    name_en:        str | None
    abbreviation:   str | None
    color_hex:      str | None
    description_el: str | None
    description_en: str | None

class MatchRequest(BaseModel):
    answers: dict[int, int]  # {statement_id: -1|0|1}

class PartyMatchResult(BaseModel):
    party_id:       int
    name_el:        str
    name_en:        str | None
    abbreviation:   str | None
    color_hex:      str | None
    match_percent:  float
    answered_count: int

class MatchResponse(BaseModel):
    results: list[PartyMatchResult]
    total_answered: int


# ─── Algorithmus ──────────────────────────────────────────────────────────────

def calculate_match(
    user_answers: dict[int, int],
    party_positions: dict[int, int]
) -> tuple[float, int]:
    """
    Einfacher Matching-Algorithmus (MVP):
    Übereinstimmung = gleiche Positionen / beantwortete Thesen (ohne neutral)
    Returns: (match_percent, answered_count)
    """
    total = 0
    matches = 0

    for stmt_id, user_pos in user_answers.items():
        if user_pos == 0:       # neutral → ignorieren
            continue
        party_pos = party_positions.get(stmt_id)
        if party_pos is None:
            continue
        total += 1
        if user_pos == party_pos:
            matches += 1

    if total == 0:
        return 0.0, 0

    return round(matches / total * 100, 1), total


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/statements", response_model=list[StatementOut])
async def get_statements(
    lang: str = Query("el", description="Sprache: el oder en"),
    limit: int = Query(0, description="Max questions (0=all). Random selection if >0 and pool is larger."),
    db: AsyncSession = Depends(get_db)
):
    """Gibt aktive Thesen zurück. Mit limit>0: zufällige Auswahl aus dem Pool."""
    result = await db.execute(
        select(Statement)
        .where(Statement.is_active == True)
        .order_by(Statement.display_order)
    )
    statements = list(result.scalars().all())

    # If limit set and pool is larger → random subset per category
    if limit > 0 and len(statements) > limit:
        import random
        random.shuffle(statements)
        statements = statements[:limit]
        statements.sort(key=lambda s: s.display_order or 0)

    return statements


@router.get("/parties", response_model=list[PartyOut])
async def get_parties(db: AsyncSession = Depends(get_db)):
    """Gibt alle aktiven Parteien zurück."""
    result = await db.execute(
        select(Party).where(Party.is_active == True).order_by(Party.id)
    )
    return result.scalars().all()


@router.post("/match", response_model=MatchResponse)
async def match_parties(req: MatchRequest, db: AsyncSession = Depends(get_db)):
    """
    Berechnet die Übereinstimmung zwischen Nutzerantworten und Parteipositionen.
    Input:  { "answers": { "1": 1, "2": -1, "3": 0 } }
    Output: Sortierte Liste aller Parteien mit Prozentwert
    """
    # Alle aktiven Parteien laden
    parties_result = await db.execute(
        select(Party).where(Party.is_active == True)
    )
    parties = parties_result.scalars().all()

    # Alle Parteipositionen laden
    positions_result = await db.execute(select(PartyPosition))
    all_positions = positions_result.scalars().all()

    # Positionen nach Partei gruppieren
    party_positions_map: dict[int, dict[int, int]] = {}
    for pos in all_positions:
        if pos.party_id not in party_positions_map:
            party_positions_map[pos.party_id] = {}
        party_positions_map[pos.party_id][pos.statement_id] = pos.position

    # Matching berechnen
    results = []
    for party in parties:
        positions = party_positions_map.get(party.id, {})
        match_pct, answered = calculate_match(req.answers, positions)
        results.append(PartyMatchResult(
            party_id=party.id,
            name_el=party.name_el,
            name_en=party.name_en,
            abbreviation=party.abbreviation,
            color_hex=party.color_hex,
            match_percent=match_pct,
            answered_count=answered,
        ))

    # Sortiert nach Übereinstimmung (absteigend)
    results.sort(key=lambda x: x.match_percent, reverse=True)

    total_answered = sum(1 for v in req.answers.values() if v != 0)

    return MatchResponse(results=results, total_answered=total_answered)
