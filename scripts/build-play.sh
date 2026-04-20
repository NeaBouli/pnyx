#!/bin/bash
# Google Play AAB build — uses local persistent keystore
# Run: bash scripts/build-play.sh
# Requires: apps/mobile/ekklesia-playstore-key.jks + android/keystore-play.properties

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../apps/mobile"

# Set channel to "play" for this build
sed -i '' 's/"distributionChannel": "direct"/"distributionChannel": "play"/' app.json

# Prebuild native project
npx expo prebuild --platform android --clean

# Ensure local.properties has SDK path
echo "sdk.dir=$HOME/Library/Android/sdk" > android/local.properties

# Patch build.gradle with Play signing + flavors
python3 "$SCRIPT_DIR/patches/patch-play-flavors.py" android/app/build.gradle

cd android
./gradlew bundlePlayRelease

# Restore channel to "direct"
cd ..
sed -i '' 's/"distributionChannel": "play"/"distributionChannel": "direct"/' app.json

AAB="android/app/build/outputs/bundle/playRelease/app-play-release.aab"
echo ""
echo "AAB ready: $AAB"
echo "Upload to: Google Play Console → Internal Testing → New Release"
