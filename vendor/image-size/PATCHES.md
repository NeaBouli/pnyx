# image-size security backport

This directory vendors the published `image-size@1.2.1` package under the
local version `1.2.2-pnyx.0`. Metro depends on the 1.x API, and the upstream
repository was archived before a patched npm release was published.

Backported fixes:

- Reject zero or undersized HEIF/JXL boxes before parser offsets can stall.
  The JXL change follows the unmerged upstream security PR head
  `bdbe560bfd98af6feab93b46aed67f2f0a77e4d5`.
- Reject undersized or out-of-bounds ICNS entries before advancing the parser
  offset.

Covered advisories:

- `GHSA-5p2g-fcmc-qvqq` / `CVE-2025-71329`
- `GHSA-w3rx-r6r6-pgpr` / `CVE-2025-71330`

The package API, supported formats, and all other distributed files are
unchanged from `image-size@1.2.1`. Run
`node --test security-regression.test.mjs` from this directory to verify the
malformed HEIF, JXL, and ICNS inputs terminate and fail closed.
