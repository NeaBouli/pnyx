"""
Seed 13 Greek Periferias (Regions) + major Dimoi (Municipalities).
Run: docker exec ekklesia-api python seeds/seed_municipal.py
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import engine, get_db_context
from models import Periferia, Dimos
from sqlalchemy import select

# 13 Periferias of Greece (ISO 3166-2:GR codes)
PERIFERIAS = [
    ("Αττικής", "Attica", "GR-I"),
    ("Κεντρικής Μακεδονίας", "Central Macedonia", "GR-B"),
    ("Δυτικής Ελλάδας", "Western Greece", "GR-G"),
    ("Θεσσαλίας", "Thessaly", "GR-E"),
    ("Κρήτης", "Crete", "GR-M"),
    ("Πελοποννήσου", "Peloponnese", "GR-J"),
    ("Ανατολικής Μακεδονίας και Θράκης", "Eastern Macedonia and Thrace", "GR-A"),
    ("Ηπείρου", "Epirus", "GR-D"),
    ("Δυτικής Μακεδονίας", "Western Macedonia", "GR-C"),
    ("Στερεάς Ελλάδας", "Central Greece", "GR-H"),
    ("Ιονίων Νήσων", "Ionian Islands", "GR-F"),
    ("Βορείου Αιγαίου", "North Aegean", "GR-K"),
    ("Νοτίου Αιγαίου", "South Aegean", "GR-L"),
]

# Major dimoi per periferia (population > 50k or capital of periferia)
DIMOI = {
    "GR-I": [
        ("Αθηναίων", "Athens", 664046),
        ("Πειραιώς", "Piraeus", 163688),
        ("Περιστερίου", "Peristeri", 139981),
        ("Καλλιθέας", "Kallithea", 100641),
        ("Αμαρουσίου", "Marousi", 72333),
        ("Γλυφάδας", "Glyfada", 87305),
        ("Ηλιουπόλεως", "Ilioupoli", 78153),
        ("Νίκαιας-Αγ.Ι.Ρέντη", "Nikaia-Rentis", 93609),
    ],
    "GR-B": [
        ("Θεσσαλονίκης", "Thessaloniki", 325182),
        ("Καλαμαριάς", "Kalamaria", 91518),
        ("Νεάπολης-Συκεών", "Neapoli-Sykies", 84741),
        ("Παύλου Μελά", "Pavlos Melas", 99245),
        ("Αμπελοκήπων-Μενεμένης", "Ampelokipoi-Menemeni", 52127),
    ],
    "GR-G": [
        ("Πατρέων", "Patras", 213984),
        ("Αγρινίου", "Agrinio", 94181),
    ],
    "GR-E": [
        ("Λαρισαίων", "Larissa", 162591),
        ("Βόλου", "Volos", 144449),
        ("Τρικκαίων", "Trikala", 81355),
    ],
    "GR-M": [
        ("Ηρακλείου", "Heraklion", 173993),
        ("Χανίων", "Chania", 108642),
        ("Ρεθύμνης", "Rethymno", 55525),
    ],
    "GR-J": [
        ("Καλαμάτας", "Kalamata", 69849),
        ("Τρίπολης", "Tripoli", 47254),
    ],
    "GR-A": [
        ("Καβάλας", "Kavala", 70501),
        ("Κομοτηνής", "Komotini", 66919),
        ("Αλεξανδρούπολης", "Alexandroupoli", 72959),
    ],
    "GR-D": [
        ("Ιωαννιτών", "Ioannina", 112486),
        ("Άρτας", "Arta", 43000),
    ],
    "GR-C": [
        ("Κοζάνης", "Kozani", 71388),
    ],
    "GR-H": [
        ("Λαμιέων", "Lamia", 75315),
        ("Χαλκιδέων", "Chalkida", 92809),
    ],
    "GR-F": [
        ("Κερκυραίων", "Corfu", 102071),
    ],
    "GR-K": [
        ("Μυτιλήνης", "Mytilene", 37890),
    ],
    "GR-L": [
        ("Ρόδου", "Rhodes", 115490),
        ("Σύρου-Ερμούπολης", "Syros-Ermoupoli", 21507),
    ],
}


async def seed():
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        inserted_p = 0
        updated_p = 0
        for name_el, name_en, code in PERIFERIAS:
            existing = (await db.execute(select(Periferia).where(Periferia.code == code))).scalar_one_or_none()
            if existing:
                existing.name_el = name_el
                existing.name_en = name_en
                updated_p += 1
            else:
                db.add(Periferia(name_el=name_el, name_en=name_en, code=code, is_active=True))
                inserted_p += 1
        await db.commit()
        print(f"Periferias: {inserted_p} inserted, {updated_p} updated")

        # Fetch periferia IDs
        periferias = {p.code: p.id for p in (await db.execute(select(Periferia))).scalars().all()}

        inserted_d = 0
        updated_d = 0
        for code, dimoi in DIMOI.items():
            periferia_id = periferias.get(code)
            if not periferia_id:
                print(f"  WARNING: periferia {code} not found, skipping dimoi")
                continue
            for name_el, name_en, pop in dimoi:
                existing = (await db.execute(
                    select(Dimos).where(Dimos.name_el == name_el, Dimos.periferia_id == periferia_id)
                )).scalar_one_or_none()
                if existing:
                    existing.name_en = name_en
                    existing.population = pop
                    updated_d += 1
                else:
                    db.add(Dimos(
                        name_el=name_el, name_en=name_en,
                        periferia_id=periferia_id, population=pop, is_active=True
                    ))
                    inserted_d += 1
        await db.commit()
        print(f"Dimoi: {inserted_d} inserted, {updated_d} updated")

    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(seed())
