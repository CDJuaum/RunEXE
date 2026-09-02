import io
import tarfile
from datetime import datetime, timezone

import pytest

from runexe.backups import (
    BackupError,
    BackupInfo,
    create_environment_backup,
    discover_backups,
    remove_backup,
    restore_backup,
)
from runexe.environments import EnvironmentInfo


def environment_info(path):
    return EnvironmentInfo(
        identifier=f"wine:{path.name}",
        backend="wine",
        path=path,
        application="Example",
        source="/downloads/example.exe",
        architecture="x86_64",
        runtime="Wine 11",
        runtime_path="/usr/bin/wine",
        windows_version="11",
        dxvk_available=False,
        dxvk_source="Wine prefix",
        dxvk_components=(),
        size_bytes=4,
        modified_at=datetime.now(timezone.utc).isoformat(),
        ready=True,
    )


def test_backup_round_trip_never_overwrites_live_environment(tmp_path):
    roots = (tmp_path / "prefixes", tmp_path / "proton")
    prefix = roots[0] / "example-123"
    (prefix / "drive_c").mkdir(parents=True)
    (prefix / "drive_c" / "settings.ini").write_text("safe=true\n", encoding="utf-8")
    info = environment_info(prefix)

    backup = create_environment_backup(info, destination=tmp_path / "backups", roots=roots)
    assert backup.archive.is_file()
    assert discover_backups(tmp_path / "backups") == [backup]

    with pytest.raises(BackupError, match="overwrite"):
        restore_backup(backup, roots=roots)

    prefix.rename(tmp_path / "removed-prefix")
    restored = restore_backup(backup, roots=roots)
    assert (restored / "drive_c" / "settings.ini").read_text(encoding="utf-8") == "safe=true\n"

    remove_backup(backup)
    assert discover_backups(tmp_path / "backups") == []


def test_restore_rejects_archive_path_traversal(tmp_path):
    roots = (tmp_path / "prefixes", tmp_path / "proton")
    archive_path = tmp_path / "malicious.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        root = tarfile.TarInfo("environment")
        root.type = tarfile.DIRTYPE
        archive.addfile(root)
        payload = b"nope"
        member = tarfile.TarInfo("environment/../../outside.txt")
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))
    backup = BackupInfo(
        identifier="malicious",
        environment_identifier="wine:example",
        backend="wine",
        environment_name="example",
        application="Example",
        source=None,
        created_at="2026-08-31T00:00:00+00:00",
        archive=archive_path,
        size_bytes=archive_path.stat().st_size,
    )

    with pytest.raises(BackupError, match="Unsafe backup path"):
        restore_backup(backup, roots=roots)

    assert not (tmp_path / "outside.txt").exists()


def test_restore_rejects_unsafe_backup_identifier(tmp_path):
    roots = (tmp_path / "prefixes", tmp_path / "proton")
    archive_path = tmp_path / "valid.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        root = tarfile.TarInfo("environment")
        root.type = tarfile.DIRTYPE
        archive.addfile(root)
    backup = BackupInfo(
        identifier="../../escape",
        environment_identifier="wine:example",
        backend="wine",
        environment_name="example",
        application="Example",
        source=None,
        created_at="2026-08-31T00:00:00+00:00",
        archive=archive_path,
        size_bytes=archive_path.stat().st_size,
    )

    with pytest.raises(BackupError, match="unsafe identifier"):
        restore_backup(backup, roots=roots)

    assert not (tmp_path / "escape").exists()


def test_backup_rejects_custom_environment_outside_managed_roots(tmp_path):
    roots = (tmp_path / "prefixes", tmp_path / "proton")
    custom = tmp_path / "custom-prefix"
    (custom / "drive_c").mkdir(parents=True)

    with pytest.raises(BackupError, match="direct children"):
        create_environment_backup(
            environment_info(custom),
            destination=tmp_path / "backups",
            roots=roots,
        )


def test_backup_preserves_wine_drive_mapping_symlinks(tmp_path):
    roots = (tmp_path / "prefixes", tmp_path / "proton")
    prefix = roots[0] / "example-links"
    dosdevices = prefix / "dosdevices"
    dosdevices.mkdir(parents=True)
    try:
        (dosdevices / "z:").symlink_to("/", target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is not permitted")
    info = environment_info(prefix)

    backup = create_environment_backup(info, destination=tmp_path / "backups", roots=roots)
    prefix.rename(tmp_path / "removed-prefix")
    restored = restore_backup(backup, roots=roots)

    mapping = restored / "dosdevices" / "z:"
    assert mapping.is_symlink()
    assert mapping.readlink().as_posix() == "/"
