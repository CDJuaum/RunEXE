import json

import pytest

from runexe.library import ApplicationLibrary, LaunchPreset


def test_library_round_trips_per_application_launch_preset(tmp_path):
    source = tmp_path / "PaintDotNet.exe"
    source.touch()
    library = ApplicationLibrary(tmp_path / "state" / "applications.json")
    preset = LaunchPreset(
        backend="wine",
        windows_version="11",
        dependencies="skip",
        arguments="--portable",
    )

    library.remember_analysis(
        source,
        display_name="Paint.NET",
        architecture="x86_64",
        file_format="PE32+ (64-bit)",
        preset=preset,
    )
    library.record_launch(source, preset)
    library.record_exit(source, 0)

    record = library.get(source)
    assert record is not None
    assert record.display_name == "Paint.NET"
    assert record.preset == preset
    assert record.launch_count == 1
    assert record.last_exit_code == 0
    assert library.path.stat().st_size > 0
    assert list(library.path.parent.glob(".*.tmp")) == []


def test_library_recovers_from_corrupt_or_oversized_state(tmp_path):
    state = tmp_path / "applications.json"
    state.write_text("{not json", encoding="utf-8")
    library = ApplicationLibrary(state)

    assert library.records() == []

    state.write_bytes(b"\xff\xfe\x80")
    assert library.records() == []

    state.write_text("x" * (2 * 1024 * 1024 + 1), encoding="utf-8")
    assert library.records() == []


@pytest.mark.parametrize("invalid", [[], {}, ["wine"], 42, True])
def test_malformed_preferences_fall_back_without_losing_record(tmp_path, invalid):
    state = tmp_path / "applications.json"
    state.write_text(
        json.dumps(
            {
                "applications": [
                    {
                        "path": str(tmp_path / "app.exe"),
                        "preset": dict.fromkeys(
                            ("backend", "windows_version", "proton_tuning", "dependencies"), invalid
                        ),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    records = ApplicationLibrary(state).records()
    assert len(records) == 1
    assert records[0].preset == LaunchPreset()


def test_library_prunes_missing_files_without_touching_existing_sources(tmp_path):
    library = ApplicationLibrary(tmp_path / "applications.json")
    existing = tmp_path / "existing.exe"
    missing = tmp_path / "missing.exe"
    existing.touch()
    for source in (existing, missing):
        library.remember_analysis(
            source,
            display_name=source.stem,
            architecture="x86_64",
            file_format="PE32+",
        )

    assert library.prune_missing() == 1
    assert [record.path for record in library.records()] == [str(existing.resolve())]


def test_library_enforces_entry_limit_and_private_schema(tmp_path):
    library = ApplicationLibrary(tmp_path / "applications.json", max_entries=2)
    for index in range(3):
        source = tmp_path / f"app-{index}.exe"
        source.touch()
        library.remember_analysis(
            source,
            display_name=source.stem,
            architecture="x86",
            file_format="PE32",
        )

    payload = json.loads(library.path.read_text(encoding="utf-8"))
    assert payload["schema"] == 1
    assert len(payload["applications"]) == 2
