# Dashboard HLR display repair

Status: initial fix (972764b) deployed and live-verified; review follow-up pending.

The overview waits for multiple services. Every request now has a 12-second
abort deadline including JSON body consumption. Failed requests yield unavailable
data rather than an invented zero. The existing refresh cadence is unchanged.

HLR primary and fallback progress use the API's `initial` field, not the absent
`total` field or a fallback denominator. Both overview and its finance tab label
the value as a local estimate, not a live provider balance. No provider request,
credit adjustment, credential change or verification-logic change was made.

Validation: four synthetic tests (`node --test overview.test.mjs` in
apps/dashboard), production build and TypeScript pass. Lint exits zero with nine
existing warnings. Kimi reviewed the initial patch without blockers; its finance
tab observation was corrected and the production build rerun. These standalone
tests are not yet wired into CI.

Before every subsequent isolated rollout, reconcile the deployed Dashboard
baseline with the candidate, create and record a Git rollback tag, and retain
the existing runtime settings and a rollback image. Do not include unrelated
pending API/mobile changes. The first rollout retained a Docker rollback tag;
it did not establish a Git rollback tag, so do not backdate that evidence.
