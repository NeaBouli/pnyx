#!/bin/bash
# Direct APK build — for ekklesia.gr/download distribution
# EAS (preferred): npx eas build --platform android --profile preview
# Local fallback: bash scripts/build-direct.sh

set -e

cd "$(dirname "$0")/../apps/mobile"
npx expo prebuild --platform android --clean
cd android
./gradlew assembleRelease

APK="app/build/outputs/apk/release/app-release.apk"
echo ""
echo "APK: apps/mobile/android/$APK"
echo "Deploy: scp apps/mobile/android/$APK root@135.181.254.229:/opt/ekklesia/downloads/ekklesia-latest.apk"
