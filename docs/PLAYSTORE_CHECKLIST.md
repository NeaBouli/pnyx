# Google Play Internal Testing Checklist

## Before first upload
- [ ] Google Play Console → Alle Apps → App erstellen
- [ ] App name: εκκλησία
- [ ] Package: gr.ekklesia.app
- [ ] Category: Tools or Social
- [ ] Content rating: fill out questionnaire
- [ ] Privacy Policy URL: https://ekklesia.gr/wiki/security.html
- [ ] Data safety form: no personal data collected, votes are anonymous

## Building AAB for Google Play
```bash
bash scripts/build-play.sh
```
- AAB: `android/app/build/outputs/bundle/playRelease/app-play-release.aab`
- Upload to Play Console → Internal Testing → New Release
- Share opt-in link with testers

## Alternative: EAS Cloud (after resets 2026-05-01)
```bash
npx eas build --platform android --profile production
```
- Download AAB from EAS dashboard

## Internal Testing setup
- Create tester list (email addresses)
- Share opt-in link with testers
- No minimum tester count required
- No minimum duration required

## When ready for public
- Promote to Closed Testing (requires 12 testers, 14 days)
- Then promote to Production

## Two channels — never mix
| Channel | Signing | Distribution | Script |
|---------|---------|-------------|--------|
| Direct APK | EAS / debug key | ekklesia.gr/download | `scripts/build-direct.sh` |
| Google Play | `ekklesia-playstore-key.jks` | Play Store | `scripts/build-play.sh` |

Users switching channels must reinstall (informed on first launch via ChannelNotice).

## Current config
- `android.package`: gr.ekklesia.app
- `android.versionCode`: 2
- `version`: 1.0.0
- Flavors: `direct` (APK) + `play` (AAB)
- Keystore backup: server `/opt/hetzner-migration/memory/ekklesia-playstore-key.jks`
