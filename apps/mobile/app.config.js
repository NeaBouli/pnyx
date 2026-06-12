const appJson = require("./app.json");

const config = appJson.expo;
const extra = config.extra || {};

module.exports = {
  ...config,
  extra: {
    ...extra,
    distributionChannel:
      process.env.EKKLESIA_DISTRIBUTION_CHANNEL ||
      extra.distributionChannel ||
      "direct",
    buildFlavor:
      process.env.EKKLESIA_BUILD_FLAVOR ||
      extra.buildFlavor ||
      "direct",
  },
};
