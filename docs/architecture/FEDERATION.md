# Federated Computing Architecture
## ekklesia.gr + TrueRepublic
Linear: NEA-113

### Current status — Central municipal data (NOW)
Municipal and regional data is served by the central ekklesia.gr API.
The dashboard exposes read-only operational status and municipal data checks.
Public node registration, independent municipal runtimes, and federation sync are not active.

### Phase 1 — Independent municipal nodes (POST-ALPHA)
Nodes = Greek municipalities, each running independently.
Data sync via Federation API. No compute sharing.
Nodes must be verified before federation access is enabled.

### Phase 2 — Task Distribution (FUTURE)
Celery + Redis Task Queue.
Main server distributes: scraping, bill analysis.

### Phase 3 — TrueRepublic Bridge (FUTURE)
ekklesia nodes use TrueRepublic infrastructure.
PNYX Token incentivizes node operators.
ZK-Proofs for verifiable computation.
ekklesia stays free for citizens.

### Separation of Concerns
ekklesia.gr  = Civic Platform (political decentralization)
TrueRepublic = Infrastructure Layer (technical decentralization)
