#!/bin/bash
# Google Play AAB build — uses local persistent keystore
# Run: bash scripts/build-play.sh
# Requires: apps/mobile/ekklesia-playstore-key.jks + android/keystore-play.properties

set -e

cd "$(dirname "$0")/../apps/mobile"

# Set channel to "play" for this build
sed -i '' 's/"distributionChannel": "direct"/"distributionChannel": "play"/' app.json

# Prebuild native project
npx expo prebuild --platform android --clean

# Patch build.gradle: add Play signing config + flavors
GRADLE="android/app/build.gradle"

# Insert signingConfigs.playRelease after signingConfigs.debug block
sed -i '' '/signingConfigs {/,/^    }$/{
  /^    }$/a\
\        playRelease {\
\            def props = new Properties()\
\            def propsFile = file("../keystore-play.properties")\
\            if (propsFile.exists()) {\
\                props.load(new FileInputStream(propsFile))\
\                storeFile file(props["storeFile"])\
\                storePassword props["storePassword"]\
\                keyAlias props["keyAlias"]\
\                keyPassword props["keyPassword"]\
\            }\
\        }
}' "$GRADLE"

# Insert flavorDimensions + productFlavors before buildTypes
sed -i '' '/buildTypes {/i\
\    flavorDimensions "distribution"\
\    productFlavors {\
\        direct {\
\            dimension "distribution"\
\            resValue "string", "distribution_channel", "direct"\
\        }\
\        play {\
\            dimension "distribution"\
\            signingConfig signingConfigs.playRelease\
\            resValue "string", "distribution_channel", "play"\
\        }\
\    }
' "$GRADLE"

cd android
./gradlew bundlePlayRelease

# Restore channel to "direct"
cd ..
sed -i '' 's/"distributionChannel": "play"/"distributionChannel": "direct"/' app.json

AAB="android/app/build/outputs/bundle/playRelease/app-play-release.aab"
echo ""
echo "AAB ready: $AAB"
echo "Upload to: Google Play Console → Internal Testing → New Release"
