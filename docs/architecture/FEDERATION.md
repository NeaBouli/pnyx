# Federated Computing Architecture
## ekklesia.gr + TrueRepublic
Linear: NEA-113

### Phase 1 — Political Decentralization (NOW)
Nodes = Greek municipalities, each running independently.
Data sync via Federation API. No compute sharing.
Node Dashboard: built

### Phase 2 — Task Distribution (POST-ALPHA)
Celery + Redis Task Queue.
Main server distributes: scraping, bill analysis.
Nodes must be verified (municipality signature).

### Phase 3 — TrueRepublic Bridge (FUTURE)
ekklesia nodes use TrueRepublic infrastructure.
PNYX Token incentivizes node operators.
ZK-Proofs for verifiable computation.
ekklesia stays free for citizens.

### Separation of Concerns
ekklesia.gr  = Civic Platform (political decentralization)
TrueRepublic = Infrastructure Layer (technical decentralization)
