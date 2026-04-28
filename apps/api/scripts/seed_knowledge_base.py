"""Seed knowledge base with ekklesia platform knowledge for RAG Agent."""
import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from sqlalchemy import text

ENTRIES = [
    ("mission", "Τι είναι η εκκλησία;", "What is ekklesia?",
     "Η εκκλησία του έθνους είναι μια ανεξάρτητη πρωτοβουλία πολιτών για άμεση δημοκρατία στην Ελλάδα. Επιτρέπει στους πολίτες να ψηφίζουν ανώνυμα σε πραγματικά νομοσχέδια της Βουλής. ΔΕΝ είναι κρατική υπηρεσία. Οι ψηφοφορίες δεν έχουν νομική δεσμευτικότητα. Είναι εργαλείο διαφάνειας και δημοκρατικής εκπαίδευσης. © 2026 Vendetta Labs, MIT License.",
     "ekklesia tou ethnous is an independent civic initiative for direct democracy in Greece. Citizens vote anonymously on real Hellenic Parliament bills. NOT a government service. Votes have no legal binding. Transparency and civic education tool.",
     '["ekklesia","democracy","parliament","civic","initiative","vote"]', 1),

    ("privacy", "Πώς προστατεύεται η ανωνυμία μου;", "How is my anonymity protected?",
     "Η εκκλησία χρησιμοποιεί κρυπτογραφία Ed25519. Ο αριθμός τηλεφώνου ΠΟΤΕ δεν αποθηκεύεται. Μόνο κρυπτογραφικό hash (nullifier) αποθηκεύεται — δεν μπορεί να αντιστραφεί. Κάθε ψήφος υπογράφεται με Ed25519 ιδιωτικό κλειδί. Το κλειδί αποθηκεύεται ΜΟΝΟ στη συσκευή σου.",
     "ekklesia uses Ed25519 cryptography. Phone number is NEVER stored. Only a cryptographic nullifier hash is stored — cannot be reversed. Each vote is signed with Ed25519 private key stored ONLY on your device.",
     '["privacy","anonymity","cryptography","Ed25519","nullifier","phone"]', 1),

    ("process", "Πώς ψηφίζω;", "How do I vote?",
     "1. Κατέβασε την εφαρμογή ekklesia. 2. Επαλήθευσε τον αριθμό τηλεφώνου (HLR — δεν στέλνεται SMS). 3. Επέλεξε Δήμο (για τοπικές αποφάσεις). 4. Ψήφισε ΝΑΙ/ΟΧΙ/ΑΠΟΧΗ σε νομοσχέδια. 5. Κάθε ψήφος βαρύνει x1 (SMS) ή x2 (gov.gr). Μπορείς να ψηφίσεις σε εθνικά, περιφερειακά και δημοτικά νομοσχέδια.",
     "1. Download ekklesia app. 2. Verify phone (HLR — no SMS). 3. Select municipality (for local decisions). 4. Vote YES/NO/ABSTAIN on bills. 5. Vote weighs x1 (SMS) or x2 (gov.gr). Vote on national, regional and municipal bills.",
     '["vote","process","HLR","verification","app","download"]', 1),

    ("faq", "Πόσο ζυγίζει η ψήφος μου;", "How much does my vote weigh?",
     "SMS/HLR Επαληθευμένος: x1.0 (βασική ψήφος). gov.gr Επαληθευμένος: x2.0 (ισχυρή ψήφος). Το gov.gr OAuth αναμένει κυβερνητική έγκριση.",
     "SMS/HLR Verified: x1.0 (basic vote). gov.gr Verified: x2.0 (strong vote). gov.gr OAuth pending government approval.",
     '["vote","weight","gov.gr","verification","x1","x2"]', 1),

    ("govgr", "Τι είναι το gov.gr OAuth;", "What is gov.gr OAuth?",
     "Το gov.gr OAuth είναι επαλήθευση ταυτότητας μέσω ελληνικής κυβέρνησης. Παρέχει ισχυρότερη ψήφο (x2) αλλά απαιτεί κυβερνητική έγκριση. Κατάσταση: ΑΝΑΜΕΝΕΙ ΕΓΚΡΙΣΗ. Δήμαρχοι μπορούν να υποβάλουν αίτηση για ενεργοποίηση στον Δήμο τους.",
     "gov.gr OAuth is identity verification through Greek government. Stronger vote (x2) but requires approval. Status: PENDING. Mayors can apply for municipal activation.",
     '["gov.gr","OAuth","government","approval","AMKA","mayor"]', 2),

    ("faq", "Είναι ασφαλής η εφαρμογή;", "Is the app safe?",
     "Ναι. Ανοιχτού κώδικα (MIT License). Κώδικας δημόσια στο GitHub (NeaBouli/pnyx). Δεν αποθηκεύουμε προσωπικά δεδομένα. Δεν πουλάμε δεδομένα. Server σε Hetzner (Ευρώπη) — GDPR compliant.",
     "Yes. Open source (MIT License). Code public on GitHub (NeaBouli/pnyx). No personal data stored. No data sold. Server in Hetzner (Europe) — GDPR compliant.",
     '["safety","open source","GDPR","privacy","GitHub","secure"]', 1),

    ("concept", "Δείκτης Απόκλισης", "Divergence Index",
     "Ο Δείκτης Απόκλισης μετρά πόσο διαφέρουν οι ψήφοι των πολιτών από τις αποφάσεις της Βουλής. Υψηλή απόκλιση = βουλευτές ψηφίζουν διαφορετικά. Χαμηλή = αντιπροσωπεύουν τη βούληση πολιτών.",
     "Divergence Index measures how much citizen votes differ from Parliament. High = MPs vote differently. Low = MPs represent citizens.",
     '["divergence","parliament","citizens","index","score"]', 2),

    ("forum", "Τι είναι η πνύκα;", "What is pnyx?",
     "Η πνύκα (pnyx.ekklesia.gr) είναι το δημόσιο forum της εκκλησίας. Συζήτηση νομοσχεδίων, προτάσεις, ανταλλαγή απόψεων. Σύνδεση: SSO (ekklesia account) ή Email/Google. Επαληθευμένοι πολίτες έχουν δικαίωμα ψήφου στο ekklesia.gr — στο forum μόνο συζήτηση.",
     "pnyx (pnyx.ekklesia.gr) is ekklesia public forum. Bill discussions, proposals, exchange views. Login: SSO (ekklesia) or Email/Google. Verified citizens have voting rights on ekklesia.gr — forum is discussion only.",
     '["pnyx","forum","discussion","community","debate"]', 2),
]


async def seed():
    from database import async_engine
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    Session = async_sessionmaker(async_engine, class_=AsyncSession)

    async with Session() as db:
        # Check if already seeded
        result = await db.execute(text("SELECT COUNT(*) FROM knowledge_base"))
        count = result.scalar()
        if count > 0:
            print(f"Already seeded ({count} entries). Skipping.")
            return

        for cat, title_el, title_en, content_el, content_en, keywords, priority in ENTRIES:
            await db.execute(text(
                "INSERT INTO knowledge_base (category, title_el, title_en, content_el, content_en, keywords, priority) "
                "VALUES (:cat, :tel, :ten, :cel, :cen, :kw::jsonb, :pri)"
            ), {"cat": cat, "tel": title_el, "ten": title_en, "cel": content_el, "cen": content_en, "kw": keywords, "pri": priority})

        await db.commit()
        print(f"Seeded {len(ENTRIES)} knowledge base entries")


if __name__ == "__main__":
    asyncio.run(seed())
