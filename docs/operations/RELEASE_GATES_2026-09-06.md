# Release Gates: September 6, 2026

This is a bounded follow-up to the published v1.0.32 release, not a new
release announcement. `docs/STATUS.md` remains the live-version authority.

| Gate | Verified evidence | Still required |
| --- | --- | --- |
| Google Closed Testing | v1.0.32 / 61 submitted, in external review | Google approval and actual tester availability |
| Production access | Console shows eight opted-in testers | Four additional testers and the qualifying continuous test period; opt-in is not daily activity |
| F-Droid | Official v1.0.31 ABI 601-604 build logs all succeed | Public repository APKs/catalog update; v1.0.32 metadata/build follow-up |
| Notification ledger (#290) | Bounded implementation and regression tests on a separate branch; native Direct debug build and Android exports pass | Android/OEM acceptance, normal PR review and a separate verified app release |
| Newsletter (#261) | No-write readiness evaluated all five confirmations; zero eligible entries and zero proposed writes | Consent evidence, preferences and provider-history review; per-recipient campaign preferences remain unenforced |
| Mail evidence | Authorized confirmation and single test newsletter received August 30; one historical DMARC aggregate available | Representative raw headers, unsubscribe evidence and complete observation window |
| Evaluation (#253) | Signed-read and consent guard source tested; corresponding new services absent from live API | Controlled API rollout, compatible-client adoption evidence, then separately approved cutoff |
| Security | Five Dependabot alerts remain visible; local installed-package backports retained | Compatible upstream releases, not forced major/ESM overrides |
| Forum canary | Login redirects to QR/app link; Play, F-Droid, Direct links and disabled iOS present | One new voluntary verified-smartphone login/logout; technical checks do not impersonate a citizen |

## API Rollout Gate

An isolated overlay image was built from the exact running API image plus
the five already-reviewed newsletter/evaluation files. No container was
replaced: configuration comparison detected a protected runtime/startup
configuration mismatch. Private evidence is held in the ignored operator
bridge. Do not reconcile protected values implicitly or deploy the whole
current branch to work around this gate.

Full API source verification in an isolated, disposable test environment:
1,008 passed, 11 skipped, 25 expected failures, four subtests passed. There
were four existing deprecation warnings. Earlier attempts lacked writable
fixtures/executable temporary files or isolated Redis and are not counted as
successful full runs. No production database was used for these tests.

The five newsletter Redis integration tests were then explicitly enabled
against the isolated disposable Redis instance and all passed. That test
instance has been stopped; the production Redis service was not used.

The focused overlay check passed 119 tests before the full source check.
Passing source tests is not evidence that the overlay is running in production.

## Official External Evidence

- [F-Droid metadata](https://gitlab.com/fdroid/fdroiddata/-/blob/master/metadata/ekklesia.gr.yml)
- [601 build](https://f-droid.org/repo/ekklesia.gr_601.log.gz),
  [602 build](https://f-droid.org/repo/ekklesia.gr_602.log.gz),
  [603 build](https://f-droid.org/repo/ekklesia.gr_603.log.gz),
  [604 build](https://f-droid.org/repo/ekklesia.gr_604.log.gz)
- [Public package API](https://f-droid.org/api/v1/packages/ekklesia.gr):
  still 1.0.29 / 581-584 at inspection; repository 604 APK returned 404.
- [Main CI](https://github.com/NeaBouli/pnyx/actions/runs/34026554854) and
  [Security Audit](https://github.com/NeaBouli/pnyx/actions/runs/34026554855)
  succeeded for the existing main revision, not this unmerged follow-up.

## Unchanged Boundaries

The local read-only Android emulator did not reach a usable Android session:
boot animation remained running and `service check package` / `service check
activity` both returned `not found`. Therefore no emulator or Samsung/Xiaomi
UI acceptance is claimed. Only the agent-owned emulator was stopped; no user
device, other agent or Codex process was restarted.

The initial mobile source suite passed 258 tests and TypeScript checking. One
installed-dependency timing test exceeded its unchanged one-second bound while
the emulator/native builds were competing for resources. After contention
cleared, the complete unmodified test command passed, including all seven
image-size and four decode-uri-component installed-package regressions.
No timeout or security rule was relaxed. Mobile has no dedicated lint script.

Sol corrected Kimi's reviewed storage/replay findings and added tests exercising
the actual CommonJS notification wiring. The final read-only Kimi review also
identified notification prose being used as a navigation title and repeated
foreground feed fetches; Sol omitted that title and added shared in-flight
refreshes with a 60-second minimum interval. No dependency, signing key,
version, voting or identity changes are included.

Weekly/system events without a stable provider event ID, version or date are
not added to the ledger. Existing automatic push producers cover new votes and
results; full event-producer coverage and OEM acceptance remain part of #290.

No new email, subscription enrollment, DNS change, identity canary, production
cutoff, payment activation or forced security upgrade was performed. The
previous one-confirmation/one-newsletter authorization is consumed. Payment
task 10 remains excluded; only the private VLABS operator can provide its
missing inputs. No private recipient/provider values belong in public docs.

## September 7 Continuation

All CI and Security jobs passed for PR #297 head `1474195`. Kimi's subsequent
review identified a storage-size portability risk: the installed SecureStore
wrapper warns above 2,048 bytes; this is not evidence of an unconditional
exception or a reproduced device failure. The unshipped ledger now uses
1,024-byte chunks in two bounded banks, publishing its manifest only after
all chunks persist. Only the two unread-state keys use this adapter; identity
keys and existing preference storage are unchanged. Corrupt manifests fail
closed instead of silently discarding acknowledgements; no automatic reset
or identity-storage deletion is provided.

Kimi supplied 34 strict storage tests, reviewed by Sol. Sol independently ran
the full suite: 293 tests in 29 files plus all eleven installed dependency
regressions passed, as did TypeScript checking. A cold-start notification tap
is now ingested through the same stable-ID deduplication path as live taps.

A connected Samsung S10 was briefly readable (Android 12, app v1.0.31 / 60),
but repeated USB read failures interrupted both available ADB backends. The
attempted screenshot was incomplete. No installation, data deletion or
successful hardware acceptance is claimed. The clean Android 15 emulator
also failed to establish a usable session and was stopped. Device acceptance
and event-producer coverage still block a new public release.

### USB Recovery and Review Remediation

Later USB checks and complete screenshots succeeded on the existing S10
v1.0.31 / 60 installation. Home, notification settings, locked profile,
bill list/filter, parties and trending views were reached without replacing
the app or clearing data. This is baseline smoke evidence, not acceptance
of PR #297. No HLR request, identity change, vote or message was submitted.
The installed update banner visibly overlaps the Android status bar; the
current source also lacks its top safe-area inset. Track this UI defect
separately before claiming complete mobile layout acceptance.

CodeRabbit completed with comments. Kimi confirmed three error-handling
issues, implemented settings hydration/retry controls and seven focused
tests. Sol reviewed every delegated diff, added recovery after remount and
protection against simultaneous toggles, and tested all push ingress error
boundaries. Opt-out persistence is never reverted after an acknowledgement
failure. One automatic retry is bounded; persistent failure remains visible
or emits a static warning without payloads/identifiers. Corrupt manifests
stay fail-closed, deliberately rejecting the suggestion to overwrite them.

Sol's full rerun passed 308 tests in 30 files, all eleven installed dependency
security regressions, TypeScript and changed-file secret scans. The settings
harness tests actual transpiled source but does not model full React batching
or native rendering. No new dependency, signing, app version, voting or
identity change is included. No new binary publication or production rollout
is implied by these source-level results.
