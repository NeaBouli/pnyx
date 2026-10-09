"""Locate repository files from tests both in a checkout and in the API image.

In a checkout the API lives at <repo>/apps/api; in the production image it is
/app with packages/crypto copied to /packages/crypto (apps/api/Dockerfile.prod).
Walking up all ancestors finds the same relative path in both layouts instead of
assuming a fixed depth.
"""
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parent


def find_repo_path(relative: str) -> Path | None:
    for base in _TESTS_DIR.parents:
        candidate = base / relative
        if candidate.exists():
            return candidate
    return None


def require_repo_path(relative: str, *, module_level: bool = False) -> Path:
    found = find_repo_path(relative)
    if found is None:
        pytest.skip(
            f"{relative} is not part of this layout (e.g. the API image has no repo checkout)",
            allow_module_level=module_level,
        )
    return found
