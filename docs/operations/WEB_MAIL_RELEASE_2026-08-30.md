# Web and Mail API Release - 2026-08-30

## Scope and Result

The authorized sequential Web and mail-only API rollout completed successfully.
This receipt does not declare all of main deployed or all project work complete.

| Component | Actual source | Start (UTC) | Image SHA-256 |
|---|---|---|---|
| Web | `c935018313eb60b31b6935535fa67ed663e15336` (PR #259/#263) | 09:49 | `62fc691e923c2ef5f711331403ed878ed104eb9d451bbcf2e747e0a732010a2c` |
| API | `25d6c14499905bdcb901488f3ac00b275fd9b620` plus five PR #262 files | 09:51 | `3bdd1e7f63ad477f399e746845379706de5cbf9d0808e40c838483409e8895bf` |

API overlay files: `routers/contact.py`, `routers/newsletter.py`,
`routers/newsletter_admin.py`, `services/newsletter_service.py`,
`services/mail_policy.py`. All original image layers/configuration were retained.
Evaluation/representative policy, agent changes, dependency bumps, app artifacts
and dashboard changes outside that scope were not deployed.

## Verification

- Kimi application and rollout-guard reviews, followed by Sol verification.
- 69 Web tests (including 29 SSO lifecycle cases), zero lint warnings,
  typecheck/build and npm audit passed.
- Eight mocked mail payload tests passed in the exact candidate API image,
  without network or production secrets/mounts. Six rollout-guard tests passed.
- [Main CI](https://github.com/NeaBouli/pnyx/actions/runs/33302711039) and
  [Security Audit](https://github.com/NeaBouli/pnyx/actions/runs/33302711045) passed.
- 16 HTTP checks passed before and after each component switch. Protected
  endpoints still reject anonymous access; production OpenAPI stays disabled.
- Browser: SSO entry/retry, bills/results and result-to-bill navigation passed;
  no browser errors observed. No new real-citizen login or real mail delivery
  was performed. The prior mobile-layout evidence is not a new device canary.
- Final 09:59 UTC snapshot: zero new service errors/restarts/OOM; all 37 other
  containers and protected configuration unchanged. HLR drift was not present.
- API mail file hashes match PR #262; base `main.py`, `requirements.txt` and
  `evaluation.py` remain unchanged. Sender/list/schedule/DOI policy unchanged.
- Contact-recipient override matches the published external operator address.
  No inbox, DNS, secret, IAM, database or provider/contact modification.
- APK files were preserved, not rebuilt or published. The documented legacy
  alias remains vC57; canonical vC58 downloads use the GitHub release URL.

## Rollback

Git tag: `rollback-pre-web-mail-20260830-c935018` at source `25d6c14`.
Prior Web/API images and image-only Compose overrides remain in the private
release directory. Use the original Compose project and `--env-file`; never
shell-source production dotenv data or rebuild full main as an assumed rollback.
Restore only the affected service, then repeat health and configuration checks.
No rollback was needed. Retain these images through the next normal mail cycle.

## Remaining Evidence

- Voluntary smartphone SSO login/logout for this release.
- Controlled real mail and Reply-To/header verification after recipient approval.
- [GH#261](https://github.com/NeaBouli/pnyx/issues/261) subscriber reconciliation;
  [read-only audit](newsletter-delivery-audit.md) confirms a separate delivery gap.
- DMARC observation and GH#253 client-adoption/cutoff remain separately gated.

Original receipt: [GH#258 rollout comment](https://github.com/NeaBouli/pnyx/issues/258#issuecomment-5467997318).
