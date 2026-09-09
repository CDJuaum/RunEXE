import struct
import zipfile
from io import BytesIO

import pytest

from runexe.analyzer import MAX_NAME_BYTES, _read_c_string, analyze_executable
from runexe.models import PESection
from runexe.packages import PackageError
from runexe.pe_utils import rva_range_to_file_offset, rva_to_file_offset

from .helpers import make_pe


@pytest.mark.parametrize("length", [1, 127, 128, 129, MAX_NAME_BYTES - 1])
def test_import_names_across_read_boundaries(length):
    raw = b"prefix" + b"A" * length + b"\0ignored"
    assert _read_c_string(BytesIO(raw), 6, len(raw)) == "A" * length


@pytest.mark.parametrize(
    ("raw", "size", "expected"),
    [
        (b"\0", 1, None),
        (b"unterminated", 12, None),
        (b"name\0", 4, None),
        (b"A" * MAX_NAME_BYTES + b"\0", MAX_NAME_BYTES + 1, None),
        (b"A\xff\0", 3, "A\ufffd"),
    ],
)
def test_import_names_keep_bounds_and_decoding(raw, size, expected):
    assert _read_c_string(BytesIO(raw), 0, size) == expected


def test_analyzes_minimal_pe_and_imports(tmp_path):
    path = make_pe(tmp_path / "sample.exe")

    result = analyze_executable(path)

    assert result.valid
    assert result.architecture == "x86"
    assert result.format == "PE32 (32-bit)"
    assert result.subsystem == "Windows Console"
    assert result.imports[0].name == "KERNEL32.dll"
    assert result.imports[0].functions == ["ExitProcess"]


def test_uses_first_thunk_when_original_thunk_is_absent(tmp_path):
    result = analyze_executable(make_pe(tmp_path / "bound.exe", original_first_thunk=False))

    assert result.valid
    assert result.imports[0].functions == ["ExitProcess"]


def test_rejects_pe_header_offset_outside_file(tmp_path):
    path = tmp_path / "bad.exe"
    raw = bytearray(64)
    raw[:2] = b"MZ"
    struct.pack_into("<I", raw, 0x3C, 0xFFFFFFF0)
    path.write_bytes(raw)

    result = analyze_executable(path)

    assert not result.valid
    assert "outside the file" in result.reason


def test_rejects_section_that_extends_past_eof(tmp_path):
    path = make_pe(tmp_path / "truncated.exe")
    raw = bytearray(path.read_bytes())
    section_offset = 0x80 + 24 + 224
    struct.pack_into("<I", raw, section_offset + 16, 0x1000)
    path.write_bytes(raw)

    result = analyze_executable(path)

    assert not result.valid
    assert "extends beyond end of file" in result.reason


def test_rva_does_not_map_zero_filled_virtual_tail():
    section = PESection(".data", 0x1000, 0x2000, 0x100, 0x400)

    assert rva_to_file_offset(0x2050, [section]) == 0x450
    assert rva_to_file_offset(0x2200, [section]) is None
    assert rva_range_to_file_offset(0x20F0, 0x10, [section]) == 0x4F0
    assert rva_range_to_file_offset(0x20F0, 0x11, [section]) is None


def test_directory_input_requires_exactly_one_executable(tmp_path):
    make_pe(tmp_path / "a.exe", with_import=False)
    make_pe(tmp_path / "b.EXE", with_import=False)

    try:
        analyze_executable(tmp_path)
    except ValueError as error:
        assert "Multiple executable files" in str(error)
        assert "a.exe" in str(error)
        assert "b.EXE" in str(error)
    else:
        raise AssertionError("Expected directory ambiguity to be rejected")


def test_analyzes_msix_manifest_and_declared_executable(tmp_path, monkeypatch):
    source = tmp_path / "source"
    (source / "PaintApp").mkdir(parents=True)
    executable = make_pe(source / "PaintApp" / "mspaint.exe")
    package = tmp_path / "Paint.msix"
    manifest = """
    <Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10">
      <Identity Name="Microsoft.Paint" Publisher="CN=Microsoft" Version="11.0.0.0" />
      <Properties><DisplayName>Paint</DisplayName></Properties>
      <Applications>
        <Application Id="Paint" Executable="PaintApp\\mspaint.exe" />
      </Applications>
    </Package>
    """
    with zipfile.ZipFile(package, "w") as archive:
        archive.write(executable, "PaintApp/mspaint.exe")
        archive.writestr("AppxManifest.xml", manifest)

    monkeypatch.setattr("runexe.packages.PACKAGE_CACHE_DIR", tmp_path / "cache")
    result = analyze_executable(package)

    assert result.valid
    assert result.path.name == "mspaint.exe"
    assert result.package.identity_name == "Microsoft.Paint"
    assert result.package.display_name == "Paint"
    assert result.package.application_id == "Paint"


def test_rejects_path_traversal_in_package_archive(tmp_path, monkeypatch):
    package = tmp_path / "unsafe.msix"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("../outside.exe", b"not safe")

    monkeypatch.setattr("runexe.packages.PACKAGE_CACHE_DIR", tmp_path / "cache")
    try:
        analyze_executable(package)
    except PackageError as error:
        assert "Unsafe package path" in str(error)
    else:
        raise AssertionError("Expected unsafe package path to be rejected")
