import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const lock = JSON.parse(
  readFileSync(new URL('../../apps/mobile/package-lock.json', import.meta.url), 'utf8'),
)
const packages = Object.entries(lock.packages)

function entriesFor(name) {
  return packages.filter(([path]) =>
    path === `node_modules/${name}` || path.endsWith(`/node_modules/${name}`),
  )
}

test('mobile dependency closure excludes the vulnerable decoder chain', () => {
  for (const name of ['query-string', 'decode-uri-component']) {
    assert.deepEqual(entriesFor(name), [], `${name} must be absent from the lockfile`)
    for (const [path, pkg] of packages) {
      assert.equal(pkg.dependencies?.[name], undefined, `${path || 'root'} depends on ${name}`)
    }
  }
})

test('mobile locks compatible React Navigation core 7.22.1 or newer', () => {
  const cores = entriesFor('@react-navigation/core')
  assert.ok(cores.length > 0, '@react-navigation/core must be installed')
  for (const [path, pkg] of cores) {
    const match = /^7\.(\d+)\.(\d+)$/.exec(pkg.version)
    assert.ok(match, `${path} must remain on stable React Navigation 7`)
    const minor = Number(match[1])
    const patch = Number(match[2])
    assert.ok(minor > 22 || (minor === 22 && patch >= 1), `${path} is ${pkg.version}`)
    assert.equal(pkg.dependencies?.['query-string'], undefined, `${path} retains query-string`)
  }
})
