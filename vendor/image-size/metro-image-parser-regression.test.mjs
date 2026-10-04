import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import test from 'node:test'
import { Worker } from 'node:worker_threads'

// Runs from a consuming workspace (apps/mobile, apps/representative) against
// the installed Metro. Metro 0.83.8 replaced image-size with its own parser
// (react/metro 809c36d897ef); this keeps the GHSA-5p2g-fcmc-qvqq and
// GHSA-w3rx-r6r6-pgpr malformed inputs from security-regression.test.mjs
// pointed at the parser Metro actually uses.
const workspaceRoot = process.cwd()
const workspaceRequire = createRequire(path.join(workspaceRoot, 'package.json'))
const metroPackageJson = workspaceRequire.resolve('metro/package.json')
const metroRequire = createRequire(metroPackageJson)
const assetsModulePath = workspaceRequire.resolve('metro/private/Assets')
const parserModulePath = workspaceRequire.resolve('metro/private/lib/imageSize')

function withUInt32BE(bytes, offset, value) {
  const copy = [...bytes]
  copy[offset] = (value >>> 24) & 0xff
  copy[offset + 1] = (value >>> 16) & 0xff
  copy[offset + 2] = (value >>> 8) & 0xff
  copy[offset + 3] = value & 0xff
  return copy
}

const heif = [
  0x00, 0x00, 0x00, 0x10, 0x66, 0x74, 0x79, 0x70,
  0x61, 0x76, 0x69, 0x66, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x24, 0x6d, 0x65, 0x74, 0x61,
  0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x08, 0x69, 0x70, 0x72, 0x70,
  0x00, 0x00, 0x00, 0x14, 0x69, 0x70, 0x63, 0x6f,
  0x00, 0x00, 0x00, 0x00, 0x69, 0x73, 0x70, 0x65,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
]
const jxl = [
  0x00, 0x00, 0x00, 0x0c, 0x4a, 0x58, 0x4c, 0x20,
  0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x0c, 0x66, 0x74, 0x79, 0x70,
  0x6a, 0x78, 0x6c, 0x20,
  0x00, 0x00, 0x00, 0x00, 0x6a, 0x78, 0x6c, 0x70,
  0x00, 0x00, 0x00, 0x00,
]
const icns = [
  0x69, 0x63, 0x6e, 0x73,
  0x00, 0x00, 0x00, 0x10,
  0x69, 0x73, 0x33, 0x32,
  0x00, 0x00, 0x00, 0x00,
]

// Same seven payloads as security-regression.test.mjs.
const advisoryPayloads = [
  ['heif zero-length box', 'heic', heif],
  ['heif undersized non-zero box', 'heic', withUInt32BE(heif, 44, 7)],
  ['jxl zero-length box', 'jxl', jxl],
  ['jxl undersized non-zero box', 'jxl', withUInt32BE(jxl, 24, 7)],
  ['icns zero-length entry', 'icns', icns],
  [
    'icns entry exceeds declared file length',
    'icns',
    withUInt32BE(withUInt32BE(icns, 4, 12), 12, 8),
  ],
  [
    'icns entry exceeds actual input length',
    'icns',
    withUInt32BE(withUInt32BE(icns, 4, 32), 12, 24),
  ],
]

const pngSignature = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]
const riffWebp = [0x52, 0x49, 0x46, 0x46, 0, 0, 0, 0, 0x57, 0x45, 0x42, 0x50]

// Length/offset fields that would stall or over-read a naive parser in the
// formats Metro 0.83.8 still decodes.
const offsetPayloads = [
  ['jpeg zero-length segment', 'jpg', [0xff, 0xd8, 0xff, 0xe0, 0x00, 0x00, 0x00, 0x00]],
  ['jpeg segment beyond input', 'jpg', [0xff, 0xd8, 0xff, 0xe0, 0xff, 0xff, 0x00, 0x00]],
  ['jpeg fill bytes without marker', 'jpg', [0xff, 0xd8, ...Array(4096).fill(0xff)]],
  [
    'webp chunk length beyond input',
    'webp',
    [...riffWebp, 0x41, 0x4c, 0x50, 0x48, 0xff, 0xff, 0xff, 0x7f, 0, 0, 0, 0],
  ],
  [
    'webp zero-length chunks without frame',
    'webp',
    [...riffWebp, ...Array(64).fill([0x41, 0x4c, 0x50, 0x48, 0, 0, 0, 0]).flat()],
  ],
  [
    'tiff entry count beyond input',
    'tiff',
    [0x49, 0x49, 0x2a, 0x00, 0x08, 0x00, 0x00, 0x00, 0xff, 0xff, 0, 0],
  ],
  [
    'tiff ifd offset beyond input',
    'tiff',
    [0x4d, 0x4d, 0x00, 0x2a, 0x7f, 0xff, 0xff, 0xff, 0, 0, 0, 0],
  ],
  [
    'png CgBI chunk length beyond input',
    'png',
    [...pngSignature, 0xff, 0xff, 0xff, 0xf0, 0x43, 0x67, 0x42, 0x49, ...Array(16).fill(0)],
  ],
  [
    'svg unterminated root tag',
    'svg',
    [...Buffer.from(`<svg width="1" height="1" data-x="${'a'.repeat(70_000)}`)],
  ],
]

function runInWorker(modulePath, exportName, args) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(
      `
        const { parentPort, workerData } = require('node:worker_threads')
        try {
          const fn = require(workerData.modulePath)[workerData.exportName]
          const [type, bytes, filePath] = workerData.args
          const result = fn(type, Buffer.from(bytes), filePath)
          parentPort.postMessage({ status: 'returned', result })
        } catch (error) {
          parentPort.postMessage({ status: 'rejected', message: error.message })
        }
      `,
      { eval: true, workerData: { modulePath, exportName, args } },
    )

    const timeout = setTimeout(() => {
      worker.terminate()
      reject(new Error('parser did not terminate within 1 second'))
    }, 1_000)

    worker.once('message', (result) => {
      clearTimeout(timeout)
      worker.terminate()
      resolve(result)
    })
    worker.once('error', (error) => {
      clearTimeout(timeout)
      reject(error)
    })
  })
}

const parse = (type, bytes, filePath = `fixture.${type}`) =>
  runInWorker(parserModulePath, 'getImageDimensions', [type, bytes, filePath])
const assetSize = (type, bytes, filePath = `fixture.${type}`) =>
  runInWorker(assetsModulePath, 'getAssetSize', [type, bytes, filePath])

test('workspace resolves Metro 0.83.8 without image-size', () => {
  assert.equal(JSON.parse(readFileSync(metroPackageJson, 'utf8')).version, '0.83.8')
  assert.throws(() => workspaceRequire.resolve('image-size'), { code: 'MODULE_NOT_FOUND' })
  assert.throws(() => metroRequire.resolve('image-size'), { code: 'MODULE_NOT_FOUND' })
})

for (const [name, type, bytes] of advisoryPayloads) {
  test(`${name}: Metro asset pipeline does not decode ${type}`, async () => {
    assert.deepEqual(await assetSize(type, bytes), { status: 'returned', result: null })
  })

  test(`${name}: parser terminates and fails closed`, async () => {
    for (const as of [type, 'png']) {
      assert.deepEqual(await parse(as, bytes), {
        status: 'rejected',
        message: `Invalid ${as} image asset: fixture.${as}`,
      })
    }
  })
}

for (const [name, type, bytes] of offsetPayloads) {
  test(`${name} terminates and fails closed`, async () => {
    assert.deepEqual(await assetSize(type, bytes), {
      status: 'rejected',
      message: `Invalid ${type} image asset: fixture.${type}`,
    })
  })
}

test('valid 1x1 PNG still yields dimensions', async () => {
  const ihdr = [0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52]
  const bytes = [...pngSignature, ...ihdr, 0, 0, 0, 1, 0, 0, 0, 1, 8, 6, 0, 0, 0]
  assert.deepEqual(await assetSize('png', bytes), {
    status: 'returned',
    result: { width: 1, height: 1 },
  })
})

test('workspace icon asset still yields positive dimensions', async () => {
  const icon = path.join(workspaceRoot, 'assets', 'icon.png')
  const { status, result } = await assetSize('png', [...readFileSync(icon)], icon)
  assert.equal(status, 'returned')
  assert.ok(result.width > 0 && result.height > 0, JSON.stringify(result))
})
