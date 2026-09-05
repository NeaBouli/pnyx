#!/bin/bash
# F-Droid compatible build script
# Produces: local compatibility APK without FCM/Google Services.
# This artifact is not for distribution; fdroidserver builds and signs the
# public package independently from the tagged source.
# Push notifications are disabled via BUILD_FLAVOR=fdroid
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../apps/mobile"

echo "Building F-Droid APK (no FCM, no Google Services)..."

APP_JSON_PATH="$SCRIPT_DIR/../apps/mobile/app.json"
APP_JSON_BACKUP="$(mktemp)"
PACKAGE_JSON_PATH="$SCRIPT_DIR/../apps/mobile/package.json"
PACKAGE_JSON_BACKUP="$(mktemp)"
ANDROID_BUILD_GRADLE_PATH="$SCRIPT_DIR/../apps/mobile/android/app/build.gradle"
ANDROID_BUILD_GRADLE_BACKUP="$(mktemp)"
cp "$APP_JSON_PATH" "$APP_JSON_BACKUP"
cp "$PACKAGE_JSON_PATH" "$PACKAGE_JSON_BACKUP"
cp "$ANDROID_BUILD_GRADLE_PATH" "$ANDROID_BUILD_GRADLE_BACKUP"
restore_build_configs() {
  cp "$APP_JSON_BACKUP" "$APP_JSON_PATH"
  cp "$PACKAGE_JSON_BACKUP" "$PACKAGE_JSON_PATH"
  cp "$ANDROID_BUILD_GRADLE_BACKUP" "$ANDROID_BUILD_GRADLE_PATH"
  rm -f "$APP_JSON_BACKUP"
  rm -f "$PACKAGE_JSON_BACKUP"
  rm -f "$ANDROID_BUILD_GRADLE_BACKUP"
}
trap restore_build_configs EXIT

# Set the F-Droid flavor and update channel before Expo resolves app.config.js.
export NODE_ENV=production
export BUILD_FLAVOR=fdroid
export EKKLESIA_BUILD_FLAVOR=fdroid
export EKKLESIA_DISTRIBUTION_CHANNEL=fdroid
export EXPO_NO_GOOGLE_SERVICES=1

# Patch package/app config to mirror the official fdroiddata recipe. The
# notification JavaScript remains testable, but F-Droid must not autolink the
# proprietary FCM-backed native module.
python3 -c "
import json
with open('package.json', 'r') as f: p = json.load(f)
p['expo'] = {'autolinking': {'android': {
    'buildFromSource': ['.*'],
    'exclude': ['expo-notifications'],
}}}
with open('package.json', 'w') as f:
    json.dump(p, f, indent=2)

with open('app.json', 'r') as f: d = json.load(f)
d['expo']['plugins'] = [
    plugin for plugin in d['expo'].get('plugins', [])
    if plugin != 'expo-notifications'
    and not (isinstance(plugin, list) and plugin and plugin[0] == 'expo-notifications')
]
d['expo']['extra']['buildFlavor'] = 'fdroid'
d['expo']['extra']['distributionChannel'] = 'fdroid'
d['expo']['extra']['zkSemaphoreEnabled'] = False
with open('app.json', 'w') as f:
    json.dump(d, f, indent=2)
print('F-Droid config patched: expo-notifications excluded, channel isolated')
"

npm ci --include=dev
npx expo prebuild --clean --platform android
python3 "$SCRIPT_DIR/patches/patch-android-manifest-package.py" android/app/src/main/AndroidManifest.xml ekklesia.gr

# Remove google-services.json if present (FCM dependency)
rm -f android/app/google-services.json
echo "Removed google-services.json (if existed)"

echo "sdk.dir=$HOME/Library/Android/sdk" > android/local.properties

cd android
./gradlew assembleRelease

cd "$SCRIPT_DIR/../apps/mobile"
APK="android/app/build/outputs/apk/release/app-release.apk"
echo "F-Droid local compatibility APK ready (not for distribution): $APK"
ls -lh "$APK"
