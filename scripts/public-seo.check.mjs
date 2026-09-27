// EKA-48 / EKA-49 regressions. Dependency-free: node --test scripts/public-seo.check.mjs
// Head metadata of every indexable static page and sitemap drift (source hash +
// rendering). Runs on a shallow CI checkout; git-history assertions are skipped there.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, relative } from 'node:path';
import {
  REQUIRED_OG,
  REQUIRED_TWITTER,
  ROOT,
  checkSitemap,
  inspectPage,
  loadSources,
  renderSitemap,
  sha256,
  sourceDrift,
} from './public-seo.mjs';

const sources = loadSources();
const staticEntries = sources.entries.filter((e) => e.source);
const locs = new Set(sources.entries.map((e) => sources.base + e.loc));

// Served HTML that is intentionally absent from the sitemap, with the reason.
const NOT_INDEXED = {
  'docs/animation-spec/LANDING_SNIPPETS.html': 'design snippet, not copied into the web image',
};

function walkHtml(dir) {
  return readdirSync(join(ROOT, dir), { withFileTypes: true }).flatMap((d) => {
    const rel = `${dir}/${d.name}`;
    if (d.isDirectory()) return walkHtml(rel);
    return d.name.endsWith('.html') ? [rel] : [];
  });
}

const disallowed = readFileSync(join(ROOT, 'docs/robots.txt'), 'utf8')
  .split('User-agent: *')[1]
  .split(/\nUser-agent:/)[0]
  .split('\n')
  .filter((l) => l.startsWith('Disallow:'))
  .map((l) => l.slice('Disallow:'.length).trim());

test('sitemap.xml matches its generator input and every source hash (drift gate)', () => {
  assert.deepEqual(checkSitemap(), []);
});

test('a changed source page is reported as drift', () => {
  const copy = structuredClone(sources);
  const entry = copy.entries.find((e) => e.source === 'docs/legal.html');
  entry.sha256 = sha256(Buffer.from('stale'));
  assert.deepEqual(sourceDrift(copy), [`docs/legal.html: content changed since lastmod ${entry.lastmod}`]);
  entry.lastmod = '2000-01-01';
  assert.notEqual(renderSitemap(copy), renderSitemap(sources));
});

test('lastmod values are ISO dates, not in the future, and only on static sources', () => {
  const today = new Date().toISOString().slice(0, 10);
  for (const e of sources.entries) {
    if (!e.source) {
      assert.equal(e.lastmod, undefined, `${e.loc}: dynamic route must not claim a lastmod`);
      continue;
    }
    assert.match(e.lastmod, /^\d{4}-\d{2}-\d{2}$/, e.source);
    assert.ok(e.lastmod <= today, `${e.source}: lastmod ${e.lastmod} is in the future`);
  }
});

test('lastmod never postdates the last git commit of the source', (t) => {
  const git = (args) => execFileSync('git', args, { cwd: ROOT, encoding: 'utf8', env: { ...process.env, TZ: 'UTC' } }).trim();
  let shallow;
  try {
    shallow = git(['rev-parse', '--is-shallow-repository']) === 'true';
  } catch {
    shallow = true;
  }
  if (shallow) {
    t.skip('shallow clone: history-based check needs full git history');
    return;
  }
  for (const e of staticEntries) {
    const last = git(['log', '-1', '--format=%cd', '--date=format-local:%Y-%m-%d', '--', e.source]);
    assert.ok(e.lastmod <= last, `${e.source}: lastmod ${e.lastmod} > last commit ${last}`);
  }
});

test('every indexable static page is in the sitemap and nothing else is', () => {
  const indexable = walkHtml('docs')
    .filter((rel) => !rel.startsWith('docs/planning/'))
    .filter((rel) => !(rel in NOT_INDEXED))
    .filter((rel) => {
      const html = readFileSync(join(ROOT, rel), 'utf8');
      if (/http-equiv="refresh"/i.test(html)) return false;
      const robots = inspectPage(rel).robots.join(',');
      if (/noindex/i.test(robots)) return false;
      const url = `/${relative('docs', rel)}`;
      return !disallowed.some((prefix) => prefix && url.startsWith(prefix));
    })
    .sort();
  assert.deepEqual(indexable, staticEntries.map((e) => e.source).sort());
});

for (const entry of staticEntries) {
  test(`head metadata: ${entry.source}`, () => {
    const p = inspectPage(entry.source);
    const url = sources.base + entry.loc;
    assert.ok(p.title && p.title.trim(), 'title');
    assert.equal(p.description.length, 1, 'exactly one meta description');
    assert.ok(p.description[0].trim(), 'non-empty description');
    assert.deepEqual(p.canonical, [url], 'canonical equals sitemap loc');
    assert.ok(entry.loc === '/' || !entry.loc.endsWith('/'), 'canonical must be the final document, not a redirecting directory URL');
    for (const k of REQUIRED_OG) assert.ok(p.og[k], `og:${k}`);
    assert.equal(p.og.url, url, 'og:url equals canonical');
    for (const k of REQUIRED_TWITTER) assert.ok(p.twitter[k], `twitter:${k}`);
    assert.equal(p.twitter.image, p.og.image, 'twitter:image equals og:image');
    assert.ok(p.og.image.startsWith(`${sources.base}/`), 'og:image on own origin');
    const imagePath = p.og.image.slice(sources.base.length);
    assert.ok(
      existsSync(join(ROOT, 'docs', imagePath)) || existsSync(join(ROOT, 'apps/web/public', imagePath)),
      `og:image ${imagePath} exists in the repo`,
    );
    assert.ok(p.jsonLd.length >= 1, 'at least one JSON-LD block');
    assert.ok(p.jsonLd.every(Boolean), 'all JSON-LD blocks parse');

    // One JS-toggled document per URL: no language may claim a URL that is
    // already the alternate of another language, and alternates are real locs.
    const byHref = new Map();
    for (const { lang, href } of p.hreflang) {
      assert.ok(locs.has(href), `hreflang ${lang} -> ${href} is not a sitemap URL`);
      if (lang === 'x-default') continue;
      assert.ok(!byHref.has(href), `hreflang ${lang} and ${byHref.get(href)} share ${href}`);
      byHref.set(href, lang);
    }
  });
}

test('sitemap alternates are distinct, existing locale routes', () => {
  const locales = readFileSync(join(ROOT, 'apps/web/src/i18n/routing.ts'), 'utf8').match(/locales:\s*\[([^\]]*)\]/)[1];
  for (const e of sources.entries.filter((x) => x.alternates)) {
    const hrefs = Object.values(e.alternates);
    assert.equal(new Set(hrefs).size, hrefs.length, `${e.loc}: two languages share one URL`);
    for (const [lang, href] of Object.entries(e.alternates)) {
      const [, locale, segment] = href.match(/^\/([a-z]{2})\/([a-z-]+)$/) || [];
      assert.equal(locale, lang, `${href} locale prefix`);
      assert.ok(locales.includes(`"${lang}"`), `${lang} is a configured locale`);
      assert.ok(existsSync(join(ROOT, 'apps/web/src/app/[locale]', segment, 'page.tsx')), `${href} route exists`);
    }
  }
});
