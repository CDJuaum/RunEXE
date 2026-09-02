"""Executable dependency detection.

This module identifies Windows runtimes and components required or
strongly suggested by an executable's imports and metadata.

Dependency detection is intentionally separate from Winetricks
installation. Detecting a dependency does not necessarily mean that
RunEXE should install a Winetricks verb.

For example, importing d3d11.dll indicates Direct3D 11 usage, but Wine
already provides d3d11.dll, so there is no reason to install DXVK
solely because the DLL is imported.

The Winetricks mapping is therefore optional and only used for
dependencies where installing a known runtime is appropriate.
"""

import re

from .models import Dependency, PEImport

# DLL -> dependency information.
#
# Keep this list conservative. A DLL should only be added when its
# presence is a reliable indicator of the corresponding runtime or
# component.
DLL_DEPENDENCIES: dict[str, Dependency] = {
    # ---------------------------------------------------------
    # Microsoft Visual C++ Redistributables
    # ---------------------------------------------------------
    "msvcp140.dll": Dependency(
        name="Microsoft Visual C++ 2015-2022 Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2022",
    ),
    "msvcp140_1.dll": Dependency(
        name="Microsoft Visual C++ 2015-2022 Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2022",
    ),
    "msvcp140_2.dll": Dependency(
        name="Microsoft Visual C++ 2015-2022 Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2022",
    ),
    "msvcp140_atomic_wait.dll": Dependency(
        name="Microsoft Visual C++ 2015-2022 Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2022",
    ),
    "msvcp140_codecvt_ids.dll": Dependency(
        name="Microsoft Visual C++ 2015-2022 Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2022",
    ),
    "vcruntime140.dll": Dependency(
        name="Microsoft Visual C++ 2015-2022 Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2022",
    ),
    "vcruntime140_1.dll": Dependency(
        name="Microsoft Visual C++ 2015-2022 Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2022",
    ),
    "vcruntime140_2.dll": Dependency(
        name="Microsoft Visual C++ 2015-2022 Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2022",
    ),
    "vcruntime140_threads.dll": Dependency(
        name="Microsoft Visual C++ 2015-2022 Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2022",
    ),
    "vccorlib140.dll": Dependency(
        name="Microsoft Visual C++ 2015-2022 Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2022",
    ),
    "vcomp140.dll": Dependency(
        name="Microsoft Visual C++ 2015-2022 Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2022",
    ),
    "concrt140.dll": Dependency(
        name="Microsoft Visual C++ 2015-2022 Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2022",
    ),
    "mfc140.dll": Dependency(
        name="Microsoft Visual C++ 2015-2022 Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2022",
    ),
    "mfc140u.dll": Dependency(
        name="Microsoft Visual C++ 2015-2022 Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2022",
    ),
    "mfcm140.dll": Dependency(
        name="Microsoft Visual C++ 2015-2022 Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2022",
    ),
    "mfcm140u.dll": Dependency(
        name="Microsoft Visual C++ 2015-2022 Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2022",
    ),
    "msvcp120.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2013",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2013",
    ),
    "msvcr120.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2013",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2013",
    ),
    "mfc120.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2013",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2013",
    ),
    "mfc120u.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2013",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2013",
    ),
    "msvcp110.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2012",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2012",
    ),
    "msvcr110.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2012",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2012",
    ),
    "mfc110.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2012",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2012",
    ),
    "mfc110u.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2012",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2012",
    ),
    "msvcp100.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2010",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2010",
    ),
    "msvcr100.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2010",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2010",
    ),
    "mfc100.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2010",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2010",
    ),
    "mfc100u.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2010",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2010",
    ),
    "msvcp90.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2008",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2008",
    ),
    "msvcr90.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2008",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2008",
    ),
    "mfc90.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2008",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2008",
    ),
    "mfc90u.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2008",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2008",
    ),
    "msvcr80.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2005",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2005",
    ),
    "mfc80.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2005",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2005",
    ),
    "mfc80u.dll": Dependency(
        name="Microsoft Visual C++ Runtime 2005",
        category="runtime",
        confidence="high",
        winetricks_verb="vcrun2005",
    ),
    # ---------------------------------------------------------
    # Universal C Runtime
    # ---------------------------------------------------------
    "ucrtbase.dll": Dependency(
        name="Universal C Runtime",
        category="runtime",
        confidence="high",
        winetricks_verb="ucrtbase2019",
    ),
    "webview2loader.dll": Dependency(
        name="Microsoft Edge WebView2 Runtime",
        category="runtime",
        confidence="high",
    ),
    # ---------------------------------------------------------
    # Direct3D
    # ---------------------------------------------------------
    "d3dx9_40.dll": Dependency(
        name="Direct3D 9 Extensions",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dx9",
    ),
    "d3dx9_41.dll": Dependency(
        name="Direct3D 9 Extensions",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dx9",
    ),
    "d3dx9_42.dll": Dependency(
        name="Direct3D 9 Extensions",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dx9",
    ),
    "d3dx9_43.dll": Dependency(
        name="Direct3D 9 Extensions",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dx9",
    ),
    "d3dx10_33.dll": Dependency(
        name="Direct3D 10 Extensions",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dx10",
    ),
    "d3dx10_34.dll": Dependency(
        name="Direct3D 10 Extensions",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dx10",
    ),
    "d3dx10_35.dll": Dependency(
        name="Direct3D 10 Extensions",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dx10",
    ),
    "d3dx10_36.dll": Dependency(
        name="Direct3D 10 Extensions",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dx10",
    ),
    "d3dx10_37.dll": Dependency(
        name="Direct3D 10 Extensions",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dx10",
    ),
    "d3dx10_38.dll": Dependency(
        name="Direct3D 10 Extensions",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dx10",
    ),
    "d3dx10_39.dll": Dependency(
        name="Direct3D 10 Extensions",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dx10",
    ),
    "d3dx10_40.dll": Dependency(
        name="Direct3D 10 Extensions",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dx10",
    ),
    "d3dx10_41.dll": Dependency(
        name="Direct3D 10 Extensions",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dx10",
    ),
    "d3dx10_42.dll": Dependency(
        name="Direct3D 10 Extensions",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dx10",
    ),
    "d3dx10_43.dll": Dependency(
        name="Direct3D 10 Extensions",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dx10",
    ),
    "d3dcompiler_43.dll": Dependency(
        name="Direct3D Shader Compiler",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dcompiler_43",
    ),
    "d3dcompiler_47.dll": Dependency(
        name="Direct3D Shader Compiler",
        category="graphics",
        confidence="high",
        winetricks_verb="d3dcompiler_47",
    ),
    # These indicate Direct3D usage but do not require a Winetricks
    # installation by themselves. DXVK/VKD3D selection belongs to
    # compatibility/configuration logic.
    "d3d9.dll": Dependency(
        name="Direct3D 9",
        category="graphics",
        confidence="high",
    ),
    "d3d8.dll": Dependency(
        name="Direct3D 8",
        category="graphics",
        confidence="high",
    ),
    "d3d10.dll": Dependency(
        name="Direct3D 10",
        category="graphics",
        confidence="high",
    ),
    "d3d10_1.dll": Dependency(
        name="Direct3D 10.1",
        category="graphics",
        confidence="high",
    ),
    "d3d10core.dll": Dependency(
        name="Direct3D 10",
        category="graphics",
        confidence="high",
    ),
    "d3d11.dll": Dependency(
        name="Direct3D 11",
        category="graphics",
        confidence="high",
    ),
    "d3d12.dll": Dependency(
        name="Direct3D 12",
        category="graphics",
        confidence="high",
    ),
    "d3d12core.dll": Dependency(
        name="Direct3D 12",
        category="graphics",
        confidence="high",
    ),
    "dxgi.dll": Dependency(
        name="DirectX Graphics Infrastructure",
        category="graphics",
        confidence="high",
    ),
    "ddraw.dll": Dependency(
        name="DirectDraw",
        category="graphics",
        confidence="high",
    ),
    "d2d1.dll": Dependency(
        name="Direct2D",
        category="graphics",
        confidence="high",
    ),
    "dwrite.dll": Dependency(
        name="DirectWrite",
        category="graphics",
        confidence="high",
    ),
    "vulkan-1.dll": Dependency(
        name="Vulkan",
        category="graphics",
        confidence="high",
    ),
    "opengl32.dll": Dependency(
        name="OpenGL",
        category="graphics",
        confidence="high",
    ),
    # ---------------------------------------------------------
    # Input
    # ---------------------------------------------------------
    "xinput1_3.dll": Dependency(
        name="XInput",
        category="input",
        confidence="high",
        winetricks_verb="xinput",
    ),
    "xinput1_4.dll": Dependency(
        name="XInput",
        category="input",
        confidence="high",
    ),
    "xinput9_1_0.dll": Dependency(
        name="XInput",
        category="input",
        confidence="high",
    ),
    "dinput8.dll": Dependency(
        name="DirectInput 8",
        category="input",
        confidence="high",
    ),
    # ---------------------------------------------------------
    # Audio
    # ---------------------------------------------------------
    "openal32.dll": Dependency(
        name="OpenAL",
        category="audio",
        confidence="high",
        winetricks_verb="openal",
    ),
    "xaudio2_7.dll": Dependency(
        name="XAudio 2.7",
        category="audio",
        confidence="high",
        winetricks_verb="xact",
    ),
    "xaudio2_8.dll": Dependency(
        name="XAudio 2.8",
        category="audio",
        confidence="high",
    ),
    "xaudio2_9.dll": Dependency(
        name="XAudio 2.9",
        category="audio",
        confidence="high",
        winetricks_verb="xaudio29",
    ),
    "x3daudio1_6.dll": Dependency(
        name="X3DAudio",
        category="audio",
        confidence="high",
        winetricks_verb="xact",
    ),
    "x3daudio1_7.dll": Dependency(
        name="X3DAudio",
        category="audio",
        confidence="high",
        winetricks_verb="xact",
    ),
    "xactengine2_0.dll": Dependency(
        name="Microsoft XACT",
        category="audio",
        confidence="high",
        winetricks_verb="xact",
    ),
    "xactengine3_0.dll": Dependency(
        name="Microsoft XACT",
        category="audio",
        confidence="high",
        winetricks_verb="xact",
    ),
    "xactengine3_7.dll": Dependency(
        name="Microsoft XACT",
        category="audio",
        confidence="high",
        winetricks_verb="xact",
    ),
    # ---------------------------------------------------------
    # Multimedia / Media Foundation
    # ---------------------------------------------------------
    "mf.dll": Dependency(
        name="Windows Media Foundation",
        category="multimedia",
        confidence="high",
    ),
    "mfplat.dll": Dependency(
        name="Windows Media Foundation",
        category="multimedia",
        confidence="high",
    ),
    "mfreadwrite.dll": Dependency(
        name="Windows Media Foundation",
        category="multimedia",
        confidence="high",
    ),
    "mfcore.dll": Dependency(
        name="Windows Media Foundation",
        category="multimedia",
        confidence="high",
    ),
    "mfperfhelper.dll": Dependency(
        name="Windows Media Foundation",
        category="multimedia",
        confidence="high",
    ),
    "evr.dll": Dependency(
        name="Enhanced Video Renderer",
        category="multimedia",
        confidence="high",
    ),
    "quartz.dll": Dependency(
        name="DirectShow",
        category="multimedia",
        confidence="high",
    ),
    "windowscodecs.dll": Dependency(
        name="Windows Imaging Component",
        category="multimedia",
        confidence="high",
        winetricks_verb="windowscodecs",
    ),
    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------
    "riched20.dll": Dependency(
        name="Microsoft RichEdit",
        category="ui",
        confidence="high",
        winetricks_verb="riched20",
    ),
    "riched32.dll": Dependency(
        name="Microsoft RichEdit",
        category="ui",
        confidence="high",
        winetricks_verb="riched30",
    ),
    # ---------------------------------------------------------
    # Networking / Windows APIs
    # ---------------------------------------------------------
    # These are detected as APIs/components but should not normally
    # trigger Winetricks installation. Wine already implements these.
    "winhttp.dll": Dependency(
        name="Windows HTTP Services",
        category="network",
        confidence="high",
    ),
    "wininet.dll": Dependency(
        name="Windows Internet API",
        category="network",
        confidence="high",
    ),
    "urlmon.dll": Dependency(
        name="Windows URL Moniker Services",
        category="network",
        confidence="high",
    ),
    "crypt32.dll": Dependency(
        name="Windows Cryptography API",
        category="security",
        confidence="high",
    ),
    "secur32.dll": Dependency(
        name="Windows Security API",
        category="security",
        confidence="high",
    ),
    "xmllite.dll": Dependency(
        name="Microsoft XML Lite",
        category="runtime",
        confidence="high",
    ),
}


DOTNET_VERB = "dotnet48"


def _pattern_dependency(name: str) -> Dependency | None:
    """Recognize versioned runtime DLL families without a brittle exhaustive table."""

    if re.fullmatch(r"api-ms-win-crt-[a-z0-9_-]+\.dll", name):
        return Dependency("Universal C Runtime", "runtime", "high", "ucrtbase2019")
    if re.fullmatch(r"d3dx9_(?:2[4-9]|3[0-9]|4[0-3])\.dll", name):
        return Dependency("Direct3D 9 Extensions", "graphics", "high", "d3dx9")
    if re.fullmatch(r"d3dx10_(?:3[3-9]|4[0-3])\.dll", name):
        return Dependency("Direct3D 10 Extensions", "graphics", "high", "d3dx10")
    d3dx11 = re.fullmatch(r"d3dx11_(4[23])\.dll", name)
    if d3dx11:
        return Dependency(
            "Direct3D 11 Extensions",
            "graphics",
            "high",
            f"d3dx11_{d3dx11.group(1)}",
        )
    if re.fullmatch(r"xactengine[23]_[0-7]\.dll", name):
        return Dependency("Microsoft XACT", "audio", "high", "xact")
    if re.fullmatch(r"xaudio2_[0-7]\.dll", name):
        return Dependency("XAudio 2.x", "audio", "high", "xact")
    return None


def detect_dependencies(
    imports: list[PEImport],
) -> list[Dependency]:
    """Detect runtime/component dependencies from PE imports."""

    dependencies: list[Dependency] = []
    seen: set[tuple[str, str]] = set()

    for imported in imports or []:
        normalized_name = imported.name.lower()
        dependency = DLL_DEPENDENCIES.get(normalized_name) or _pattern_dependency(normalized_name)

        if dependency is None:
            continue

        key = (
            dependency.name,
            dependency.category,
        )

        if key in seen:
            continue

        dependencies.append(dependency)
        seen.add(key)

    return dependencies


def resolve_verbs_for_dependencies(
    dependencies: list[Dependency],
) -> list[str]:
    """Return the Winetricks verbs required by detected dependencies."""

    verbs: list[str] = []
    seen: set[str] = set()

    for dependency in dependencies:
        verb = dependency.winetricks_verb

        if verb is None or verb in seen:
            continue

        verbs.append(verb)
        seen.add(verb)

    return verbs
