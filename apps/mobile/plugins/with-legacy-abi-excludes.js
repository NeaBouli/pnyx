const { withGradleProperties } = require("@expo/config-plugins");

// JNA 5.19.1 (semaphore-react-native) ships libjnidispatch.so for armeabi, mips and mips64 as well.
// Android has not supported these ABIs for years; keep them out of the APK/AAB. The generated
// app/build.gradle adds every entry of `android.packagingOptions.excludes` to packagingOptions.
const PROPERTY = "android.packagingOptions.excludes";
const LEGACY_ABI_EXCLUDES = ["lib/armeabi/**", "lib/mips/**", "lib/mips64/**"];

function setLegacyAbiExcludes(properties) {
  const existing = properties.find(
    (item) => item.type === "property" && item.key === PROPERTY
  );
  const values = existing
    ? existing.value.split(",").map((value) => value.trim()).filter(Boolean)
    : [];
  for (const pattern of LEGACY_ABI_EXCLUDES) {
    if (!values.includes(pattern)) values.push(pattern);
  }
  if (existing) {
    existing.value = values.join(",");
  } else {
    properties.push({ type: "property", key: PROPERTY, value: values.join(",") });
  }
  return properties;
}

function withLegacyAbiExcludes(config) {
  return withGradleProperties(config, (config) => {
    config.modResults = setLegacyAbiExcludes(config.modResults);
    return config;
  });
}

module.exports = withLegacyAbiExcludes;
module.exports.setLegacyAbiExcludes = setLegacyAbiExcludes;
module.exports.LEGACY_ABI_EXCLUDES = LEGACY_ABI_EXCLUDES;
