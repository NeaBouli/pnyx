#!/usr/bin/env python3
"""Ensure Expo prebuild output exposes the real Android package to RN autolinking."""
import re
import sys

manifest_path = sys.argv[1] if len(sys.argv) > 1 else "apps/mobile/android/app/src/main/AndroidManifest.xml"
package_name = sys.argv[2] if len(sys.argv) > 2 else "ekklesia.gr"

with open(manifest_path, "r") as f:
    content = f.read()

if "package=" in content.split(">", 1)[0]:
    content = re.sub(r'package="[^"]+"', f'package="{package_name}"', content, count=1)
else:
    content = content.replace("<manifest ", f'<manifest package="{package_name}" ', 1)

with open(manifest_path, "w") as f:
    f.write(content)

print(f"Patched manifest package: {manifest_path} -> {package_name}")
