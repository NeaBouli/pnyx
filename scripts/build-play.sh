#!/bin/bash
# Google Play AAB build — uses local persistent keystore
# Run: bash scripts/build-play.sh
# Requires: apps/mobile/ekklesia-playstore-key.jks + android/keystore-play.properties

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MOBILE_DIR="$SCRIPT_DIR/../apps/mobile"
cd "$MOBILE_DIR"

export EKKLESIA_DISTRIBUTION_CHANNEL=play
export EKKLESIA_BUILD_FLAVOR=play

# Prebuild native project
npx expo prebuild --platform android --clean

# Ensure local.properties has SDK path
echo "sdk.dir=$HOME/Library/Android/sdk" > android/local.properties

# Expo/RN autolinking falls back to a transliterated Gradle project name unless
# the source manifest exposes the real package before Gradle generates entrypoints.
python3 "$SCRIPT_DIR/patches/patch-android-manifest-package.py" android/app/src/main/AndroidManifest.xml ekklesia.gr

# Patch build.gradle with Play signing + flavors
python3 "$SCRIPT_DIR/patches/patch-play-flavors.py" android/app/build.gradle

cd android
./gradlew bundlePlayRelease

AAB="android/app/build/outputs/bundle/playRelease/app-play-release.aab"
echo ""
echo "AAB ready: $AAB"
echo "Upload to: Google Play Console → Internal Testing → New Release"
