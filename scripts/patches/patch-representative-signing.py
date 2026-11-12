#!/usr/bin/env python3
"""Patch the prebuilt representative build.gradle to sign release builds with
the project release key instead of the Expo debug key.

The keystore properties file is read at Gradle time from the absolute path in
REP_SIGNING_PROPERTIES (keys: storeFile, storePassword, keyAlias, keyPassword;
a relative storeFile resolves against the properties file's directory). A
missing variable or file fails the release build instead of silently falling
back to the debug key.
"""
import re
import sys

gradle_path = sys.argv[1] if len(sys.argv) > 1 else "apps/representative/android/app/build.gradle"

with open(gradle_path, "r") as f:
    content = f.read()

if "repRelease" in content:
    print(f"Already patched: {gradle_path}")
    sys.exit(0)

signing_block = '''        repRelease {
            def propsPath = System.getenv("REP_SIGNING_PROPERTIES")
            if (propsPath) {
                def propsFile = new File(propsPath)
                if (!propsFile.exists()) {
                    throw new GradleException("REP_SIGNING_PROPERTIES file not found")
                }
                def props = new Properties()
                propsFile.withInputStream { props.load(it) }
                def store = new File(props["storeFile"])
                storeFile store.isAbsolute() ? store : new File(propsFile.parentFile, props["storeFile"])
                storePassword props["storePassword"]
                keyAlias props["keyAlias"]
                keyPassword props["keyPassword"]
            }
        }
    }'''

content, n = re.subn(
    r"(signingConfigs\s*\{.*?keyPassword 'android'\s*\}\s*)\}",
    lambda m: m.group(1) + signing_block,
    content,
    count=1,
    flags=re.DOTALL,
)
if n != 1:
    sys.exit("signingConfigs block not found")

content, n = re.subn(
    r"(release\s*\{\s*(?://[^\n]*\n\s*)*)signingConfig signingConfigs\.debug",
    r"\1signingConfig signingConfigs.repRelease",
    content,
    count=1,
)
if n != 1:
    sys.exit("release buildType signingConfig not found")

content += '''
gradle.taskGraph.whenReady { graph ->
    if (graph.allTasks.any { it.name.toLowerCase().contains("release") } && !System.getenv("REP_SIGNING_PROPERTIES")) {
        throw new GradleException("REP_SIGNING_PROPERTIES is required for release builds")
    }
}
'''

with open(gradle_path, "w") as f:
    f.write(content)
print(f"Patched: {gradle_path}")
