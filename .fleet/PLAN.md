# Ekklesia NEO 12 — milestone plan

- Proven main / rollback remains `4cc11930f4be82ba2d012def487fb34abca9da26`; no merge or deployment occurred.
- EKA-63 is published only as Draft PR #405 at exact head `3c6483fa701c70cb8c07a4159eeb345c6e24869a`, base `4cc11930`; CI/Security is green. Greek wording remains a Gio/native-content gate.
- CodeRabbit allowance has not reset; at least nine completed PRs wait. This is a Gio/review-capacity bottleneck only: no retry, bypass or parallel review request.
- EKA-24 map T-509 was corrected after cross-review found the semantic dependency on Draft #397. Integrated map base `cde455cc` contains exact #397 head `399b42502854833d2975950f6b9f6b991cd0ff23` plus rendered EKA-18/EKA-22/EKA-24 diagrams.
- EKA-24 final local code head `5390412d`: product `computeNullifier(phone, serverSalt)` removed; legacy Web tests and the exact EKA-22 Web KAT derive privately in test code. Combined tests 32/32, typecheck and production build passed; independent corrected review is `ok`.
- T-510 is preserved as stacked Draft PR #406 on branch `agent/codex/T-510-397-integration`. It must not merge before #397 and needs a fresh post-#397 base/diff proof before review. Rollback is the selected #397 head `399b4250` (or proven main for the whole stack).
- Serial review priority remains #395, #388, then #401 → #398 → #396 → #400 (after #399) → #399 → #397 → #402 → #404. #405 and T-510 are not in that queue.
- Gio-only list remains: EKA-13 rollout; #389 deploy/Sentry/rotation; T-498/T-501 decisions; #383; EKA-21/KDF; EKA-65. No production, data, secrets, Sentry-event inspection, rotation, SSH, KDF action or deploy.
- Next milestone: wait for the serial review/allowance gate or select another genuinely ungated mapped EKA node in a fresh session; do not extend this session further.
