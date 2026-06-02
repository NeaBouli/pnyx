const { withDangerousMod } = require("@expo/config-plugins");
const fs = require("fs");
const path = require("path");

function packageToPath(packageName) {
  return packageName.split(".").join(path.sep);
}

module.exports = function withReactNativeEngine(config) {
  return withDangerousMod(config, [
    "android",
    async (config) => {
      const packageName = config.android && config.android.package;
      if (!packageName) {
        return config;
      }

      const mainApplicationPath = path.join(
        config.modRequest.platformProjectRoot,
        "app",
        "src",
        "main",
        "java",
        packageToPath(packageName),
        "MainApplication.kt"
      );

      if (!fs.existsSync(mainApplicationPath)) {
        return config;
      }

      const source = fs.readFileSync(mainApplicationPath, "utf8");
      if (source.includes("override val isHermesEnabled")) {
        return config;
      }

      const target =
        "override val isNewArchEnabled: Boolean = BuildConfig.IS_NEW_ARCHITECTURE_ENABLED";
      const replacement =
        target +
        "\n          override val isHermesEnabled: Boolean = BuildConfig.IS_HERMES_ENABLED";

      if (!source.includes(target)) {
        throw new Error(
          "Could not patch MainApplication.kt: isNewArchEnabled override not found"
        );
      }

      fs.writeFileSync(mainApplicationPath, source.replace(target, replacement));
      return config;
    },
  ]);
};
