"""EVA-034/035: admin test accounts are handed over as an in-app import code."""
import hashlib

from routers.admin_account import IMPORT_CODE_PREFIX, build_import_code

PRIV = "11" * 32
NULL = "22" * 32
PUB = "33" * 32


def test_import_code_format_and_checksum() -> None:
    code = build_import_code(PRIV, NULL, PUB)
    prefix, priv, null, pub, checksum = code.split(":")

    assert prefix == IMPORT_CODE_PREFIX
    assert (priv, null, pub) == (PRIV, NULL, PUB)
    expected = hashlib.sha256(f"{IMPORT_CODE_PREFIX}:{PRIV}:{NULL}:{PUB}".encode()).hexdigest()[:8]
    assert checksum == expected
    assert "ekklesia://" not in code and "?" not in code and "&" not in code


def test_import_code_golden_vector_shared_with_mobile() -> None:
    # Same vector as apps/mobile/src/lib/import-code.test.ts.
    assert build_import_code(PRIV.upper(), NULL, PUB) == f"{IMPORT_CODE_PREFIX}:{PRIV}:{NULL}:{PUB}:3d847acc"
