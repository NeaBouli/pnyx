"""Tests für MOD-02 VAA Matching-Algorithmus"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from routers.vaa import calculate_match


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
