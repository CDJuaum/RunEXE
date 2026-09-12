"""Entry point for Linux bundles; keep bundled libraries out of child processes."""

import os
import sys


def restore_library_path() -> None:
    # PyInstaller prepends its private libraries. Wine and other host programs
    # must use the host's libraries, not the Python/Qt copies in our bundle.
    if getattr(sys, "frozen", False) and sys.platform.startswith("linux"):
        original = os.environ.get("LD_LIBRARY_PATH_ORIG")
        if original is None:
            os.environ.pop("LD_LIBRARY_PATH", None)
        else:
            os.environ["LD_LIBRARY_PATH"] = original


if __name__ == "__main__":
    restore_library_path()
    from runexe.cli import main

    main()
