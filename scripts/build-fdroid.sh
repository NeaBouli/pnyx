#!/bin/bash
# F-Droid compatible build script
# Produces: unsigned APK without FCM/Google Services
# Push notifications are disabled via BUILD_FLAVOR=fdroid
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../apps/mobile"

echo "Building F-Droid APK (no FCM, no Google Services)..."

APP_JSON_PATH="$SCRIPT_DIR/../apps/mobile/app.json"
APP_JSON_BACKUP="$(mktemp)"
cp "$APP_JSON_PATH" "$APP_JSON_BACKUP"
restore_app_json() {
  cp "$APP_JSON_BACKUP" "$APP_JSON_PATH"
  rm -f "$APP_JSON_BACKUP"
}
trap restore_app_json EXIT

# Set the F-Droid flavor and update channel before Expo resolves app.config.js.
export NODE_ENV=production
export BUILD_FLAVOR=fdroid
export EKKLESIA_BUILD_FLAVOR=fdroid
export EKKLESIA_DISTRIBUTION_CHANNEL=fdroid
export EXPO_NO_GOOGLE_SERVICES=1

# Patch app.json to mirror the official fdroiddata recipe.
python3 -c "
import json
with open('app.json', 'r') as f: d = json.load(f)
d['expo']['extra']['buildFlavor'] = 'fdroid'
d['expo']['extra']['distributionChannel'] = 'fdroid'
d['expo']['extra']['zkSemaphoreEnabled'] = False
with open('app.json', 'w') as f:
    json.dump(d, f, indent=2)
print('app.json patched: buildFlavor=fdroid, distributionChannel=fdroid, zkSemaphoreEnabled=false')
"

npm ci
npx expo prebuild --clean --platform android
python3 "$SCRIPT_DIR/patches/patch-android-manifest-package.py" android/app/src/main/AndroidManifest.xml ekklesia.gr

# Remove google-services.json if present (FCM dependency)
rm -f android/app/google-services.json
echo "Removed google-services.json (if existed)"

echo "sdk.dir=$HOME/Library/Android/sdk" > android/local.properties

cd android
./gradlew assembleFreeRelease || ./gradlew assembleRelease

cd "$SCRIPT_DIR/../apps/mobile"
APK="android/app/build/outputs/apk/free/release/app-free-release-unsigned.apk"
if [ -f "$APK" ]; then
  echo "F-Droid APK ready: $APK"
else
  APK="android/app/build/outputs/apk/release/app-release-unsigned.apk"
  echo "F-Droid APK: $APK"
fi
ls -lh "$APK" 2>/dev/null
