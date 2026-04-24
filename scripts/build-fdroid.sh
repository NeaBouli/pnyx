#!/bin/bash
# F-Droid compatible build script
# Produces: unsigned APK for F-Droid signing
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../apps/mobile"

echo "Building F-Droid APK..."

npm ci
npx expo prebuild --clean --platform android

echo "sdk.dir=$HOME/Library/Android/sdk" > android/local.properties

cd android
./gradlew assembleFreeRelease

APK="app/build/outputs/apk/free/release/app-free-release-unsigned.apk"
if [ -f "$APK" ]; then
  echo "APK ready: $APK"
else
  echo "Fallback: assembleRelease"
  ./gradlew assembleRelease
  echo "APK: app/build/outputs/apk/release/app-release-unsigned.apk"
fi
