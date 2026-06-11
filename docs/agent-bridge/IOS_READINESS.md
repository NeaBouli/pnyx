# iOS Readiness - ekklesia mobile

Date: 2026-06-11
Status: Preparation only, no iOS build produced

## Current Expo iOS Config

| Field | Value |
|---|---|
| Expo owner | `kaspartisan` |
| Expo slug | `ekklesia-gr` |
| App name | `εκκλησία` |
| Version | `1.0.4` |
| Scheme | `ekklesia` |
| iOS bundle identifier | `gr.ekklesia.app` |
| Tablet support | `false` |
| EAS project ID | `f6cfa7b1-ff85-4020-ac35-94d3774615fd` |

## Local Tooling Check

| Check | Result |
|---|---|
| EAS CLI | Installed (`eas-cli/18.4.0`) |
| EAS login | OK (`kaspartisan`, `kaspartisan@proton.me`) |
| Xcode | Not ready: `xcodebuild` points at Command Line Tools, not full Xcode |
| iOS build artifact | Not produced |

Observed error:

```text
xcode-select: error: tool 'xcodebuild' requires Xcode, but active developer directory '/Library/Developer/CommandLineTools' is a command line tools instance
```

## Apple Account Reality

Official Apple pages checked:

- Free registration: https://developer.apple.com/register/
- Membership comparison: https://developer.apple.com/support/compare-memberships/

Free Apple developer registration is enough to:

- Accept the Apple Developer Agreement.
- Access Xcode, docs, forums, Feedback Assistant.
- Run/test apps on personal devices via Xcode.

Paid Apple Developer Program membership is required for:

- TestFlight distribution.
- App Store distribution.
- App Store Connect release management.

## Safe Next Steps

1. Install full Xcode from the Mac App Store.
2. Open Xcode once and accept licenses.
3. Select full Xcode:

```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
xcodebuild -version
```

4. With a free Apple Account, run a local development build to a connected iPhone only.
5. For TestFlight/App Store, enroll in the paid Apple Developer Program and configure Apple credentials via EAS.

## Guardrails

- Do not promise iOS App Store/TestFlight without paid membership.
- Do not create or upload iOS credentials without Gio present for Apple ID and 2FA.
- Do not change the Android release while preparing iOS.
- Do not enable production ZK flags as part of iOS preparation.
