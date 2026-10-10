# Follow-up API/Web deploy runbook (2026-10-10)

**Status: IMPLEMENTED as documentation — NOT EXECUTED — not a deploy approval.**
Nothing in this file has been run against production. Its existence does not
mean a release happened or is scheduled, and no public page may announce one
based on it. Existing private deploy packages are historical only; this runbook
does not reuse them.

Scope: one future follow-up release of the `api` and `web` services only,
including Alembic revision `y801a2b3c4d5` (Diavgeia ADA length). `db`, `redis`,
`ollama`, `dashboard`, `docker-proxy` and `monitor` are not touched. The general
procedure is in [infra/hetzner/DEPLOY.md](../../infra/hetzner/DEPLOY.md); where
the two differ for this release, this file governs the order
build → migration → per-service stop/up (the older "stop `api` before build"
guidance does not apply here).

The web scope also includes #565 (merged as `537eecd8`): request-time SSR for
EL/EN bills and results with uncached public reads (`cache: "no-store"`).
Its merge is not a deploy approval; the follow-up release remains a Gio gate.

Placeholders: `<SHA>` full 40-character approved commit, `<REL>` release
directory `/opt/ekklesia/releases/<name>-<SHA8>-<UTC TS>/`, `<TS>` UTC timestamp,
`<PRIV>` a private operator directory (mode `0700`, never in the repo, never
uploaded). `COMPOSE` below means
`docker compose -p docker --env-file /opt/ekklesia/.env.production -f infra/docker/docker-compose.prod.yml`
run from `/opt/ekklesia/app` — the same base chain that produced the live
containers, confirmed in step 2.

## 0. Entry gates (all required before any host command)

| Gate | Evidence recorded |
|---|---|
| Gio's explicit scope for this release (services, migration, window) | quote + UTC time |
| Exact full SHA `<SHA>` on `main`, immutable (no moving `origin/main`) | SHA |
| Green CI on exactly `<SHA>` | run URLs |
| Review of the diff since the live commit | reviewer + PR |
| Runtime rollback records possible (old image IDs, old commit, dump) | confirmed in steps 2–4 |
| `HETZNER_MONTHLY_COST` decision by owner | see §9 |

Missing any gate → stop. Do not start "read-only" host work on an unapproved scope.

## 1. JEV first, separately

Run the dispatch judgement (JEV: risk, reversibility, narrowness, `needs_human`)
as its own step, **read its result**, and continue only if it allows the scope.
JEV input and output contain no secrets, env values or customer data.

## 2. Read-only inventory

- `git -C /opt/ekklesia/app rev-parse HEAD` and `git status --porcelain`
  (dirty tree → stop; never stash/reset/overwrite someone's work).
- Per service `api`, `web`: container name, image tag and **image ID**
  (`docker inspect --format '{{.Image}}' ekklesia-api` style single fields —
  never a full `docker inspect`, never `env`/`config` dumps).
- Exact Compose chain from the label
  `com.docker.compose.project.config_files` (single-field format) and the
  project name. If it differs from `COMPOSE`, use the recorded chain everywhere below.
- Alembic state from the **running** API: `alembic current` only. Expected:
  `x701a2b3c4d5` (live) — any other value → stop and escalate.
- Free space on the Docker data volume ≥ 8 GB, else stop.

Record in `<REL>/inventory.txt` (no secret values).

## 3. Rollback records (private release files)

- `git tag rollback-pre-<name>-<TS> <live commit>` in `/opt/ekklesia/app`.
- `docker tag <old api image ID> ekklesia-api:rollback-pre-<name>-<TS>` and the
  same for `web`.
- Write `<REL>/compose.rollback.yml` pinning `image:` to these old image IDs/tags
  for `api` and `web` (no `build:` use), and `<REL>/compose.release.yml` with the
  new release tags. Keep old checkout metadata (commit, chain) in `<REL>/README`.
- Never delete old releases, dumps, tags or images in this release.

## 4. Database backup (custom format, fail-closed)

Do **not** use `backup-offsite.sh` or `/opt/ekklesia/scripts/backup.sh`
(cleanup, upload and Redis actions are out of scope).

```bash
set -euo pipefail; umask 077; set -o noclobber
OUT=<PRIV>/ekklesia_prod_pre-<name>-<TS>.dump
docker exec ekklesia-db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$OUT.tmp"
# PG15 parser (same major as postgres:15-alpine) validates the archive TOC:
docker exec -i ekklesia-db pg_restore -l < "$OUT.tmp" > <PRIV>/toc-<TS>.txt
test -s "$OUT.tmp" && test -s <PRIV>/toc-<TS>.txt
mv --no-clobber "$OUT.tmp" "$OUT"; test ! -e "$OUT.tmp"
chmod 600 "$OUT" <PRIV>/toc-<TS>.txt
stat -c %s "$OUT"; sha256sum "$OUT"
```

Credentials stay inside the db container environment and are never echoed.
`noclobber` makes an existing name fail instead of overwriting. Publish only
size + SHA-256 + "pg_restore -l OK"; the TOC stays private. **A readable TOC is
not a restore proof**; a restore drill is a separate scope.

## 5. Checkout the approved SHA

```bash
git -C /opt/ekklesia/app fetch origin
git -C /opt/ekklesia/app merge --ff-only <SHA>
test "$(git -C /opt/ekklesia/app rev-parse HEAD)" = "<SHA>"
test -z "$(git -C /opt/ekklesia/app status --porcelain)"
```

No `checkout -f`, no `reset --hard`. Non-fast-forward or dirty → stop.

## 6. Build candidates (services keep running)

```bash
COMPOSE -f <REL>/compose.release.yml build api web
```

Same base file + release override, so existing tags stay intact. Record the new
image IDs. The web image copies `docs/` into `public/` (landing, community, wiki),
so static pages change with this build.

## 7. Migration y801 from the NEW API image

The host checkout alone is not enough and the **old** API image does not
contain `y801`. Use a one-off container of the new image (Alembic at `/app`,
URL from `settings.database_url`):

```bash
COMPOSE -f <REL>/compose.release.yml run --rm --no-deps -T api alembic current
COMPOSE -f <REL>/compose.release.yml run --rm --no-deps -T api alembic heads
```

Gate: `current` = `x701a2b3c4d5`, `heads` = exactly one line `y801a2b3c4d5 (head)`.
Extra heads, a different current, or any pending revision besides `y801` → stop.
Confirm old-API compatibility with the wider 9..32 check BEFORE `upgrade head`:
the old API is still serving during migration; an unknown result → stop.
Then:

```bash
COMPOSE -f <REL>/compose.release.yml run --rm --no-deps -T api alembic upgrade head
COMPOSE -f <REL>/compose.release.yml run --rm --no-deps -T api alembic current   # expect y801a2b3c4d5
```

What `y801` does: replaces `diavgeia_decisions_ada_chk` from
`length(ada) BETWEEN 10 AND 32` to `BETWEEN 9 AND 32`. No regex, no
transliteration, no data change. The old API is expected to stay compatible
with the wider check, but that is an **operator gate**: confirm it before
continuing with the old API still serving.

## 8. Switch per service

For `api`, then `web`, one at a time:

```bash
COMPOSE -f <REL>/compose.release.yml stop <svc>
COMPOSE -f <REL>/compose.release.yml up -d --no-deps --no-build <svc>
```

After each: container healthy / no restart loop, running image ID equals the
step-6 candidate ID; `api` → `https://api.ekklesia.gr/health`.

## 9. Smoke checks (390 px and 1280 px)

- Viewports 390 and 1280: `/el`, `/en`, bills list + detail, results,
  `/community.html`, `/wiki/`; language switch EL↔EN; CPLM checks as in the release scope.
- #565: populated EL/EN bills/results contain initial cards in SSR HTML;
  successful seeded views make no duplicate client GET. Check empty/API-failure
  fallback separately; do not assume visible result counts.
- Community funding block shows exactly one of ready / unavailable / stale —
  never invented numbers.
- `HETZNER_MONTHLY_COST`: check only that the variable name exists or that the
  public value equals the expected 25 EUR default; never read or write the env value.
- API logs **since this restart**: Diavgeia scrape log lines present and no
  `CheckViolation`.
- `POST /api/v1/payments/webhook` with a deliberately invalid
  `stripe-signature` → `400` (never a real Stripe event).
- `POST /api/v1/vote` with an empty JSON body → `422`.

No seeding, no `seed_knowledge_base.py sync`, no push/flag change (PUSH_DATA_ONLY
stays OFF, intake stays closed).

## 10. Postflight

`<REL>/postflight.txt`: `<SHA>`, old and new image IDs for `api`/`web`, DB
revision (`y801a2b3c4d5`), UTC start/end, dump size + SHA-256, smoke evidence.
Only after this file exists and all checks pass may anyone call the release LIVE.

## 11. Rollback

Trigger: any failed check in steps 8–9.

**Application rollback (default):**

```bash
COMPOSE -f <REL>/compose.rollback.yml stop <svc>
COMPOSE -f <REL>/compose.rollback.yml up -d --no-deps --no-build <svc>
```

for `api` and/or `web` only, same approved chain, pinned old image IDs; never
rebuild. Do not touch `db`, `redis`, `dashboard`, `monitor`. The schema stays at
`y801` (9..32) — this is the default and is safe only if old-API compatibility
was confirmed in step 7. No automatic `git reset`/checkout over a dirty tree,
no prune/delete.

**Database downgrade / restore — never automatic.** Only as a separate explicit
DB decision with its own backup, drill, accepted data loss and quiesced traffic:

- `alembic downgrade x701a2b3c4d5` restores `10..32` as **NOT VALID**: existing
  9-character rows stay, but every later INSERT or UPDATE of such a row
  (even with unchanged `ada`) is rejected. Do not `VALIDATE`, delete or
  normalise rows.
- The downgrade cannot run from the old image (it has no `y801` file); it
  needs the candidate image and is allowed only if separately authorised.
- Restoring the step-4 dump loses every write after the dump.
