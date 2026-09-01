import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import path from 'node:path'
import test from 'node:test'
import { Worker } from 'node:worker_threads'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const packageRoot = process.env.DECODE_URI_COMPONENT_PACKAGE_ROOT
  ? path.resolve(process.cwd(), process.env.DECODE_URI_COMPONENT_PACKAGE_ROOT)
  : fileURLToPath(new URL('.', import.meta.url))
const modulePath = path.join(packageRoot, 'index.js')
const decodeUriComponent = require(modulePath)

const compatibilityCases = new Map([
  ['a+b+c', 'a b c'],
  ['%25', '%'],
  ['st%C3%A5le', 'ståle'],
  ['%7B%ab%%7C%de%%7D', '{%ab%|%de%}'],
  ['%FE%FF', '\uFFFD\uFFFD'],
  ['a%FE%FFb', 'a\uFFFD\uFFFDb'],
  ['%C2', '\uFFFD'],
  ['%C3%A5%C2', 'å\uFFFD'],
  ['%C2%C2', '\uFFFD\uFFFD'],
  ['prefix%C2suffix', 'prefix\uFFFDsuffix'],
  ['%%C2%%', '%\uFFFD%%'],
  ['%C2%B5', 'µ'],
  ['%F0%9F%98%80', '😀'],
  ['%E0%80%80', '%E0%80%80'],
  ['%ED%A0%80', '%ED%A0%80'],
  ['%F4%90%80%80', '%F4%90%80%80'],
  ['%84%D7%25%88%90', '%84%D7%%88%90'],
  ['%C3%5A%A5%AB', '%C3Z%A5%AB'],
  ['%G0%C3%A5%ab', '%G0å%ab'],
])

test('retains the v0.2.2 CommonJS contract and decoding behavior', () => {
  assert.equal(typeof decodeUriComponent, 'function')

  for (const [input, expected] of compatibilityCases) {
    assert.equal(decodeUriComponent(input), expected, input)
  }

  assert.throws(
    () => decodeUriComponent(5),
    { message: 'Expected `encodedURI` to be of type `string`, got `number`' },
  )
})

function decodeInWorker(input, timeoutMs = 1_000) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(
      `
        const { parentPort, workerData } = require('node:worker_threads')
        const decode = require(workerData.modulePath)
        const startedAt = Date.now()
        const output = decode(workerData.input)
        parentPort.postMessage({ output, elapsedMs: Date.now() - startedAt })
      `,
      { eval: true, workerData: { input, modulePath } },
    )

    const timeout = setTimeout(() => {
      worker.terminate()
      reject(new Error(`decoder did not terminate within ${timeoutMs}ms`))
    }, timeoutMs)

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

test('malformed percent runs complete within a fixed bound', async () => {
  const input = '%C3'.repeat(512)
  const result = await decodeInWorker(input)

  assert.equal(result.output, input)
  assert.ok(result.elapsedMs < 500, `decoder took ${result.elapsedMs}ms`)
})

test('mixed valid and malformed sequences decode without recombination', async () => {
  const input = '%F0%9F%98%80%G0%C3%A5%ab'.repeat(64)
  const result = await decodeInWorker(input)

  assert.equal(result.output, '😀%G0å%ab'.repeat(64))
  assert.ok(result.elapsedMs < 500, `decoder took ${result.elapsedMs}ms`)
})

if (process.env.DECODE_URI_COMPONENT_PACKAGE_ROOT) {
  const queryStringPath = require.resolve('query-string', { paths: [process.cwd()] })

  test('query-string resolves and executes the installed backport', async () => {
    const resolvedDecoder = require.resolve('decode-uri-component', {
      paths: [path.dirname(queryStringPath)],
    })
    assert.equal(resolvedDecoder, modulePath)

    const input = '%C3'.repeat(512)
    const result = await new Promise((resolve, reject) => {
      const worker = new Worker(
        `
          const { parentPort, workerData } = require('node:worker_threads')
          const queryString = require(workerData.queryStringPath)
          const startedAt = Date.now()
          const parsed = queryString.parse('value=' + workerData.input)
          parentPort.postMessage({ value: parsed.value, elapsedMs: Date.now() - startedAt })
        `,
        { eval: true, workerData: { input, queryStringPath } },
      )

      const timeout = setTimeout(() => {
        worker.terminate()
        reject(new Error('query-string did not terminate within 1000ms'))
      }, 1_000)

      worker.once('message', (message) => {
        clearTimeout(timeout)
        worker.terminate()
        resolve(message)
      })
      worker.once('error', (error) => {
        clearTimeout(timeout)
        reject(error)
      })
    })

    assert.equal(result.value, input)
    assert.ok(result.elapsedMs < 500, `query-string took ${result.elapsedMs}ms`)
  })
}
