# CSP inventory — T-9138 / EVA-023

Snapshot: 2026-10-17. Regenerate with `python3 scripts/csp-inventory.py`; verify with `--check`.

The 35 live `docs/**/*.html` pages contain **55 executable inline blocks**, **25 JSON-LD blocks**, **1 empty block**, **230 literal event-handler attributes**, and **0 javascript: URLs** after this change. There are also **12 handler template sites** inside HTML script blocks and **6** in external docs JavaScript; runtime instances depend on data.

Scope includes redirects, embeds, demos, and the live `wiki/audit.html` disclosure. Historical planning/community audit reports and `animation-spec/LANDING_SNIPPETS.html` (a design snippet, zero inline scripts/handlers) are excluded. The frozen `docs/planning/r0` inventory is unchanged. Production copies only the docs paths listed in `apps/web/Dockerfile.prod`; demos, mirror-setup and the legacy static sso-verify page are also inventoried because they are live docs pages on the static host.

## Policy and migration strategy

The existing enforced CSP remains byte-identical in `infra/docker/docker-compose.prod.yml`. The same Traefik `ekklesia-headers` middleware adds `Content-Security-Policy-Report-Only` using `customResponseHeaders` (the existing compose mechanism also used for API response headers). The gate parses active Compose YAML with PyYAML, requires both policies on the enabled `web` service, and verifies the `ekklesia-web` router binds `ekklesia-headers`. The `ekklesia-www` router only redirects to the canonical host. The policies apply to the shared production origin, including static HTML paths that bypass the Next proxy matcher. Static hosting outside this Traefik deployment requires its own HTTP header configuration; an HTML meta tag cannot deliver Report-Only.

The target changes `script-src 'self' 'unsafe-inline'` to `script-src 'self'` plus the two real SHA-256 sources below, and adds `object-src 'none'; base-uri 'self'`. `frame-ancestors 'none'` and all other existing directives are retained, including `style-src 'self' 'unsafe-inline'`. There is no `unsafe-hashes`, `unsafe-eval`, fixed nonce, or `strict-dynamic` escape hatch. The script hashes allow whole script blocks, never event attributes.

| Allowed inline script | SHA-256 source (exact UTF-8 body, including whitespace) |
| --- | --- |
| `docs/legal.html:226` — language toggle | `'sha256-Dj8kl3l3xRPY+CsP2kC3GsPGU1uHVf8DpiAitpCfAeQ='` |
| `docs/municipality/article.html:561` — scroll reveals | `'sha256-VOp/zUPtScCqBHSO9r9FbsJDFk2RkAWNKFzns7sDCT4='` |

No CSP report receiver, `report-uri`, `report-to`, or Reporting-Endpoints configuration exists in the inspected API/web/infra sources. No receiver or third party is added: violations are browser-console-only. Remaining inline scripts and handlers, including Next bootstrap, intentionally produce Report-Only violations; their execution still follows the unchanged enforced policy.

**Externalize** means move the exact body into a same-origin classic script at the same document position and preserve dependencies, then replace inline attributes/generated attributes with `addEventListener` (or CSS for hover decoration). A nonce or script hash does not authorize an `onclick` attribute. **Hash** means retain stable inline bytes and update the allowlist when they change. JSON-LD is inert structured data, listed separately from executable code: preserve it inline for SEO; hash it if the supported browser/consumer requires CSP authorization. **Nonce** is reserved for response-specific Next bootstrap/Flight scripts, not static files.

This change moves `docs/mirror-setup.html`'s 292-character language toggle to `docs/assets/csp/mirror-setup.js` and the 2,264-character OAuth callback from `docs/tickets/auth/callback.html` to adjacent `callback.js`. Bodies are byte-identical, with no defer/module/async change; callback remains after `../config.js`. The callback's first head element sets `no-referrer` before any resources, preventing OAuth query parameters from reaching same-origin asset-request referrers. Mirror's existing inline click handler remains callable through its global `toggleLang`. Both asset locations are copied by the existing Dockerfile rules where their HTML is served. Only the two exact HTML hashes in `approved_analytics_delta.py` change; no frozen baseline or wiki/audit approvals change. These pages are absent from sitemap sources, so no sitemap/hash change is needed.

## Counts by file

| File | Executable blocks | JSON-LD | Empty | Literal handlers | Generated handler sites | javascript: URLs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `docs/community.html` | 6 | 1 | 1 | 14 | 0 | 0 |
| `docs/demo/admin.html` | 1 | 0 | 0 | 1 | 1 | 0 |
| `docs/demo/bills.html` | 1 | 0 | 0 | 0 | 6 | 0 |
| `docs/demo/index.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/embed/qr-login.html` | 2 | 0 | 0 | 1 | 0 | 0 |
| `docs/embed/results.html` | 1 | 0 | 0 | 0 | 0 | 0 |
| `docs/embed/vote.html` | 1 | 0 | 0 | 0 | 3 | 0 |
| `docs/govgr-dimos.html` | 1 | 1 | 0 | 10 | 0 | 0 |
| `docs/index.html` | 7 | 3 | 0 | 26 | 0 | 0 |
| `docs/legal.html` | 1 | 1 | 0 | 0 | 0 | 0 |
| `docs/mirror-setup.html` | 0 | 0 | 0 | 1 | 0 | 0 |
| `docs/municipality/article.html` | 1 | 1 | 0 | 0 | 0 | 0 |
| `docs/municipality/index.html` | 0 | 1 | 0 | 0 | 0 | 0 |
| `docs/representative.html` | 1 | 1 | 0 | 1 | 0 | 0 |
| `docs/sso-verify.html` | 1 | 0 | 0 | 1 | 0 | 0 |
| `docs/tickets/auth/callback.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/tickets/index.html` | 2 | 1 | 0 | 18 | 2 | 0 |
| `docs/votes/active.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/votes/recent.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/votes/results.html` | 0 | 0 | 0 | 0 | 0 | 0 |
| `docs/wiki/api.html` | 2 | 1 | 0 | 5 | 0 | 0 |
| `docs/wiki/architecture.html` | 2 | 1 | 0 | 5 | 0 | 0 |
| `docs/wiki/audit.html` | 2 | 1 | 0 | 5 | 0 | 0 |
| `docs/wiki/broadcasting.html` | 2 | 1 | 0 | 23 | 0 | 0 |
| `docs/wiki/contributing.html` | 2 | 1 | 0 | 5 | 0 | 0 |
| `docs/wiki/database.html` | 2 | 1 | 0 | 5 | 0 | 0 |
| `docs/wiki/delete-account.html` | 2 | 1 | 0 | 5 | 0 | 0 |
| `docs/wiki/faq.html` | 2 | 1 | 0 | 62 | 0 | 0 |
| `docs/wiki/index.html` | 2 | 1 | 0 | 5 | 0 | 0 |
| `docs/wiki/modules.html` | 2 | 1 | 0 | 5 | 0 | 0 |
| `docs/wiki/privacy.html` | 2 | 1 | 0 | 5 | 0 | 0 |
| `docs/wiki/roadmap.html` | 2 | 1 | 0 | 16 | 0 | 0 |
| `docs/wiki/security.html` | 2 | 1 | 0 | 5 | 0 | 0 |
| `docs/wiki/whitepaper.html` | 2 | 1 | 0 | 5 | 0 | 0 |
| `docs/wiki/zk-voting.html` | 1 | 1 | 0 | 1 | 0 | 0 |

## Every remaining block and handler

Locations refer to this tree. Identical handler bodies are grouped with every source line listed; counts are attribute occurrences, not distinct code strings. Template rows count creation sites, not runtime elements.

### `docs/community.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 39 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 521 | Executable: <code>function switchHlrTab(tab) {</code> | Externalize; preserve globals and execution order. |
| 929 | Executable: <code>(function(){</code> | Externalize; preserve globals and execution order. |
| 997 | Executable: <code>var _privacyHtml='&lt;h2 style="margin-top:0"&gt;Πολιτική Απορρήτου&lt;/h2&gt;&lt;p&gt;&lt;strong&gt;Τι ΔΕΝ αποθηκεύουμ</code> | Externalize; preserve globals and execution order. |
| 1005 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 1023 | Empty script block | Externalize: remove the empty placeholder with the surrounding script migration. |
| 1026 | Executable: <code>// @ai-anchor INVOICE_AMPEL_TIMER</code> | Externalize; preserve globals and execution order. |
| 1766 | Executable: <code>// NGO Contact Modal</code> | Externalize; preserve globals and execution order. |
| 317 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 541 | <code>onclick=switchHlrTab('primary')</code> | Externalize to listeners. |
| 542 | <code>onclick=switchHlrTab('fallback')</code> | Externalize to listeners. |
| 797 | <code>onclick=openSharePopup();return false;</code> | Externalize to listeners. |
| 812 | <code>onclick=openNgoModal();return false;</code> | Externalize to listeners. |
| 818 | <code>onclick=document.getElementById('finance').scrollIntoView({behavior:'smooth'});return false;</code> | Externalize to listeners. |
| 985 | <code>onclick=openLegalModal('privacy');return false</code> | Externalize to listeners. |
| 986 | <code>onclick=openLegalModal('delete');return false</code> | Externalize to listeners. |
| 991 | <code>onclick=if(event.target===this)closeLegalModal()</code> | Externalize to listeners. |
| 993 | <code>onclick=closeLegalModal()</code> | Externalize to listeners. |
| 1720 | <code>onclick=closeNgoModal()</code> | Externalize to listeners. |
| 1723 | <code>onsubmit=submitNgoForm(event)</code> | Externalize to listeners. |
| 1741 | <code>onclick=closeSharePopup()</code> | Externalize to listeners. |
| 1744 | <code>onclick=copyShareLink()</code> | Externalize to listeners. |

### `docs/demo/admin.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 95 | Executable: <code>var html = "";</code> | Externalize; preserve globals and execution order. |
| 75 | <code>onclick=createBill()</code> | Externalize to listeners. |
| 99 | Generated handler: <code>onclick="alert(\'Demo: Bill würde auf ACTIVE gesetzt\')"&gt;→ ACTIVE&lt;/button&gt;' : '';</code> | Externalize to listeners after element creation / delegation. |

### `docs/demo/bills.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 76 | Executable: <code>var currentFilter = "ALL";</code> | Externalize; preserve globals and execution order. |
| 89 | Generated handler: <code>onclick="setFilter(\'' + f.key + '\')"&gt;' + f.label + ' (' + (f.key === "ALL" ? DEMO_BILLS.length : DEMO_BILLS.filter(function(b){return b.status===f.key}).length) + ')&lt;/button&gt;';</code> | Externalize to listeners after element creation / delegation. |
| 123 | Generated handler: <code>onclick="castVote(\'' + b.id + '\',\'YES\')"&gt;ΝΑΙ&lt;/button&gt;';</code> | Externalize to listeners after element creation / delegation. |
| 124 | Generated handler: <code>onclick="castVote(\'' + b.id + '\',\'NO\')"&gt;ΟΧΙ&lt;/button&gt;';</code> | Externalize to listeners after element creation / delegation. |
| 125 | Generated handler: <code>onclick="castVote(\'' + b.id + '\',\'ABSTAIN\')"&gt;ΑΠΟΧΗ&lt;/button&gt;';</code> | Externalize to listeners after element creation / delegation. |
| 141 | Generated handler: <code>oninput="document.getElementById(\'sv_' + b.id + '\').textContent=this.value&gt;0?\'+\'+this.value:this.value"&gt;';</code> | Externalize to listeners after element creation / delegation. |
| 143 | Generated handler: <code>onclick="castConsensus(\'' + b.id + '\')"&gt;Υποβολή Βαθμολογίας&lt;/button&gt;';</code> | Externalize to listeners after element creation / delegation. |

### `docs/demo/index.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| — | None | No inline migration needed. |

### `docs/embed/qr-login.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 8 | Executable: <code>var QRCode;!function(){function a(a){this.mode=c.MODE_8BIT_BYTE,this.data=a,this.parsedData=[];</code> | Externalize; preserve globals and execution order. |
| 56 | Executable: <code>var API='https://api.ekklesia.gr';</code> | Externalize; preserve globals and execution order. |
| 53 | <code>onclick=startSession()</code> | Externalize to listeners. |

### `docs/embed/results.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 40 | Executable: <code>var API='https://api.ekklesia.gr';</code> | Externalize; preserve globals and execution order. |

### `docs/embed/vote.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 47 | Executable: <code>var API='https://api.ekklesia.gr';</code> | Externalize; preserve globals and execution order. |
| 180 | Generated handler: <code>onclick="castVote(\'YES\')"&gt;'+(el?'ΝΑΙ':'YES')+'&lt;/button&gt;';</code> | Externalize to listeners after element creation / delegation. |
| 181 | Generated handler: <code>onclick="castVote(\'NO\')"&gt;'+(el?'ΟΧΙ':'NO')+'&lt;/button&gt;';</code> | Externalize to listeners after element creation / delegation. |
| 182 | Generated handler: <code>onclick="castVote(\'ABSTAIN\')"&gt;'+(el?'ΑΠΟΧΗ':'ABSTAIN')+'&lt;/button&gt;';</code> | Externalize to listeners after element creation / delegation. |

### `docs/govgr-dimos.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 31 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 843 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 214 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 337, 348 | <code>onclick=openNgoModal()</code> | Externalize to listeners. |
| 752 | <code>onclick=openNgoModal();return false;</code> | Externalize to listeners. |
| 752 | <code>onmouseenter=this.style.background='#1d4ed8'</code> | Externalize to listeners / CSS hover rules. |
| 752 | <code>onmouseleave=this.style.background='#2563eb'</code> | Externalize to listeners / CSS hover rules. |
| 753 | <code>onmouseenter=this.style.background='#eff6ff'</code> | Externalize to listeners / CSS hover rules. |
| 753 | <code>onmouseleave=this.style.background='transparent'</code> | Externalize to listeners / CSS hover rules. |
| 775 | <code>onclick=closeNgoModal()</code> | Externalize to listeners. |
| 778 | <code>onsubmit=submitNgoForm(event)</code> | Externalize to listeners. |

### `docs/index.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 413 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 447 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 457 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 951 | Executable: <code>(function(){</code> | Externalize; preserve globals and execution order. |
| 1188 | Executable: <code>(function(){</code> | Externalize; preserve globals and execution order. |
| 1683 | Executable: <code>async function submitNewsletter(e) {</code> | Externalize; preserve globals and execution order. |
| 1749 | Executable: <code>var _privacyHtml='&lt;h2 style="margin-top:0"&gt;Πολιτική Απορρήτου / Privacy Policy&lt;/h2&gt;'</code> | Externalize; preserve globals and execution order. |
| 1776 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 1793 | Executable: <code>// Democracy Cycle Animation — 6 Phasen (#356)</code> | Externalize; preserve globals and execution order. |
| 2254 | Executable: <code>// EKA-62: every chat string reaches the DOM via textContent on created nodes;</code> | Externalize; preserve globals and execution order. |
| 505 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 663 | <code>onmouseover=this.style.borderColor='#2563eb';this.style.transform='translateY(-2px)'</code> | Externalize to listeners / CSS hover rules. |
| 663 | <code>onmouseout=this.style.borderColor='#22c55e';this.style.transform='none'</code> | Externalize to listeners / CSS hover rules. |
| 672 | <code>onmouseenter=this.style.borderColor='#3b82f6';this.style.opacity='1'</code> | Externalize to listeners / CSS hover rules. |
| 672 | <code>onmouseleave=this.style.borderColor='#334155';this.style.opacity='0.8'</code> | Externalize to listeners / CSS hover rules. |
| 683 | <code>onmouseenter=this.style.borderColor='#3b82f6'</code> | Externalize to listeners / CSS hover rules. |
| 683 | <code>onmouseleave=this.style.borderColor='#22c55e'</code> | Externalize to listeners / CSS hover rules. |
| 1406 | <code>onmouseenter=this.style.background='#1d4ed8'</code> | Externalize to listeners / CSS hover rules. |
| 1406 | <code>onmouseleave=this.style.background='#2563eb'</code> | Externalize to listeners / CSS hover rules. |
| 1565, 1571 | <code>onmouseover=this.style.transform='translateY(-2px)'</code> | Externalize to listeners / CSS hover rules. |
| 1565, 1571 | <code>onmouseout=this.style.transform='none'</code> | Externalize to listeners / CSS hover rules. |
| 1651 | <code>onsubmit=submitNewsletter(event)</code> | Externalize to listeners. |
| 1736 | <code>onclick=openLegalModal('privacy');return false</code> | Externalize to listeners. |
| 1737 | <code>onclick=openLegalModal('delete');return false</code> | Externalize to listeners. |
| 1743 | <code>onclick=if(event.target===this)closeLegalModal()</code> | Externalize to listeners. |
| 1745 | <code>onclick=closeLegalModal()</code> | Externalize to listeners. |
| 2200 | <code>onclick=if(event.target===this)this.style.display='none'</code> | Externalize to listeners. |
| 2202 | <code>onclick=document.getElementById('pwaModal').style.display='none'</code> | Externalize to listeners. |
| 2236, 2240 | <code>onclick=toggleChat()</code> | Externalize to listeners. |
| 2236 | <code>onmouseenter=this.style.transform='scale(1.1)'</code> | Externalize to listeners / CSS hover rules. |
| 2236 | <code>onmouseleave=this.style.transform='scale(1)'</code> | Externalize to listeners / CSS hover rules. |
| 2247 | <code>onkeydown=if(event.key==='Enter')sendChat()</code> | Externalize to listeners. |
| 2248 | <code>onclick=sendChat()</code> | Externalize to listeners. |

### `docs/legal.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 26 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 226 | Executable: <code>(function () {</code> | Hash: exact digest already in Report-Only. |

### `docs/mirror-setup.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 65 | <code>onclick=navigator.clipboard.writeText('curl -fsSL https://ekklesia.gr/mirror-setup.sh &#124; sudo bash')</code> | Externalize to listeners. |

### `docs/municipality/article.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 24 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 561 | Executable: <code>// Scroll-triggered section reveals</code> | Hash: exact digest already in Report-Only. |

### `docs/municipality/index.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 26 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |

### `docs/representative.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 25 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 202 | Executable: <code>var currentLang="el";</code> | Externalize; preserve globals and execution order. |
| 92 | <code>onclick=toggleLang()</code> | Externalize to listeners. |

### `docs/sso-verify.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 306 | Executable: <code>(function () {</code> | Externalize; preserve globals and execution order. |
| 289 | <code>onclick=retryAuth()</code> | Externalize to listeners. |

### `docs/tickets/auth/callback.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| — | None | No inline migration needed. |

### `docs/tickets/index.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 25 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 63 | Executable: <code>// Phase B: auth-state-aware ticket guard (replaces old desktop blanket block)</code> | Externalize; preserve globals and execution order. |
| 221 | Executable: <code>// Populate category sidebar + select</code> | Externalize; preserve globals and execution order. |
| 58 | <code>onclick=document.getElementById('phaseBModal').style.display='none'</code> | Externalize to listeners. |
| 103 | <code>onclick=setPolisLang(polisLang==='el'?'en':'el');document.getElementById('langBtn').textContent=polisLang==='el'?'EN':'ΕΛ'</code> | Externalize to listeners. |
| 115 | <code>onclick=openNewTicketModal()</code> | Externalize to listeners. |
| 118 | <code>onclick=openQRLogin()</code> | Externalize to listeners. |
| 129 | <code>onclick=filterByStatus(this,'')</code> | Externalize to listeners. |
| 130 | <code>onclick=filterByStatus(this,'status:pending')</code> | Externalize to listeners. |
| 131 | <code>onclick=filterByStatus(this,'status:open')</code> | Externalize to listeners. |
| 132 | <code>onclick=filterByStatus(this,'status:claimed')</code> | Externalize to listeners. |
| 133 | <code>onclick=filterByStatus(this,'status:resolved')</code> | Externalize to listeners. |
| 137 | <code>onclick=filterByCat(this,'')</code> | Externalize to listeners. |
| 142 | <code>onclick=sortBy(this,'newest')</code> | Externalize to listeners. |
| 143 | <code>onclick=sortBy(this,'votes')</code> | Externalize to listeners. |
| 144 | <code>onclick=sortBy(this,'oldest')</code> | Externalize to listeners. |
| 156 | <code>onclick=loadMoreTickets()</code> | Externalize to listeners. |
| 173 | <code>onclick=closeTicketModal()</code> | Externalize to listeners. |
| 176 | <code>onsubmit=submitTicketForm(event)</code> | Externalize to listeners. |
| 199 | <code>onclick=if(event.target===this)closeMobileDetail()</code> | Externalize to listeners. |
| 202 | <code>onclick=closeMobileDetail()</code> | Externalize to listeners. |
| 226 | Generated handler: <code>onclick="filterByCat(this,\'category:' + cat.id + '\')"&gt;' + (polisLang === "el" ? cat.el : cat.en) + '&lt;/div&gt;';</code> | Externalize to listeners after element creation / delegation. |
| 300 | Generated handler: <code>onclick="closeQRLogin()" style="padding:8px 20px;background:#f1f5f9;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;cursor:pointer"&gt;' + _qr("cancel") + '&lt;/button&gt;' +</code> | Externalize to listeners after element creation / delegation. |

### `docs/votes/active.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| — | None | No inline migration needed. |

### `docs/votes/recent.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| — | None | No inline migration needed. |

### `docs/votes/results.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| — | None | No inline migration needed. |

### `docs/wiki/api.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 174 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 375 | Executable: <code>var _privacyHtml='&lt;h2 style="margin-top:0"&gt;Πολιτική Απορρήτου&lt;/h2&gt;&lt;p&gt;&lt;strong&gt;Τι ΔΕΝ αποθηκεύουμ</code> | Externalize; preserve globals and execution order. |
| 383 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 209 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 363 | <code>onclick=openLegalModal('privacy');return false</code> | Externalize to listeners. |
| 364 | <code>onclick=openLegalModal('delete');return false</code> | Externalize to listeners. |
| 369 | <code>onclick=if(event.target===this)closeLegalModal()</code> | Externalize to listeners. |
| 371 | <code>onclick=closeLegalModal()</code> | Externalize to listeners. |

### `docs/wiki/architecture.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 172 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 387 | Executable: <code>var _privacyHtml='&lt;h2 style="margin-top:0"&gt;Πολιτική Απορρήτου&lt;/h2&gt;&lt;p&gt;&lt;strong&gt;Τι ΔΕΝ αποθηκεύουμ</code> | Externalize; preserve globals and execution order. |
| 395 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 207 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 375 | <code>onclick=openLegalModal('privacy');return false</code> | Externalize to listeners. |
| 376 | <code>onclick=openLegalModal('delete');return false</code> | Externalize to listeners. |
| 381 | <code>onclick=if(event.target===this)closeLegalModal()</code> | Externalize to listeners. |
| 383 | <code>onclick=closeLegalModal()</code> | Externalize to listeners. |

### `docs/wiki/audit.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 181 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 461 | Executable: <code>var _privacyHtml='&lt;h2 style="margin-top:0"&gt;Πολιτική Απορρήτου&lt;/h2&gt;&lt;p&gt;&lt;a href="privacy.html" sty</code> | Externalize; preserve globals and execution order. |
| 469 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 216 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 449 | <code>onclick=openLegalModal('privacy');return false</code> | Externalize to listeners. |
| 450 | <code>onclick=openLegalModal('delete');return false</code> | Externalize to listeners. |
| 455 | <code>onclick=if(event.target===this)closeLegalModal()</code> | Externalize to listeners. |
| 457 | <code>onclick=closeLegalModal()</code> | Externalize to listeners. |

### `docs/wiki/broadcasting.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 61 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 273 | Executable: <code>var _privacyHtml='&lt;h2 style="margin-top:0"&gt;Πολιτική Απορρήτου&lt;/h2&gt;&lt;p&gt;&lt;strong&gt;Τι ΔΕΝ αποθηκεύουμ</code> | Externalize; preserve globals and execution order. |
| 280 | Executable: <code>var currentLang="el";function toggleLang(){currentLang=currentLang==="el"?"en":"el";document.ge</code> | Externalize; preserve globals and execution order. |
| 96 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 157, 161, 165, 169, 173, 182, 186, 190 | <code>onmouseover=this.style.opacity='0.85'</code> | Externalize to listeners / CSS hover rules. |
| 157, 161, 165, 169, 173, 182, 186, 190 | <code>onmouseout=this.style.opacity='1'</code> | Externalize to listeners / CSS hover rules. |
| 207 | <code>onclick=navigator.clipboard.writeText(document.getElementById('embed-all').innerText)</code> | Externalize to listeners. |
| 217 | <code>onclick=navigator.clipboard.writeText(document.getElementById('embed-single').innerText)</code> | Externalize to listeners. |
| 261 | <code>onclick=openLegalModal('privacy');return false</code> | Externalize to listeners. |
| 262 | <code>onclick=openLegalModal('delete');return false</code> | Externalize to listeners. |
| 267 | <code>onclick=if(event.target===this)closeLegalModal()</code> | Externalize to listeners. |
| 269 | <code>onclick=closeLegalModal()</code> | Externalize to listeners. |

### `docs/wiki/contributing.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 171 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 279 | Executable: <code>var _privacyHtml='&lt;h2 style="margin-top:0"&gt;Πολιτική Απορρήτου&lt;/h2&gt;&lt;p&gt;&lt;strong&gt;Τι ΔΕΝ αποθηκεύουμ</code> | Externalize; preserve globals and execution order. |
| 287 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 206 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 267 | <code>onclick=openLegalModal('privacy');return false</code> | Externalize to listeners. |
| 268 | <code>onclick=openLegalModal('delete');return false</code> | Externalize to listeners. |
| 273 | <code>onclick=if(event.target===this)closeLegalModal()</code> | Externalize to listeners. |
| 275 | <code>onclick=closeLegalModal()</code> | Externalize to listeners. |

### `docs/wiki/database.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 171 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 302 | Executable: <code>var _privacyHtml='&lt;h2 style="margin-top:0"&gt;Πολιτική Απορρήτου&lt;/h2&gt;&lt;p&gt;&lt;strong&gt;Τι ΔΕΝ αποθηκεύουμ</code> | Externalize; preserve globals and execution order. |
| 310 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 206 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 290 | <code>onclick=openLegalModal('privacy');return false</code> | Externalize to listeners. |
| 291 | <code>onclick=openLegalModal('delete');return false</code> | Externalize to listeners. |
| 296 | <code>onclick=if(event.target===this)closeLegalModal()</code> | Externalize to listeners. |
| 298 | <code>onclick=closeLegalModal()</code> | Externalize to listeners. |

### `docs/wiki/delete-account.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 138 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 324 | Executable: <code>var _privacyHtml='&lt;h2 style="margin-top:0"&gt;Πολιτική Απορρήτου&lt;/h2&gt;&lt;p&gt;&lt;strong&gt;Τι ΔΕΝ αποθηκεύουμ</code> | Externalize; preserve globals and execution order. |
| 332 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 173 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 312 | <code>onclick=openLegalModal('privacy');return false</code> | Externalize to listeners. |
| 313 | <code>onclick=openLegalModal('delete');return false</code> | Externalize to listeners. |
| 318 | <code>onclick=if(event.target===this)closeLegalModal()</code> | Externalize to listeners. |
| 320 | <code>onclick=closeLegalModal()</code> | Externalize to listeners. |

### `docs/wiki/faq.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 533 | Executable: <code>var _privacyHtml='&lt;h2 style="margin-top:0"&gt;Πολιτική Απορρήτου&lt;/h2&gt;&lt;p&gt;&lt;strong&gt;Τι ΔΕΝ αποθηκεύουμ</code> | Externalize; preserve globals and execution order. |
| 541 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 558 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 188 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 203, 208, 213, 218, 223, 231, 236, 241, 246, 251, 256, 261, 266, 271, 279, 283, 287, 291, 295, 300, 308, 313, 318, 323, 328, 333, 338, 343, 351, 356, 361, 366, 371, 376, 384, 389, 394, 399, 404, 412, 417, 422, 427, 432, 440, 445, 450, 458, 463, 468, 473, 478, 483, 488, 493, 498, 503 | <code>onclick=this.parentElement.classList.toggle('open')</code> | Externalize to listeners. |
| 521 | <code>onclick=openLegalModal('privacy');return false</code> | Externalize to listeners. |
| 522 | <code>onclick=openLegalModal('delete');return false</code> | Externalize to listeners. |
| 527 | <code>onclick=if(event.target===this)closeLegalModal()</code> | Externalize to listeners. |
| 529 | <code>onclick=closeLegalModal()</code> | Externalize to listeners. |

### `docs/wiki/index.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 33 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 313 | Executable: <code>var _privacyHtml='&lt;h2 style="margin-top:0"&gt;Πολιτική Απορρήτου&lt;/h2&gt;&lt;p&gt;&lt;strong&gt;Τι ΔΕΝ αποθηκεύουμ</code> | Externalize; preserve globals and execution order. |
| 321 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 223 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 301 | <code>onclick=openLegalModal('privacy');return false</code> | Externalize to listeners. |
| 302 | <code>onclick=openLegalModal('delete');return false</code> | Externalize to listeners. |
| 307 | <code>onclick=if(event.target===this)closeLegalModal()</code> | Externalize to listeners. |
| 309 | <code>onclick=closeLegalModal()</code> | Externalize to listeners. |

### `docs/wiki/modules.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 180 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 282 | Executable: <code>var _privacyHtml='&lt;h2 style="margin-top:0"&gt;Πολιτική Απορρήτου&lt;/h2&gt;&lt;p&gt;&lt;strong&gt;Τι ΔΕΝ αποθηκεύουμ</code> | Externalize; preserve globals and execution order. |
| 290 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 215 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 270 | <code>onclick=openLegalModal('privacy');return false</code> | Externalize to listeners. |
| 271 | <code>onclick=openLegalModal('delete');return false</code> | Externalize to listeners. |
| 276 | <code>onclick=if(event.target===this)closeLegalModal()</code> | Externalize to listeners. |
| 278 | <code>onclick=closeLegalModal()</code> | Externalize to listeners. |

### `docs/wiki/privacy.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 183 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 349 | Executable: <code>var _privacyHtml='&lt;h2 style="margin-top:0"&gt;Πολιτική Απορρήτου&lt;/h2&gt;&lt;p&gt;&lt;strong&gt;Τι ΔΕΝ αποθηκεύουμ</code> | Externalize; preserve globals and execution order. |
| 357 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 218 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 337 | <code>onclick=openLegalModal('privacy');return false</code> | Externalize to listeners. |
| 338 | <code>onclick=openLegalModal('delete');return false</code> | Externalize to listeners. |
| 343 | <code>onclick=if(event.target===this)closeLegalModal()</code> | Externalize to listeners. |
| 345 | <code>onclick=closeLegalModal()</code> | Externalize to listeners. |

### `docs/wiki/roadmap.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 24 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 589 | Executable: <code>var _privacyHtml='&lt;h2 style="margin-top:0"&gt;Πολιτική Απορρήτου&lt;/h2&gt;&lt;p&gt;&lt;strong&gt;Τι ΔΕΝ αποθηκεύουμ</code> | Externalize; preserve globals and execution order. |
| 597 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 255 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 267, 280, 306, 328, 349, 390, 409, 429, 450, 478, 504 | <code>onclick=toggleSection(this)</code> | Externalize to listeners. |
| 577 | <code>onclick=openLegalModal('privacy');return false</code> | Externalize to listeners. |
| 578 | <code>onclick=openLegalModal('delete');return false</code> | Externalize to listeners. |
| 583 | <code>onclick=if(event.target===this)closeLegalModal()</code> | Externalize to listeners. |
| 585 | <code>onclick=closeLegalModal()</code> | Externalize to listeners. |

### `docs/wiki/security.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 184 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 490 | Executable: <code>var _privacyHtml='&lt;h2 style="margin-top:0"&gt;Πολιτική Απορρήτου&lt;/h2&gt;&lt;p&gt;&lt;strong&gt;Τι ΔΕΝ αποθηκεύουμ</code> | Externalize; preserve globals and execution order. |
| 498 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 219 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 478 | <code>onclick=openLegalModal('privacy');return false</code> | Externalize to listeners. |
| 479 | <code>onclick=openLegalModal('delete');return false</code> | Externalize to listeners. |
| 484 | <code>onclick=if(event.target===this)closeLegalModal()</code> | Externalize to listeners. |
| 486 | <code>onclick=closeLegalModal()</code> | Externalize to listeners. |

### `docs/wiki/whitepaper.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 183 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 361 | Executable: <code>var _privacyHtml='&lt;h2 style="margin-top:0"&gt;Πολιτική Απορρήτου&lt;/h2&gt;&lt;p&gt;&lt;strong&gt;Τι ΔΕΝ αποθηκεύουμ</code> | Externalize; preserve globals and execution order. |
| 369 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 218 | <code>onclick=toggleLang()</code> | Externalize to listeners. |
| 349 | <code>onclick=openLegalModal('privacy');return false</code> | Externalize to listeners. |
| 350 | <code>onclick=openLegalModal('delete');return false</code> | Externalize to listeners. |
| 355 | <code>onclick=if(event.target===this)closeLegalModal()</code> | Externalize to listeners. |
| 357 | <code>onclick=closeLegalModal()</code> | Externalize to listeners. |

### `docs/wiki/zk-voting.html`

| Location(s) | Category / item | Plan |
| --- | --- | --- |
| 25 | JSON-LD data | Hash if CSP authorization is needed; retain inline for SEO. |
| 145 | Executable: <code>var currentLang = "el";</code> | Externalize; preserve globals and execution order. |
| 71 | <code>onclick=toggleLang()</code> | Externalize to listeners. |

## Generated handlers in external docs scripts

Externalizing a script alone does not remove the handlers it creates. These sites are loaded by `docs/tickets/index.html`.

| File:line | Item | Plan |
| --- | --- | --- |
| `docs/tickets/polis.js:357` | <code>onclick="login()"&gt;' + t("loginGitHub") + '&lt;/button&gt;';</code> | Externalize to listeners / delegated events. |
| `docs/tickets/polis.js:372` | <code>onclick="selectTicket(' + issue.number + ')"&gt;'</code> | Externalize to listeners / delegated events. |
| `docs/tickets/polis.js:374` | <code>onclick="event.stopPropagation();toggleVote(' + issue.number + ')" title="' + t("vote") + '"&gt;▲&lt;/button&gt;'</code> | Externalize to listeners / delegated events. |
| `docs/tickets/polis.js:431` | <code>onclick="toggleVote(' + issue.number + ')"&gt;'</code> | Externalize to listeners / delegated events. |
| `docs/tickets/polis.js:434` | <code>onclick="doClaim(' + issue.number + ')"&gt;🙋 ' + t("claim") + '&lt;/button&gt;' : '')</code> | Externalize to listeners / delegated events. |
| `docs/tickets/polis.js:545` | <code>onclick="loadAndRender()" style="margin-top:1rem"&gt;' + t("loadMore") + '&lt;/button&gt;&lt;/div&gt;';</code> | Externalize to listeners / delegated events. |

## Next.js app inventory and nonce prerequisite

Source scan of 42 production JS/TS/JSX/TSX/MJS files in `apps/web/src` plus `apps/web/next.config.mjs` (tests excluded): **0 Inline scripts**, **0 next/script elements**, **0 beforeInteractive**, **1 dangerouslySetInnerHTML**, **0 String handlers**, **0 javascript: URLs**.

Counts are generated from source sites, including literal HTML strings; comments are ignored. Inline script elements include data blocks and `next/script` elements without an actual `src` attribute; `data-src` and mentions inside attribute values do not make a script external. Default imports of `next/script` are tracked by their local name, including combined default/named imports and `default as` aliases within named imports; `beforeInteractive` is counted even for external scripts. All `dangerouslySetInnerHTML` sites are listed for review, including styles and non-script HTML. Categories can overlap. This conservative scan does not evaluate spreads, computed props or dynamically assembled HTML; inspect production output before enforcement. React callback props are counted separately and do not require `unsafe-inline`.

| File | Inline scripts | next/script elements | beforeInteractive | dangerouslySetInnerHTML | String handlers | javascript: URLs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `apps/web/next.config.mjs` | 0 | 0 | 0 | 0 | 0 | 0 |
| `apps/web/src/app/[locale]/layout.tsx` | 0 | 0 | 0 | 0 | 0 | 0 |
| `apps/web/src/app/[locale]/sso-verify/page.tsx` | 0 | 0 | 0 | 1 | 0 | 0 |
| `apps/web/src/proxy.ts` | 0 | 0 | 0 | 0 | 0 | 0 |

| File:line | Source site | Plan |
| --- | --- | --- |
| `apps/web/src/app/[locale]/sso-verify/page.tsx:222` | dangerouslySetInnerHTML on <code>&lt;style&gt;</code> | Style injection; outside this script hardening step. |

Next-emitted bootstrap / hydration / Flight (`self.__next_f.push(...)`, etc.) remains response-dependent and unmeasured without a production build/render. Use a nonce for each response, since contents vary with route, build and payload. Generate a fresh cryptographically random nonce in `src/proxy.ts`, pass it with the matching CSP to the Next renderer, and apply the policy to the response. Ensure `src/app/[locale]/layout.tsx` and any authored scripts receive it. Preserve next-intl, redirects and rewrites; evaluate dynamic rendering, prefetches, streaming, error routes and caching. PWA auto-registration is enabled in `next.config.mjs`; inspect its built output for inline script and nonce compatibility.

Current nonce plumbing is absent. A static Traefik label cannot create a per-request nonce or stamp it on Next scripts. Before enforcement, retain the static-docs policy at the edge and route dynamic HTML through a matching nonce-aware application policy; avoid a second static strict enforced policy that would still block Next even if its application policy allows the nonce. Never reuse a constant nonce, echo a client-supplied nonce, or cache nonce-bearing HTML independently of its header. Current PWA `StaleWhileRevalidate` document caching also needs review before serving per-response nonces. No Next code is changed in this PR; an offline production render was unavailable because this worktree has no installed web dependencies.

React callback occurrences (source JSX expressions; separate from string handlers):

| File | Callback props |
| --- | ---: |
| `apps/web/src/app/[locale]/analytics/page.tsx` | 1 |
| `apps/web/src/app/[locale]/bills/BillsClient.tsx` | 10 |
| `apps/web/src/app/[locale]/bills/[id]/page.tsx` | 6 |
| `apps/web/src/app/[locale]/mp/page.tsx` | 1 |
| `apps/web/src/app/[locale]/municipal/page.tsx` | 3 |
| `apps/web/src/app/[locale]/results/ResultsClient.tsx` | 2 |
| `apps/web/src/app/[locale]/sso-verify/page.tsx` | 4 |
| `apps/web/src/components/QRCodeVoteStub.tsx` | 2 |
| `apps/web/src/components/RelevanceButtons.tsx` | 2 |
| `apps/web/src/components/VoteButton.tsx` | 1 |

## Work remaining before enforcement

1. Externalize the remaining executable blocks and all literal/generated handlers listed above, including language controls, FAQ/roadmap toggles, modals, newsletter/chat, demos, embeds and ticket rendering. Keep inert JSON-LD and approved stable hashes synchronized.
2. Implement and verify the Next nonce path, rendering/cache/PWA behavior, and edge/application policy composition; exercise all locale routes, errors, hydration, navigation and offline/service-worker updates with the unchanged enforced policy plus the nonce-aware Report-Only candidate.
3. Inspect console violations on deployed static and dynamic routes, including templates populated from API data and translated DOM, and verify both HTTP headers at the edge. The current local checks validate configuration, not a deployed Traefik response.
4. Review other HTML served on this origin (notably `apps/representative/web`, copied separately by the Dockerfile) before changing a shared enforced header. Confirm existing `frame-ancestors 'none'` remains intentional for embeds. Remove script `unsafe-inline` from enforcement only in a later reviewed rollout after violations are resolved.
