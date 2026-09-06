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

The final mobile source suite passed 258 tests and TypeScript checking. One
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
