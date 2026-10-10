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
| 1 | [#110](https://github.com/NeaBouli/pnyx/security/dependabot/110) representative, GHSA-hp3w-g68c-fv3c / CVE-2026-97058, medium | sprintf-js `<=1.1.3` → `1.0.3` | `sprintf-js@1.0.3` ← root `argparse@1.0.10` ← `@istanbuljs/load-nyc-config/node_modules/js-yaml@3.15.2` ← `@istanbuljs/load-nyc-config` (Jest coverage). Correction (T-9061): `@expo/xcpretty/node_modules/js-yaml@4.3.2` → `argparse@2.0.1` has **no** `sprintf-js` edge and is not in this chain | S3 (Jest coverage config loader) | Source: CLI args/format strings inside argparse. Control: developer/CI. Sink: `sprintf`. | Proven: lockfile edge only. Not proven: whether argparse ever formats attacker-controlled precision; whether anything is bundled into S1. No direct `sprintf-js`/`argparse` import in inspected `apps/representative/App.tsx` or `apps/representative/web` (rg, absence ≠ proof). | needs_review | 6 |
| 2 | [#109](https://github.com/NeaBouli/pnyx/security/dependabot/109) mobile, GHSA-hp3w-g68c-fv3c / CVE-2026-97058, medium | sprintf-js `<=1.1.3` → `1.0.3` | same chain as #110 in `apps/mobile` | S3 | as #110 | as #110 (`apps/mobile/src`) | needs_review | 7 |
| 3 | [#107](https://github.com/NeaBouli/pnyx/security/dependabot/107) web, GHSA-vfj7-8cjw-p6xm / CVE-2026-93687, high | braces `<=3.0.3` → `3.0.3` | `micromatch` ← `fast-glob` (+ `@next/eslint-plugin-next/node_modules/fast-glob`) ← `@ducanh2912/next-pwa`, `@next/eslint-plugin-next` | S3 (`next.config.mjs` l.1/6/69 `withPWA`, `next build` in `Dockerfile.prod` l.23); S2 not excluded | Source: glob patterns from `next-pwa` constants and `next.config.mjs` options (T-9061: `sync()` calls in `@ducanh2912/next-pwa@10.2.9` `dist/index.cjs` l.738/869/1029/1038). Control: repo owner. Sink: `braces` via `fast-glob` `expandBraceExpansion` → `micromatch.braces` (T-9061 evidence below). | Proven: build-plugin edge (`next.config.mjs::withPWA`), Dockerfile build stage installs the full tree (l.5). Not proven: whether Next output-file tracing copies `braces`/`micromatch` into `.next/standalone` (S2), and whether any S2 request path passes request data into a glob. | needs_review | 1 |
| 4 | [#106](https://github.com/NeaBouli/pnyx/security/dependabot/106) representative, GHSA-vfj7-8cjw-p6xm / CVE-2026-93687, high | braces `<=3.0.3` → `3.0.3` | `micromatch` ← `metro-file-map`, `jest-haste-map`, `@jest/transform`, `jest-message-util`; `metro-file-map` ← `metro`, `@expo/metro`, `expo/node_modules/@expo/cli` | S3/S4 (Metro, Jest) | Source: project/Metro/Jest config globs. Control: repo owner. Sink (corrected T-9061): `metro-file-map@0.83.8` calls only `micromatch.some` → `picomatch`, not the `braces` package; Jest-side callers not read. | Proven: lockfile edges to Metro/Jest. Not proven: absence from S1 bundle; any S4 dev-server path taking network-supplied patterns. | needs_review | 4 |
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

## Upstream source evidence (T-9061, static read only)

Plain-file GETs of public upstream source at the tag/commit matching the locked version. Nothing
was installed, executed or bundled. Tarball integrity vs. this source (source parity) is
**not verified**.

- **micromatch 4.0.8** (`https://raw.githubusercontent.com/micromatch/micromatch/4.0.8/index.js`):
  l.4 `const braces = require('braces')`. The `braces` package is called only from
  `micromatch.parse` (l.424–428: `braces(String(pattern), options)` then `picomatch.parse`),
  `micromatch.braces` (l.451–456) and `micromatch.braces(..., {expand: true})` (l.465). The
  matching entry points `micromatch()` (l.32/49), `isMatch` (l.128), `matcher` (l.109) and
  `makeRe` (l.392) call `picomatch` directly, whose own brace handling is not the `braces`
  package. Callers: see the fast-glob and metro-file-map items below.
- **argparse 1.0.10** (`https://raw.githubusercontent.com/nodeca/argparse/1.0.10/lib/help/formatter.js`):
  l.16 `require('sprintf-js').sprintf`; calls at l.325 (`usage`, `{prog}`), l.559 (description
  text, `{prog}`) and l.744 (`sprintf(this._getHelpString(action), params)`). The format string is
  the parser's own usage/help text (programmer-defined options), not parsed YAML values.
  **sprintf-js 1.0.3** (`https://raw.githubusercontent.com/alexei/sprintf.js/1.0.3/src/sprintf.js`):
  precision `match[7]` comes from the format string and feeds `toExponential` (l.75), `toFixed`
  (l.79), `toPrecision` (l.82). Not read: whether `js-yaml@3.15.2` or `load-nyc-config` invoke
  the argparse help formatter at all (js-yaml uses argparse for its CLI binary). #109/#110 stay
  `needs_review`.
- **@expo/code-signing-certificates 0.0.6**: npm registry `gitHead`
  `83f39c0e8f9c2833571951f3fc21464c9df4bcaf`, dependency `node-forge ^1.3.3`; source
  `https://raw.githubusercontent.com/expo/code-signing-certificates/83f39c0e8f9c2833571951f3fc21464c9df4bcaf/src/main.ts`.
  node-forge verify calls: l.232 `certificate.verify(certificate)` in
  `validateSelfSignedCertificate` (self-signature check of a caller-supplied cert), l.265
  `publicKey.verify(...)` in `signBufferRSASHA256AndVerify` (verifies its own fresh signature),
  l.319 `csr.verify(csr)` in `generateDevelopmentCertificateFromCSR` (self-signed CSR). None is
  a verification of a third-party signature against a trusted key; all are signing/creation/
  self-verify paths. Not read: `@expo/cli@54.0.27` callers of these functions and its **direct**
  `node-forge@1.4.0` use, or whether any dev-server flow verifies network-supplied signatures.
  #102/#103 stay `needs_review`.

### Follow-up callers (T-9061 continuation, static read only)

Local cached modules were read as text only (never required/executed) from the main checkout
`/Users/gio/Desktop/repo/pnyx/apps/web/node_modules` where the version matched the lockfile;
other files are published-version-addressed plain-file GETs from `unpkg.com`. Tarball
integrity/source parity is **not verified** for either source.

- **fast-glob 3.3.2** (local cache, version = lock): `out/managers/tasks.js` l.26–27
  `if (settings.braceExpansion) patterns = utils.pattern.expandPatternsWithBraceExpansion(patterns)`;
  `out/utils/pattern.js` l.136–137 `expandBraceExpansion` →
  `micromatch.braces(pattern, { expand: true, nodupes: true, keepEscaping: true })`, i.e. the
  `braces` package (micromatch l.451–456). `micromatch.scan`/`makeRe` (pattern.js l.150/170) go to
  `picomatch`. **fast-glob 3.3.1** (local cache, `@next/eslint-plugin-next/node_modules`): same
  lines, `micromatch.braces(pattern, { expand: true, nodupes: true })`. So the #107 braces sink
  is real for both copies, on the brace-expansion default path.
- Pattern origin #107: `@ducanh2912/next-pwa@10.2.9` (local cache, version = lock)
  `dist/index.cjs` l.738 (`**/*` plus negations built from the configured `swPath`), l.869
  (`"{src/,}index.{ts,js}"`, `cwd: customWorkerSrc`), l.1029/1038 (fixed worker names, `swPath`,
  `customWorkerPrefix`). All are package constants or `next.config.mjs` options: repo-owner
  controlled, build time (S3). `@next/eslint-plugin-next` `dist/utils/get-root-dirs.js` l.15
  `globSync(rootDir…)` takes ESLint `rootDir` settings; the cached copy is 16.3.1 while the lock
  pins 16.3.8, so that caller is **not verified at the pinned version**. No request-data → glob
  path was found; S2 presence stays G2.
- **metro-file-map 0.83.8** (`https://unpkg.com/metro-file-map@0.83.8/src/watchers/common.js`):
  l.14 `require("micromatch")`; `includedByGlob(type, globs, dot, relativePath)` l.23–29 calls
  only `micromatch.some(relativePath, "**/*")` / `micromatch.some(relativePath, globs, {dot})`.
  `micromatch.some` (4.0.8 l.264–273) compiles each pattern with `picomatch`, not `braces`.
  Correction: the earlier "Sink: braces" for #105/#106 is not supported by this file. Not read:
  other `metro-file-map` files (grep of the cached 0.83.3 found only this file), `jest-haste-map`,
  `@jest/transform`, `jest-message-util`; any of them could still call `micromatch.braces`.
- **@expo/cli 54.0.27** (`https://unpkg.com/@expo/cli@54.0.27/build/src/utils/codesigning.js`):
  `getProjectPrivateKeyAndCertificateFromFilePathsAsync` l.315–325 →
  `validateSelfSignedCertificate(certificate, {publicKey: certificate.publicKey, privateKey})`
  on the project's own cert/key files; `validateStoredDevelopmentExpoRootCertificateCodeSigningInfo`
  l.335–358 parses the cached Expo certificate chain and checks only `validity` dates (no
  signature verify); `fetchAndCacheNewDevelopmentCodeSigningInfoAsync` l.367–387 generates key
  pair + CSR; `signManifestString` l.412–415 → `signBufferRSASHA256AndVerify` (verifies its own
  signature). **Direct node-forge** (`https://unpkg.com/@expo/cli@54.0.27/build/src/run/ios/codeSigning/Security.js` l.41–42
  `require("node-forge")`, l.70 `pki.certificateFromPem(pem)` on output of the local macOS
  `security` tool): parse only, no verify. No call verifies a third-party RSA PKCS#1 v1.5
  signature in these two files. **Trust boundary unresolved, not a safety claim:** the file list
  came from a grep of the cached 54.0.24 build; other 54.0.27 files, the Expo-server-delivered
  certificate chain (no signature check in the inspected validation function, l.342–349;
  transport/protocol trust was not assessed) and whether `expo-updates`/
  `expo-dev-client` verify manifests in the app were not read.
- **js-yaml 3.15.2** (`https://unpkg.com/js-yaml@3.15.2/index.js`, `/package.json`):
  `index.js` requires only `./lib/js-yaml.js`; package.json `bin: {js-yaml: bin/js-yaml.js}`,
  `dependencies.argparse ^1.0.7`. **@istanbuljs/load-nyc-config 1.1.0**
  (`https://unpkg.com/@istanbuljs/load-nyc-config@1.1.0/index.js`) l.80
  `require('js-yaml').load(...)`: library import, not the CLI binary. Not read: `lib/js-yaml/*.js`
  to prove the library never requires `argparse` (expected only in `bin/`). If confirmed, the
  argparse/sprintf-js edge is install-only for #109/#110.

## Missing facts and safe next steps

| Gap | Missing fact | Safe next step (not done here) |
| --- | --- | --- |
| G1 | Partly closed (T-9061 sources above). Open: tarball/source parity; `@next/eslint-plugin-next@16.3.8` caller; Jest-side micromatch callers; remaining `metro-file-map`/`@expo/cli` files; `js-yaml/lib` argparse absence | Read those pinned sources in an isolated sandbox, without executing them |
| G2 (#107) | Is `braces` in `.next/standalone`? | List `.next/standalone/node_modules` and `.next/*.nft.json` from a sandboxed `next build` of this commit |
| G3 (#105/#106) | Is braces/micromatch in the Metro bundle? | Inspect the sandboxed release bundle's module map |
| G4 (#102/#103) | Which Expo CLI flows verify untrusted signatures? | Two `@expo/cli@54.0.27` files read (no third-party verify). Open: full-package grep at the pinned version, server-delivered chain trust, `expo-updates`/`expo-dev-client` manifest verification |
| G5 (#109/#110) | Does argparse ever format with attacker-controlled precision? | sprintf sites help/usage only; `load-nyc-config` imports the js-yaml library, not the bin. Open: grep `js-yaml@3.15.2/lib` for `argparse` |
| G6 | Upstream fix availability | Re-check advisories before `review_by` 2026-11-01. Any override or upgrade needs a full app build/tests and owner review. |

Ranks order the queue for that follow-up: shipped Web server exposure first (#107), then Expo
CLI signature verification (#102/#103), then Metro/Jest DoS (#105/#106), then the medium
sprintf-js items (#109/#110).
