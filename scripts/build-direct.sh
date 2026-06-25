#!/bin/bash
# Direct APK build — for ekklesia.gr/download distribution
# EAS (preferred): npx eas build --platform android --profile preview
# Local fallback: bash scripts/build-direct.sh

set -e

cd "$(dirname "$0")/../apps/mobile"
export EKKLESIA_DISTRIBUTION_CHANNEL=direct
export EKKLESIA_BUILD_FLAVOR=direct
npx expo prebuild --platform android --clean
echo "sdk.dir=$HOME/Library/Android/sdk" > android/local.properties
python3 ../../scripts/patches/patch-android-manifest-package.py android/app/src/main/AndroidManifest.xml ekklesia.gr
python3 ../../scripts/patches/patch-play-flavors.py android/app/build.gradle
cd android
./gradlew assembleDirectRelease

APK="app/build/outputs/apk/direct/release/app-direct-release.apk"
echo ""
echo "APK: apps/mobile/android/$APK"
echo "Deploy: scp apps/mobile/android/\$APK root@<SERVER>:/opt/ekklesia/downloads/ekklesia-latest.apk"
