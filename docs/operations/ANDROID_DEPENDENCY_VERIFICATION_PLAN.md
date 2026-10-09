# Android dependency verification: source gap and implementation gate

Status: **planned, not implemented or validated**. Source baseline
`a22508e33d05bf85dcdf312455df51ca29a0d287` (2026-10-09). This document
does not approve native builds, signing, uploads, production changes or release.

## Current boundary

- `apps/mobile/.gitignore` excludes generated `android/`; only
  `android/app/build.gradle` is tracked there. No versioned
  `verification-metadata.xml` or Wrapper checksum contract exists in this baseline.
- `scripts/build-play.sh` and `scripts/build-direct.sh` run clean Expo prebuild
  before release Gradle tasks. An edit confined to generated Android files would
  not be a durable control. The registered prebuild plugins contain no dependency
  verification wiring.
- Mobile CI checks the JavaScript dependency graph, typecheck and tests; it does
  not establish Maven/Gradle input integrity. The existing release gate checks
  final artifact hashes, zkey provenance, signatures and native alignment. Those
  checks must remain, but do not verify the downloaded build dependencies.
- A local ignored Wrapper currently names 8.14.3 without
  `distributionSha256Sum`. This observation is not an accepted-commit version pin
  or proof of the distribution/Wrapper JAR's provenance.

This is a supply-chain hardening gap, **not evidence of a compromised artifact**.
The actual dependency graph and its trusted hashes cannot be reconstructed from
the tracked files alone.

## Bounded implementation proposal

1. Keep reviewed verification metadata and the Wrapper integrity contract in a
   versioned source directory outside generated `android/`. Record the precise
   Gradle distribution, Wrapper JAR and independently checked checksum origins;
   do not invent hashes or accept arbitrary downloaded bytes.
2. Add a prebuild plugin, registered in `app.json`, that transfers the reviewed
   metadata and validates the generated Wrapper contract. Reject missing or
   mismatched inputs before invoking Gradle. Expo config plugins are the durable
   hook for regenerated native files. [Expo config plugins](https://docs.expo.dev/config-plugins/introduction/)
3. Review the resolved graph for both Play and Direct, including applicable
   variants and plugin/build dependencies. A generated checksum baseline is only
   a candidate: generation trusts the current repository contents and therefore
   requires independent review. Ordinary CI/release tasks must not silently
   regenerate or trust new hashes. [Gradle dependency verification](https://docs.gradle.org/current/userguide/dependency_verification.html)
4. Wire both build helpers to enforce strict verification, without `lenient`,
   `off`, wildcard trust or ignored failures. Unknown and changed dependencies
   must stop the build. [Gradle verification modes](https://docs.gradle.org/current/userguide/dependency_verification.html#sec:dependency-verification-modes)
5. Check the distribution checksum and Wrapper JAR separately. Distribution
   checksum verification occurs on a new download; an existing cache alone is
   not a fresh negative-test receipt. [Gradle Wrapper integrity](https://docs.gradle.org/current/userguide/gradle_wrapper.html)

## Acceptance before claiming enforcement

- Fixture tests: clean prebuild preserves/reinstalls the exact reviewed metadata;
  missing metadata, wrong distribution/version/checksum and conflicting generated
  inputs fail closed before a native task starts.
- An isolated, explicitly authorized native-resolution run covers both flavor
  graphs with the accepted source/toolchain and strict verification. Use scratch
  caches and the existing `--no-daemon --max-workers=2` build limit. No signing
  key, production environment or provider credential belongs in this test.
- Negative checks against scratch inputs: a modified dependency artifact, an
  unknown dependency, and a wrong fresh-distribution checksum each fail before
  execution of that input. Do not mutate or delete the operator's normal cache.
- Attach source/ref, graph coverage, checksum provenance and positive/negative
  logs to the exact candidate; then green CI and independent review. Fixture-only
  tests do not substitute for real Gradle enforcement.
- Keep the existing release/OEM/16-KB/Direct/Alpha/Gio gates separate. No Gradle
  upgrade, metadata allowlist or release permission is granted by this plan.

Verification in this change: source inventory and official documentation only.
No Gradle/dependency resolution, download, native build, signing, upload or
runtime/configuration change was performed. The original verification TODO stays
open until the enforcement and all evidence above exist.
