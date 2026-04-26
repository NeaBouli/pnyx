#!/bin/bash
# F-Droid compatible build script
# Produces: unsigned APK without FCM/Google Services
# Push notifications are disabled via BUILD_FLAVOR=fdroid
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../apps/mobile"

echo "Building F-Droid APK (no FCM, no Google Services)..."

# Set F-Droid flavor — disables push notifications at runtime
export BUILD_FLAVOR=fdroid
export EXPO_NO_GOOGLE_SERVICES=1

# Patch app.json to set buildFlavor=fdroid
python3 -c "
import json
with open('app.json', 'r') as f:
    d = json.load(f)
d['expo']['extra']['buildFlavor'] = 'fdroid'
with open('app.json', 'w') as f:
    json.dump(d, f, indent=2)
print('app.json patched: buildFlavor=fdroid')
"

npm ci
npx expo prebuild --clean --platform android

# Remove google-services.json if present (FCM dependency)
rm -f android/app/google-services.json
echo "Removed google-services.json (if existed)"

echo "sdk.dir=$HOME/Library/Android/sdk" > android/local.properties

cd android
./gradlew assembleFreeRelease || ./gradlew assembleRelease

# Restore app.json
cd "$SCRIPT_DIR/../apps/mobile"
python3 -c "
import json
with open('app.json', 'r') as f:
    d = json.load(f)
d['expo']['extra']['buildFlavor'] = 'play'
with open('app.json', 'w') as f:
    json.dump(d, f, indent=2)
print('app.json restored: buildFlavor=play')
"

APK="android/app/build/outputs/apk/free/release/app-free-release-unsigned.apk"
if [ -f "$APK" ]; then
  echo "F-Droid APK ready: $APK"
else
  APK="android/app/build/outputs/apk/release/app-release-unsigned.apk"
  echo "F-Droid APK: $APK"
fi
ls -lh "$APK" 2>/dev/null
