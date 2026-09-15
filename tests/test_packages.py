import zipfile

from runexe import packages

MIB = 1024 * 1024
GIB = 1024 * MIB


def test_package_byte_limit_scales_past_legacy_512_mib_limit():
    limit = packages._package_byte_limit(600 * MIB)

    assert limit == 600 * MIB * packages.PACKAGE_EXPANSION_FACTOR
    assert limit > 512 * MIB


def test_package_byte_limit_keeps_absolute_ceiling():
    assert packages._package_byte_limit(10 * GIB) == packages.MAX_PACKAGE_BYTES


def test_extract_archive_automatically_allows_more_than_baseline(tmp_path, monkeypatch):
    archive = tmp_path / "large.msix"
    payload = b"x" * 256
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("payload.bin", payload)

    destination = tmp_path / "extracted"
    destination.mkdir()
    monkeypatch.setattr(packages, "BASE_PACKAGE_BYTES", 64)
    monkeypatch.setattr(packages, "MAX_PACKAGE_BYTES", 4096)
    monkeypatch.setattr(packages, "PACKAGE_EXPANSION_FACTOR", 16)
    monkeypatch.setattr(packages, "PACKAGE_DISK_RESERVE_BYTES", 0)

    packages._extract_archive(archive, destination)

    assert (destination / "payload.bin").read_bytes() == payload
