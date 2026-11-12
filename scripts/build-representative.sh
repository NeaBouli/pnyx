#!/bin/bash
# Release APK build for the representative app (ekprosopos).
# Usage: REP_SIGNING_PROPERTIES=/abs/path/keystore.properties bash scripts/build-representative.sh
# Signs with the project release key (same certificate as the main app) and
# refuses to finish if the APK certificate does not match the pinned digest.

set -euo pipefail

EXPECTED_CERT_SHA256="d94c24d182737445a62bd9637397cfe95407b62f34d07eb57ef11b30e10e5dec"

: "${REP_SIGNING_PROPERTIES:?set REP_SIGNING_PROPERTIES to the keystore properties file}"
[ -f "$REP_SIGNING_PROPERTIES" ] || { echo "REP_SIGNING_PROPERTIES file not found" >&2; exit 1; }

SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
APKSIGNER="$(ls -d "$SDK"/build-tools/*/apksigner | sort -V | tail -1)"

cd "$(dirname "$0")/../apps/representative"
export NODE_ENV=production
npm ci --ignore-scripts
npx expo prebuild --platform android --clean
echo "sdk.dir=$SDK" > android/local.properties
python3 ../../scripts/patches/patch-representative-signing.py android/app/build.gradle
(cd android && ./gradlew --no-daemon assembleRelease)

APK="android/app/build/outputs/apk/release/app-release.apk"
"$APKSIGNER" verify --verbose "$APK" >/dev/null
CERT="$("$APKSIGNER" verify --print-certs "$APK" | sed -n 's/^Signer #1 certificate SHA-256 digest: //p')"
if [ "$CERT" != "$EXPECTED_CERT_SHA256" ]; then
  echo "Unexpected signing certificate: $CERT" >&2
  exit 1
fi

echo ""
echo "APK: apps/representative/$APK"
echo "cert SHA-256: $CERT"
shasum -a 256 "$APK"
