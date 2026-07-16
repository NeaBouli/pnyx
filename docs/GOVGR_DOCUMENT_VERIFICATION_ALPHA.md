# Gov.gr Document Verification — Alpha Design

Status: design only. This flow is not active in Beta and no gov.gr credentials,
document upload, QR scanner, or production identity migration are enabled.

Tracking: [GH#141](https://github.com/NeaBouli/pnyx/issues/141)

## Purpose

The optional Alpha gate may strengthen the binding between one natural person
and one anonymous ekklesia credential. It must not increase vote weight:
one eligible person remains one vote per scope.

Gov.gr documents can be checked with their verification code or QR code and
carry an advanced electronic seal. These mechanisms prove document
authenticity. A QR code by itself does not prove that the person presenting the
document is its subject and therefore cannot replace holder authentication.

Official references:

- [Gov.gr document validity check](https://www.gov.gr/ipiresies/polites-kai-kathemerinoteta/psephiaka-eggrapha-gov-gr/elegkhos-egkurotetas-eggraphon-gov-gr)
- [Gov.gr step-by-step QR and verification-code guide](https://howto.gov.gr/mod/book/tool/print/index.php?id=844)

## Threat Model

The design must prevent:

- reuse of another person's valid document;
- replay of one document or verification code on multiple devices;
- forged or altered PDFs and redirected QR URLs;
- registration of a second voting credential for the same official subject;
- linking a person's identity to later votes;
- retention or logging of the document, QR payload, AMKA, AFM, phone number,
  name, address, or other personal data;
- bypass through an undocumented or scraped gov.gr endpoint;
- silent migration of existing Beta identities.

## Candidate Flow

1. The server creates a short-lived, single-use challenge bound to the device,
   purpose, and verification session.
2. The citizen authenticates through an approved official flow. A QR/PDF route
   is acceptable only if the freshly issued official evidence binds that
   challenge and proves that the authenticated holder is the document subject.
3. The app validates the official origin. PDF validation must verify the full
   seal certificate chain, validity period, and revocation status. A browser
   success page or QR URL alone is insufficient.
4. The backend accepts only explicitly documented claims needed for eligibility
   and duplicate prevention. It must not infer citizenship, age, residence, or
   electoral eligibility from an unrelated document.
5. A server-keyed, versioned one-way credential handle is derived from a stable
   official subject identifier. The raw identifier must never be stored.
6. The document, QR payload, temporary claims, and verification response are
   deleted immediately after the transaction. Logs contain only a result code,
   assurance version, and non-identifying audit event.
7. The anonymous Ed25519/Semaphore credential is issued separately so later
   votes cannot be linked back to the verification session.

## Activation Gates

Implementation remains disabled until all gates pass:

- an officially approved machine-to-machine or holder-authenticated interface;
- documented claims sufficient for the intended eligibility decision;
- legal basis, DPIA, retention policy, and data-subject process;
- replay, revocation, recovery, and credential-migration design;
- test vectors for QR/PDF/eSeal validation and adversarial fixtures;
- independent privacy, cryptography, and application-security review;
- isolated sandbox and one-scope canary with backup and rollback;
- public documentation that describes the exact assurance and its limits.

## Explicit Non-Goals

- no QR-only identity claim;
- no face recognition or biometric database;
- no storage of government documents or personal identifiers;
- no vote weighting by verification method;
- no undocumented gov.gr scraping;
- no Beta activation before the Alpha gates are complete.
