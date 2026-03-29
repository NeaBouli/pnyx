<!--
@wiki-page PRIVACY
@update-hint Update on privacy concept changes.
@ai-anchor WIKI_PRIVACY
-->

# Πολιτική Απορρήτου / Privacy Policy
# Copyright (c) 2026 Vendetta Labs — MIT License

## Τι ΔΕΝ αποθηκεύουμε / What we do NOT store

| Δεδομένο / Data | Κατάσταση / Status |
|---|---|
| Αριθμός κινητού / Phone number | ❌ Διαγράφεται αμέσως / Deleted immediately |
| Ιδιωτικό κλειδί / Private key | ❌ Ποτέ στον server / Never on server |
| Ακριβής ηλικία / Exact age | ❌ Μόνο ομάδα (18-25 κλπ) / Group only |
| Ακριβής διεύθυνση / Exact address | ❌ Μόνο περιφέρεια / Region only |
| Email | ❌ Δεν ζητείται / Not requested |
| Cookies | ❌ Δεν χρησιμοποιούνται / Not used |

## Τι αποθηκεύουμε / What we DO store

| Δεδομένο / Data | Format | Σκοπός / Purpose |
|---|---|---|
| Nullifier Hash | SHA256 (64 chars) | Αποφυγή διπλής ψήφου / Prevent double voting |
| Public Key | Ed25519 Hex | Επαλήθευση υπογραφής / Signature verification |
| Περιφέρεια / Region (opt.) | REG_ATTICA etc. | Δημογραφική ανάλυση / Demographic analysis |
| Φύλο / Gender (opt.) | GENDER_MALE etc. | Δημογραφική ανάλυση / Demographic analysis |
| Ψήφοι / Votes | YES/NO/ABSTAIN | Αποτελέσματα / Results |
| Χρονοσφραγίδα / Timestamp | UTC timestamp | Audit |

## GDPR Συμμόρφωση / GDPR Compliance
- Servers αποκλειστικά στην Ευρώπη / Exclusively in Europe
- Δεν πωλούνται δεδομένα σε τρίτους / No data sold to third parties
- Ανοιχτός κώδικας — πλήρης έλεγχος / Open source — full auditability
- MIT License © 2026 Vendetta Labs

## Επικοινωνία / Contact
GitHub Issues: https://github.com/NeaBouli/pnyx/issues
