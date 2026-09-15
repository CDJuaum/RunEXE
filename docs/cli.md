# CLI reference

RunEXE's command-line interface exposes the same analysis, runtime selection, environment preparation, and management services used by the desktop application.

## Analyze a Windows executable

Inspect a PE executable without launching it:

```bash
runexe analyze path/to/app.exe
```

List imported functions in addition to DLL summaries:

```bash
runexe analyze path/to/app.exe --imports
```

Emit JSON for scripts or support tooling:

```bash
runexe analyze path/to/app.exe --json
```

Skip host detection for a purely static report:

```bash
runexe analyze path/to/app.exe --no-host
```

AppX/MSIX packages and unpacked package directories are supported too:

```bash
runexe analyze Paint.msix
runexe run Paint.msix --no-deps
```

RunEXE reads the package manifest, safely materializes the declared executable, and launches that executable through the selected compatibility runtime. Package identity and Microsoft Store services are not recreated.

## Run software

Analyze, prepare an isolated environment, and launch:

```bash
runexe run path/to/app.exe
```

Useful options:

```bash
runexe run path/to/app.exe --verbose
runexe run path/to/app.exe --timeout 60
runexe run path/to/app.exe --winver 10
runexe run path/to/app.exe --no-deps
runexe run path/to/app.exe --backend wine
runexe run path/to/game.exe --backend proton
runexe run path/to/game.exe --proton "Proton Experimental"
runexe run path/to/game.exe --proton ~/.steam/root/compatibilitytools.d/GE-Proton/proton
runexe run path/to/game.exe --backend proton --tuning diagnostics
runexe run path/to/game.exe --backend proton --tuning wined3d
```

Pass arguments to the Windows application after `--`:

```bash
runexe run path/to/app.exe -- --portable "C:\\data file.txt"
```

`--backend auto` is the default. It prefers Proton for detected games and Wine for regular applications, then falls back to whichever suitable runtime is available. `--proton` implies the Proton backend.

Wine dependency provisioning is automatic by default. Proton dependency changes are opt-in with `--deps` because modifying a game-focused Proton environment can reduce compatibility.

## Runtime discovery and managed Proton

Inspect the runtimes RunEXE can use:

```bash
runexe backends
```

Install the latest supported managed GE-Proton release into RunEXE's user data directory:

```bash
runexe proton install
```

RunEXE discovers managed builds alongside Valve, Proton Experimental, GE-Proton, custom Steam libraries, Flatpak, Snap, and explicit runtime paths.

## Host and graphics diagnostics

Run the read-only host readiness check:

```bash
runexe doctor
runexe doctor --no-gui
runexe doctor --json
```

Inspect local Vulkan/DXVK readiness:

```bash
runexe graphics
runexe graphics --json
```

Install the distribution's Vulkan diagnostic tooling explicitly and rerun the report:

```bash
runexe graphics --install-tools
```

That final command is an explicit system change and may request administrator authentication through the detected package manager.

## Recent applications

```bash
runexe recent
runexe recent --json
runexe recent --prune-missing
runexe rerun APPLICATION_ID
runexe forget-recent APPLICATION_ID
```

Saved launch presets include backend, Proton build, reported Windows version, dependency policy, custom prefix, tuning selection, and application arguments.

## Managed environments

List RunEXE-owned Wine prefixes and Proton compat-data directories:

```bash
runexe environments
runexe environments --json
```

Open native Wine configuration tools for an exact managed environment:

```bash
runexe configure-environment wine:example-0123456789 --tool winecfg
runexe configure-environment wine:example-0123456789 --tool regedit
```

Environment deletion is deliberately explicit because a prefix can contain application settings or saves:

```bash
runexe remove-environment wine:example-0123456789 --yes
```

RunEXE accepts only the exact managed identifier, validates that the target is a direct child of a RunEXE-managed data root, and creates a restorable backup by default. Use `--no-backup` only when you deliberately do not want the safety snapshot.

## Backups

```bash
runexe backups
runexe restore-backup BACKUP_ID --yes
runexe remove-backup BACKUP_ID --yes
```

Restore validates archive paths and refuses to replace an existing live environment.

## Local state locations

Recent application state is stored under:

```text
$XDG_STATE_HOME/runexe/applications.json
```

Normally this resolves to `~/.local/state/runexe/applications.json`.

Managed Wine prefixes live under `$XDG_DATA_HOME/runexe/prefixes`, Proton compat data under `$XDG_DATA_HOME/runexe/proton`, managed runtimes under `$XDG_DATA_HOME/runexe/runtimes`, and backups under `$XDG_DATA_HOME/runexe/backups`.

The desktop Activity page exports a support report only when you explicitly choose a destination. Local application history and environment data are not uploaded automatically.

## Check the installed version

```bash
runexe version
```
