#!/usr/bin/env python3
"""Patch build.gradle to add Play Store signing + flavors after expo prebuild."""
import sys
import re

gradle_path = sys.argv[1] if len(sys.argv) > 1 else "apps/mobile/android/app/build.gradle"

with open(gradle_path, "r") as f:
    content = f.read()

if "playRelease" in content:
    print(f"Already patched: {gradle_path}")
    sys.exit(0)

# 1. Add playRelease signingConfig inside signingConfigs block
# Path from android/app/ → ../../keystore-play.properties (apps/mobile/)
signing_block = '''        playRelease {
            def props = new Properties()
            def propsFile = new File(rootDir.parentFile, "keystore-play.properties")
            if (propsFile.exists()) {
                props.load(new FileInputStream(propsFile))
                storeFile new File(rootDir.parentFile, props["storeFile"])
                storePassword props["storePassword"]
                keyAlias props["keyAlias"]
                keyPassword props["keyPassword"]
            }
        }
    }'''

# Replace the closing } of signingConfigs block
content = re.sub(
    r"(signingConfigs\s*\{.*?keyPassword 'android'\s*\}\s*)\}",
    r"\1" + signing_block,
    content,
    count=1,
    flags=re.DOTALL,
)

# 2. Add flavorDimensions + productFlavors before buildTypes
# play flavor gets signingConfig directly here
flavors_patch = """    flavorDimensions "distribution"
    productFlavors {
        direct {
            dimension "distribution"
            resValue "string", "distribution_channel", "direct"
        }
        play {
            dimension "distribution"
            resValue "string", "distribution_channel", "play"
            signingConfig signingConfigs.playRelease
        }
    }
"""

content = content.replace("    buildTypes {", flavors_patch + "    buildTypes {")

# 3. In buildTypes.release: remove signingConfig so flavor's config is used
# For 'direct' flavor we still want debug key, so set it only if no flavor override
# AGP behavior: if flavor sets signingConfig AND buildType sets signingConfig,
# the buildType wins. So we must remove signingConfig from release buildType.
content = content.replace(
    "            // Caution! In production, you need to generate your own keystore file.\n"
    "            // see https://reactnative.dev/docs/signed-apk-android.\n"
    "            signingConfig signingConfigs.debug",
    "            // Signing handled per flavor (direct=debug, play=playRelease)\n"
    "            signingConfig null"
)

with open(gradle_path, "w") as f:
    f.write(content)

print(f"Patched: {gradle_path}")
