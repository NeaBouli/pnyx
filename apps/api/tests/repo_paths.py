"""Locate repository files from tests in a checkout and in the API image.

Checkout: the API lives at <repo>/apps/api, so repo files are under <repo>.
API image (apps/api/Dockerfile.prod): the API is /app and packages/crypto is
copied to /packages/crypto; docs/ is intentionally not part of the image.

The lookup is anchored to exactly these two bases (no open-ended walk up the
tree), required files fail loudly when missing, and only explicitly optional
files may be skipped, and only inside the API image.
"""
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]


def in_api_image(api_root: Path = API_ROOT) -> bool:
    """True in the image layout (/app), False in a checkout (<repo>/apps/api)."""
    return api_root.parent.name != "apps"


def _base(api_root: Path) -> Path:
    # Checkout: <repo>/apps/api -> <repo>; image: /app -> /.
    return api_root.parent if in_api_image(api_root) else api_root.parent.parent


def find_repo_path(relative: str, api_root: Path = API_ROOT) -> Path | None:
    candidate = _base(api_root) / relative
    return candidate if candidate.exists() else None


def require_repo_path(relative: str, api_root: Path = API_ROOT) -> Path:
    """A file the tests cannot run without: missing means failure, never a skip."""
    found = find_repo_path(relative, api_root)
    if found is None:
        raise FileNotFoundError(f"required repository file missing: {relative}")
    return found


def repo_path_or_skip_in_image(relative: str, api_root: Path = API_ROOT) -> Path:
    """For files that are not shipped in the API image (e.g. docs/): skip there,
    fail in a checkout where they must exist."""
    found = find_repo_path(relative, api_root)
    if found is not None:
        return found
    if in_api_image(api_root):
        pytest.skip(f"{relative} is not part of the API image")
    raise FileNotFoundError(f"required repository file missing: {relative}")
