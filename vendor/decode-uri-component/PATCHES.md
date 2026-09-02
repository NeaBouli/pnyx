# decode-uri-component security backport

This directory vendors `decode-uri-component@0.2.2` under the local version
`0.2.2-pnyx.0`. React Navigation 7 reaches this package through
`query-string@7.1.3`, whose CommonJS call site is incompatible with the
ESM-only upstream fix in `decode-uri-component@0.5.0`.

Backported fix:

- Replace the recursive malformed-percent decoder with the bounded,
  left-to-right UTF-8 scanner released upstream in v0.5.0.
- Preserve the v0.2.2 CommonJS export, type error, plus-to-space behavior, BOM
  replacements, and truncated `%C2` behavior used by query-string 7.

Upstream provenance:

- Advisory: `GHSA-vcc3-ghjq-m6fr` / `CVE-2026-45822`
- Fix commit: `fa479dafeede7bedf04e5c89aa78f2a78c664005`
- Fixed release: `decode-uri-component@0.5.0`

## Threat model

The Android app accepts `ekklesia://` and `https://ekklesia.gr` deep links.
React Navigation parses their query strings through this dependency. An
attacker who convinces a user to open a URL containing a long malformed
percent-encoded value could otherwise consume excessive CPU and make the app
unresponsive. This is an availability issue; it does not expose data, execute
code, or affect vote and identity cryptography.

Run `node --test security-regression.test.mjs` from this directory to verify
the CommonJS contract, existing decoding behavior, malformed input handling,
and bounded completion of the advisory payload.

## Monitoring and retirement

Dependabot alert `#82` remains open because the package keeps its upstream
identity and a version within the advisory range. The alert must not be
dismissed or suppressed. Replace this backport when React Navigation publishes
a supported dependency chain that consumes `decode-uri-component@0.5.0` or a
later fixed release, then let the real dependency change close the alert.

Do not assign an artificial version outside the advisory range solely to hide
the alert. The regression test must run against the installed tarball before
this backport is changed.
