"""GH#112 scoped ZK group registry helper tests."""
import pytest

from services.zk_group_registry import (
    build_active_group_root_for_scope,
    count_active_commitments_for_scope,
    list_active_commitments_for_scope,
    list_public_group_members_for_scope,
    public_group_members_for_root,
    validate_vote_scope_id,
)
from services.zk_merkle_root import poseidon2


class _FakeScalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class _FakeResult:
    def __init__(self, values=None, scalar=None):
        self.values = values or []
        self.scalar = scalar

    def scalars(self):
        return _FakeScalars(self.values)

    def scalar_one(self):
        return self.scalar


class _FakeDb:
    def __init__(self, result):
        self.result = result
        self.executed = []

    async def execute(self, statement):
        self.executed.append(statement)
        return self.result


def test_validate_vote_scope_id_accepts_expected_scopes() -> None:
    assert validate_vote_scope_id("bill:GR-0490a766") == "bill:GR-0490a766"
    assert validate_vote_scope_id("municipal:ATH_001") == "municipal:ATH_001"
    assert validate_vote_scope_id("regional:REG.006") == "regional:REG.006"


@pytest.mark.parametrize("value", ["", "bad", "bill:bad/slash", "bill:bad:colon", "x:GR-1"])
def test_validate_vote_scope_id_rejects_invalid_scopes(value: str) -> None:
    with pytest.raises(ValueError):
        validate_vote_scope_id(value)


@pytest.mark.asyncio
async def test_list_active_commitments_for_scope_returns_public_commitments_only() -> None:
    db = _FakeDb(_FakeResult(values=["123", 456]))

    commitments = await list_active_commitments_for_scope(db, vote_scope_id="bill:GR-0490a766")

    assert commitments == ["123", "456"]
    statement = str(db.executed[0])
    assert "zk_identity_commitments.commitment" in statement
    assert "identity_record_id" not in statement
    assert "tier_guard_hash" not in statement


def test_public_group_members_pad_singletons_with_public_dummy() -> None:
    members = public_group_members_for_root(["123"])

    assert members[0] == "123"
    assert len(members) == 2
    assert members[1].isdigit()
    assert members[1] != "123"


def test_public_group_members_leave_larger_groups_unchanged() -> None:
    assert public_group_members_for_root(["1", "2", "3"]) == ["1", "2", "3"]


@pytest.mark.asyncio
async def test_list_public_group_members_for_scope_uses_active_commitments_plus_padding() -> None:
    db = _FakeDb(_FakeResult(values=["123"]))

    members = await list_public_group_members_for_scope(db, vote_scope_id="bill:GR-0490a766")

    assert members[0] == "123"
    assert len(members) == 2
    statement = str(db.executed[0])
    assert "zk_identity_commitments.commitment" in statement
    assert "identity_record_id" not in statement
    assert "tier_guard_hash" not in statement


@pytest.mark.asyncio
async def test_list_active_commitments_for_scope_rejects_unsafe_limit() -> None:
    with pytest.raises(ValueError):
        await list_active_commitments_for_scope(_FakeDb(_FakeResult()), vote_scope_id="bill:GR-1", limit=0)

    with pytest.raises(ValueError):
        await list_active_commitments_for_scope(_FakeDb(_FakeResult()), vote_scope_id="bill:GR-1", limit=5001)


@pytest.mark.asyncio
async def test_count_active_commitments_for_scope_returns_count() -> None:
    db = _FakeDb(_FakeResult(scalar=2))

    count = await count_active_commitments_for_scope(db, vote_scope_id="bill:GR-0490a766")

    assert count == 2
    assert "count" in str(db.executed[0]).lower()


@pytest.mark.asyncio
async def test_build_active_group_root_for_scope_uses_public_commitments() -> None:
    db = _FakeDb(_FakeResult(values=["1", "2", "3"]))

    group = await build_active_group_root_for_scope(db, vote_scope_id="bill:GR-0490a766")

    assert group.root == poseidon2(poseidon2(1, 2), 3)
    assert group.depth == 2
    assert group.size == 3
    statement = str(db.executed[0])
    assert "zk_identity_commitments.commitment" in statement
    assert "identity_record_id" not in statement
    assert "tier_guard_hash" not in statement


@pytest.mark.asyncio
async def test_build_active_group_root_for_scope_pads_singleton_for_native_prover() -> None:
    db = _FakeDb(_FakeResult(values=["123"]))

    group = await build_active_group_root_for_scope(db, vote_scope_id="bill:GR-0490a766")
    padded = public_group_members_for_root(["123"])

    assert group.root == poseidon2(int(padded[0]), int(padded[1]))
    assert group.depth == 1
    assert group.size == 2
