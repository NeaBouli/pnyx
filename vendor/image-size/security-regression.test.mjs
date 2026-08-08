import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import { Worker } from 'node:worker_threads'

const packageRoot = process.env.IMAGE_SIZE_PACKAGE_ROOT
  ? path.resolve(process.cwd(), process.env.IMAGE_SIZE_PACKAGE_ROOT)
  : fileURLToPath(new URL('.', import.meta.url))

const typeModule = (name) => path.join(packageRoot, 'dist', 'types', `${name}.js`)

const payloads = {
  heif: {
    modulePath: typeModule('heif'),
    exportName: 'HEIF',
    expectedError: 'Invalid HEIF box size',
    bytes: [
    0x00, 0x00, 0x00, 0x10, 0x66, 0x74, 0x79, 0x70,
    0x61, 0x76, 0x69, 0x66, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x24, 0x6d, 0x65, 0x74, 0x61,
    0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x08, 0x69, 0x70, 0x72, 0x70,
    0x00, 0x00, 0x00, 0x14, 0x69, 0x70, 0x63, 0x6f,
    0x00, 0x00, 0x00, 0x00, 0x69, 0x73, 0x70, 0x65,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ],
  },
  jxl: {
    modulePath: typeModule('jxl'),
    exportName: 'JXL',
    expectedError: 'Invalid JXL box size',
    bytes: [
    0x00, 0x00, 0x00, 0x0c, 0x4a, 0x58, 0x4c, 0x20,
    0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x0c, 0x66, 0x74, 0x79, 0x70,
    0x6a, 0x78, 0x6c, 0x20,
    0x00, 0x00, 0x00, 0x00, 0x6a, 0x78, 0x6c, 0x70,
    0x00, 0x00, 0x00, 0x00,
    ],
  },
  icns: {
    modulePath: typeModule('icns'),
    exportName: 'ICNS',
    expectedError: 'Invalid ICNS entry length',
    bytes: [
    0x69, 0x63, 0x6e, 0x73,
    0x00, 0x00, 0x00, 0x10,
    0x69, 0x73, 0x33, 0x32,
    0x00, 0x00, 0x00, 0x00,
    ],
  },
}

function withUInt32BE(bytes, offset, value) {
  const copy = [...bytes]
  copy[offset] = (value >>> 24) & 0xff
  copy[offset + 1] = (value >>> 16) & 0xff
  copy[offset + 2] = (value >>> 8) & 0xff
  copy[offset + 3] = value & 0xff
  return copy
}

const testCases = [
  ['heif zero-length box', payloads.heif],
  [
    'heif undersized non-zero box',
    { ...payloads.heif, bytes: withUInt32BE(payloads.heif.bytes, 44, 7) },
  ],
  ['jxl zero-length box', payloads.jxl],
  [
    'jxl undersized non-zero box',
    { ...payloads.jxl, bytes: withUInt32BE(payloads.jxl.bytes, 24, 7) },
  ],
  ['icns zero-length entry', payloads.icns],
  [
    'icns entry exceeds declared file length',
    {
      ...payloads.icns,
      bytes: withUInt32BE(
        withUInt32BE(payloads.icns.bytes, 4, 12),
        12,
        8,
      ),
    },
  ],
  [
    'icns entry exceeds actual input length',
    {
      ...payloads.icns,
      bytes: withUInt32BE(
        withUInt32BE(payloads.icns.bytes, 4, 32),
        12,
        24,
      ),
    },
  ],
]

function runInWorker(testCase) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(
      `
        const { parentPort, workerData } = require('node:worker_threads')
        try {
          const handler = require(workerData.modulePath)[workerData.exportName]
          handler.calculate(Uint8Array.from(workerData.bytes))
          parentPort.postMessage('returned')
        } catch (error) {
          parentPort.postMessage({ status: 'rejected', message: error.message })
        }
      `,
      { eval: true, workerData: testCase },
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

for (const [name, testCase] of testCases) {
  test(`${name} terminates and fails closed`, async () => {
    assert.deepEqual(await runInWorker(testCase), {
      status: 'rejected',
      message: testCase.expectedError,
    })
  })
}
