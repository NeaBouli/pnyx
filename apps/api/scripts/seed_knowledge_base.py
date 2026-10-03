"""Canonical RAG knowledge-base catalog and its exact database synchronizer.

``ENTRIES`` is the only repository authority for the ``knowledge_base`` table.

    python scripts/seed_knowledge_base.py sync   # one transaction: table := ENTRIES
    python scripts/seed_knowledge_base.py check  # read-only drift check

Rows are matched on the natural key ``(category, title_en)``. Sync keeps the
lowest id per key, updates changed fields, inserts missing rows and deletes
stale rows and duplicate keys, then re-verifies before commit.
Exit codes: 0 = table matches ENTRIES, 1 = drift (check), 2 = error/rolled back.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from database import engine
from models import KnowledgeBase

ENTRIES = [
    ("mission", "Τι είναι η εκκλησία;", "What is ekklesia?",
     "Η εκκλησία του έθνους είναι μια ανεξάρτητη πρωτοβουλία πολιτών για άμεση δημοκρατία στην Ελλάδα. Επιτρέπει στους πολίτες να ψηφίζουν ανώνυμα σε πραγματικά νομοσχέδια της Βουλής. ΔΕΝ είναι κρατική υπηρεσία. Οι ψηφοφορίες δεν έχουν νομική δεσμευτικότητα. Είναι εργαλείο διαφάνειας και δημοκρατικής εκπαίδευσης. © 2026 V-Labs Development, MIT License.",
     "ekklesia tou ethnous is an independent civic initiative for direct democracy in Greece. Citizens vote anonymously on real Hellenic Parliament bills. NOT a government service. Votes have no legal binding. Transparency and civic education tool.",
     '["ekklesia","democracy","parliament","civic","initiative","vote"]', 1),

    ("privacy", "Πώς προστατεύεται η ανωνυμία μου;", "How is my anonymity protected?",
     "Η εκκλησία χρησιμοποιεί κρυπτογραφία Ed25519 για υπογραφές ψήφων. Ο αριθμός τηλεφώνου ΠΟΤΕ δεν αποθηκεύεται. Μόνο κρυπτογραφικό hash (nullifier) αποθηκεύεται — δεν μπορεί να αντιστραφεί. Το ιδιωτικό κλειδί μένει στη συσκευή σου (Web Beta: localStorage του browser· εφαρμογή κινητού: Expo SecureStore). Ο server το δημιουργεί μία φορά κατά την επαλήθευση και σου το παραδίδει μόνο μία φορά· δεν το αποθηκεύει.",
     "ekklesia uses Ed25519 cryptography for vote signatures. Phone number is NEVER stored. Only a cryptographic nullifier hash is stored — it cannot be reversed. The private key stays on your device (Web Beta: browser localStorage; mobile app: Expo SecureStore). The server creates it once during verification and hands it to you a single time; it does not store it.",
     '["privacy","anonymity","cryptography","Ed25519","nullifier","phone"]', 1),

    ("process", "Πώς ψηφίζω;", "How do I vote?",
     "1. Κατέβασε την εφαρμογή ekklesia. 2. Ολοκλήρωσε τον έλεγχο HLR, ο οποίος ελέγχει μόνο κατάσταση και συμβατότητα ελληνικού αριθμού χωρίς SMS. 3. Δήλωσε Περιφέρεια και Δήμο για τις τοπικές αποφάσεις. 4. Ψήφισε ΝΑΙ/ΟΧΙ/ΑΠΟΧΗ μόνο στα εθνικά θέματα και στα τοπικά scopes όπου δικαιούσαι. 5. Κάθε έγκυρη ψήφος έχει το ίδιο βάρος: ένα άτομο = μία ψήφος.",
     "1. Download the ekklesia app. 2. Complete the HLR check, which checks only Greek-number status and compatibility without SMS. 3. Set your Region and Municipality for local decisions. 4. Vote YES/NO/ABSTAIN only on national matters and local scopes where you are eligible. 5. Every valid vote has equal weight: one person equals one vote.",
     '["vote","process","HLR","verification","app","download"]', 1),

    ("process", "Μπορώ να διορθώσω την ψήφο μου;", "Can I correct my vote?",
     "Δεν μπορείτε να ψηφίσετε δύο φορές στο ίδιο νομοσχέδιο. Αν είναι ενεργό το παράθυρο διόρθωσης (WINDOW_24H), η εφαρμογή μπορεί να επιτρέπει μία διόρθωση ψήφου σύμφωνα με την κατάσταση του νομοσχεδίου. Εκτός αυτού του παραθύρου η ψήφος δεν αλλάζει.",
     "You cannot vote twice on the same bill. If the correction window (WINDOW_24H) is active, the app may allow one vote correction depending on the bill status. Outside that window, the vote cannot be changed.",
     '["vote","correction","change vote","WINDOW_24H","duplicate","bill"]', 1),

    ("faq", "Πόσο ζυγίζει η ψήφος μου;", "How much does my vote weigh?",
     "Κάθε έγκυρη ψήφος έχει βάρος x1.0, ανεξάρτητα από τη μέθοδο επαλήθευσης: ένα άτομο = μία ψήφος. Η ισχυρότερη επαλήθευση περιορίζει τις διπλές εγγραφές· δεν πολλαπλασιάζει την ψήφο. Η gov.gr μέθοδος είναι μόνο σχεδιασμός Alpha 0.1 και δεν είναι ενεργή στη Beta.",
     "Every valid vote has weight x1.0 regardless of verification method. Stronger verification limits duplicate registrations; it does not multiply a vote. The gov.gr method is an Alpha 0.1 design only and is not active in Beta.",
     '["vote","weight","gov.gr","verification","x1","equal"]', 1),

    ("govgr", "Τι είναι το gov.gr OAuth;", "What is gov.gr OAuth?",
     "Το gov.gr OAuth ή η επαλήθευση νέου challenge-bound QR/PDF είναι σχεδιασμός Alpha 0.1 και δεν είναι ενεργός στη Beta. Ο QR ή ο κωδικός ελέγχει την εγκυρότητα του εγγράφου, όχι από μόνος του την ταυτότητα του προσώπου που το παρουσιάζει. Απαιτούνται εγκεκριμένη επίσημη διασύνδεση ή πλήρης eSeal validation, έλεγχος κατόχου, DPIA, σχέδιο credential migration, ανεξάρτητος security/privacy review και sandbox canary.",
     "Gov.gr OAuth or fresh challenge-bound QR/PDF verification is an Alpha 0.1 design and is not active in Beta. A QR code or verification code checks document validity; by itself it does not authenticate the person presenting it. An approved official integration or full eSeal validation, holder authentication, DPIA, credential-migration design, independent security/privacy review and sandbox canary are required.",
     '["gov.gr","OAuth","government","approval","AMKA","mayor","deferred","gated"]', 1),

    ("faq", "Είναι ασφαλής η εφαρμογή;", "Is the app safe?",
     "Ναι. Ανοιχτού κώδικα (MIT License). Κώδικας δημόσια στο GitHub (NeaBouli/pnyx). Δεν αποθηκεύουμε προσωπικά δεδομένα. Δεν πουλάμε δεδομένα. Server σε Hetzner (Ευρώπη) — GDPR compliant.",
     "Yes. Open source (MIT License). Code public on GitHub (NeaBouli/pnyx). No personal data stored. No data sold. Server in Hetzner (Europe) — GDPR compliant.",
     '["safety","open source","GDPR","privacy","GitHub","secure"]', 1),

    ("concept", "Δείκτης Απόκλισης", "Divergence Index",
     "Ο Δείκτης Απόκλισης μετρά πόσο διαφέρουν οι ψήφοι των πολιτών από τις αποφάσεις της Βουλής. Υψηλή απόκλιση = βουλευτές ψηφίζουν διαφορετικά. Χαμηλή = αντιπροσωπεύουν τη βούληση πολιτών.",
     "Divergence Index measures how much citizen votes differ from Parliament. High = MPs vote differently. Low = MPs represent citizens.",
     '["divergence","parliament","citizens","index","score"]', 2),

    ("concept", "Τι είναι το CPLM;", "What is CPLM?",
     "Το CPLM (Citizens Political Liquid Mirror) είναι δημόσιο, ανώνυμο συγκεντρωτικό σήμα που δείχνει τη συνολική πολιτική θέση των συμμετεχόντων πολιτών με βάση τις ψήφους τους. Δεν αποκαλύπτει μεμονωμένες ψήφους ή ταυτότητες.",
     "CPLM (Citizens Political Liquid Mirror) is a public, anonymous aggregate signal showing the overall political position of participating citizens based on their votes. It does not reveal individual votes or identities.",
     '["CPLM","liquid mirror","political mirror","aggregate","analytics","citizens"]', 1),

    ("privacy", "Τι είναι το nullifier hash;", "What is a nullifier hash?",
     "Το nullifier hash είναι ένας μη αναστρέψιμος κρυπτογραφικός αναγνωριστής που επιτρέπει στο σύστημα να ελέγχει μοναδικότητα χωρίς να αποθηκεύει τον αριθμό τηλεφώνου. Το Ed25519 χρησιμοποιείται για ψηφιακές υπογραφές ψήφων, όχι ως γεννήτρια του nullifier.",
     "A nullifier hash is a non-reversible cryptographic identifier used to enforce uniqueness without storing the phone number. Ed25519 is used for vote signatures; it is not the mechanism that generates the nullifier hash.",
     '["nullifier","hash","privacy","phone","unique","Ed25519"]', 1),

    ("privacy", "Τι γίνεται αν χάσω το ιδιωτικό κλειδί;", "What if I lose my private key?",
     "Το σημείο αποθήκευσης του ιδιωτικού κλειδιού εξαρτάται από την πλατφόρμα. Web Beta: φυλάσσεται στο localStorage του browser — απλή αποθήκευση browser, όχι iOS Keychain ή Android Keystore. Εφαρμογή κινητού: αποθηκεύεται μέσω Expo SecureStore, που χρησιμοποιεί Android Keystore και, στην υλοποιημένη διαδρομή κώδικα iOS, iOS Keychain. Ο server δημιουργεί το ζεύγος κλειδιών μία φορά κατά την επαλήθευση και σας παραδίδει το ιδιωτικό κλειδί μόνο μία φορά· δεν το αποθηκεύει και δεν μπορεί να το ανακτήσει αργότερα. Αν χαθεί, ακολουθείτε μόνο την επίσημη ροή επαλήθευσης/επανέκδοσης που παρέχει η εφαρμογή· δεν υπάρχει μυστική ανάκτηση από τον server.",
     "Where your private key is stored depends on the platform. Web Beta: it is kept in the browser's localStorage — plain browser storage, not iOS Keychain or Android Keystore. Mobile app: it is stored via Expo SecureStore, which uses Android Keystore and, in the implemented iOS code path, iOS Keychain. The server creates the key pair once during verification and hands you the private key a single time; it does not store it and cannot recover it later. If it is lost, use only the official app re-verification/key-rotation flow; there is no hidden server-side recovery process.",
     '["private key","lost key","recovery","device","localStorage","SecureStore","keychain","keystore"]', 1),

    ("process", "Πώς κατεβάζω την εφαρμογή Android;", "How do I download the Android app?",
     "Η εφαρμογή Android διανέμεται μέσω των επίσημων καναλιών που ανακοινώνει το ekklesia.gr, όπως η άμεση λήψη APK, F-Droid/IzzyOnDroid ή Google Play όταν είναι διαθέσιμο. Χρησιμοποιείτε μόνο συνδέσμους από το ekklesia.gr ή το επίσημο repository.",
     "The Android app is distributed through official channels announced by ekklesia.gr, such as direct APK download, F-Droid/IzzyOnDroid, or Google Play when available. Use only links from ekklesia.gr or the official repository.",
     '["android","download","apk","fdroid","izzyondroid","google play","app"]', 1),

    ("process", "Δήμοι και Διαύγεια", "Municipal governance and Diavgeia",
     "Η πλατφόρμα περιλαμβάνει και δημοτικό/περιφερειακό πεδίο μέσω Διαύγειας: οι πολίτες μπορούν να βλέπουν σχετικές αποφάσεις και, όπου η λειτουργία είναι ενεργή, να συμμετέχουν σε μη δεσμευτικές ψηφοφορίες για τοπικά θέματα.",
     "The platform includes municipal/regional scope through Diavgeia: citizens can view relevant decisions and, where the feature is active, participate in non-binding votes on local issues.",
     '["municipal","municipality","dimos","δήμος","diavgeia","διαύγεια","local"]', 1),

    ("forum", "Τι είναι η πνύκα;", "What is pnyx?",
     "Η πνύκα (pnyx.ekklesia.gr) είναι το δημόσιο forum της εκκλησίας. Συζήτηση νομοσχεδίων, προτάσεις, ανταλλαγή απόψεων. Σύνδεση: SSO (ekklesia account) ή Email/Google. Επαληθευμένοι πολίτες έχουν δικαίωμα ψήφου στο ekklesia.gr — στο forum μόνο συζήτηση.",
     "pnyx (pnyx.ekklesia.gr) is ekklesia public forum. Bill discussions, proposals, exchange views. Login: SSO (ekklesia) or Email/Google. Verified citizens have voting rights on ekklesia.gr — forum is discussion only.",
     '["pnyx","forum","discussion","community","debate"]', 2),
]


FIELDS = ("category", "title_el", "title_en", "content_el", "content_en", "keywords", "priority")
_TEXT_FIELDS = ("category", "title_el", "title_en", "content_el", "content_en")
_CATEGORY_MAX = 50  # models.KnowledgeBase.category String(50)
TABLE = KnowledgeBase.__table__

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_ERROR = 2

NaturalKey = tuple[Any, Any]
Catalog = dict[NaturalKey, dict[str, Any]]


class CatalogError(ValueError):
    """ENTRIES is malformed; nothing may be written."""


class SyncVerificationError(RuntimeError):
    """The table still differs from ENTRIES after applying the plan."""


def canonical_rows(entries: Sequence[tuple] = ENTRIES) -> Catalog:
    """Validate ENTRIES and return it keyed by the unique natural key."""
    rows: Catalog = {}
    for index, entry in enumerate(entries):
        if len(entry) != len(FIELDS):
            raise CatalogError(f"entry {index}: expected {len(FIELDS)} fields, got {len(entry)}")
        values = dict(zip(FIELDS, entry))
        for name in _TEXT_FIELDS:
            if not isinstance(values[name], str) or not values[name].strip():
                raise CatalogError(f"entry {index}: {name} must be a non-empty string")
        if len(values["category"]) > _CATEGORY_MAX:
            raise CatalogError(f"entry {index}: category longer than {_CATEGORY_MAX}")
        try:
            keywords = json.loads(values["keywords"])
        except (TypeError, ValueError) as exc:
            raise CatalogError(f"entry {index}: keywords must be a JSON array string") from exc
        if not isinstance(keywords, list) or not all(isinstance(k, str) and k.strip() for k in keywords):
            raise CatalogError(f"entry {index}: keywords must be a JSON array of non-empty strings")
        values["keywords"] = keywords
        if type(values["priority"]) is not int:
            raise CatalogError(f"entry {index}: priority must be an int")
        key = (values["category"], values["title_en"])
        if key in rows:
            raise CatalogError(f"entry {index}: duplicate natural key {key!r}")
        rows[key] = values
    return rows


@dataclass
class SyncPlan:
    inserts: list[NaturalKey] = field(default_factory=list)
    updates: list[tuple[int, NaturalKey]] = field(default_factory=list)
    stale: list[int] = field(default_factory=list)
    duplicates: list[int] = field(default_factory=list)

    @property
    def deletes(self) -> list[int]:
        return sorted(self.stale + self.duplicates)

    @property
    def is_empty(self) -> bool:
        return not (self.inserts or self.updates or self.stale or self.duplicates)

    def summary(self) -> str:
        """Counts, keys and ids only — never row content."""
        parts = [
            f"missing={len(self.inserts)}",
            f"changed={len(self.updates)}",
            f"stale={len(self.stale)}",
            f"duplicate={len(self.duplicates)}",
        ]
        details = [f"  missing {key!r}" for key in self.inserts]
        details += [f"  changed id={row_id} {key!r}" for row_id, key in self.updates]
        details += [f"  stale id={row_id}" for row_id in self.stale]
        details += [f"  duplicate id={row_id}" for row_id in self.duplicates]
        return " ".join(parts) + ("\n" + "\n".join(details) if details else "")


def plan_sync(catalog: Catalog, db_rows: Iterable[dict[str, Any]]) -> SyncPlan:
    """Diff DB rows against the catalog. The lowest id per natural key is kept."""
    by_key: dict[NaturalKey, list[dict[str, Any]]] = {}
    for row in sorted(db_rows, key=lambda r: r["id"]):
        by_key.setdefault((row["category"], row["title_en"]), []).append(row)

    plan = SyncPlan()
    for key, rows in by_key.items():
        if key not in catalog:
            plan.stale.extend(row["id"] for row in rows)
            continue
        keeper, *extra = rows
        plan.duplicates.extend(row["id"] for row in extra)
        if any(keeper[name] != catalog[key][name] for name in FIELDS):
            plan.updates.append((keeper["id"], key))
    plan.inserts = [key for key in catalog if key not in by_key]
    return plan


async def load_rows(conn: AsyncConnection) -> list[dict[str, Any]]:
    result = await conn.execute(
        select(TABLE.c.id, *(TABLE.c[name] for name in FIELDS)).order_by(TABLE.c.id)
    )
    return [dict(row._mapping) for row in result]


async def apply_plan(conn: AsyncConnection, catalog: Catalog, plan: SyncPlan) -> None:
    if plan.deletes:
        await conn.execute(delete(TABLE).where(TABLE.c.id.in_(plan.deletes)))
    for row_id, key in plan.updates:
        await conn.execute(update(TABLE).where(TABLE.c.id == row_id).values(**catalog[key]))
    for key in plan.inserts:
        await conn.execute(insert(TABLE).values(**catalog[key]))


async def sync(conn: AsyncConnection, catalog: Catalog) -> SyncPlan:
    """Make the table equal the catalog inside the caller's transaction."""
    # Blocks concurrent writers (incl. a second sync); runtime reads stay unblocked.
    await conn.execute(text("LOCK TABLE knowledge_base IN SHARE ROW EXCLUSIVE MODE"))
    plan = plan_sync(catalog, await load_rows(conn))
    await apply_plan(conn, catalog, plan)
    remaining = plan_sync(catalog, await load_rows(conn))
    if not remaining.is_empty:
        raise SyncVerificationError(remaining.summary())
    return plan


async def check(conn: AsyncConnection, catalog: Catalog) -> SyncPlan:
    """Read-only diff; the transaction is marked READ ONLY before any read."""
    await conn.execute(text("SET TRANSACTION READ ONLY"))
    return plan_sync(catalog, await load_rows(conn))


async def run(mode: str, db_engine: AsyncEngine) -> int:
    catalog = canonical_rows(ENTRIES)  # validated before any connection is opened
    try:
        if mode == "sync":
            async with db_engine.begin() as conn:  # commit on success, rollback on any error
                plan = await sync(conn, catalog)
            print(f"knowledge_base sync ok ({len(catalog)} rows): {plan.summary()}")
            return EXIT_OK
        async with db_engine.connect() as conn:
            plan = await check(conn, catalog)
            await conn.rollback()
        if plan.is_empty:
            print(f"knowledge_base check ok: {len(catalog)} rows match ENTRIES")
            return EXIT_OK
        print(f"knowledge_base drift: {plan.summary()}", file=sys.stderr)
        return EXIT_DRIFT
    finally:
        await db_engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync or check knowledge_base against ENTRIES.")
    parser.add_argument("mode", choices=("sync", "check"))
    args = parser.parse_args(argv)
    try:
        return asyncio.run(run(args.mode, engine))
    except (CatalogError, SyncVerificationError) as exc:
        print(f"knowledge_base {args.mode} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
    except Exception as exc:  # DB errors may echo statements/params; report the type only
        print(f"knowledge_base {args.mode} failed: {type(exc).__name__}", file=sys.stderr)
    return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
