from clyro.updater import _body_checksum_for_installer, _normalize_sha256, _parse_checksum_text


def test_normalize_sha256_extracts_digest():
    digest = "a" * 64
    assert _normalize_sha256(f"sha256:{digest}") == digest


def test_parse_checksum_text_finds_named_installer():
    digest = "b" * 64
    text = f"{digest} *ClyroSetup.exe\n"

    assert _parse_checksum_text(text, "ClyroSetup.exe") == digest


def test_body_checksum_for_installer_prefers_named_digest():
    digest = "c" * 64
    body = f"Installer ClyroSetup.exe SHA-256: {digest}"

    assert _body_checksum_for_installer(body, "ClyroSetup.exe") == digest


def test_body_checksum_for_installer_returns_none_without_digest():
    assert _body_checksum_for_installer("Release notes only.", "ClyroSetup.exe") is None


def test_body_checksum_for_installer_ignores_unscoped_digest():
    digest = "d" * 64
    body = f"Other asset checksum: {digest}"

    assert _body_checksum_for_installer(body, "ClyroSetup.exe") is None
