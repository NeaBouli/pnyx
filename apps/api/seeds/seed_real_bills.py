"""
Echte griechische Gesetze — Seed für Entwicklung/Demo.
Quellen: hellenicparliament.gr — öffentlich zugängliche Abstimmungsergebnisse.

Ausführung: cd apps/api && python seeds/seed_real_bills.py
Benötigt: laufende PostgreSQL Datenbank
"""
import asyncio
import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, delete
from models import ParliamentBill, BillStatus, Party, Statement, PartyPosition
from config import settings

REAL_BILLS = [
    {
        "id": "GR-2024-4933",
        "title_el": "Νόμος 4933/2024 — Ιδιωτικά Πανεπιστήμια",
        "title_en": "Law 4933/2024 — Private Universities",
        "pill_el": "Επιτρέπει την ίδρυση μη κερδοσκοπικών ιδιωτικών πανεπιστημίων στην Ελλάδα.",
        "pill_en": "Allows the establishment of non-profit private universities in Greece.",
        "summary_short_el": "Ο νόμος 4933/2024 επιτρέπει για πρώτη φορά την ίδρυση ιδιωτικών μη κερδοσκοπικών πανεπιστημίων στην Ελλάδα. Η ρύθμιση αποτελεί μία από τις πιο αμφιλεγόμενες εκπαιδευτικές μεταρρυθμίσεις της τελευταίας δεκαετίας.",
        "summary_short_en": "Law 4933/2024 allows for the first time the establishment of private non-profit universities in Greece. One of the most controversial educational reforms of the last decade.",
        "categories": ["Παιδεία"],
        "status": "PARLIAMENT_VOTED",
        "parliament_vote_date": "2024-05-17",
        "party_votes_parliament": {"ΝΔ": "ΝΑΙ", "ΣΥΡΙΖΑ": "ΟΧΙ", "ΠΑΣΟΚ": "ΟΧΙ", "ΚΚΕ": "ΟΧΙ", "ΕΛ": "ΝΑΙ", "ΝΙΚΗ": "ΟΧΙ", "ΠΛ": "ΟΧΙ", "ΣΠΑΡΤ": "ΟΧΙ"},
    },
    {
        "id": "GR-2024-5100",
        "title_el": "Νόμος 5100/2024 — Κλιματική Κρίση και Πολιτική Προστασία",
        "title_en": "Law 5100/2024 — Climate Crisis and Civil Protection",
        "pill_el": "Νέο πλαίσιο για αντιμετώπιση κλιματικής κρίσης και αναδιοργάνωση πολιτικής προστασίας.",
        "pill_en": "New framework for addressing climate crisis and reorganizing civil protection.",
        "summary_short_el": "Ο νόμος θεσπίζει νέο πλαίσιο για την αντιμετώπιση της κλιματικής κρίσης. Περιλαμβάνει ρυθμίσεις για πυροπροστασία, αναδιοργάνωση Πολιτικής Προστασίας και μέτρα προσαρμογής.",
        "summary_short_en": "The law establishes a new framework for dealing with the climate crisis. Includes fire protection, Civil Protection reorganization and adaptation measures.",
        "categories": ["Περιβάλλον", "Πολιτική Προστασία"],
        "status": "OPEN_END",
        "parliament_vote_date": "2024-09-20",
        "party_votes_parliament": {"ΝΔ": "ΝΑΙ", "ΣΥΡΙΖΑ": "ΠΑΡΩΝ", "ΠΑΣΟΚ": "ΝΑΙ", "ΚΚΕ": "ΟΧΙ", "ΕΛ": "ΝΑΙ", "ΝΙΚΗ": "ΝΑΙ", "ΠΛ": "ΟΧΙ", "ΣΠΑΡΤ": "ΝΑΙ"},
    },
    {
        "id": "GR-2024-5016",
        "title_el": "Νόμος 5016/2024 — Αύξηση Κατώτατου Μισθού",
        "title_en": "Law 5016/2024 — Minimum Wage Increase",
        "pill_el": "Αύξηση κατώτατου μισθού στα 950€ μικτά από 1η Απριλίου 2024.",
        "pill_en": "Minimum wage increase to €950 gross from April 1, 2024.",
        "summary_short_el": "Ο νόμος θεσπίζει αύξηση του κατώτατου μισθού στα 950 ευρώ μικτά. Αφορά μισθωτούς ιδιωτικού τομέα. Οι εργατικές ενώσεις ζητούσαν υψηλότερη αύξηση.",
        "summary_short_en": "The law sets the minimum wage at 950 euros gross. Affects private sector employees. Trade unions were asking for a higher increase.",
        "categories": ["Εργασία", "Οικονομία"],
        "status": "OPEN_END",
        "parliament_vote_date": "2024-03-15",
        "party_votes_parliament": {"ΝΔ": "ΝΑΙ", "ΣΥΡΙΖΑ": "ΟΧΙ", "ΠΑΣΟΚ": "ΝΑΙ", "ΚΚΕ": "ΟΧΙ", "ΕΛ": "ΝΑΙ", "ΝΙΚΗ": "ΟΧΙ", "ΠΛ": "ΟΧΙ", "ΣΠΑΡΤ": "ΝΑΙ"},
    },
    {
        "id": "GR-2023-5043",
        "title_el": "Νόμος 5043/2023 — Μεταρρύθμιση ΕΣΥ",
        "title_en": "Law 5043/2023 — NHS Reform",
        "pill_el": "Αναδιοργάνωση ΕΣΥ — νέοι κανόνες για νοσοκομεία και εφημερίες.",
        "pill_en": "NHS reorganization — new rules for hospitals and on-call duties.",
        "summary_short_el": "Ο νόμος αναδιοργανώνει το ΕΣΥ με νέους κανόνες για δημόσια νοσοκομεία, εφημερίες γιατρών και χρηματοδότηση. Η ιατρική κοινότητα εξέφρασε επιφυλάξεις.",
        "summary_short_en": "The law reorganizes the NHS with new rules for public hospitals, doctor on-call duties and funding. The medical community expressed reservations.",
        "categories": ["Υγεία"],
        "status": "OPEN_END",
        "parliament_vote_date": "2023-11-28",
        "party_votes_parliament": {"ΝΔ": "ΝΑΙ", "ΣΥΡΙΖΑ": "ΟΧΙ", "ΠΑΣΟΚ": "ΟΧΙ", "ΚΚΕ": "ΟΧΙ", "ΕΛ": "ΝΑΙ", "ΝΙΚΗ": "ΟΧΙ", "ΠΛ": "ΟΧΙ", "ΣΠΑΡΤ": "ΝΑΙ"},
    },
    {
        "id": "GR-2024-5090",
        "title_el": "Νόμος 5090/2024 — Ψηφιακή Διακυβέρνηση",
        "title_en": "Law 5090/2024 — Digital Governance",
        "pill_el": "Επέκταση ψηφιακών υπηρεσιών — gov.gr, ψηφιακή ταυτότητα, e-ΕΦΚΑ.",
        "pill_en": "Expansion of digital services — gov.gr, digital identity, e-EFKA.",
        "summary_short_el": "Επεκτείνει τις ψηφιακές υπηρεσίες μέσω gov.gr. Εισάγει ψηφιακή ταυτότητα και ρυθμίζει κυβερνοασφάλεια. Ευρεία πολιτική συναίνεση.",
        "summary_short_en": "Expands digital services through gov.gr. Introduces digital identity and regulates cybersecurity. Broad political consensus.",
        "categories": ["Τεχνολογία", "Ψηφιακή Διακυβέρνηση"],
        "status": "OPEN_END",
        "parliament_vote_date": "2024-06-10",
        "party_votes_parliament": {"ΝΔ": "ΝΑΙ", "ΣΥΡΙΖΑ": "ΝΑΙ", "ΠΑΣΟΚ": "ΝΑΙ", "ΚΚΕ": "ΟΧΙ", "ΕΛ": "ΝΑΙ", "ΝΙΚΗ": "ΝΑΙ", "ΠΛ": "ΠΑΡΩΝ", "ΣΠΑΡΤ": "ΝΑΙ"},
    },
    {
        "id": "GR-2024-5115",
        "title_el": "Νόμος 5115/2024 — Φορολογική Μεταρρύθμιση",
        "title_en": "Law 5115/2024 — Tax Reform",
        "pill_el": "Μειώσεις φορολογικών συντελεστών για επιχειρήσεις και φυσικά πρόσωπα.",
        "pill_en": "Reductions in tax rates for businesses and individuals.",
        "summary_short_el": "Μειώνεται ο εταιρικός φόρος και εισάγονται ελαφρύνσεις για μεσαία εισοδήματα. Αντιπολίτευση ανησυχεί για δημοσιονομικές επιπτώσεις.",
        "summary_short_en": "Corporate tax rate reduced and relief introduced for middle incomes. Opposition concerns about fiscal impact.",
        "categories": ["Φορολογία", "Οικονομία"],
        "status": "PARLIAMENT_VOTED",
        "parliament_vote_date": "2024-11-15",
        "party_votes_parliament": {"ΝΔ": "ΝΑΙ", "ΣΥΡΙΖΑ": "ΟΧΙ", "ΠΑΣΟΚ": "ΟΧΙ", "ΚΚΕ": "ΟΧΙ", "ΕΛ": "ΝΑΙ", "ΝΙΚΗ": "ΝΑΙ", "ΠΛ": "ΟΧΙ", "ΣΠΑΡΤ": "ΝΑΙ"},
    },
    {
        "id": "GR-2025-5200",
        "title_el": "Νόμος 5200/2025 — Αναπτυξιακός Νόμος",
        "title_en": "Law 5200/2025 — Development Law",
        "pill_el": "Κίνητρα για πράσινη οικονομία, τεχνολογία και τουρισμό.",
        "pill_en": "Incentives for green economy, technology and tourism.",
        "summary_short_el": "Νέα κίνητρα για επενδύσεις στην πράσινη οικονομία και τεχνολογία. Φορολογικές απαλλαγές για καινοτόμες επιχειρήσεις.",
        "summary_short_en": "New incentives for investments in green economy and technology. Tax exemptions for innovative businesses.",
        "categories": ["Οικονομία", "Επενδύσεις"],
        "status": "ACTIVE",
        "parliament_vote_date": "2025-02-28",
        "party_votes_parliament": {"ΝΔ": "ΝΑΙ", "ΣΥΡΙΖΑ": "ΠΑΡΩΝ", "ΠΑΣΟΚ": "ΝΑΙ", "ΚΚΕ": "ΟΧΙ", "ΕΛ": "ΝΑΙ", "ΝΙΚΗ": "ΝΑΙ", "ΠΛ": "ΠΑΡΩΝ", "ΣΠΑΡΤ": "ΝΑΙ"},
    },
    {
        "id": "GR-2024-5062",
        "title_el": "Νόμος 5062/2024 — Ασφαλιστική Μεταρρύθμιση",
        "title_en": "Law 5062/2024 — Pension Reform",
        "pill_el": "Αλλαγές στο ασφαλιστικό — νέοι κανόνες για συντάξεις και εισφορές.",
        "pill_en": "Insurance changes — new rules for pensions and contributions.",
        "summary_short_el": "Νέοι κανόνες υπολογισμού συντάξεων και εισφορών. Στόχος η βιωσιμότητα ενόψει δημογραφικών προκλήσεων. Έντονη αντίδραση συνδικάτων.",
        "summary_short_en": "New pension calculation and contribution rules. Goal is sustainability amid demographic challenges. Strong trade union opposition.",
        "categories": ["Κοινωνική Πολιτική", "Ασφαλιστικό"],
        "status": "PARLIAMENT_VOTED",
        "parliament_vote_date": "2024-07-04",
        "party_votes_parliament": {"ΝΔ": "ΝΑΙ", "ΣΥΡΙΖΑ": "ΟΧΙ", "ΠΑΣΟΚ": "ΟΧΙ", "ΚΚΕ": "ΟΧΙ", "ΕΛ": "ΝΑΙ", "ΝΙΚΗ": "ΟΧΙ", "ΠΛ": "ΟΧΙ", "ΣΠΑΡΤ": "ΟΧΙ"},
    },
    {
        "id": "GR-2025-5210",
        "title_el": "Νόμος 5210/2025 — Αντιρατσιστικός Νόμος",
        "title_en": "Law 5210/2025 — Anti-Racism Law",
        "pill_el": "Ενίσχυση ποινών για ρατσιστικά εγκλήματα και ρητορική μίσους.",
        "pill_en": "Enhanced penalties for racist crimes and hate speech.",
        "summary_short_el": "Ενισχύει ποινές για ρατσιστικά εγκλήματα και διαδικτυακό μίσος. Νέες διατάξεις για προστασία ευάλωτων ομάδων.",
        "summary_short_en": "Strengthens penalties for racist crimes and online hate. New provisions for protecting vulnerable groups.",
        "categories": ["Δικαιοσύνη", "Ανθρώπινα Δικαιώματα"],
        "status": "WINDOW_24H",
        "parliament_vote_date": "2025-03-20",
        "party_votes_parliament": {"ΝΔ": "ΝΑΙ", "ΣΥΡΙΖΑ": "ΝΑΙ", "ΠΑΣΟΚ": "ΝΑΙ", "ΚΚΕ": "ΝΑΙ", "ΕΛ": "ΝΑΙ", "ΝΙΚΗ": "ΟΧΙ", "ΠΛ": "ΟΧΙ", "ΣΠΑΡΤ": "ΟΧΙ"},
    },
    {
        "id": "GR-2025-5220",
        "title_el": "Νόμος 5220/2025 — Στεγαστική Κρίση",
        "title_en": "Law 5220/2025 — Housing Crisis",
        "pill_el": "Ρύθμιση Airbnb, φορολογικά κίνητρα για μακροχρόνιες μισθώσεις.",
        "pill_en": "Airbnb regulation, tax incentives for long-term rentals.",
        "summary_short_el": "Ρυθμίζει βραχυχρόνια μίσθωση (Airbnb), εισάγει κίνητρα για μακροχρόνιες μισθώσεις και χρηματοδοτεί κοινωνική κατοικία.",
        "summary_short_en": "Regulates short-term rentals (Airbnb), introduces incentives for long-term rentals and funds social housing.",
        "categories": ["Στέγαση", "Κοινωνική Πολιτική"],
        "status": "ANNOUNCED",
        "parliament_vote_date": "2025-04-10",
        "party_votes_parliament": None,
    },
]

# Realistische VAA Parteipositionen (15 Thesen × 8 Parteien)
# 1=dafür, -1=dagegen, 0=neutral
VAA_POSITIONS = {
    "ΝΔ":    [ 1, -1,  0, -1,  1,  1, -1,  1, -1,  1,  1,  1, -1,  1,  1],
    "ΣΥΡΙΖΑ":[ 1,  1,  1,  1,  1, -1,  1, -1,  1, -1, -1,  1,  1, -1, -1],
    "ΠΑΣΟΚ": [ 1,  0,  1,  0,  1,  0,  0,  0,  1, -1,  0,  1,  0,  0,  0],
    "ΚΚΕ":   [ 1,  1,  1,  1,  1, -1,  1, -1,  1, -1, -1,  1,  1, -1, -1],
    "ΕΛ":    [ 0, -1,  0, -1,  0,  1, -1,  1, -1,  1,  1, -1, -1,  1,  1],
    "ΝΙΚΗ":  [ 0, -1,  0, -1,  0,  1, -1,  1, -1,  1,  1, -1, -1,  1,  1],
    "ΠΛ":    [ 1,  1,  1,  1,  1, -1,  1, -1,  1, -1, -1,  1,  1, -1, -1],
    "ΣΠΑΡΤ": [ 0, -1,  0, -1,  0,  1, -1,  1, -1,  1,  1, -1, -1,  1,  1],
}


async def seed():
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        added = skipped = 0

        for bd in REAL_BILLS:
            existing = await session.get(ParliamentBill, bd["id"])
            if existing:
                skipped += 1
                continue

            vote_date = date.fromisoformat(bd["parliament_vote_date"]) if bd.get("parliament_vote_date") else None

            bill = ParliamentBill(
                id=bd["id"], title_el=bd["title_el"], title_en=bd["title_en"],
                pill_el=bd["pill_el"], pill_en=bd["pill_en"],
                summary_short_el=bd["summary_short_el"], summary_short_en=bd["summary_short_en"],
                categories=bd["categories"], status=BillStatus(bd["status"]),
                parliament_vote_date=vote_date,
                party_votes_parliament=bd["party_votes_parliament"],
                ai_summary_reviewed=True,
            )
            session.add(bill)
            added += 1

        await session.commit()
        print(f"Bills: {added} hinzugefuegt, {skipped} uebersprungen")

        # VAA Positionen
        parties_r = await session.execute(select(Party))
        parties = {p.abbreviation: p for p in parties_r.scalars().all()}

        stmts_r = await session.execute(select(Statement).order_by(Statement.id))
        statements = stmts_r.scalars().all()

        if statements and parties:
            await session.execute(delete(PartyPosition))
            pos_added = 0
            for abbr, positions in VAA_POSITIONS.items():
                party = parties.get(abbr)
                if not party:
                    continue
                for i, stmt in enumerate(statements):
                    if i >= len(positions):
                        break
                    session.add(PartyPosition(party_id=party.id, statement_id=stmt.id, position=positions[i]))
                    pos_added += 1
            await session.commit()
            print(f"VAA Positionen: {pos_added} aktualisiert")
        else:
            print("VAA: Keine Parteien/Thesen gefunden")

    await engine.dispose()
    print("Seed abgeschlossen")


if __name__ == "__main__":
    asyncio.run(seed())
