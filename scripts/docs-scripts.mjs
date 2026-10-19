// Offline test helper: follow same-origin classic script URLs in document order.
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const docs = fileURLToPath(new URL('../docs/', import.meta.url));
export function scriptBodies(page, scriptBase = page) {
  const path = page instanceof URL ? fileURLToPath(page) : page;
  // Copied pages may resolve assets from a different directory when deployed.
  const base = scriptBase instanceof URL ? fileURLToPath(scriptBase) : scriptBase;
  const html = readFileSync(path, 'utf8');
  return [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)].map((match) => {
    if (/application\/ld\+json/i.test(match[1])) return '';
    const src = match[1].match(/\bsrc="([^"]+)"/i)?.[1];
    if (!src) return match[2];
    if (/^(?:https?:)?\/\//.test(src)) throw new Error('Tests must use local script assets');
    return readFileSync(src.startsWith('/') ? resolve(docs, src.slice(1)) : resolve(dirname(base), src), 'utf8');
  }).filter(Boolean);
}
export function pageWithScripts(page) {
  const path = page instanceof URL ? fileURLToPath(page) : page;
  return readFileSync(path, 'utf8') + '\n' + scriptBodies(path).join('\n');
}
