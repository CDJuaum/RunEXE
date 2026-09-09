"""Defensive, dependency-free parsing of Windows PE executables."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import BinaryIO

from .constants import IMAGE_DIRECTORY_ENTRY_IMPORT, IMAGE_DIRECTORY_ENTRY_RESOURCE, SUBSYSTEM_TYPES
from .models import ExecutableInfo, PEDataDirectory, PEImport, PESection
from .packages import resolve_input
from .pe_utils import rva_to_file_offset
from .resources import extract_manifest, extract_version_info

MACHINE_TYPES = {0x014C: "x86", 0x8664: "x86_64", 0xAA64: "ARM64"}
PE_FORMATS = {0x10B: "PE32 (32-bit)", 0x20B: "PE32+ (64-bit)"}

MAX_SECTIONS = 96
MAX_IMPORT_DESCRIPTORS = 4096
MAX_IMPORT_FUNCTIONS = 65_536
MAX_NAME_BYTES = 4096
MAX_DATA_DIRECTORIES = 16


def _section_file_end(rva: int, sections: list[PESection]) -> int | None:
    for section in sections:
        if section.virtual_address <= rva < section.virtual_address + section.raw_size:
            return section.raw_offset + section.raw_size
    return None


def _invalid(path: Path, reason: str) -> ExecutableInfo:
    return ExecutableInfo(path=path, valid=False, reason=reason)


def _read_c_string(file: BinaryIO, offset: int, file_size: int) -> str | None:
    if offset < 0 or offset >= file_size:
        return None
    file.seek(offset)
    raw = bytearray()
    remaining = min(MAX_NAME_BYTES, file_size - offset)
    while remaining:
        chunk = file.read(min(128, remaining))
        if not chunk:
            break
        terminator = chunk.find(b"\x00")
        if terminator >= 0:
            raw.extend(chunk[:terminator])
            return raw.decode("ascii", errors="replace") if raw else None
        raw.extend(chunk)
        remaining -= len(chunk)
    return None


def parse_import_functions(
    file: BinaryIO,
    thunk_rva: int,
    sections: list[PESection],
    pe_format: str,
    file_size: int | None = None,
) -> list[str]:
    """Parse imported names from an Import Lookup Table safely."""

    thunk_offset = rva_to_file_offset(thunk_rva, sections)
    if thunk_offset is None:
        return []
    if file_size is None:
        current = file.tell()
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(current)

    if pe_format == "PE32+ (64-bit)":
        thunk_size, unpack_format, ordinal_flag = 8, "<Q", 1 << 63
    else:
        thunk_size, unpack_format, ordinal_flag = 4, "<I", 1 << 31

    functions: list[str] = []
    section_end = _section_file_end(thunk_rva, sections) or file_size
    max_entries = min(
        MAX_IMPORT_FUNCTIONS,
        (min(file_size, section_end) - thunk_offset) // thunk_size,
    )
    for index in range(max_entries):
        file.seek(thunk_offset + index * thunk_size)
        raw = file.read(thunk_size)
        if len(raw) != thunk_size:
            break
        thunk_value = struct.unpack(unpack_format, raw)[0]
        if thunk_value == 0:
            break
        if thunk_value & ordinal_flag:
            functions.append(f"Ordinal #{thunk_value & (ordinal_flag - 1)}")
            continue
        name_offset = rva_to_file_offset(thunk_value, sections)
        if name_offset is None or name_offset + 2 > file_size:
            continue
        name = _read_c_string(file, name_offset + 2, file_size)
        if name:
            functions.append(name)
    return functions


def parse_imports(
    file: BinaryIO,
    import_rva: int,
    sections: list[PESection],
    pe_format: str,
    import_size: int | None = None,
    file_size: int | None = None,
) -> list[PEImport]:
    """Parse the bounded PE import directory and return imported DLLs."""

    import_offset = rva_to_file_offset(import_rva, sections)
    if import_offset is None:
        return []
    if file_size is None:
        current = file.tell()
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(current)

    section_end = _section_file_end(import_rva, sections) or file_size
    available = max(0, min(file_size, section_end) - import_offset)
    declared = import_size if import_size and import_size > 0 else available
    descriptor_count = min(MAX_IMPORT_DESCRIPTORS, declared // 20, available // 20)
    imports: list[PEImport] = []
    for index in range(descriptor_count):
        file.seek(import_offset + index * 20)
        descriptor = file.read(20)
        if len(descriptor) != 20:
            break
        original_thunk, timestamp, forwarder, name_rva, first_thunk = struct.unpack(
            "<IIIII", descriptor
        )
        if not any((original_thunk, timestamp, forwarder, name_rva, first_thunk)):
            break
        name_offset = rva_to_file_offset(name_rva, sections)
        if name_offset is None:
            continue
        name = _read_c_string(file, name_offset, file_size)
        if not name:
            continue
        lookup_thunk = original_thunk or first_thunk
        functions = (
            parse_import_functions(file, lookup_thunk, sections, pe_format, file_size)
            if lookup_thunk
            else []
        )
        imports.append(PEImport(name=name, functions=functions))
    return imports


def parse_sections(
    file: BinaryIO,
    section_table_start: int,
    number_of_sections: int,
    file_size: int | None = None,
) -> list[PESection]:
    if number_of_sections <= 0 or number_of_sections > MAX_SECTIONS:
        raise ValueError("Unrealistic number of sections in PE header")
    if file_size is not None and section_table_start + number_of_sections * 40 > file_size:
        raise ValueError("Incomplete PE section table")

    file.seek(section_table_start)
    sections: list[PESection] = []
    for _ in range(number_of_sections):
        header = file.read(40)
        if len(header) != 40:
            raise ValueError("Incomplete PE section header")
        name = header[:8].rstrip(b"\x00").decode("ascii", errors="replace")
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack("<IIII", header[8:24])
        if raw_size and file_size is not None:
            if raw_offset >= file_size or raw_size > file_size - raw_offset:
                raise ValueError(f"Section {name or '<unnamed>'} extends beyond end of file")
        sections.append(PESection(name, virtual_size, virtual_address, raw_size, raw_offset))
    return sections


def parse_data_directories(
    file: BinaryIO,
    data_directory_start: int,
    count: int = MAX_DATA_DIRECTORIES,
) -> list[PEDataDirectory]:
    """Read up to the standard 16 directories and pad absent entries."""

    count = max(0, min(count, MAX_DATA_DIRECTORIES))
    file.seek(data_directory_start)
    directories: list[PEDataDirectory] = []
    for _ in range(count):
        raw = file.read(8)
        if len(raw) != 8:
            raise ValueError("Incomplete PE data directory")
        directories.append(PEDataDirectory(*struct.unpack("<II", raw)))
    directories.extend(
        PEDataDirectory(0, 0) for _ in range(MAX_DATA_DIRECTORIES - len(directories))
    )
    return directories


def _select_executable(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_dir():
        if not path.is_file():
            raise ValueError(f"Not a regular file: {path}")
        return path

    executables = sorted(
        (item for item in path.iterdir() if item.is_file() and item.suffix.lower() == ".exe"),
        key=lambda item: item.name.lower(),
    )
    if not executables:
        raise ValueError(f"No executable files found in directory: {path}")
    if len(executables) > 1:
        names = "\n".join(f"  - {item.name}" for item in executables)
        raise ValueError(f"Multiple executable files found in directory:\n{names}")
    return executables[0]


def analyze_executable(file_path: str | Path) -> ExecutableInfo:
    """Analyze a PE executable or materialize an AppX/MSIX package for inspection."""

    input_path = Path(file_path)
    path, package = resolve_input(input_path)
    if package is None:
        path = _select_executable(path)
    file_size = path.stat().st_size
    if file_size < 64:
        return _invalid(path, "File is too small to contain a valid DOS header")

    with path.open("rb") as file:
        if file.read(2) != b"MZ":
            return _invalid(path, "Not a valid Windows executable (missing MZ signature)")
        file.seek(0x3C)
        raw = file.read(4)
        if len(raw) != 4:
            return _invalid(path, "File is too small to contain a valid PE header")
        pe_offset = struct.unpack("<I", raw)[0]
        if pe_offset > file_size - 24:
            return _invalid(path, "PE header offset is outside the file")

        file.seek(pe_offset)
        if file.read(4) != b"PE\x00\x00":
            return _invalid(path, "Invalid PE signature")
        coff = file.read(20)
        if len(coff) != 20:
            return _invalid(path, "Incomplete COFF header")
        machine, section_count, _timestamp, _symbols, _symbol_count, optional_size, _flags = (
            struct.unpack("<HHIIIHH", coff)
        )
        architecture = MACHINE_TYPES.get(machine, f"Unknown (0x{machine:04X})")

        optional_start = file.tell()
        if optional_size < 2 or optional_start + optional_size > file_size:
            return _invalid(path, "Incomplete PE optional header")
        optional = file.read(optional_size)
        magic = struct.unpack_from("<H", optional)[0]
        pe_format = PE_FORMATS.get(magic)
        if pe_format is None:
            return _invalid(path, f"Unknown PE optional header format (0x{magic:04X})")

        directory_offset = 96 if magic == 0x10B else 112
        count_offset = 92 if magic == 0x10B else 108
        if optional_size < count_offset + 4:
            return _invalid(path, "Optional header is too small for its PE format")
        subsystem = None
        if optional_size >= 70:
            subsystem_value = struct.unpack_from("<H", optional, 68)[0]
            subsystem = SUBSYSTEM_TYPES.get(subsystem_value, f"Unknown (0x{subsystem_value:04X})")

        declared_count = struct.unpack_from("<I", optional, count_offset)[0]
        available_count = max(0, (optional_size - directory_offset) // 8)
        directory_count = min(declared_count, available_count, MAX_DATA_DIRECTORIES)
        try:
            data_directories = parse_data_directories(
                file, optional_start + directory_offset, directory_count
            )
            sections = parse_sections(
                file, optional_start + optional_size, section_count, file_size
            )
        except ValueError as error:
            return _invalid(path, str(error))

        imports: list[PEImport] = []
        import_directory = data_directories[IMAGE_DIRECTORY_ENTRY_IMPORT]
        if import_directory.virtual_address and import_directory.size:
            imports = parse_imports(
                file,
                import_directory.virtual_address,
                sections,
                pe_format,
                import_directory.size,
                file_size,
            )

        manifest = None
        version_info = None
        resource_directory = data_directories[IMAGE_DIRECTORY_ENTRY_RESOURCE]
        if resource_directory.virtual_address and resource_directory.size:
            manifest = extract_manifest(
                file,
                sections,
                resource_directory.virtual_address,
                resource_directory.size,
                file_size,
            )
            version_info = extract_version_info(
                file,
                sections,
                resource_directory.virtual_address,
                resource_directory.size,
                file_size,
            )

    return ExecutableInfo(
        path=path,
        valid=True,
        format=pe_format,
        architecture=architecture,
        subsystem=subsystem,
        sections=sections,
        data_directories=data_directories,
        imports=imports,
        manifest=manifest,
        version_info=version_info,
        package=package,
    )
