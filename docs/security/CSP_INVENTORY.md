# CSP inventory — T-9156 / EVA-023 enforcement

Snapshot: 2026-10-20. Regenerate with `python3 scripts/csp-inventory.py`; verify with `--check`.

The 36 live docs pages and representative web page contain **0 executable inline blocks**, **26 JSON-LD blocks**, **0 empty blocks**, **0 literal event-handler attributes**, **0 generated handlers**, and **0 javascript: URLs**.

Historical planning/community audit reports and animation-spec snippets are excluded. The frozen R0 inventory is unchanged. All production public HTML from docs and the separately copied representative app is checked. JSON-LD stays inline: application/ld+json is a non-executable data block, valid JSON, and needs neither a nonce nor a script hash. Observation run 2 reported no JSON-LD violations in Chromium/WebKit; the added offline browser regression is available for a browser-enabled environment (local launch is sandbox-blocked).

## Enforced policy and rollback

Production enforces the strict policy by default. Static HTML receives exactly one Content-Security-Policy with script-src 'self', font-src 'self', object-src 'none', base-uri 'self' and frame-ancestors 'none'. Other directives remain unchanged, including style-src 'unsafe-inline'. No script unsafe-inline, unsafe-eval, unsafe-hashes, strict-dynamic, build-dependent hash, or fixed nonce is added. No Content-Security-Policy-Report-Only header is emitted.

The priority-100 ekklesia-static router covers /, top-level docs HTML and the wiki/tickets/votes/municipality/demo/representative directories, using ekklesia-static-csp. The priority-110 embed router uses ekklesia-embed-csp with frame-ancestors * and no frame-deny header. The general web router has no edge CSP writer; Next supplies a response-specific enforced nonce policy. Each response has exactly one CSP header. The gate checks router bindings, strict policies, duplicate writers, default enforcement, the compatibility no-op and app/edge legacy policy parity.

Strict static/embed enforcement is folded into docker-compose.prod.yml. docker-compose.csp-enforce.yml remains a compatibility no-op for existing deployment commands. Next enforces by default when CSP_ENFORCE is unset or true. Explicit CSP_ENFORCE=false restores the legacy enforced Next response policy through next.config while preserving nonce rendering; it emits no Report-Only header. This app rollback does not relax the edge static/embed policies. See CSP_OBSERVATION.md for deployment and edge rollback details. Static hosting outside Traefik needs equivalent HTTP headers.

## What moved

All executable blocks now load deferred classic scripts in dependency order at their original document positions under docs/assets/js/. Twelve wiki legal-modal bodies share wiki-legal.js; eight wiki language bodies share wiki-language.js. Page-specific language/modal/nav logic retains its globals, with null guards. Language defaults and landing textContent match local origin/main; those old toggles never persisted language. events.js contains a closed allowlist of listener functions for data-csp-* controls; delegated listeners support generated cards, translated markup, nearest matching ancestor dispatch, return-false cancellation and vote stopPropagation. Parameters in generated controls use data-number/data-bill/data-choice/data-value, never evaluated strings. The prior mirror and OAuth callback assets moved here too; callback keeps no-referrer first in head and config-before-callback ordering. SSO verification script requests use no-referrer so the nonce query cannot leak into asset referrers. The minified QR vendor body is unchanged. Municipality Google Fonts links were removed: their existing serif/sans-serif fallbacks already render under the enforced policy, and no external font origins are authorized.

scripts/csp-migration.json records each source page, externalized assets and original body digests for review. The table below pins current assets, including the few template bodies changed to remove generated handlers. The new-ticket auth guard now runs in the same listener path before opening the modal; it no longer wraps a removed onclick property. Redesign approvals pin the new HTML/inventory bytes without changing frozen R0 data. Sitemap source hashes and lastmod dates reflect this migration; SEO content and JSON-LD stay unchanged.

## Counts by file

| File | Executable blocks | JSON-LD | Empty | Literal handlers | Generated handler sites | javascript: URLs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `docs/bot.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/community.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/demo/admin.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/demo/bills.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/demo/index.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/embed/qr-login.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/embed/results.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/embed/vote.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/govgr-dimos.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/index.html` | 0 | 3 | 0 | 0 | 0 | 0 |
| `docs/legal.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/mirror-setup.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/municipality/article.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/municipality/index.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/representative.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/sso-verify.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/tickets/auth/callback.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/tickets/index.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/votes/active.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/votes/recent.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/votes/results.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/wiki/api.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/wiki/architecture.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/wiki/audit.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/wiki/broadcasting.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/wiki/contributing.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/wiki/database.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/wiki/delete-account.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/wiki/faq.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/wiki/index.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/wiki/modules.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/wiki/privacy.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/wiki/roadmap.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/wiki/security.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/wiki/whitepaper.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/wiki/zk-voting.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `apps/representative/web/index.html` | 0 | 0 | 0 | 0 | 0 | 0 |

## Every remaining block and handler

Only inert JSON-LD remains. No executable inline items, empty placeholders, string handlers or generated handler sites remain.

| File:line | Category | Reason |
| --- | --- | --- |
| `docs/bot.html:26` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/community.html:40` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/govgr-dimos.html:32` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/index.html:418` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/index.html:452` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/index.html:462` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/legal.html:26` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/municipality/article.html:24` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/municipality/index.html:24` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/representative.html:26` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/tickets/index.html:26` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/wiki/api.html:175` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/wiki/architecture.html:173` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/wiki/audit.html:182` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/wiki/broadcasting.html:62` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/wiki/contributing.html:172` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/wiki/database.html:172` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/wiki/delete-account.html:139` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/wiki/faq.html:548` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/wiki/index.html:34` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/wiki/modules.html:181` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/wiki/privacy.html:184` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/wiki/roadmap.html:25` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/wiki/security.html:185` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/wiki/whitepaper.html:184` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/wiki/zk-voting.html:26` | JSON-LD data | Retain inline for SEO; inert under script-src. |

## External script digests

| Asset | SHA-256 (hex) |
| --- | --- |
| `docs/assets/js/community-finance.js` | `3c91becc9cc52c3cb5d6ddb3a5847c3f68ba0336bbb98f00095fda191379cb6f` |
| `docs/assets/js/community-language.js` | `efcdadc65102400c45e0ae063bffafc08d9658b5aed3664ad9aaa7a650011458` |
| `docs/assets/js/community-legal.js` | `ecd486c44686216d91a6b47869852d83b6290a9ff9619d53888efd6817790354` |
| `docs/assets/js/community-modals.js` | `50b7e26ae7934646376cbc788bade42d74f2555e91714abdac02525f52bae067` |
| `docs/assets/js/community-stats.js` | `9b7057c32f64757235ac2d6e97db6e0f71ce41040544b85e5fd2ff136068a294` |
| `docs/assets/js/community-tabs.js` | `a1020a98520fad523cdfaa00a63933cf173eb401f98a3222d0d9b8e0ade71f7f` |
| `docs/assets/js/demo-admin.js` | `1e2db56d71adaa48de5ba3972b2ae72184ba7c1633ca76a8d0d179374ce75364` |
| `docs/assets/js/demo-bills.js` | `ebaf37f97ca68bd1a0ba9484dc1f064aed295972e1023f49b16c38db691e469a` |
| `docs/assets/js/embed-results.js` | `81ae54ed15d517880012f7ac7ea87ed935ec63d3c233cbe88fb4996b084bf7f2` |
| `docs/assets/js/embed-ui.js` | `d386c127213ddefdef2d73c5c7dddf63d041e9ff90e0ee926f63c9124cb9bbc3` |
| `docs/assets/js/embed-vote.js` | `660e46c24691465216a2b72456068b67fe93817f0672f86183a03ffba8a63be3` |
| `docs/assets/js/events.js` | `ebcc4436e5b94be0263719f3c110d344aecbf8ecb168ea2564758743f7b6b97a` |
| `docs/assets/js/govgr-dimos.js` | `b3797f416e307b94fa946ad7910cb0a2a7faa9419500b5abf7dad91e350b6cd9` |
| `docs/assets/js/landing-chat.js` | `213091827168f7076f0d0bfa29a1f009d18ff2ae3ea88ad8742198d45fa7ffee` |
| `docs/assets/js/landing-comparison.js` | `48d9a11d784dee8e7420c6586a72737ca7c7ba72358ea77be710c5d6550a6b7a` |
| `docs/assets/js/landing-cplm.js` | `3b3cc40c0cad6c65fabb6d655dbb3ec1199d8478c39b7eff4d4a1a5913484b4e` |
| `docs/assets/js/landing-cycle.js` | `ee60bde57f02de5b592dc38c9dcc942b739dd2345669557a47fe5261319626b4` |
| `docs/assets/js/landing-language.js` | `fc576345c5a0bea6943933e5fa885fac906450d6ded5256f78e8d827f7131779` |
| `docs/assets/js/landing-legal.js` | `d5dc177aa0f9ca9460ba46af7048c880db44ca97d75f9d28e2c57789caf8fc01` |
| `docs/assets/js/landing-newsletter.js` | `b3952f0d61caf8dc2f703132221c5526bc9ea7e09176d5598c15c838ec857110` |
| `docs/assets/js/legal-language.js` | `a5b51c7f2191dd05377f265a8405ea45e64a9735a39d4bcce66e16ce72943cbb` |
| `docs/assets/js/mirror-setup-language.js` | `fd14cda09238a0f075916da340dd827d40de84b3f195a9dc08b781f6c2485f99` |
| `docs/assets/js/municipality-article.js` | `54ea7fcd43ed49c0aa04748ef6bf456ec243164d9190058d285ce7b3bb03093e` |
| `docs/assets/js/qr-login.js` | `8ac64095c45eac5455ceecde1b02169578c0d16f0a6f0b6befa8fd3958fa987e` |
| `docs/assets/js/qrcode-vendor.js` | `c541ef06327885a8415bca8df6071e14189b4855336def4f36db54bde8484f36` |
| `docs/assets/js/representative-app.js` | `93285d84949fca2edb2e74f7ccf4283a40a4281ac65e80ad46d2d63cbe2d59a4` |
| `docs/assets/js/representative-language.js` | `9e276d68e552e0abe8f39144f0ab4f18d7d44fe068ddd014c134ca990987fe86` |
| `docs/assets/js/sso-verify.js` | `f2551e8442de7ae06a22d327998dddb27db1c99163d2c6a100475aa7c816f306` |
| `docs/assets/js/tickets-auth-guard.js` | `5c734d80fc69928afe9022fa59883f236e1c6a2c8dad7783a743f822c5d5683e` |
| `docs/assets/js/tickets-board.js` | `47495b3920a4d635a8f14f59ab236907b13854470cb5f7ca699634f8dbc390c4` |
| `docs/assets/js/tickets-callback.js` | `c0b997148b6e5c1430ecaa6a1022d6d090cdde6382190ac4de51eca6cbd7b771` |
| `docs/assets/js/wiki-audit-1.js` | `287b412bb9d45a6895479f9d2aa03a3635fb65dca96721594627709587a24752` |
| `docs/assets/js/wiki-audit-2.js` | `96bb335d590a6ecdb4cbd084ab6a2e2364b8db97c2fc9f06c0a4ddfaae899364` |
| `docs/assets/js/wiki-broadcasting-2.js` | `d2c2f13a273eea52ac6d1011f58d4ea2b20588870bb427d6ef75033640fbd2aa` |
| `docs/assets/js/wiki-faq-2.js` | `417b4905c67943cbe6d580fa652445d0bad0ebd68acd1c00967ac2355c7d679c` |
| `docs/assets/js/wiki-index-2.js` | `ed80408e7514afa30e0dfab25decde1d965ae0d39495fc8011e239aa687c89c5` |
| `docs/assets/js/wiki-language.js` | `357101cfb25d4d756f4242be55347c69c9365b2ea0d1d7c3993b6e042f0d0d26` |
| `docs/assets/js/wiki-legal.js` | `99989df4947964c296d147bfb3b8cdd7eef3ba5f0ba4113f6a62b3590aba6fed` |
| `docs/assets/js/wiki-modules-2.js` | `c1631e014d00757ebf2884947da14b4d15441ec3348796bb398e21ac864ed33e` |
| `docs/assets/js/wiki-privacy-1.js` | `433c5e952b6fc31975af5804d7c2b5feb6366541305ca7f1de0b88ba9ea8bdf2` |
| `docs/assets/js/wiki-roadmap-2.js` | `8070253e7067aca9bca10ebf719a56dd382c0e1b5a386d1cc763e4e3c7da3798` |
| `docs/assets/js/wiki-zk-voting-1.js` | `bc1b1e922136bc07de623050ce65270e178bb4520042e65a624fddc50680a67e` |

## Next.js nonce and rendering

Source scan of 47 production files: **0 Inline scripts**, **0 next/script elements**, **0 beforeInteractive**, **1 dangerouslySetInnerHTML**, **0 String handlers**, **0 javascript: URLs**.

Next 16 uses src/proxy.ts. A fresh 256-bit Web Crypto nonce replaces untrusted request nonce/CSP values. The request Content-Security-Policy and x-nonce reach Next through next-intl's request-header overrides. Next automatically nonces bootstrap, Flight and streaming scripts from that request policy (verified against the locally installed Next renderer). No authored Script/inline script components exist. Future authored Script components must read x-nonce with await headers() and pass nonce explicitly.

The locale layout is force-dynamic, including formerly static client pages: nonce-bearing HTML cannot use prerender/ISR document caching. Existing SSR data fetches already use no-store; static docs stay fully static and need no nonce. Responses are private/no-store. PWA start-URL and navigation caching is disabled; public HTML is excluded from precache, and runtime same-origin caching is restricted to script/style/image/font destinations. A new worker must replace old document caches during rollout. No strict-dynamic exception is needed.

## Evidence and regression checks

T-9156 starts from production strict enforcement with zero observed violations, as reported by the owner. This change removes the redundant target Report-Only policy and makes the existing enforcement the default; no deployment or new production observation is performed here. The observer now requires an enforced header and absence of Report-Only. There is no report receiver; violations are captured locally. See CSP_OBSERVATION.md for coverage limitations and targeted offline regression commands. Verify exactly one CSP header and matching fresh HTML/Flight nonces after deployment.
