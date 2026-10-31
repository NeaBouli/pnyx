"""Explicit owner-approved delta from the frozen R0 public-page baseline.

The original inventory remains immutable. Only the precise Plausible loader
removed under EKA-33 is excluded when comparing semantic page contracts.
Non-gated pages retain exact post-removal byte hashes below.
"""

from __future__ import annotations

from copy import deepcopy

SCRIPT = {
    "src": "https://analytics.ekklesia.gr/js/script.js",
    "attrs": {
        "data-domain": "ekklesia.gr",
        "defer": "",
        "src": "https://analytics.ekklesia.gr/js/script.js",
    },
}
RESOURCE = {
    "host": "analytics.ekklesia.gr",
    "kind": "external",
    "source": "script.src",
    "url": "https://analytics.ekklesia.gr/js/script.js",
}

# T-9149: pins cover deferred script/listener migration, safe embed DOM, and local fonts.
# Generated from the reviewed single-line removal, pinned to prevent any other
# change to public pages outside the R2-R4 redesign gates.
# T-9138 (EVA-023): exact script-only externalization on mirror-setup and
# tickets/auth/callback; source bodies are unchanged, execution order preserved.
# Callback also sets no-referrer first in head to protect OAuth asset referrers.
POST_REMOVAL_SHA256 = {
    "docs/govgr-dimos.html": "073a89aeaf3ee7d4bd98ecaecde28b3461cf99a5f33bd501ab54c6e65ee629a6",  # B08: conditional Arweave publication
    "docs/mirror-setup.html": "0d2b1d6e642535d2e0298fcf4397b5e46c0d05a60435153de6c5f12e23ef9c6f",
    "docs/municipality/article.html": "9232d97104dcae0962c4eef7104c2a6b95d53b61de5126e709685d579a747016",
    "docs/municipality/index.html": "2ee8ab81fae1ec9978a73f785d14502c31cd121e912c738867e5c78b6b7328ce",  # B08: conditional Arweave publication
    "docs/sso-verify.html": "a782566fb0a5cdc52b02f742e376c54150a3adb6caf04d49d5ccc37976ba00a7",  # T-9172: APK v1.0.37/vC66; Play vC62 closed testing
    "docs/tickets/auth/callback.html": "a11ccd12e9c35e51582f6d7c0e07a7c98159d9a3cc7a551cc32cd6fe9a28266a",
    "docs/tickets/index.html": "d15da5a5e2b2831f4784f8da49b0994aeb35c449571a44b290e62cc27f4f21ff",
    "docs/votes/active.html": "3f0f66f9b994de76c70392eb04cf15f405f7892c731ae9230aec2937c343125a",
    "docs/votes/recent.html": "fc8beb7d125cc0d93824053c4759128391671a9bc59ce3d24a189f5b66109ab8",
    "docs/votes/results.html": "7e7686b50d4d9ed60d9ac4fd1790093ec4145bb7862aa162e837ce12d0b5230a",
}

# T-394 (EKA-14): reviewed security remediation on a non-gated page (API error
# detail rendered via textContent), pinned to its exact post-fix bytes.
SECURITY_REMEDIATION_SHA256 = {
    "docs/embed/qr-login.html": "b4350dffb479679a4db917471283889e522013584d68e9d4942263c068b68173",
}


# T-420 (EKA-51): "24 Ώρες" footer now targets /el/bills?status=WINDOW_24H;
# single-line change on top of the post-removal bytes above.
# T-421 (EKA-48/49): head metadata only on top of the bytes above — no
# same-URL hreflang="en", complete og/twitter/hreflang/JSON-LD on legal.html,
# twitter cards on tickets and municipality, municipality canonical/og:url on
# the final /municipality/index.html document.
# T-9132 (Gio approved 2026-10-16, ADR-007 S1): no-name / pseudonymous
# ordinary-vote claims and qualified IP assurances; T-9127 OPEN_END logic retained.
# T-9132 review: demo discloses possible linkage through verification; demo and
# govgr-dimos separate expiring daily HMAC counters from size-rotated IP logs.
CONTENT_REMEDIATION_SHA256 = {
    "docs/representative.html": "1579bf57e09a70bbb40bcc700969c129c7afe833aa008e958c9ffc0a64fc55c6",  # B08/B12/B17: reviewed content only
    "docs/demo/admin.html": "50908f9c0f1221a0e988fa21aa9487511daaa9d36a7880338bbe82c00b632642",  # B08: conditional Arweave publication
    "docs/embed/results.html": "aecebcb2965f4443fc29f486706a9364e1e052af99c97825788737c37ffe5699",  # T-9128: nullable public result cells
    "docs/demo/index.html": "0f962779807d86bd9e2d93c1d1d0dac45be35da68a0741f89be57bf24f46448c",  # B08: conditional Arweave publication
    "docs/demo/bills.html": "7b17fd081470cd7c852ec5eb4691f92da8b759cf4d929bb24d8350fceeaa8071",  # T-9127: OPEN_END voting closed
    "docs/embed/vote.html": "2c065daa0cc82b22c695b2634f7738b3cc6766233db2541965f56e982aaab98b",  # T-9127: OPEN_END voting closed
    "docs/govgr-dimos.html": "073a89aeaf3ee7d4bd98ecaecde28b3461cf99a5f33bd501ab54c6e65ee629a6",  # B08: conditional Arweave publication
    "docs/legal.html": "b444bf53ec77adbb783100d9d1f03c083e33864906b3562fb46f245bb00b165c",  # T-9147: bilingual bot footer link.
    "docs/municipality/article.html": "9232d97104dcae0962c4eef7104c2a6b95d53b61de5126e709685d579a747016",
    "docs/municipality/index.html": "2ee8ab81fae1ec9978a73f785d14502c31cd121e912c738867e5c78b6b7328ce",  # B08: conditional Arweave publication
    "docs/tickets/index.html": "d15da5a5e2b2831f4784f8da49b0994aeb35c449571a44b290e62cc27f4f21ff",
}

# T-9148 (#636, owner-requested): replace only the two vendor-naming landing
# pairs. The R2 gate requires their exact neutral replacements, including both
# languages, rather than permitting the feature text to disappear.
LANDING_BILINGUAL_REPLACEMENTS = {
    ("Ollama + DeepL: Περιλήψεις νόμων, Chat Q&A, επιτήρηση server, αυτόματη επισκευή scraper, ανάλυση logs.",
     "Ollama + DeepL: Bill summaries, Chat Q&A, server monitoring, auto-healing scraper, log analysis."):
    ("AI: Περιλήψεις νομοσχεδίων, ερωτήσεις και απαντήσεις πολιτών, παρακολούθηση διακομιστή, αυτόματη επιδιόρθωση του συλλέκτη δεδομένων, ανάλυση αρχείων καταγραφής.",
     "AI: Bill summaries, citizen Q&A, server monitoring, auto-healing scraper, log analysis."),
    ("AI Agent (Ollama + DeepL)", "AI Agent (Ollama + DeepL)"): ("AI Agent", "AI Agent"),
}

# T-9128: embed vote/results nullable counts and withheld breakdowns.
# T-421 (EKA-48): landing head drops only the same-URL hreflang="en" alternate.
# Pinned hash of the r0 "seo" category; any other SEO change fails the R2 gate.
APPROVED_SEO_HASH = {
    "docs/index.html": "dde736d4392f47b4f7a7ad2e5101bb4abe2a6b6a03a4ad2609670e298883e69a",
}


def expected_sha256(path: str, frozen_sha256: str) -> str:
    """Return the exact approved byte hash, or the frozen hash otherwise."""
    if path in SECURITY_REMEDIATION_SHA256:
        return SECURITY_REMEDIATION_SHA256[path]
    if path in CONTENT_REMEDIATION_SHA256:
        return CONTENT_REMEDIATION_SHA256[path]
    return POST_REMOVAL_SHA256.get(path, frozen_sha256)


def baseline_without_analytics(page: dict) -> dict:
    """Drop only the exact old loader's parser evidence from an R0 page."""
    expected = deepcopy(page)
    external = expected["scripts"]["external"]
    if SCRIPT not in external:
        return expected
    external.remove(SCRIPT)
    expected["resources"].remove(RESOURCE)
    expected["external_hosts"].remove("analytics.ekklesia.gr")
    return expected

# T-9147 (Gio, 2026-10-18): bilingual bot policy, exact new-page bytes.
ADDITIONAL_PAGE_SHA256 = {
    "docs/bot.html": "21092ed849430fe1e2b78472c7a3f99f18b8cb8793bdc1ae262a7477a0b101f9",  # T-9148: neutral EL/EN bot-policy text.
}

# B08 (EKA-34/36): exact user-requested bilingual replacements.
LANDING_BILINGUAL_REPLACEMENTS.update({
    ('Εξελισσόμενη πολιτική πυξίδα. 4 μοντέλα. Κρυπτογραφημένη τοπικά, ποτέ στον server.', 'Evolving political compass. 4 models. Encrypted locally, never on server.'):
        ('Στον browser το προφίλ Compass αποθηκεύεται τοπικά με κρυπτογράφηση AES-256-GCM και κλειδί στη συσκευή. Χωριστά, ο server αποθηκεύει ψευδώνυμες ψήφους και ιστορικό συναίνεσης και επιστρέφει προσωπική θέση από το ιστορικό μετά από έλεγχο υπογραφής· η τοπική κρυπτογράφηση δεν καλύπτει αυτά τα δεδομένα.', 'Browser Compass profiles are stored locally with AES-256-GCM encryption and a key held on the device. Separately, the server stores pseudonymous votes and consensus history and returns a personal position derived from that history after signature verification; local encryption does not cover those records.'),
    ('Κάθε αποτέλεσμα αρχειοθετείται μόνιμα στο Arweave. Αδύνατο να διαγραφεί.', 'Every result is permanently archived on Arweave. Impossible to delete.'):
        ('Η βάση δεδομένων της πλατφόρμας είναι το κύριο αρχείο. Συγκεντρωτικά στιγμιότυπα μπορεί να δημοσιευθούν στο Arweave για επιλέξιμα νομοσχέδια της Βουλής μετά την κοινοβουλευτική ψηφοφορία. Η δημοσίευση και η μόνιμη διαθεσιμότητα δεν είναι εγγυημένες. Η δημοσίευση ZK είναι σε παύση. Αποτελέσματα με λιγότερες από 10 ψήφους δεν εμφανίζονται δημόσια· αποκρύπτονται επίσης μικρές επιμέρους ομάδες.', 'The platform database is the primary record. Aggregate snapshots may be published to Arweave for eligible Parliament bills after the parliamentary vote. Publication and permanent availability are not guaranteed. ZK publication is paused. Results with fewer than 10 votes are not shown publicly; small subgroups are also withheld.'),
    ('Arweave Blockchain — μόνιμη αρχειοθέτηση', 'Arweave Blockchain — permanent archive'):
        ('Arweave — δυνατότητα δημοσίευσης επιλέξιμων συγκεντρωτικών στιγμιότυπων', 'Arweave — optional publication of eligible aggregate snapshots'),
    ('Τα αποτελέσματα βασίζονται αποκλειστικά σε ψήφους πολιτών. Αρχειοθέτηση στο Arweave blockchain.', 'Results based exclusively on citizen votes. Archived on Arweave blockchain.'):
        ('Τα αποτελέσματα βασίζονται αποκλειστικά σε ψήφους πολιτών. Η βάση δεδομένων της πλατφόρμας είναι το κύριο αρχείο. Συγκεντρωτικά στιγμιότυπα μπορεί να δημοσιευθούν στο Arweave για επιλέξιμα νομοσχέδια της Βουλής μετά την κοινοβουλευτική ψηφοφορία. Η δημοσίευση και η μόνιμη διαθεσιμότητα δεν είναι εγγυημένες. Η δημοσίευση ZK είναι σε παύση. Αποτελέσματα με λιγότερες από 10 ψήφους δεν εμφανίζονται δημόσια· αποκρύπτονται επίσης μικρές επιμέρους ομάδες.', 'Results are based exclusively on citizen votes. The platform database is the primary record. Aggregate snapshots may be published to Arweave for eligible Parliament bills after the parliamentary vote. Publication and permanent availability are not guaranteed. ZK publication is paused. Results with fewer than 10 votes are not shown publicly; small subgroups are also withheld.'),
})

# B17 (EKA-55): exact R0 quote and MIT feature replacements using legal-page responsibility.
LANDING_BILINGUAL_REPLACEMENTS.update({
    (
        '«Η Εκκλησία του Δήμου — η κύρια δημοκρατική συνέλευση της αρχαίας Αθήνας — πραγματοποιούνταν στον λόφο της Πνύκας, στην Αρχαία Αγορά ή στο Θέατρο του Διονύσου και αποτελούσε τον πυρήνα της αθηναϊκής δημοκρατίας. Η ιστοσελίδα ekklesia.gr εμπνέεται από αυτή την ιστορική παράδοση και αποτελεί ανεξάρτητη, κοινοτική πλατφόρμα ανοιχτού κώδικα — χωρίς ιδιοκτήτη, χωρίς εταιρεία, χωρίς κεντρικό έλεγχο. Δεν ανήκει σε κανέναν και ανήκει σε όλους. Χωρίς κρατική συγκατάθεση ή επίσημο χαρακτήρα. Όλες οι ψηφοφορίες που διεξάγονται στην πλατφόρμα αφορούν αποκλειστικά πραγματικά νομοσχέδια, αποφάσεις και ανακοινώσεις που προέρχονται από επίσημες δημόσιες πηγές — τη Βουλή των Ελλήνων, τις Περιφέρειες και τους Δήμους — και έχουν αποκλειστικά ενημερωτικό χαρακτήρα. Δεν παράγουν κανενός είδους νομική ή πολιτική δεσμευτικότητα.»',
        '"The Ekklesia — the principal democratic assembly of ancient Athens — convened on Pnyx hill, the Ancient Agora, or the Theatre of Dionysus and formed the core of Athenian democracy. ekklesia.gr is inspired by this historical tradition and is an independent, community-driven open-source platform — no owner, no company, no central control. It belongs to no one and belongs to everyone. Without state endorsement or official status. All votes conducted on this platform concern exclusively real bills, decisions and announcements from official public sources — the Hellenic Parliament, Regions and Municipalities — and are purely informational. They carry no legal or political binding force."',
    ): (
        '«Η Εκκλησία του Δήμου — η κύρια δημοκρατική συνέλευση της αρχαίας Αθήνας — πραγματοποιούνταν στον λόφο της Πνύκας, στην Αρχαία Αγορά ή στο Θέατρο του Διονύσου και αποτελούσε τον πυρήνα της αθηναϊκής δημοκρατίας. Η ιστοσελίδα ekklesia.gr εμπνέεται από αυτή την ιστορική παράδοση. Η ekklesia.gr αναπτύσσεται ως κοινοτικό έργο ανοικτού κώδικα. Φορέας λειτουργίας είναι η V-Labs IT Solutions & Development (εμπορική επωνυμία Vendetta Labs). Η συνεισφορά της κοινότητας στον κώδικα και στο περιεχόμενο δεν μεταβιβάζει την ευθύνη λειτουργίας: ο παραπάνω φορέας είναι υπεύθυνος για την τεχνική λειτουργία της δημόσιας υπηρεσίας και αποτελεί τον υπεύθυνο επεξεργασίας όπου η ekklesia.gr επεξεργάζεται δεδομένα προσωπικού χαρακτήρα. Χωρίς κρατική συγκατάθεση ή επίσημο χαρακτήρα. Όλες οι ψηφοφορίες που διεξάγονται στην πλατφόρμα αφορούν αποκλειστικά πραγματικά νομοσχέδια, αποφάσεις και ανακοινώσεις που προέρχονται από επίσημες δημόσιες πηγές — τη Βουλή των Ελλήνων, τις Περιφέρειες και τους Δήμους — και έχουν αποκλειστικά ενημερωτικό χαρακτήρα. Δεν παράγουν κανενός είδους νομική ή πολιτική δεσμευτικότητα.»',
        '"The Ekklesia — the principal democratic assembly of ancient Athens — convened on Pnyx hill, the Ancient Agora, or the Theatre of Dionysus and formed the core of Athenian democracy. ekklesia.gr is inspired by this historical tradition. ekklesia.gr is developed as a community-driven open-source project. The operator is V-Labs IT Solutions & Development (trading name Vendetta Labs). Community contributions to code and content do not transfer operational responsibility: the operator named above is responsible for the technical operation of the public service and is the data controller where ekklesia.gr processes personal data. Without state endorsement or official status. All votes conducted on this platform concern exclusively real bills, decisions and announcements from official public sources — the Hellenic Parliament, Regions and Municipalities — and are purely informational. They carry no legal or political binding force."',
    ),
    (
        'MIT License. Ο κώδικας ανήκει σε όλους. Κανείς δεν ελέγχει.',
        'MIT License. Code belongs to everyone. Nobody controls.',
    ): (
        'Ο πηγαίος κώδικας δημοσιεύεται στο GitHub με άδεια MIT. Η συνεισφορά της κοινότητας δεν μεταβιβάζει την ευθύνη λειτουργίας.',
        'The source code is published on GitHub under the MIT License. Community contributions do not transfer operational responsibility.',
    ),
})
