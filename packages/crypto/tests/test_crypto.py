"""Unit Tests für packages/crypto"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from keypair import generate_keypair, sign_payload, verify_signature
from nullifier import generate_nullifier_hash, generate_demographic_hash
from hlr import is_valid_greek_mobile, normalize_greek_number


class TestKeypair:
    def test_generate_returns_hex_strings(self):
        kp = generate_keypair()
        assert len(kp["public_key_hex"]) == 64
        assert len(kp["private_key_hex"]) == 64

    def test_sign_and_verify(self):
        kp = generate_keypair()
        payload = b'{"bill_id": "GR-2024-0042", "vote": "YES"}'
        sig = sign_payload(kp["private_key_hex"], payload)
        assert verify_signature(kp["public_key_hex"], payload, sig)

    def test_wrong_signature_rejected(self):
        kp1 = generate_keypair()
        kp2 = generate_keypair()
        payload = b"test vote"
        sig = sign_payload(kp1["private_key_hex"], payload)
        assert not verify_signature(kp2["public_key_hex"], payload, sig)

    def test_tampered_payload_rejected(self):
        kp = generate_keypair()
        payload = b"original vote"
        sig = sign_payload(kp["private_key_hex"], payload)
        assert not verify_signature(kp["public_key_hex"], b"tampered vote", sig)


class TestNullifier:
    def test_same_input_same_hash(self):
        h1 = generate_nullifier_hash("+306912345678")
        h2 = generate_nullifier_hash("+306912345678")
        assert h1 == h2

    def test_different_numbers_different_hashes(self):
        h1 = generate_nullifier_hash("+306912345678")
        h2 = generate_nullifier_hash("+306987654321")
        assert h1 != h2

    def test_hash_is_64_chars(self):
        h = generate_nullifier_hash("+306912345678")
        assert len(h) == 64

    def test_demographic_hash(self):
        h = generate_demographic_hash("AGE_26_35", "REG_ATTICA", "GENDER_MALE")
        assert len(h) == 64

    def test_demographic_different_groups(self):
        h1 = generate_demographic_hash("AGE_26_35", "REG_ATTICA", "GENDER_MALE")
        h2 = generate_demographic_hash("AGE_36_45", "REG_ATTICA", "GENDER_MALE")
        assert h1 != h2


class TestHLR:
    def test_valid_greek_mobile(self):
        assert is_valid_greek_mobile("+306912345678") is True
        assert is_valid_greek_mobile("6912345678") is True
        assert is_valid_greek_mobile("00306912345678") is True

    def test_landline_rejected(self):
        assert is_valid_greek_mobile("+302101234567") is False

    def test_invalid_format(self):
        assert is_valid_greek_mobile("12345") is False
