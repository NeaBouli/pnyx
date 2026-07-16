<!-- @ai-anchor WHITEPAPER_ROOT -->
<!-- @update-hint Technical whitepaper. Update on architecture changes. -->
<!-- @seo Ekklesia.gr Whitepaper — Ψηφιακή Δημοκρατία Ελλάδα -->

<div align="center">

# εκκλησία · Ekklesia.gr
## Λευκό Βιβλίο / Technical Whitepaper
### Version 1.0 — 2026

**© 2026 V-Labs Development — MIT License**

</div>

---

## Περίληψη / Abstract

Η **Ekklesia.gr** είναι μια ανοιχτού κώδικα πλατφόρμα άμεσης ψηφιακής
δημοκρατίας για τον Έλληνα πολίτη. Επιτρέπει την ανώνυμη, επαληθευμένη
συμμετοχή στις πολιτικές διαδικασίες μέσω δύο βασικών λειτουργιών: της
**Πολιτικής Πυξίδας** (σύγκριση πολιτικών θέσεων) και της **Ψηφοφορίας Πολιτών**
(αντικατοπτρισμός κοινοβουλευτικών αποφάσεων).

**Ekklesia.gr** is an open-source platform for digital direct democracy for
Greek citizens. It enables anonymous, verified participation in political
processes through two core functions: the **VoteCompass** (political position
comparison) and **Citizen Voting** (mirroring parliamentary decisions).

---

## 1. Πρόβλημα & Κίνητρο / Problem & Motivation

### 1.1 Το Δημοκρατικό Έλλειμμα / The Democratic Deficit

Η σύγχρονη αντιπροσωπευτική δημοκρατία αντιμετωπίζει θεμελιώδη προβλήματα:

- **Απόσταση εκπροσώπησης**: Βουλευτές ψηφίζουν χωρίς να γνωρίζουν τη γνώμη
  των πολιτών τους σε κάθε νομοσχέδιο
- **Έλλειψη διαφάνειας**: Κανένα σύστημα δεν μετρά συστηματικά την απόκλιση
  μεταξύ κοινοβουλίου και λαού
- **Παθητική συμμετοχή**: Οι πολίτες ψηφίζουν κάθε 4 χρόνια — όχι για
  συγκεκριμένες αποφάσεις

### 1.2 Η Λύση / The Solution

Η Ekklesia.gr δεν αντικαθιστά τη δημοκρατία — την **ενισχύει** με:

1. Μια **Πολιτική Πυξίδα** που βοηθά πολίτες να κατανοήσουν τις πολιτικές τους θέσεις
2. Ένα σύστημα **παράλληλης ψηφοφορίας** για κοινοβουλευτικά νομοσχέδια
3. Έναν **Δείκτη Απόκλισης** που ποσοτικοποιεί τη διαφορά Βουλής-Πολιτών
4. Πλήρη **ανωνυμία** μέσω κρυπτογραφικών πρωτοκόλλων

---

## 2. Αρχιτεκτονική Συστήματος / System Architecture

### 2.1 Επισκόπηση / Overview
```
┌─────────────────────────────────────────────────────────┐
│                    PNYX MONOREPO                         │
│                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  Next.js 16 │  │  Expo RN    │  │   FastAPI        │  │
│  │  (Web)      │  │  (Mobile)   │  │   Backend        │  │
│  └──────┬──────┘  └──────┬──────┘  │                  │  │
│         └────────────────┘         │  MOD-01 Identity  │  │
│              REST / WebSocket       │  MOD-02 VAA       │  │
│                    │               │  MOD-03 Parliament │  │
│                    └──────────────►│  MOD-04 CitizenVote│  │
│                                    │  MOD-05 Analytics  │  │
│  ┌─────────────────┐               └────────┬──────────┘  │
│  │ packages/crypto │                        │             │
│  │ Ed25519·Nullifier│          ┌─────────────▼──────────┐ │
│  │ HLR·ZK          │          │  PostgreSQL + Redis     │ │
│  └─────────────────┘          └────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                      │
                      ▼  (Phase V2)
        [TrueRepublic / Cosmos SDK / PnyxCoin]
```

### 2.2 Στοίβα Τεχνολογιών / Technology Stack

| Επίπεδο | Τεχνολογία | Αιτιολόγηση |
|---|---|---|
| Backend | Python FastAPI | Async, type-safe, OpenAPI native |
| Database | PostgreSQL 15 | JSONB, reliable, GDPR-ready |
| Cache | Redis 7 | PubSub, WebSocket relay |
| Web | Next.js 16 | SSR, i18n, SEO |
| Mobile | Expo React Native | iOS + Android + Web |
| Crypto | PyNaCl + @noble/curves | Ed25519, battle-tested |
| Infra | Docker + Traefik | Reproducible, SSL-auto |
| CI/CD | GitHub Actions | Free, transparent |
| V2 Crypto | Rust + WASM | Browser-native signing |
| V2 Chain | Cosmos SDK | PnyxCoin, TrueRepublic |

---

## 3. Μοντέλο Ταυτότητας / Identity Model

### 3.1 Αρχές / Principles

Η ταυτότητα στην Ekklesia.gr βασίζεται σε τρεις αρχές:
1. **Μοναδικότητα**: Ένας αριθμός = μία ψήφος
2. **Ανωνυμία**: Κανένα προσωπικό δεδομένο δεν αποθηκεύεται
3. **Επαληθευσιμότητα**: Κάθε ψήφος είναι κρυπτογραφικά επαληθεύσιμη

### 3.2 Ροή Επαλήθευσης Beta / Beta Verification Flow
```
Αριθμός κινητού (+306xxxxxxxxx)
│
▼
HLR Lookup → κατάσταση δικτύου/συμβατότητα GR αριθμού, όχι απόδειξη κατοχής SIM ή ταυτότητας
│
▼
SHA256 compatibility anchor + Argon2id v2 identity hash
│
▼
Τηλέφωνο ΔΙΑΓΡΑΦΕΤΑΙ (gc.collect())
│
▼
Ed25519 Keypair δημιουργείται
│
├── Public Key  → Βάση δεδομένων
└── Private Key → Client ΜΟΝΟ (εφάπαξ)
```

### 3.3 Nullifier Hash

Το **Nullifier** είναι ο κρυπτογραφικός αναγνωριστής του χρήστη:
```python
compatibility_anchor = SHA256(f"{phone_number}:{SERVER_SALT}")
identity_nullifier_v2 = "v2:" + Argon2id(
    normalized_phone,
    salt=SHA256("ekklesia:identity-nullifier:v2" + SERVER_SALT),
    memory=64_MiB,
    iterations=2,
)
```

- Η παραγωγική ρύθμιση είναι `v2`. Νέες και επανεπαληθευμένες ταυτότητες λαμβάνουν memory-hard Argon2id hash. Το παλιό SHA256 παραμένει ως compatibility anchor για υπάρχοντα vote interfaces και ασφαλή migration lookup.
- Δεν αποθηκεύεται ο αριθμός τηλεφώνου. Το `SERVER_SALT` παραμένει κρίσιμο μυστικό και ελέγχεται fail-closed κατά την εκκίνηση.
- Αποτρέπει διπλή εγγραφή (UNIQUE constraint)
- Ενεργοποιείται αμέσως, τηλέφωνο διαγράφεται

### 3.4 Ανάκτηση Κλειδιού / Key Recovery
```
Νέα επαλήθευση με ίδιο/νέο τηλέφωνο
│
▼
Παλιό κλειδί → status = REVOKED
│
▼
Νέο Ed25519 Keypair → νέες ψήφοι
Παλιές ψήφοι → παραμένουν έγκυρες
```

---

## 4. Κύκλος Ζωής Νομοσχεδίου / Bill Lifecycle

### 4.1 Πέντε Καταστάσεις / Five States
```
ANNOUNCED → ACTIVE → WINDOW_24H → PARLIAMENT_VOTED → OPEN_END
```

| Κατάσταση | Ψηφοφορία | Αλλαγή | Αυτόματες Ενέργειες |
|---|---|---|---|
| ANNOUNCED | ❌ | — | Ειδοποιήσεις συνδρομητών |
| ACTIVE | ✅ | ❌ Κλειδωμένη | Live counter |
| WINDOW_24H | ✅ | ✅ Επιτρέπεται | WebSocket, push |
| PARLIAMENT_VOTED | ❌ | — | OG Image, RSS, Divergence |
| OPEN_END | ✅ | ✅ Πάντα | Trend analysis |

### 4.2 Αυτόματη Δημοσίευση / Automatic Publication

Οι νέες αυτόματα παραγόμενες σύντομες περιλήψεις και τα πρώτα posts του forum καταγράφουν SHA-256 ownership digest. Αυτόματη ανανέωση επιτρέπεται μόνο όσο το τρέχον περιεχόμενο ταιριάζει με το digest. Review από admin ή αλλαγή από moderator αφαιρεί το αυτόματο ownership και το χειροκίνητο κείμενο διατηρείται. Υπάρχον Beta περιεχόμενο δεν χαρακτηρίστηκε αναδρομικά· επίσημο long text και PDF links δεν ανήκουν σε αυτό το update path.

Κατά τη μετάβαση σε PARLIAMENT_VOTED:
1. Δημοσίευση αποτελεσμάτων (Redis cache)
2. Υπολογισμός Divergence Score
3. Αυτόματη δημιουργία OG Image
4. RSS/Atom Feed ενημέρωση
5. Push Notifications
6. TrueRepublic Bridge webhook (V2)

---

## 5. Αλγόριθμος Ψηφοφορίας / Voting Algorithm

### 5.1 Πολιτική Πυξίδα / VoteCompass Matching
```python
def calculate_match(user_answers, party_positions):
    total, matches = 0, 0
    for stmt_id, user_pos in user_answers.items():
        if user_pos == 0: continue  # neutral ignored
        party_pos = party_positions.get(stmt_id)
        if party_pos is not None:
            total += 1
            if user_pos == party_pos:
                matches += 1
    return (matches / total * 100) if total > 0 else 0
```

### 5.2 Δείκτης Απόκλισης / Divergence Score
```python
def compute_divergence(yes, no, abstain, parliament_votes):
    citizen_yes_pct = yes / (yes + no + abstain)
    parliament_passed = majority(parliament_votes)
    score = abs(citizen_yes_pct - (1.0 if parliament_passed else 0.0))
    # score: 0.0 = full convergence / 1.0 = full divergence
    return score
```

**Ερμηνεία / Interpretation:**
- `0.0 – 0.2`: Σύγκλιση (Convergence)
- `0.2 – 0.4`: Μέτρια Απόκλιση (Moderate Divergence)
- `0.4 – 1.0`: Έντονη Απόκλιση (Strong Divergence)

### 5.3 Αλυσίδα Ασφαλείας Ψήφου / Vote Security Chain
```
Nullifier ACTIVE?          → 403
Bill votable?              → 400
VoteChoice valid?          → 400
Ed25519 signature valid?   → 401
UNIQUE(nullifier, bill_id) → 409
Change only in WINDOW_24H  → 409 if ACTIVE
```

---

## 6. Ιδιωτικότητα & GDPR / Privacy & GDPR

### 6.1 Δεδομένα που ΔΕΝ αποθηκεύονται

- Αριθμός κινητού τηλεφώνου
- Ιδιωτικό κλειδί (private key)
- Ακριβής ηλικία ή ημερομηνία γέννησης
- Ακριβής διεύθυνση ή ΤΚ
- Email, όνομα, οποιοδήποτε αναγνωριστικό

### 6.2 Αρχή k-Ανωνυμίας

Τα δημογραφικά αποτελέσματα εμφανίζονται μόνο εφόσον `k ≥ 10` ψήφοι
υπάρχουν στη συγκεκριμένη ομάδα — αποτρέποντας επαναναγνώριση.

### 6.3 Servers & Δικαιοδοσία

- Φιλοξενία αποκλειστικά σε ευρωπαϊκά data centers
- Πλήρης συμμόρφωση GDPR
- Ανοιχτός κώδικας — πλήρης έλεγχος

---

## 7. Στρατηγική Ανάπτυξης / Development Strategy

### 7.1 Φάσεις / Phases

**Beta** (Τώρα): Αυτόνομη πλατφόρμα χωρίς κρατική εξάρτηση
- HLR έλεγχος κατάστασης ελληνικού αριθμού χωρίς SMS → Ed25519 → Nullifier (δεν αποδεικνύει κατοχή SIM ή ταυτότητα)
- Χωρίς gov.gr, χωρίς OAuth, χωρίς εξωτερικές εξαρτήσεις

**Alpha** (Trigger: 500+ χρήστες + 3+ NGO-εταίροι):
- gov.gr OAuth2.0 ενσωμάτωση
- Προαιρετική επαλήθευση εγγράφου gov.gr με νέο challenge, QR/PDF και επίσημο API ή πλήρη έλεγχο ηλεκτρονικής σφραγίδας. Πρόκειται για σχεδιασμό Alpha (GH#141), όχι ενεργή λειτουργία Beta. Το έγγραφο και τα ακατέργαστα αναγνωριστικά δεν διατηρούνται· μόνο ψευδωνυμικός credential handle και ελάχιστα audit metadata μπορούν να παραμείνουν μετά από DPIA και νομικό έλεγχο.
- Αίτηση Sandbox στην ΑΑΑΔΕ
- Μια άρνηση θα ήταν πολιτικά δύσκολη με δημόσια υποστήριξη

**V2** (Αποδεδειγμένη σταθερότητα):
- TrueRepublic Blockchain Bridge (PnyxCoin)
- Rust + WASM κρυπτογράφηση
- ZK Commit-Reveal ψηφοφορία

### 7.2 Ανοιχτός Κώδικας ως Στρατηγική

Ο ανοιχτός κώδικας δεν είναι μόνο τεχνική επιλογή — είναι στρατηγική
προστασία:
- Κανείς δεν μπορεί να κατηγορήσει αυτό που μπορεί να ελέγξει ο καθένας
- NGOs, δημοσιογράφοι και ερευνητές μπορούν να επαληθεύσουν κάθε claim
- Κάθε backdoor ή manipulation είναι άμεσα ορατό

---

## 8. TrueRepublic Ενσωμάτωση / TrueRepublic Integration

### 8.1 Σχέση / Relationship

Η Ekklesia.gr λύνει ένα κεντρικό πρόβλημα του TrueRepublic Blockchain:
**πώς αποδεικνύεται ότι ένα wallet ανήκει σε πραγματικό πολίτη;**

```
Ekklesia.gr (Identity Layer)
│
│  ZK-Proof "Είμαι επαληθευμένος πολίτης"
▼
TrueRepublic (Blockchain Layer)
│
│  On-chain ψήφοι με PnyxCoin
▼
Αμετάβλητο δημοκρατικό αρχείο
```

### 8.2 MOD-08 Bridge (V2)

- Ενεργοποιείται με `ENV_TRUEREPUBLIC_ENABLED=true`
- ZK-Proof συνδέει επαληθευμένο πολίτη με Keplr wallet
- Αθροιστικά αποτελέσματα → Cosmos SDK chain
- PnyxCoin governance token

---

## 9. Οικονομικό Μοντέλο / Economic Model

### 9.1 Beta Phase (Τώρα)
- Κόστος hosting: ~15-25€/μήνα (Hetzner CX21)
- Κόστος domain: ~10€/χρόνο
- Σύνολο: ~200-300€/χρόνο
- Χρηματοδότηση: V-Labs Development + NGO donations

### 9.2 Βιωσιμότητα / Sustainability
- Κανένα paywall, κανένα freemium
- Κανένα διαφημιστικό μοντέλο
- Open Source donations + institutional support
- V2: PnyxCoin ecosystem (TrueRepublic)

---

## 10. Νομικό Πλαίσιο / Legal Framework

**Σημαντική Δήλωση**: Η Ekklesia.gr **δεν** είναι νομικά δεσμευτική
ψηφοφορία και **δεν** αντικαθιστά επίσημες εκλογικές διαδικασίες.
Αποτελεί εργαλείο **έκφρασης** πολιτικής γνώμης και **μέτρησης**
δημοκρατικής αντιπροσώπευσης.

**Important Disclaimer**: Ekklesia.gr is **not** a legally binding vote and
**does not** replace official electoral processes. It is a tool for
**expressing** political opinion and **measuring** democratic representation.

- MIT License © 2026 V-Labs Development
- GDPR Compliant
- Δεν συλλέγει δεδομένα εκστρατείας / No campaign data collection
- Πολιτικά ουδέτερο σύστημα / Politically neutral system

---

## 10.1 ZK Voting V2 Status / Κατάσταση

Ο native Android Semaphore/Mopro prover έχει επαληθευτεί σε πραγματική συσκευή S10. Το κρυφό canary scope `ZK-CANARY-001` ολοκληρώθηκε end-to-end με πραγματικό S10 proof: opt-in, δημοσιευμένο group root, server verification, rejected mutation checks και δοκιμαστική ZK ψήφος. Το πρώτο δημόσιο scoped rollout ολοκληρώθηκε για ένα συγκεκριμένο νομοσχέδιο (`bill:GR-d4c62ed4`) με πραγματική ZK ψήφο και δημόσιο receipt.

Η ZK παραγωγή είναι ενεργή με φυλασσόμενο Parliament rollout: επιτρέπονται μόνο δημόσια scopes νομοσχεδίων Βουλής και test/canary/hidden scopes απορρίπτονται. Η δημοσίευση ZK verifier payloads στο Arweave είναι ενεργή μόνο για επιλέξιμα δημόσια Parliament scopes, με ελάχιστο μέγεθος ομάδας 5, ώστε να μειώνεται ο κίνδυνος συσχέτισης.

Native Android Semaphore/Mopro proving, hidden S10 canary, and the first public one-bill scoped rollout have passed. Guarded Parliament ZK rollout is live, and ZK Arweave auto-publication is enabled only for eligible public Parliament scopes with minimum group size 5.

---

## 11. Βιβλιογραφία / References

| Αναφορά | Σχέση |
|---|---|
| [OpenVAA](https://github.com/OpenVAA) | VAA Framework Reference |
| [Decidim](https://decidim.org) | Deliberation Model |
| [vTaiwan / pol.is](https://pol.is) | Consensus Engine |
| [TrueRepublic](https://github.com/NeaBouli/TrueRepublic) | Blockchain Layer |
| [Hellenic Parliament API](https://www.hellenicparliament.gr) | Data Source |
| [Semaphore ZK](https://semaphore.appliedzkp.org) | ZK Identity V2 |

---

<div align="center">

**© 2026 V-Labs Development — MIT License**

[GitHub](https://github.com/NeaBouli/pnyx) · [Wiki](https://github.com/NeaBouli/pnyx/wiki) · [ekklesia.gr](https://ekklesia.gr)

*Η δημοκρατία δεν είναι θέαμα. Είναι πράξη.*

</div>
