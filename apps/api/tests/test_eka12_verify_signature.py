"""
EKA-12 — verify_signature must not swallow unexpected verifier/programming faults.

Invalid or malformed signature material stays a deterministic False (fail closed);
anything else raises SignatureVerificationError instead of posing as "invalid".
"""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from nacl.signing import SigningKey

from models import BillStatus, GovernanceLevel
from routers import voting

API_DIR = Path(__file__).resolve().parents[1]
PAYLOAD = b"GR-1:YES:" + b"a" * 64


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


KEYPAIR_MODULES = [
    # Runtime module: routers put packages/crypto first on sys.path.
    _load(API_DIR.parents[1] / "packages" / "crypto" / "keypair.py", "eka12_pkg_keypair"),
    # Shadowed mirror kept in sync.
    _load(API_DIR / "keypair.py", "eka12_api_keypair"),
]


@pytest.fixture(params=KEYPAIR_MODULES, ids=["packages-crypto", "apps-api"])
def kp(request):
    return request.param


@pytest.fixture()
def signed():
    sk = SigningKey.generate()
    return bytes(sk.verify_key).hex(), sk.sign(PAYLOAD).signature.hex()


def test_runtime_import_is_packages_crypto():
    import keypair

    assert Path(keypair.__file__).resolve().parent.name == "crypto"
    assert Path(keypair.__file__).resolve().parent.parent.name == "packages"
    assert voting.verify_signature is keypair.verify_signature


def test_valid_signature(kp, signed):
    pk, sig = signed
    assert kp.verify_signature(pk, PAYLOAD, sig) is True
    assert kp.verify_signature(pk, PAYLOAD.decode(), sig) is True


def test_tampered_signature_and_payload_false(kp, signed):
    pk, sig = signed
    flipped = bytearray.fromhex(sig)
    flipped[0] ^= 1
    assert kp.verify_signature(pk, PAYLOAD, flipped.hex()) is False
    assert kp.verify_signature(pk, PAYLOAD + b"x", sig) is False


def test_wrong_public_key_false(kp, signed):
    _pk, sig = signed
    other = bytes(SigningKey.generate().verify_key).hex()
    assert kp.verify_signature(other, PAYLOAD, sig) is False


@pytest.mark.parametrize(
    "pk, sig",
    [
        ("zz" * 32, "00" * 64),       # non-hex key
        ("00" * 31, "00" * 64),       # short key
        ("é" * 32, "00" * 64),        # non-ascii key
        ("00" * 32, "0" * 127),       # odd-length signature
        ("00" * 32, "00" * 63),       # short signature
        ("", ""),
        (None, "00" * 64),            # client JSON may carry any type (sso body)
        ("00" * 32, 12345),
    ],
)
def test_malformed_material_false(kp, pk, sig):
    assert kp.verify_signature(pk, PAYLOAD, sig) is False


def test_programming_error_raises_typed(kp, signed, caplog):
    pk, sig = signed
    with caplog.at_level(logging.ERROR):
        with pytest.raises(kp.SignatureVerificationError):
            kp.verify_signature(pk, 12345, sig)  # server-built payload of wrong type
    assert "TypeError" in caplog.text
    assert pk not in caplog.text and sig not in caplog.text


def test_backend_failure_raises_typed(kp, signed, monkeypatch):
    import nacl.signing

    class _Broken:
        def __init__(self, *_a, **_k):
            raise RuntimeError("libsodium unavailable")

    monkeypatch.setattr(nacl.signing, "VerifyKey", _Broken)
    pk, sig = signed
    with pytest.raises(kp.SignatureVerificationError):
        kp.verify_signature(pk, PAYLOAD, sig)


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeDb:
    def __init__(self, values):
        self.values = list(values)
        self.added = []

    async def execute(self, _statement):
        return _Result(self.values.pop(0))

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        raise AssertionError("must not commit")


@pytest.mark.asyncio
async def test_submit_vote_backend_failure_propagates_without_vote_row(monkeypatch):
    import keypair

    def _broken(*_args):
        raise keypair.SignatureVerificationError("RuntimeError")

    monkeypatch.setattr(voting, "verify_signature", _broken)
    req = voting.VoteRequest(
        nullifier_hash="a" * 64, bill_id="GR-1", vote="YES", signature_hex="b" * 128,
    )
    identity = SimpleNamespace(public_key_hex="c" * 64, periferia_id=None, dimos_id=None)
    bill = SimpleNamespace(
        id="GR-1", status=BillStatus.ACTIVE, governance_level=GovernanceLevel.NATIONAL,
        admin_hidden=False,
    )
    db = _FakeDb([identity, bill])
    with pytest.raises(keypair.SignatureVerificationError):
        await voting.submit_vote(req, db)
    assert db.added == []
