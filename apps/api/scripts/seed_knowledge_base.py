"""Seed knowledge base with ekklesia platform knowledge for RAG Agent."""
import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from sqlalchemy import text

ENTRIES = [
    ("mission", "Τι είναι η εκκλησία;", "What is ekklesia?",
     "Η εκκλησία του έθνους είναι μια ανεξάρτητη πρωτοβουλία πολιτών για άμεση δημοκρατία στην Ελλάδα. Επιτρέπει στους πολίτες να ψηφίζουν ανώνυμα σε πραγματικά νομοσχέδια της Βουλής. ΔΕΝ είναι κρατική υπηρεσία. Οι ψηφοφορίες δεν έχουν νομική δεσμευτικότητα. Είναι εργαλείο διαφάνειας και δημοκρατικής εκπαίδευσης. © 2026 V-Labs Development, MIT License.",
     "ekklesia tou ethnous is an independent civic initiative for direct democracy in Greece. Citizens vote anonymously on real Hellenic Parliament bills. NOT a government service. Votes have no legal binding. Transparency and civic education tool.",
     '["ekklesia","democracy","parliament","civic","initiative","vote"]', 1),

    ("privacy", "Πώς προστατεύεται η ανωνυμία μου;", "How is my anonymity protected?",
     "Η εκκλησία χρησιμοποιεί κρυπτογραφία Ed25519 για υπογραφές ψήφων. Ο αριθμός τηλεφώνου ΠΟΤΕ δεν αποθηκεύεται. Μόνο κρυπτογραφικό hash (nullifier) αποθηκεύεται — δεν μπορεί να αντιστραφεί. Το ιδιωτικό κλειδί αποθηκεύεται ΜΟΝΟ στη συσκευή σου.",
     "ekklesia uses Ed25519 cryptography for vote signatures. Phone number is NEVER stored. Only a cryptographic nullifier hash is stored — it cannot be reversed. The private key is stored ONLY on your device.",
     '["privacy","anonymity","cryptography","Ed25519","nullifier","phone"]', 1),

    ("process", "Πώς ψηφίζω;", "How do I vote?",
     "1. Κατέβασε την εφαρμογή ekklesia. 2. Επαλήθευσε τον αριθμό τηλεφώνου (HLR — δεν στέλνεται SMS). 3. Επέλεξε Δήμο (για τοπικές αποφάσεις). 4. Ψήφισε ΝΑΙ/ΟΧΙ/ΑΠΟΧΗ σε νομοσχέδια. 5. Κάθε ψήφος βαρύνει x1 (SMS) ή x2 (gov.gr). Μπορείς να ψηφίσεις σε εθνικά, περιφερειακά και δημοτικά νομοσχέδια.",
     "1. Download ekklesia app. 2. Verify phone (HLR — no SMS). 3. Select municipality (for local decisions). 4. Vote YES/NO/ABSTAIN on bills. 5. Vote weighs x1 (SMS) or x2 (gov.gr). Vote on national, regional and municipal bills.",
     '["vote","process","HLR","verification","app","download"]', 1),

    ("process", "Μπορώ να διορθώσω την ψήφο μου;", "Can I correct my vote?",
     "Δεν μπορείτε να ψηφίσετε δύο φορές στο ίδιο νομοσχέδιο. Αν είναι ενεργό το παράθυρο διόρθωσης (WINDOW_24H), η εφαρμογή μπορεί να επιτρέπει μία διόρθωση ψήφου σύμφωνα με την κατάσταση του νομοσχεδίου. Εκτός αυτού του παραθύρου η ψήφος δεν αλλάζει.",
     "You cannot vote twice on the same bill. If the correction window (WINDOW_24H) is active, the app may allow one vote correction depending on the bill status. Outside that window, the vote cannot be changed.",
     '["vote","correction","change vote","WINDOW_24H","duplicate","bill"]', 1),

    ("faq", "Πόσο ζυγίζει η ψήφος μου;", "How much does my vote weigh?",
     "SMS/HLR Επαληθευμένος: x1.0 (βασική ψήφος). gov.gr Επαληθευμένος: x2.0 (ισχυρή ψήφος). Το gov.gr OAuth αναμένει κυβερνητική έγκριση.",
     "SMS/HLR Verified: x1.0 (basic vote). gov.gr Verified: x2.0 (strong vote). gov.gr OAuth pending government approval.",
     '["vote","weight","gov.gr","verification","x1","x2"]', 1),

    ("govgr", "Τι είναι το gov.gr OAuth;", "What is gov.gr OAuth?",
     "Το gov.gr OAuth είναι τεχνικά προβλεπόμενο αλλά δεν θεωρείται ενεργό παραγωγικά. Είναι deferred/gated και χρειάζεται επίσημη έγκριση/ενεργοποίηση. Μέχρι τότε χρησιμοποιείται η επαλήθευση HLR όπου είναι διαθέσιμη.",
     "gov.gr OAuth is technically planned but must not be treated as active in production. It is deferred/gated and requires official approval/activation. Until then, HLR verification is used where available.",
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
     "Το ιδιωτικό κλειδί αποθηκεύεται μόνο στη συσκευή σας. Ο server δεν το γνωρίζει και δεν μπορεί να το ανακτήσει. Αν χαθεί, ακολουθείτε μόνο την επίσημη ροή επαλήθευσης/επανέκδοσης που παρέχει η εφαρμογή· δεν υπάρχει μυστική ανάκτηση από τον server.",
     "Your private key is stored only on your device. The server does not know it and cannot recover it. If it is lost, use only the official app re-verification/key-rotation flow; there is no hidden server-side recovery process.",
     '["private key","lost key","recovery","device","keychain","keystore"]', 1),

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


async def seed():
    from database import async_engine
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    Session = async_sessionmaker(async_engine, class_=AsyncSession)

    async with Session() as db:
        inserted = 0
        updated = 0
        for cat, title_el, title_en, content_el, content_en, keywords, priority in ENTRIES:
            existing = await db.execute(text(
                "SELECT id FROM knowledge_base WHERE category = :cat AND title_en = :ten LIMIT 1"
            ), {"cat": cat, "ten": title_en})
            row = existing.first()
            params = {"cat": cat, "tel": title_el, "ten": title_en, "cel": content_el, "cen": content_en, "kw": keywords, "pri": priority}
            if row:
                await db.execute(text(
                    "UPDATE knowledge_base SET title_el = :tel, content_el = :cel, content_en = :cen, "
                    "keywords = :kw::jsonb, priority = :pri, updated_at = NOW() WHERE id = :id"
                ), {**params, "id": row.id})
                updated += 1
            else:
                await db.execute(text(
                    "INSERT INTO knowledge_base (category, title_el, title_en, content_el, content_en, keywords, priority) "
                    "VALUES (:cat, :tel, :ten, :cel, :cen, :kw::jsonb, :pri)"
                ), params)
                inserted += 1

        await db.commit()
        print(f"Knowledge base synced: {inserted} inserted, {updated} updated")


if __name__ == "__main__":
    asyncio.run(seed())
