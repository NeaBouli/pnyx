"""repo_paths: anchored lookup, required files fail, docs skip only in the image (T-629)."""
import pytest

from tests.repo_paths import find_repo_path, in_api_image, repo_path_or_skip_in_image, require_repo_path


def _checkout(tmp_path, with_crypto=True, with_docs=True):
    api = tmp_path / "repo" / "apps" / "api"
    api.mkdir(parents=True)
    if with_crypto:
        (tmp_path / "repo" / "packages" / "crypto").mkdir(parents=True)
        (tmp_path / "repo" / "packages" / "crypto" / "keypair.py").write_text("")
    if with_docs:
        (tmp_path / "repo" / "docs").mkdir()
        (tmp_path / "repo" / "docs" / "community.html").write_text("")
    return api


def _image(tmp_path, with_crypto=True):
    root = tmp_path / "image"
    api = root / "app"
    api.mkdir(parents=True)
    if with_crypto:
        (root / "packages" / "crypto").mkdir(parents=True)
        (root / "packages" / "crypto" / "keypair.py").write_text("")
    return api


def test_layout_detection(tmp_path):
    assert in_api_image(_checkout(tmp_path)) is False
    assert in_api_image(_image(tmp_path)) is True


def test_finds_crypto_in_both_layouts(tmp_path):
    checkout = _checkout(tmp_path)
    image = _image(tmp_path)
    assert require_repo_path("packages/crypto/keypair.py", checkout) == checkout.parent.parent / "packages/crypto/keypair.py"
    assert require_repo_path("packages/crypto/keypair.py", image) == image.parent / "packages/crypto/keypair.py"


@pytest.mark.parametrize("layout", ["checkout", "image"])
def test_missing_required_crypto_fails_not_skips(tmp_path, layout):
    api = _checkout(tmp_path, with_crypto=False) if layout == "checkout" else _image(tmp_path, with_crypto=False)
    with pytest.raises(FileNotFoundError):
        require_repo_path("packages/crypto/keypair.py", api)


def test_docs_missing_in_image_skips_with_reason(tmp_path):
    with pytest.raises(pytest.skip.Exception, match="not part of the API image"):
        repo_path_or_skip_in_image("docs/community.html", _image(tmp_path))


def test_docs_missing_in_checkout_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        repo_path_or_skip_in_image("docs/community.html", _checkout(tmp_path, with_docs=False))


def test_lookup_is_anchored_not_an_open_walk(tmp_path):
    # A crypto copy further up the tree must not be picked up.
    (tmp_path / "packages" / "crypto").mkdir(parents=True)
    (tmp_path / "packages" / "crypto" / "keypair.py").write_text("")
    api = _checkout(tmp_path, with_crypto=False)
    assert find_repo_path("packages/crypto/keypair.py", api) is None
