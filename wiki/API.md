<!--
@wiki-page API
@update-hint Update on new endpoints or changes.
@ai-anchor WIKI_API
-->

# API Documentation

Base URL: `https://ekklesia.gr/api/v1` (Production) | `http://localhost:8000` (Dev)

Swagger UI: `http://localhost:8000/docs`

## MOD-01: Identity

| Method | Endpoint | Description |
|---|---|---|
| POST | `/identity/verify` | SMS → Ed25519 Keypair |
| POST | `/identity/revoke` | Revoke key |
| POST | `/identity/status` | Check status |

## MOD-02: VAA

| Method | Endpoint | Description |
|---|---|---|
| GET | `/vaa/statements` | 38 positions (el/en) |
| GET | `/vaa/parties` | 8 parties |
| POST | `/vaa/match` | Matching algorithm |

## MOD-03: Parliament

| Method | Endpoint | Description |
|---|---|---|
| GET | `/bills` | All bills (filter, pagination) |
| GET | `/bills/trending` | By relevance score |
| GET | `/bills/{id}` | Detail + AI summaries |
| POST | `/bills/{id}/transition` | Lifecycle transition |
| POST | `/bills/admin/create` | Create new bill |

## MOD-04: CitizenVote

| Method | Endpoint | Description |
|---|---|---|
| POST | `/vote` | Submit vote (Ed25519) |
| GET | `/vote/{id}/results` | Results + Divergence Score |
| POST | `/vote/{id}/relevance` | Up/Down signal |
