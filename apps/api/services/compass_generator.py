"""
Compass Question Generator — Ollama + DeepL
Generates evidence-based political compass questions from real parliamentary data.
Flow: Bill data → Ollama (EN) → DeepL (EN→EL) → Store as pending → Admin review
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models import ParliamentBill, BillStatus, CitizenVote, VoteChoice, Statement
from .ollama_service import ollama_generate, deepl_translate, ollama_available

logger = logging.getLogger(__name__)

CATEGORIES = [
    "Οικονομία", "Περιβάλλον & Ενέργεια", "Κοινωνική Πολιτική",
    "Υγεία", "Παιδεία", "Εργασία & Οικονομία",
    "Άμυνα & Εξωτερική Πολιτική", "Τεχνολογία & Ψηφιακή Πολιτική",
]


async def generate_questions_from_bill(
    bill: ParliamentBill, citizen_yes_pct: float, db: AsyncSession,
) -> list[dict]:
    """Generate 2 compass questions from a real bill using Ollama (EN) + DeepL (→EL)."""

    if not await ollama_available():
        logger.warning("Ollama unavailable — skipping compass generation")
        return []

    title = bill.title_en or bill.title_el
    categories = ", ".join(bill.categories or ["General"])

    prompt = f"""You are a political scientist creating a voter alignment compass for Greece.
Based on this real parliamentary bill, generate exactly 2 neutral political statements
that citizens can agree or disagree with.

Bill: {title}
Categories: {categories}
Citizen support: {citizen_yes_pct:.0f}% voted YES
Parliament result: {"Approved" if citizen_yes_pct < 50 else "Matches citizen majority"}

Rules:
- Statements must be NEUTRAL (not leading or biased)
- Citizens answer: Agree / Disagree / Neutral
- Must reflect a genuine political divide
- Keep each statement under 100 characters
- Category must be one of: Economy, Environment, Social, Health, Education, Labor, Defense, Technology

Respond ONLY with valid JSON (no explanation):
[
  {{"text_en": "...", "category_en": "...", "explanation_en": "One sentence explaining why this divides opinion"}},
  {{"text_en": "...", "category_en": "...", "explanation_en": "..."}}
]"""

    response = await ollama_generate(prompt, max_tokens=500)
    if not response:
        return []

    # Parse JSON from Ollama response
    try:
        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if not json_match:
            return []
        questions_en = json.loads(json_match.group())
    except (json.JSONDecodeError, AttributeError) as e:
        logger.error("Failed to parse compass questions JSON: %s", e)
        return []

    # Translate EN → EL via DeepL
    results = []
    for q in questions_en[:2]:
        text_en = q.get("text_en", "").strip()
        explanation_en = q.get("explanation_en", "").strip()
        category_en = q.get("category_en", "General").strip()

        if not text_en or len(text_en) < 10:
            continue

        # Translate to Greek
        text_el = await deepl_translate(text_en, "EL", "EN")
        explanation_el = await deepl_translate(explanation_en, "EL", "EN") if explanation_en else ""

        # Map category
        cat_map = {
            "Economy": "Οικονομία", "Environment": "Περιβάλλον & Ενέργεια",
            "Social": "Κοινωνική Πολιτική", "Health": "Υγεία",
            "Education": "Παιδεία", "Labor": "Εργασία & Οικονομία",
            "Defense": "Άμυνα & Εξωτερική Πολιτική",
            "Technology": "Τεχνολογία & Ψηφιακή Πολιτική",
        }
        category_el = cat_map.get(category_en, "Οικονομία")

        if text_el:
            results.append({
                "text_el": text_el,
                "text_en": text_en,
                "explanation_el": explanation_el,
                "explanation_en": explanation_en,
                "category": category_el,
                "source_bill_id": bill.id,
            })

    return results


async def run_compass_update(db: AsyncSession) -> list[dict]:
    """
    Generate new compass questions from recent bills.
    Returns list of generated questions (stored as pending in DB).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    # Get recent bills with votes
    result = await db.execute(
        select(ParliamentBill)
        .where(ParliamentBill.created_at >= cutoff)
        .where(ParliamentBill.status.in_([
            BillStatus.PARLIAMENT_VOTED, BillStatus.OPEN_END, BillStatus.ACTIVE,
        ]))
        .order_by(ParliamentBill.created_at.desc())
        .limit(10)
    )
    bills = result.scalars().all()

    all_questions = []
    for bill in bills:
        # Get citizen vote stats
        yes_count = await db.scalar(
            select(func.count()).where(
                CitizenVote.bill_id == bill.id,
                CitizenVote.vote == VoteChoice.YES,
            )
        ) or 0
        total_count = await db.scalar(
            select(func.count()).where(CitizenVote.bill_id == bill.id)
        ) or 0
        citizen_yes_pct = (yes_count / total_count * 100) if total_count > 0 else 50.0

        questions = await generate_questions_from_bill(bill, citizen_yes_pct, db)

        # Store in DB as pending (is_active=False)
        for q in questions:
            stmt = Statement(
                text_el=q["text_el"],
                text_en=q["text_en"],
                explanation_el=q.get("explanation_el"),
                explanation_en=q.get("explanation_en"),
                category=q["category"],
                source_bill_id=q["source_bill_id"],
                is_active=False,  # PENDING — admin must approve
                generated_by="ollama",
                version=2,
                display_order=99,
            )
            db.add(stmt)
            all_questions.append(q)

        await asyncio.sleep(3)  # rate limiting between bills

    await db.commit()
    logger.info("Generated %d compass questions from %d bills", len(all_questions), len(bills))
    return all_questions
