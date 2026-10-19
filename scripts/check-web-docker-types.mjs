// Match Dockerfile.prod's COPY apps/web/ . for TypeScript inputs. The other
// COPY instructions add static assets under public/, not repo-level scripts.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, mkdtempSync, rmSync, symlinkSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const web = fileURLToPath(new URL("../apps/web/", import.meta.url));
const require = createRequire(join(web, "package.json"));
const loadConfig = require("next/dist/server/config").default;
const { PHASE_PRODUCTION_BUILD } = require("next/constants");
const stage = mkdtempSync(join(tmpdir(), "web-docker-types-"));
const previousCwd = process.cwd();

function run(module, args) {
  const result = spawnSync(process.execPath, [require.resolve(module), ...args], {
    cwd: stage,
    stdio: "inherit",
    env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" },
  });
  if (result.error) throw result.error;
  assert.equal(result.status, 0, `${module} failed (${result.signal || result.status})`);
}

try {
  cpSync(web, stage, {
    recursive: true,
    filter: (source) => !relative(web, source).split(sep).some(
      (part) => ["node_modules", ".next"].includes(part) || part.endsWith(".tsbuildinfo"),
    ),
  });
  // Reuse CI's installed dependencies; the staged app cannot reach repo sources.
  symlinkSync(join(web, "node_modules"), join(stage, "node_modules"), "dir");
  process.chdir(stage);
  const config = await loadConfig(PHASE_PRODUCTION_BUILD, stage);
  assert.equal(config.typescript.ignoreBuildErrors, false);
  run("next/dist/bin/next", ["typegen"]);
  run("typescript/bin/tsc", [
    "--project", config.typescript.tsconfigPath, "--noEmit", "--incremental", "false",
  ]);
} finally {
  process.chdir(previousCwd);
  rmSync(stage, { recursive: true, force: true });
}
