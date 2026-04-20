# Google Play Internal Testing Checklist

## Before first upload
- [ ] Google Play Console → Alle Apps → App erstellen
- [ ] App name: εκκλησία
- [ ] Package: gr.ekklesia.app
- [ ] Category: Tools or Social
- [ ] Content rating: fill out questionnaire
- [ ] Privacy Policy URL: https://ekklesia.gr/wiki/security.html
- [ ] Data safety form: no personal data collected, votes are anonymous

## Build (after EAS resets 2026-05-01)
```bash
npx eas build --platform android --profile production
```
- Download AAB from EAS dashboard
- Upload to Play Console → Internal Testing → New Release

## Internal Testing setup
- Create tester list (email addresses)
- Share opt-in link with testers
- No minimum tester count required
- No minimum duration required

## When ready for public
- Promote to Closed Testing (requires 12 testers, 14 days)
- Then promote to Production

## Current config
- `android.package`: gr.ekklesia.app
- `android.versionCode`: 2
- `version`: 1.0.0
- EAS production: app-bundle (AAB)
- EAS preview: apk (beta testers)
