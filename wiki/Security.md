<!--
@wiki-page SECURITY
@update-hint Update on crypto model or privacy concept changes.
@ai-anchor WIKI_SECURITY
-->

# Ασφάλεια & Ιδιωτικότητα / Security & Privacy

## Τρεις Χρυσοί Κανόνες / Three Golden Rules

1. **Κανένα μόνιμο προσωπικό δεδομένο** — Τηλέφωνο, ημερομηνία γέννησης, διεύθυνση δεν αποθηκεύονται ΠΟΤΕ
2. **Το ιδιωτικό κλειδί μένει στη συσκευή** — Ο server βλέπει μόνο το δημόσιο κλειδί
3. **Μονόδρομο Hashing** — SHA256(data + SERVER_SALT), μη αντιστρέψιμο

## Ροή Επαλήθευσης (Beta) / Verification Flow
```
Ο χρήστης εισάγει αριθμό κινητού
↓
HLR Lookup (μόνο πραγματικοί ελληνικοί αριθμοί)
↓
Nullifier Hash = SHA256(phone + SERVER_SALT)
↓
Ο αριθμός κινητού ΔΙΑΓΡΑΦΕΤΑΙ (gc.collect())
↓
Ed25519 Keypair δημιουργείται
↓
Public Key + Nullifier → Βάση Δεδομένων
Private Key → μία φορά στον client → ΔΕΝ αποθηκεύεται
```

## Αλυσίδα Ασφαλείας Ψηφοφορίας / Voting Security Chain
```
Nullifier ACTIVE?          → 403 Forbidden
Bill votable?              → 400 Bad Request
VoteChoice valid?          → 400 Bad Request
Ed25519 Signature valid?   → 401 Unauthorized
UNIQUE(nullifier, bill_id) → 409 Conflict (double vote)
Vote change only in        → WINDOW_24H + OPEN_END
```

## Απειλές & Αντίμετρα / Attack Vectors & Countermeasures

| Επίθεση / Attack | Αντίμετρο / Countermeasure |
|---|---|
| VoIP mass creation | HLR Lookup: only real GR mobile numbers |
| Double voting | UNIQUE constraint at DB level |
| Vote manipulation | Ed25519 signature — impossible without private key |
| State SIM farms | Rate limiting, behavioral analysis, k-anonymity |
| Server compromise | Public key only — private key never on server |
| Re-identification | Nullifier hash not reversible without SERVER_SALT |

## Πίνακας Δεδομένων / Data Table

| Data | Stored? | Format |
|---|---|---|
| Phone number | ❌ NO | Deleted immediately |
| Private key | ❌ NO | Client only |
| Public key | ✅ YES | Hex string |
| Nullifier hash | ✅ YES | SHA256 (64 chars) |
| Region (optional) | ✅ YES | Code (REG_ATTICA) |
| Gender (optional) | ✅ YES | Code (GENDER_MALE) |
| Votes | ✅ YES | Linked to nullifier |
