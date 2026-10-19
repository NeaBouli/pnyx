import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: { server: { deps: { inline: ["next-intl"] } } },
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
});
