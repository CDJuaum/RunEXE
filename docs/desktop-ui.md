# Desktop interface

RunEXE follows the [KDE Human Interface Guidelines](https://develop.kde.org/hig/)
for its Qt desktop interface. The goal is a familiar Linux utility: clear actions,
compact layouts, and the user's desktop colors and fonts.

## Design rules

- Use a tab bar for the four main destinations. Keep Open, Analyze, and Launch
  in the shared toolbar so the current file remains actionable from every page.
  See [layout and navigation](https://develop.kde.org/hig/layout_and_nav/).
- Prefer standard Qt controls and themed icons with Qt fallbacks. Keep custom
  styling limited to spacing, grouping, and semantic status colors. Avoid large
  banners, decorative dashboard cards, and custom control artwork.
- Show the file picker first. Reveal file-specific results and arguments after a
  file is selected. Place details and compatibility side by side when space allows.
  See [simple by default](https://develop.kde.org/hig/simple_by_default/).
- Use short, descriptive labels and reserve the accent color for the main action
  and current tab. Pair status colors with text; preserve keyboard focus and native
  menus. See [text and labels](https://develop.kde.org/hig/text_and_labels/) and
  [accessibility](https://develop.kde.org/hig/accessibility/).
- Switch pages and update results immediately. Apply touchpad pixel deltas directly;
  only mouse-wheel scrolling uses a short, interruptible animation.

## Keyboard access

Open: Ctrl+O. Analyze: Ctrl+R. Launch: Ctrl+Enter. Next/previous page:
Ctrl+Tab / Ctrl+Shift+Tab. Activity: Ctrl+L. Library: Ctrl+Shift+L.
The file picker also opens with Space or Enter when focused.

## Visual checks

`python scripts/capture_gui.py` renders an isolated demonstration without changing
the user's saved settings. The default uses the current platform theme. These
environment variables support repeatable visual checks:

- `RUNEXE_SCREENSHOT_SCHEME`: `system`, `light`, or `dark`.
- `RUNEXE_SCREENSHOT_PAGE`: `overview`, `runtime`, `library`, or `activity`.
- `RUNEXE_SCREENSHOT_EMPTY=1`: start without a selected application.
- `RUNEXE_SCREENSHOT_WIDTH` / `RUNEXE_SCREENSHOT_HEIGHT`: viewport size, down to
  the supported minimum of 920 × 680.
- `RUNEXE_SCREENSHOT_TARGET`: output PNG path (default: `assets/runexe-gui.png`).

Explicit light/dark captures use Qt Fusion for repeatability. The running app keeps
the platform style. Check native Linux rendering as well before a release; a
Windows or offscreen capture cannot validate every distribution's Qt theme.
