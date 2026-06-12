# CC Review Request — vC35 release prep before build

Mode: review/diagnosis first. Do not edit files.

Gio requested:
- build a new Google Play AAB,
- put the correct APK on the landing download buttons,
- verify GitHub/repo status,
- keep everything cautious with rollback and Bridge docs.

Current state:
- HEAD `d0fd022`, clean.
- Mobile app currently `version=1.0.5`, Android `versionCode=34`.
- vC34 AAB was already uploaded to Google Play closed/internal test.
- `scripts/build-play.sh` sets `EKKLESIA_DISTRIBUTION_CHANNEL=play`, `EKKLESIA_BUILD_FLAVOR=play`.
- `scripts/build-direct.sh` sets `direct/direct`.
- Landing APK file appears to be `docs/download/ekklesia-latest.apk`.

Please inspect:
- `apps/mobile/app.json`
- `apps/mobile/app.config.js`
- `scripts/build-play.sh`
- `scripts/build-direct.sh`
- landing/download files (`docs/`, `apps/web/`) that reference APK version/hash/download buttons.

Questions:
1. For vC35, should version bump be `versionCode 35` and `versionName 1.0.6`, or keep `1.0.5` with code 35?
2. Does direct APK output path in `scripts/build-direct.sh` match the actual Gradle output?
3. Which files must be updated so landing download button serves the new APK and shows the visible current version?
4. Any known hazard before building AAB/APK from current HEAD?

Report concrete findings and recommended exact next steps. No edits.
