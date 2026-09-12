# Desktop interface

RunEXE uses a lightweight Qt Quick/QML shell designed to feel at home on a Linux desktop
while providing clearer hierarchy than a traditional tool window. It follows the active
system palette and platform font stack, uses lightweight built-in navigation glyphs, and keeps
application state and runtime behavior in the Python controller behind the QML presentation layer.

## Design rules

- Use a sidebar with focused destinations: Overview, Launch setup, Runtimes, Applications,
  Environments, Backups, and Activity. It collapses to an icon rail at narrower widths
  while preserving accessible labels and tooltips. Keep Open, Analyze, and Launch in the
  shared page header so the current file remains actionable from every page.
  See [layout and navigation](https://develop.kde.org/hig/layout_and_nav/).
- Prefer standard Qt Quick Controls and lightweight built-in glyphs. Keep custom
  styling focused on spacing, rounded surfaces, hierarchy, and semantic status colors.
  Derive the shell from the active SystemPalette and keep semantic colors centralized in the
  QML theme singleton.
- Show the file picker first. Reveal file-specific results and arguments after a
  file is selected. Place details and compatibility side by side when space allows.
  See [simple by default](https://develop.kde.org/hig/simple_by_default/).
- Use short, descriptive labels and reserve the accent color for the main action
  and current navigation marker. Pair status colors with text; preserve keyboard focus and native
  menus. See [text and labels](https://develop.kde.org/hig/text_and_labels/) and
  [accessibility](https://develop.kde.org/hig/accessibility/).
- Switch pages immediately and use one short opacity transition to soften page changes without
  allocating graphics effects. Let Qt Quick handle wheel, touchpad, and kinetic scrolling so
  pointer input stays native to Flickable/ListView controls.
- Keep management lists on their own pages so their native mouse-wheel and scrollbar
  behavior never competes with a second page scrollbar. Runtime selectors disable wheel
  selection while collapsed so scrolling the page cannot silently change settings.

## Keyboard access

Open: Ctrl+O. Analyze: Ctrl+R. Launch: Ctrl+Enter. Next/previous page:
Ctrl+Tab / Ctrl+Shift+Tab. Activity: Ctrl+L. Applications: Ctrl+Shift+L.
The file picker also opens with Space or Enter when focused.

## UI framework

The production shell uses PySide6 with Qt Quick/QML. QML owns the window, responsive page
layout, controls, scrolling, and transitions; `RunEXEController` remains a QObject-backed
client of the same Python analysis, library, environment, backup, Wine, and Proton services
used by the CLI. Release wheels and source archives ship the QML files as package data, and
the frozen glibc desktop bundle carries the Qt QML/Quick/Controls/Dialogs runtime modules.
The musl release remains CLI-only because PyPI does not publish a musllinux PySide6 wheel.

## Visual checks

`python scripts/capture_gui.py` renders an isolated demonstration without changing
the user's saved settings. It uses the same QML shell as the production desktop
entry point and Qt's Basic control style for repeatable captures. These environment
variables support visual checks:

- `RUNEXE_SCREENSHOT_PAGE`: `overview`, `launch`, `runtimes`, `applications`,
  `environments`, `backups`, or `activity`. `library` remains an alias for Applications.
- `RUNEXE_SCREENSHOT_EMPTY=1`: start without a selected application.
- `RUNEXE_SCREENSHOT_WIDTH` / `RUNEXE_SCREENSHOT_HEIGHT`: viewport size, down to
  the supported minimum of 920 × 680.
- `RUNEXE_SCREENSHOT_TARGET`: output PNG path (default: `assets/runexe-gui.png`).

Headless Linux captures use Qt's offscreen platform with software Qt Quick rendering.
Check native Linux rendering as well before a release; a Windows or offscreen capture
cannot validate every distribution's graphics stack and font rendering.
