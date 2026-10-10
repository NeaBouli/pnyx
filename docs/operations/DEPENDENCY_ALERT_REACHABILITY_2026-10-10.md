# Dependency alert reachability — 2026-10-10 (T-9060)

Static, documentation-only assessment of the **seven** Dependabot alerts that were open in
`NeaBouli/pnyx` at the GitHub REST snapshot of 2026-10-10T10:09Z. Nothing in this document
changes packages, lockfiles, the audit allowlist, CI or alert state.

## Scope and evidence basis

- Source base: `aa99c4c806709962d75d7e4bcb6d916666b56244`. The worktree HEAD `6f131fbf`
  (docs-only #545) has no diff against it in `apps/{web,mobile,representative}/package{,-lock}.json`
  or `apps/web/Dockerfile.prod`.
- Alert metadata (number, manifest, relationship `transitive`, scope `runtime`,
  `first_patched_version = null`) is a dated GitHub snapshot. It does not prove that no newer
  upstream release exists elsewhere.
- Severity below is the **reported advisory severity**, not an Ekklesia-confirmed severity.
- Methods: `jq` over the three lockfiles, `rg` over app sources/config, reading
  `apps/web/Dockerfile.prod`, `apps/web/next.config.mjs`, `.github/npm-audit-allowlist.json`,
  `scripts/npm-audit-gate.mjs`. No install, build, test, audit, runtime, Metro, Docker or
  scanner run. Local `node_modules` were **not present** for the checked packages, so
  dependency source code was not read: every "caller" statement stops at the lockfile edge
  (proof gap G1).
- Lockfile `dev=false` / GitHub scope `runtime` only means the package is not marked dev in
  `package-lock.json`. It does not mean the package ships in an app or is attacker-reachable.
- Static source and lockfile only; nothing here describes the deployed build or a store binary.

Surfaces distinguished:

| Code | Surface |
| --- | --- |
| S1 | Shipped mobile/representative app bundle (JS compiled by Metro into the APK/IPA) |
| S2 | Production Web standalone server (`apps/web/Dockerfile.prod` runner stage: `.next/standalone`, `.next/static`, `public`, l.29–34) |
| S3 | Build tooling (`next build` incl. `@ducanh2912/next-pwa`; Metro/Expo CLI; Jest) on developer/CI machines |
| S4 | Developer servers (`next dev`, `expo start`/Metro dev server) |

## Advisories (own short summary; upstream text is untrusted evidence)

- **[GHSA-hp3w-g68c-fv3c / CVE-2026-97058](https://github.com/advisories/GHSA-hp3w-g68c-fv3c)**, `sprintf-js <= 1.1.3`, reported *medium*: a
  format string with attacker-controlled precision can throw `RangeError` (crash/DoS). Needs
  the attacker to control the format string or precision passed to `sprintf`.
- **[GHSA-vfj7-8cjw-p6xm / CVE-2026-93687](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)**, `braces <= 3.0.3`, reported *high*: deeply nested
  brace patterns exhaust the stack (DoS). Needs attacker-controlled glob/brace patterns.
- **[GHSA-86w9-cpqp-85rv / CVE-2026-85393](https://github.com/advisories/GHSA-86w9-cpqp-85rv)**, `node-forge <= 1.4.0`, reported *high*: RSA
  PKCS#1 v1.5 signature verification accepts an extra nested DigestAlgorithm structure
  (signature-verification weakness). Needs attacker-supplied signatures/certificates verified
  through node-forge.

## Alerts (original order, one row each)

| # | Alert | Package (affected → locked) | Lockfile parents (`apps/<x>/package-lock.json`) | Surface class | Source → control → sink | Proven / not proven | Verdict | Queue rank |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [#110](https://github.com/NeaBouli/pnyx/security/dependabot/110) representative, GHSA-hp3w-g68c-fv3c / CVE-2026-97058, medium | sprintf-js `<=1.1.3` → `1.0.3` | `argparse` ← `js-yaml` (`@expo/xcpretty/node_modules/js-yaml`, `@istanbuljs/load-nyc-config/node_modules/js-yaml`) ← `@expo/xcpretty`, `@istanbuljs/load-nyc-config` | S3 (iOS build log formatter, coverage config loader) | Source: CLI args/format strings inside argparse. Control: developer/CI. Sink: `sprintf`. | Proven: lockfile edge only. Not proven: whether argparse ever formats attacker-controlled precision; whether anything is bundled into S1. No direct `sprintf-js`/`argparse` import in inspected `apps/representative/App.tsx` or `apps/representative/web` (rg, absence ≠ proof). | needs_review | 6 |
| 2 | [#109](https://github.com/NeaBouli/pnyx/security/dependabot/109) mobile, GHSA-hp3w-g68c-fv3c / CVE-2026-97058, medium | sprintf-js `<=1.1.3` → `1.0.3` | same chain as #110 in `apps/mobile` | S3 | as #110 | as #110 (`apps/mobile/src`) | needs_review | 7 |
| 3 | [#107](https://github.com/NeaBouli/pnyx/security/dependabot/107) web, GHSA-vfj7-8cjw-p6xm / CVE-2026-93687, high | braces `<=3.0.3` → `3.0.3` | `micromatch` ← `fast-glob` (+ `@next/eslint-plugin-next/node_modules/fast-glob`) ← `@ducanh2912/next-pwa`, `@next/eslint-plugin-next` | S3 (`next.config.mjs` l.1/6/69 `withPWA`, `next build` in `Dockerfile.prod` l.23); S2 not excluded | Source: glob patterns from repo config. Control: repo owner. Sink: `braces` expansion during build. | Proven: build-plugin edge (`next.config.mjs::withPWA`), Dockerfile build stage installs the full tree (l.5). Not proven: whether Next output-file tracing copies `braces`/`micromatch` into `.next/standalone` (S2), and whether any S2 request path passes request data into a glob. | needs_review | 1 |
| 4 | [#106](https://github.com/NeaBouli/pnyx/security/dependabot/106) representative, GHSA-vfj7-8cjw-p6xm / CVE-2026-93687, high | braces `<=3.0.3` → `3.0.3` | `micromatch` ← `metro-file-map`, `jest-haste-map`, `@jest/transform`, `jest-message-util`; `metro-file-map` ← `metro`, `@expo/metro`, `expo/node_modules/@expo/cli` | S3/S4 (Metro, Jest) | Source: project/Metro/Jest config globs. Control: repo owner. Sink: braces. | Proven: lockfile edges to Metro/Jest. Not proven: absence from S1 bundle; any S4 dev-server path taking network-supplied patterns. | needs_review | 4 |
| 5 | [#105](https://github.com/NeaBouli/pnyx/security/dependabot/105) mobile, GHSA-vfj7-8cjw-p6xm / CVE-2026-93687, high | braces `<=3.0.3` → `3.0.3` | same chain as #106 in `apps/mobile` | S3/S4 | as #106 | as #106 | needs_review | 5 |
| 6 | [#103](https://github.com/NeaBouli/pnyx/security/dependabot/103) representative, GHSA-86w9-cpqp-85rv / CVE-2026-85393, high | node-forge `<=1.4.0` → `1.4.0` | `@expo/code-signing-certificates` ← `expo/node_modules/@expo/cli`; `@expo/cli` also depends on `node-forge` directly | S3/S4 (Expo CLI) | Source: certificates/signatures handled by Expo CLI (code signing, dev-server HTTPS/manifest signing). Control: unknown — possibly network-supplied in dev flows. Sink: node-forge RSA verify. | Proven: lockfile edges into Expo CLI. Not proven: which CLI commands verify (vs. only create) signatures and with whose input; `expo-updates` absence from `apps/representative` was not re-verified at file level. No direct `node-forge` import in inspected `apps/representative/App.tsx` or `apps/representative/web` (rg). | needs_review | 2 |
| 7 | [#102](https://github.com/NeaBouli/pnyx/security/dependabot/102) mobile, GHSA-86w9-cpqp-85rv / CVE-2026-85393, high | node-forge `<=1.4.0` → `1.4.0` | same chain as #103 in `apps/mobile` | S3/S4 | as #103 | as #103 (`apps/mobile/src`) | needs_review | 3 |

No row is `confirmed` (no complete static boundary trace to an attacker-controlled sink) and
no row is `not_actionable` (no positive exclusion from S1/S2 was proven). Protected boundaries
(Ed25519 identity/voting, nullifier, POLIS) use `@noble/*` / PyNaCl per
`docs/architecture/MAP.md` and have no lockfile edge to these three packages. That is an
observation, not a reachability proof.

## Existing gate state (unchanged)

- `.github/npm-audit-allowlist.json` covers the braces tuple (dashboard/mobile/representative/web,
  approved Gio 2026-10-03) and the node-forge tuple (mobile/representative, approved Gio
  2026-10-02), both `review_by: 2026-11-01`.
- `scripts/npm-audit-gate.mjs` (l.12) only blocks `high`/`critical`. The medium sprintf-js alerts
  are therefore not blocked and have **no waiver**. That is not risk acceptance and not a fix.

## Missing facts and safe next steps

| Gap | Missing fact | Safe next step (not done here) |
| --- | --- | --- |
| G1 | Dependency source not read (no local `node_modules`) | Read the pinned tarball sources in an isolated sandbox, without executing them |
| G2 (#107) | Is `braces` in `.next/standalone`? | List `.next/standalone/node_modules` and `.next/*.nft.json` from a sandboxed `next build` of this commit |
| G3 (#105/#106) | Is braces/micromatch in the Metro bundle? | Inspect the sandboxed release bundle's module map |
| G4 (#102/#103) | Which Expo CLI flows verify untrusted signatures? | Read `@expo/cli` / `@expo/code-signing-certificates` source; confirm `expo-updates` absence in both manifests |
| G5 (#109/#110) | Does argparse ever format with attacker-controlled precision? | Read `argparse` 1.x call sites to `sprintf` |
| G6 | Upstream fix availability | Re-check advisories before `review_by` 2026-11-01. Any override or upgrade needs a full app build/tests and owner review. |

Ranks order the queue for that follow-up: shipped Web server exposure first (#107), then Expo
CLI signature verification (#102/#103), then Metro/Jest DoS (#105/#106), then the medium
sprintf-js items (#109/#110).
