from runexe.dependencies import detect_dependencies, resolve_verbs_for_dependencies
from runexe.models import PEImport


def test_detects_versioned_directx_and_universal_runtime_families():
    dependencies = detect_dependencies(
        [
            PEImport("D3DX9_24.dll"),
            PEImport("d3dx11_43.dll"),
            PEImport("api-ms-win-crt-runtime-l1-1-0.dll"),
            PEImport("WebView2Loader.dll"),
        ]
    )

    assert {item.name for item in dependencies} == {
        "Direct3D 9 Extensions",
        "Direct3D 11 Extensions",
        "Universal C Runtime",
        "Microsoft Edge WebView2 Runtime",
    }
    assert resolve_verbs_for_dependencies(dependencies) == [
        "d3dx9",
        "d3dx11_43",
        "ucrtbase2019",
    ]
