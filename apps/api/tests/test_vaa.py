"""Tests für MOD-02 VAA Matching-Algorithmus"""
import pytest
import sys, os
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from routers.vaa import calculate_match, get_questions, get_statements


class _FakeScalars:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _FakeResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _FakeScalars(self._values)


class _FakeDb:
    def __init__(self, values):
        self.values = values

    async def execute(self, _statement):
        return _FakeResult(self.values)


class TestMatchingAlgorithm:
    def test_perfect_match(self):
        user    = {1: 1, 2: -1, 3: 1}
        party   = {1: 1, 2: -1, 3: 1}
        pct, cnt = calculate_match(user, party)
        assert pct == 100.0
        assert cnt == 3

    def test_zero_match(self):
        user    = {1: 1, 2: 1,  3: 1}
        party   = {1: -1, 2: -1, 3: -1}
        pct, cnt = calculate_match(user, party)
        assert pct == 0.0
        assert cnt == 3

    def test_neutral_ignored(self):
        user    = {1: 1, 2: 0, 3: 1}   # 2 ist neutral
        party   = {1: 1, 2: -1, 3: 1}
        pct, cnt = calculate_match(user, party)
        assert pct == 100.0
        assert cnt == 2

    def test_partial_match(self):
        user    = {1: 1, 2: 1, 3: 1, 4: 1}
        party   = {1: 1, 2: 1, 3: -1, 4: -1}
        pct, cnt = calculate_match(user, party)
        assert pct == 50.0
        assert cnt == 4

    def test_empty_answers(self):
        pct, cnt = calculate_match({}, {1: 1})
        assert pct == 0.0
        assert cnt == 0

    def test_all_neutral(self):
        user    = {1: 0, 2: 0, 3: 0}
        party   = {1: 1, 2: -1, 3: 1}
        pct, cnt = calculate_match(user, party)
        assert pct == 0.0
        assert cnt == 0


class TestVaaQuestionsAlias:
    @pytest.mark.asyncio
    async def test_questions_alias_returns_same_items_as_statements(self):
        statements = [
            SimpleNamespace(id=2, display_order=2),
            SimpleNamespace(id=1, display_order=1),
        ]

        statement_payload = await get_statements(limit=0, db=_FakeDb(statements))
        question_payload = await get_questions(limit=0, db=_FakeDb(statements))

        assert question_payload == statement_payload
