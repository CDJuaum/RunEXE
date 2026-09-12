# Desktop interface

RunEXE uses a lightweight Qt shell designed to feel at home on a Linux desktop while
providing clearer hierarchy than a traditional tool window. It keeps the user's desktop
palette and fonts, uses themed icons with Qt fallbacks, and adds only small structural
styles and animations on top of native Qt widgets.

## Design rules

- Use a sidebar with focused destinations: Overview, Launch setup, Runtimes, Applications,
  Environments, Backups, and Activity. It collapses to an icon rail at narrower widths
  while preserving accessible labels and tooltips. Keep Open, Analyze, and Launch in the
  shared page header so the current file remains actionable from every page.
  See [layout and navigation](https://develop.kde.org/hig/layout_and_nav/).
- Prefer standard Qt controls and themed icons with Qt fallbacks. Keep custom
  styling focused on spacing, rounded surfaces, hierarchy, and semantic status colors.
  Derive shell colors from the active light/dark palette rather than replacing it.
- Show the file picker first. Reveal file-specific results and arguments after a
  file is selected. Place details and compatibility side by side when space allows.
  See [simple by default](https://develop.kde.org/hig/simple_by_default/).
- Use short, descriptive labels and reserve the accent color for the main action
  and current navigation marker. Pair status colors with text; preserve keyboard focus and native
  menus. See [text and labels](https://develop.kde.org/hig/text_and_labels/) and
  [accessibility](https://develop.kde.org/hig/accessibility/).
- Switch pages immediately and use one short reusable position animation to soften page
  changes without fades or graphics effects. Apply touchpad pixel deltas directly; only
  mouse-wheel scrolling uses a short, interruptible animation.
- Keep management lists on their own pages so their native mouse-wheel and scrollbar
  behavior never competes with a second page scrollbar. Page scrollbars use a larger
  pointer-friendly handle and manual scrollbar interaction always cancels wheel animation.

## Keyboard access

Open: Ctrl+O. Analyze: Ctrl+R. Launch: Ctrl+Enter. Next/previous page:
Ctrl+Tab / Ctrl+Shift+Tab. Activity: Ctrl+L. Applications: Ctrl+Shift+L.
The file picker also opens with Space or Enter when focused.

## UI framework

The production shell stays on PySide6/Qt Widgets for now. It keeps the existing Python
backend direct, packages cleanly with RunEXE's current Linux builds, and provides mature
desktop controls and accessibility. If the visual shell eventually needs richer continuous
motion or touch-first interaction, Qt Quick/QML is the preferred migration path because it
can reuse the same Qt/Python backend while moving rendering and transitions to Qt Quick's
scene graph. A WebView or GTK rewrite would add a second application/runtime stack without
solving a current functional limitation.

## Visual checks

`python scripts/capture_gui.py` renders an isolated demonstration without changing
the user's saved settings. The default uses the current platform theme. These
environment variables support repeatable visual checks:

- `RUNEXE_SCREENSHOT_SCHEME`: `system`, `light`, or `dark`.
- `RUNEXE_SCREENSHOT_PAGE`: `overview`, `launch`, `runtimes`, `applications`,
  `environments`, `backups`, or `activity`. `library` remains an alias for Applications.
- `RUNEXE_SCREENSHOT_EMPTY=1`: start without a selected application.
- `RUNEXE_SCREENSHOT_WIDTH` / `RUNEXE_SCREENSHOT_HEIGHT`: viewport size, down to
  the supported minimum of 920 × 680.
- `RUNEXE_SCREENSHOT_TARGET`: output PNG path (default: `assets/runexe-gui.png`).

Explicit light/dark captures use Qt Fusion for repeatability. The running app keeps
the platform style. Check native Linux rendering as well before a release; a
Windows or offscreen capture cannot validate every distribution's Qt theme.
