const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const test = require('node:test');

const root = process.cwd();
const lock = JSON.parse(readFileSync(path.join(root, 'package-lock.json'), 'utf8'));
const packages = Object.entries(lock.packages).filter(([name]) => name.endsWith('/js-yaml'));

test('workspace retains audited YAML packages', () => assert.ok(packages.length > 0));

for (const [name, entry] of packages) {
  const directory = path.join(root, name);
  test(`${name}: installed patched version matches the lock`, () => {
    const installed = JSON.parse(readFileSync(path.join(directory, 'package.json'), 'utf8'));
    assert.equal(installed.version, entry.version);
    assert.ok(['3.15.2', '4.3.2'].includes(installed.version));
  });

  test(`${name}: ordinary mappings and merges still load`, () => {
    const yaml = require(directory);
    assert.deepEqual(yaml.load('base: &base {enabled: true}\nitem: {<<: *base, count: 2}\n'), {
      base: { enabled: true }, item: { enabled: true, count: 2 },
    });
  });

  test(`${name}: empty merge sources consume the configured budget`, () => {
    // Bound the subprocess even if a future regression bypasses the merge budget.
    const script = `
      const assert = require('node:assert/strict');
      const yaml = require(process.argv[1]);
      const input = 'empty: &empty {}\\nresult:\\n' + '  <<: *empty\\n'.repeat(64);
      assert.throws(() => yaml.load(input, { maxTotalMergeKeys: 8 }), /merge/i);
    `;
    const result = spawnSync(process.execPath, ['-e', script, directory], {
      encoding: 'utf8', timeout: 5000, maxBuffer: 16384,
    });
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stderr);
  });
}
