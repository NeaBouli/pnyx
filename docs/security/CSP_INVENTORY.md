# CSP inventory — T-9149 / EVA-023 step 2

Snapshot: 2026-10-19. Regenerate with `python3 scripts/csp-inventory.py`; verify with `--check`.

The 36 live docs pages and representative web page contain **0 executable inline blocks**, **26 JSON-LD blocks**, **0 empty blocks**, **0 literal event-handler attributes**, **0 generated handlers**, and **0 javascript: URLs**.

Historical planning/community audit reports and animation-spec snippets are excluded. The frozen R0 inventory is unchanged. All production public HTML from docs and the separately copied representative app is checked. JSON-LD stays inline: application/ld+json is a non-executable data block, valid JSON, and needs neither a nonce nor a script hash. Observation run 2 reported no JSON-LD violations in Chromium/WebKit; the added offline browser regression is available for a browser-enabled environment (local launch is sandbox-blocked).

## Policy and promotion

The default enforced Traefik header is byte-identical to the previous deployment. Static HTML receives a Report-Only policy with script-src 'self', object-src 'none', base-uri 'self' and the existing frame-ancestors 'none'. All other directives remain unchanged, including style-src 'unsafe-inline'. No script unsafe-inline, unsafe-eval, unsafe-hashes, strict-dynamic, build-dependent hash, or fixed nonce is added to the target.

The priority-100 ekklesia-static router covers /, top-level docs HTML and the wiki/tickets/votes/embed/municipality/demo/representative directories. It uses the shared headers middleware plus ekklesia-static-csp. The general web router uses only shared headers; Next supplies a response-specific Report-Only policy. Applying the static candidate to dynamic HTML would block bootstrap even when the app supplies a valid nonce. The gate checks both routers, both policies, the promotion override and app/edge legacy policy parity.

Promote only in a separate deployment after a new observation has zero violations and interaction/hydration checks pass. Add `-f infra/docker/docker-compose.csp-enforce.yml` after the normal production Compose file. The override enables CSP_ENFORCE=true in Next, removes the shared legacy CSP writer, and enforces the static target in the static middleware. Both surfaces retain the target Report-Only header. Omit the override and recreate web to roll back. See CSP_OBSERVATION.md for commands and prerequisites. Static hosting outside Traefik needs equivalent HTTP headers.

## What moved

All executable blocks now load classic scripts at their original document positions under docs/assets/js/. Twelve wiki legal-modal bodies share wiki-legal.js; eight wiki language bodies share wiki-language.js. Page-specific language/modal/nav logic retains its original body and globals. events.js contains a closed allowlist of listener functions for data-csp-* controls; delegated listeners support generated cards, translated markup, bubbling, return-false cancellation and vote stopPropagation. Parameters in generated controls use data-number/data-bill/data-choice/data-value, never evaluated strings. The prior mirror and OAuth callback assets moved here too; callback keeps no-referrer first in head and config-before-callback ordering. SSO verification script requests use no-referrer so the nonce query cannot leak into asset referrers. The minified QR vendor body is unchanged. Municipality Google Fonts links were removed: their existing serif/sans-serif fallbacks already render under the enforced policy, and no external font origins are authorized.

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
| `docs/index.html:414` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/index.html:448` | JSON-LD data | Retain inline for SEO; inert under script-src. |
| `docs/index.html:458` | JSON-LD data | Retain inline for SEO; inert under script-src. |
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
| `docs/wiki/faq.html:543` | JSON-LD data | Retain inline for SEO; inert under script-src. |
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
| `docs/assets/js/community-finance.js` | `743184a207cf296ffd1080000d0be9b29dcea519ab856ec2385118bfb6737503` |
| `docs/assets/js/community-language.js` | `3b1f76f5f01ef707204fd5144081a3ae917672eccb0a32fd4a38e408cf5f277c` |
| `docs/assets/js/community-legal.js` | `ecd486c44686216d91a6b47869852d83b6290a9ff9619d53888efd6817790354` |
| `docs/assets/js/community-modals.js` | `7041ed54facdff87d5d2579bab28dec42faea28412642db811e41337da698f4d` |
| `docs/assets/js/community-stats.js` | `9b7057c32f64757235ac2d6e97db6e0f71ce41040544b85e5fd2ff136068a294` |
| `docs/assets/js/community-tabs.js` | `013f961f7ca551fbdbc2df2ea5181903d7f44f6bc4e7acd40494b210f01c3749` |
| `docs/assets/js/demo-admin.js` | `1f691dcec2f2aaa0cd578a15167abf1cf249cfb83c928da1ccd9ce53470974bd` |
| `docs/assets/js/demo-bills.js` | `8a380ee4b9658c831f199ffe80523005e8c4dd4d9a01438464ca1dcafdeda484` |
| `docs/assets/js/embed-results.js` | `193aa472a02e3492a447b62596d7e3011eb631ce7d5ad5fa2103a09b383ebb7e` |
| `docs/assets/js/embed-vote.js` | `8ebb372c011ce1c12483401a6a83582a39f00c7cf3f2b3b5baf1ba0a60835b8b` |
| `docs/assets/js/events.js` | `d7654c9626aca4ec1cc087f92d080cadca24b55c02f6ae266a75378fb5b43a32` |
| `docs/assets/js/govgr-dimos.js` | `403a38d3152a14fea1aa1e53c0c674273b61c73e1174c432870cdb198cbf7e04` |
| `docs/assets/js/landing-chat.js` | `213091827168f7076f0d0bfa29a1f009d18ff2ae3ea88ad8742198d45fa7ffee` |
| `docs/assets/js/landing-comparison.js` | `2d2fbe06400ef46b59e5044c0c1faeac986710cf04f7f27fbcda06d41826247f` |
| `docs/assets/js/landing-cplm.js` | `3b3cc40c0cad6c65fabb6d655dbb3ec1199d8478c39b7eff4d4a1a5913484b4e` |
| `docs/assets/js/landing-cycle.js` | `f0758af21846772ff7a7512a8f70c115aa862b92b90d187ffa2cb901dc36d353` |
| `docs/assets/js/landing-language.js` | `eb7fa7f5de3c172fd478774f0a567c40a6a8250a60db2562f4023aac7a16617d` |
| `docs/assets/js/landing-legal.js` | `d5dc177aa0f9ca9460ba46af7048c880db44ca97d75f9d28e2c57789caf8fc01` |
| `docs/assets/js/landing-newsletter.js` | `b3952f0d61caf8dc2f703132221c5526bc9ea7e09176d5598c15c838ec857110` |
| `docs/assets/js/legal-language.js` | `0e3f24977977c513d8f82b0fda40b71ac3c6535b8755ff03a62022b6909f01e4` |
| `docs/assets/js/mirror-setup-language.js` | `fd14cda09238a0f075916da340dd827d40de84b3f195a9dc08b781f6c2485f99` |
| `docs/assets/js/municipality-article.js` | `54ea7fcd43ed49c0aa04748ef6bf456ec243164d9190058d285ce7b3bb03093e` |
| `docs/assets/js/qr-login.js` | `ce47bea344cb453cab3f19e07be0dc0b08d0fbc64940e3e8efef58736676c291` |
| `docs/assets/js/qrcode-vendor.js` | `c541ef06327885a8415bca8df6071e14189b4855336def4f36db54bde8484f36` |
| `docs/assets/js/representative-app.js` | `4352b043a9b4358134aedf012519681aac0a7aa48dd09c82a9acabcd29bcafda` |
| `docs/assets/js/representative-language.js` | `1a7ad510edb7e5fba7071329db5c143d3e5b0cc8c7cdbfc1b286319a2dc6ed64` |
| `docs/assets/js/sso-verify.js` | `f2551e8442de7ae06a22d327998dddb27db1c99163d2c6a100475aa7c816f306` |
| `docs/assets/js/tickets-auth-guard.js` | `5c734d80fc69928afe9022fa59883f236e1c6a2c8dad7783a743f822c5d5683e` |
| `docs/assets/js/tickets-board.js` | `68e2f062662ca1264eac9cd4bdb973a7cdced156461da630c9dd134aeecea344` |
| `docs/assets/js/tickets-callback.js` | `283c66e31dfc034130bb09523e8a33979ac19e8cf4ddfdeae2d5ae5308325a82` |
| `docs/assets/js/wiki-audit-1.js` | `287b412bb9d45a6895479f9d2aa03a3635fb65dca96721594627709587a24752` |
| `docs/assets/js/wiki-audit-2.js` | `6407ecd6e9b9a07083807057012f54e7035ab9b84703887b2c9c8c7886e2a284` |
| `docs/assets/js/wiki-broadcasting-2.js` | `c589b3f7e6f9290aeb7d510ee8916beef9137190523a5228918cca91001f6ce1` |
| `docs/assets/js/wiki-faq-2.js` | `d78f285885464f5b4707ca87e1c622c60193bc6c73d23f2d86570168d1ae52cf` |
| `docs/assets/js/wiki-index-2.js` | `ada406adfd100c5d16a05f2036debfce00a5ae8e8e6b51bbc20089cf39ac1ed5` |
| `docs/assets/js/wiki-language.js` | `217f0cc023029244017434da203029292dad9d8af7bd6b2e8936759149d06579` |
| `docs/assets/js/wiki-legal.js` | `99989df4947964c296d147bfb3b8cdd7eef3ba5f0ba4113f6a62b3590aba6fed` |
| `docs/assets/js/wiki-modules-2.js` | `79a9c78f7289d16102131968e93c5b0a7394e960a2eed25f3d864492d79b86e1` |
| `docs/assets/js/wiki-privacy-1.js` | `433c5e952b6fc31975af5804d7c2b5feb6366541305ca7f1de0b88ba9ea8bdf2` |
| `docs/assets/js/wiki-roadmap-2.js` | `ff1fafeb2c3a0ce5e06c685708a8909764fac9ec252d95883f9d892f55f174e6` |
| `docs/assets/js/wiki-zk-voting-1.js` | `99a710f14f56afdc9cc4f8255c20c984244285598f8966074fa670e00db27c03` |

## Next.js nonce and rendering

Source scan of 44 production files: **0 Inline scripts**, **0 next/script elements**, **0 beforeInteractive**, **1 dangerouslySetInnerHTML**, **0 String handlers**, **0 javascript: URLs**.

Next 16 uses src/proxy.ts. A fresh 256-bit Web Crypto nonce replaces untrusted request nonce/CSP values. The request Content-Security-Policy and x-nonce reach Next through next-intl's request-header overrides. Next automatically nonces bootstrap, Flight and streaming scripts from that request policy (verified against the locally installed Next renderer). No authored Script/inline script components exist. Future authored Script components must read x-nonce with await headers() and pass nonce explicitly.

The locale layout is force-dynamic, including formerly static client pages: nonce-bearing HTML cannot use prerender/ISR document caching. Existing SSR data fetches already use no-store; static docs stay fully static and need no nonce. Responses are private/no-store. PWA start-URL and navigation caching is disabled; public HTML is excluded from precache, and runtime same-origin caching is restricted to script/style/image/font destinations. A new worker must replace old document caches before promotion. No strict-dynamic exception is needed.

## Evidence and rollout gate

Observation run 2 (132 visits, Chromium/WebKit at 390/1280) diagnosed static inline code, ticket handlers, Next bootstrap and municipality external font styles. It predates this migration and is not zero-violation evidence for this tree. No network, deployment or new production observation is performed by this task. There is no report receiver; violations are captured locally by the observation tool. See CSP_OBSERVATION.md for coverage limitations and required follow-up. A production build/render with the pinned Next version and deployed Traefik verification remain prerequisites to enforcement.
