#!/usr/bin/env python3
"""Patch build.gradle to add Play Store signing + flavors after expo prebuild."""
import sys

gradle_path = sys.argv[1] if len(sys.argv) > 1 else "apps/mobile/android/app/build.gradle"

with open(gradle_path, "r") as f:
    content = f.read()

# 1. Add playRelease inside signingConfigs block (after debug closing brace)
signing_patch = '''        playRelease {
            def props = new Properties()
            def propsFile = file("../keystore-play.properties")
            if (propsFile.exists()) {
                props.load(new FileInputStream(propsFile))
                storeFile file(props["storeFile"])
                storePassword props["storePassword"]
                keyAlias props["keyAlias"]
                keyPassword props["keyPassword"]
            }
        }'''

# Find the end of debug signingConfig and insert playRelease after it
debug_end = "            keyPassword 'android'\n        }\n    }"
if debug_end in content and "playRelease" not in content:
    content = content.replace(
        debug_end,
        debug_end.replace("    }", "") + "    }\n" + signing_patch + "\n    }"
    )

# 2. Add flavorDimensions + productFlavors before buildTypes
flavors_patch = '''    flavorDimensions "distribution"
    productFlavors {
        direct {
            dimension "distribution"
            resValue "string", "distribution_channel", "direct"
        }
        play {
            dimension "distribution"
            signingConfig signingConfigs.playRelease
            resValue "string", "distribution_channel", "play"
        }
    }
'''

if "flavorDimensions" not in content:
    content = content.replace("    buildTypes {", flavors_patch + "    buildTypes {")

with open(gradle_path, "w") as f:
    f.write(content)

print(f"Patched: {gradle_path}")
