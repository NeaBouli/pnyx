import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { spawnSync } from "node:child_process";
import sharp from "sharp";
import semver from "semver";
import { optimizeImage } from "next/dist/server/image-optimizer.js";

test("Next encodes AVIF output with expected dimensions", async () => {
  const buffer = await sharp({
    create: { width: 64, height: 48, channels: 3, background: { r: 24, g: 60, b: 180 } },
  }).png().toBuffer();
  const result = await optimizeImage({
    buffer, contentType: "image/avif", quality: 90, width: 16,
    limitInputPixels: 4096, timeoutInSeconds: 5,
  });
  // Next 16.3.3 blocks AVIF decoding globally; inspect in an isolated process.
  const decoded = spawnSync(process.execPath, ["-e", "require('sharp')(require('fs').readFileSync(0)).metadata().then(m => process.stdout.write(JSON.stringify(m)))"], { input: result, timeout: 10000 });
  assert.equal(decoded.status, 0, decoded.stderr?.toString());
  const metadata = JSON.parse(decoded.stdout.toString());
  assert.equal(metadata.format, "heif");
  assert.equal(metadata.compression, "av1");
  assert.equal(metadata.width, 16);
  assert.equal(metadata.height, 12);
});

test("Next rejects input exceeding the pixel limit", async () => {
  const buffer = await sharp({
    create: { width: 65, height: 65, channels: 3, background: "blue" },
  }).png().toBuffer();
  await assert.rejects(optimizeImage({
    buffer, contentType: "image/webp", quality: 90, width: 16,
    limitInputPixels: 4096, timeoutInSeconds: 5,
  }), /pixel limit/i);
});

test("Sharp override matches the installed Next requirement", () => {
  const next = JSON.parse(readFileSync(new URL("./node_modules/next/package.json", import.meta.url)));
  const manifest = JSON.parse(readFileSync(new URL("./package.json", import.meta.url)));
  assert.ok(semver.satisfies(sharp.versions.sharp, next.optionalDependencies.sharp));
  assert.equal(manifest.overrides.sharp, "0.35.4");
  assert.equal(sharp.versions.sharp, "0.35.4");
});

for (const format of ["png", "jpeg", "webp"]) {
  test(`Next decodes synthetic ${format} and preserves resized pixels`, async () => {
    const buffer = await sharp({
      create: { width: 64, height: 48, channels: 3, background: { r: 24, g: 60, b: 180 } },
    }).toFormat(format).toBuffer();
    const result = await optimizeImage({
      buffer, contentType: "image/webp", quality: 90, width: 16,
      limitInputPixels: 4096, timeoutInSeconds: 5,
    });
    const metadata = await sharp(result).metadata();
    assert.equal(metadata.format, "webp");
    assert.equal(metadata.width, 16);
    assert.equal(metadata.height, 12);
    const { data, info } = await sharp(result).removeAlpha().raw().toBuffer({ resolveWithObject: true });
    assert.equal(info.channels, 3);
    for (let i = 0; i < data.length; i++) {
      assert.ok(Math.abs(data[i] - [24, 60, 180][i % 3]) <= 8);
    }
  });
}

test("Next retains its existing AVIF input restriction", async () => {
  const buffer = await sharp({ create: { width: 16, height: 16, channels: 3, background: "blue" } }).avif().toBuffer();
  await assert.rejects(optimizeImage({
    buffer, contentType: "image/webp", quality: 90, width: 8,
    limitInputPixels: 4096, timeoutInSeconds: 5,
  }), /unsupported image format/i);
});

test("Next rejects malformed input instead of returning a successful image", async () => {
  await assert.rejects(optimizeImage({
    buffer: Buffer.from("synthetic-invalid-image"), contentType: "image/webp",
    quality: 90, width: 16, limitInputPixels: 4096, timeoutInSeconds: 5,
  }));
});
