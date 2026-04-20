#!/bin/bash
# Local Gradle APK build — alternative to EAS Cloud
# Use when: EAS limit reached, offline, or testing
# Note: produces different signing key than EAS builds
# For production/updates: always use EAS (npx eas build)

set -e

cd "$(dirname "$0")/../apps/mobile"
npx expo prebuild --platform android --clean
cd android
./gradlew assembleRelease

echo ""
echo "✅ APK: apps/mobile/android/app/build/outputs/apk/release/app-release.apk"
