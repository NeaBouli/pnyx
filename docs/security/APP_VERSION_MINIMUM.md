# Minimum supported Android version (#660 / T-9157)

The first release that signs vote-status reads and uses v2 evaluations is
v1.0.33 (base versionCode 62). `/api/v1/app/version` retains the legacy
`min_required_version_code: 62` and adds
`min_required_version_code_by_channel: {"direct": 62, "play": 62, "fdroid": 621}`.
F-Droid appends an ABI digit (1–4) to the base code. The server supplies the
minimum in each channel's native code scheme; clients must select their channel
before comparing. This is an update advisory, not API request enforcement.

| Channel / release | Native codes | Below minimum? |
| --- | --- | --- |
| Direct/Play 1.0.32 | 61 | Yes |
| Direct/Play 1.0.33 | 62 | No |
| Direct/Play 1.0.36 | 65 | No |
| F-Droid 1.0.32 | 611–614 | Yes |
| F-Droid 1.0.33 | 621–624 | No |
| F-Droid 1.0.36 | 651–654 | No |

`getCurrentVersionCode` reads the native build version, with Expo config as a
fallback. Previously, `shouldOfferUpdate` only compared `latest_version_code`
for Direct/Play and always returned false for F-Droid. No client code evaluated
the minimum. Home copied `force_update` into unused state; neither banner
blocked app use. Profile also skipped the version request for F-Droid.

The updated shared helper checks the channel minimum first. Unsupported
F-Droid builds receive an update prompt linking to F-Droid in Home, UpdateBanner
and Profile; supported F-Droid builds still delegate optional updates to the
F-Droid client. Direct/Play retain optional latest-release prompts. If an older
API lacks the channel map, Direct/Play fall back to the scalar minimum, while
F-Droid never compares its ABI code against that scalar. Unknown channels retain
the existing Direct behavior. `force_update` remains false so supported clients
are not globally forced to upgrade. These prompts remain advisory/dismissible;
this change does not add a blocking update screen.

Already-installed clients cannot acquire new comparison logic from a JSON
response. Existing F-Droid 1.0.32 clients still skip these prompts and must update
through F-Droid. A raw comparison against 62 would also incorrectly accept
611–614. Existing Direct/Play clients continue offering v1.0.36 through their
usual latest-code check. New fields are additive and legacy camelCase download
aliases are preserved. The new helper takes effect only in builds containing
this change; the published v1.0.36 binary is not changed by this patch.

Targeted regressions: `apps/api/tests/test_app_version.py` verifies the response
contract and compatibility aliases; `apps/mobile/src/lib/update-channel.test.ts`
checks all F-Droid ABI boundaries, Direct/Play boundaries, channel routing,
optional updates and legacy/malformed payloads. No live release lookup is needed.
