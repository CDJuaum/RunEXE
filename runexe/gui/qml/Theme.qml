pragma Singleton
import QtQuick

QtObject {
    property string mode: "system"
    readonly property SystemPalette palette: SystemPalette { colorGroup: SystemPalette.Active }
    readonly property bool forcedDark: mode === "dark"
    readonly property bool forcedLight: mode === "light"
    readonly property bool dark: forcedDark || (!forcedLight && palette.window.hslLightness < 0.5)
    readonly property color window: forcedDark ? "#171a1f" : (forcedLight ? "#f5f6f8" : palette.window)
    readonly property color sidebar: forcedDark ? "#1d2127" : (forcedLight ? "#eceff3" : (dark ? Qt.lighter(palette.window, 1.08) : Qt.darker(palette.window, 1.025)))
    readonly property color surface: forcedDark ? "#20252b" : (forcedLight ? "#ffffff" : palette.base)
    readonly property color surfaceRaised: forcedDark ? "#2a3038" : (forcedLight ? "#f0f3f6" : (dark ? Qt.lighter(palette.base, 1.14) : Qt.darker(palette.base, 1.035)))
    readonly property color field: forcedDark ? "#181c21" : (forcedLight ? "#f8fafc" : (dark ? Qt.darker(palette.base, 1.06) : Qt.lighter(palette.base, 1.02)))
    readonly property color border: forcedDark ? "#46505d" : (forcedLight ? "#c7cdd5" : (dark ? Qt.lighter(palette.window, 1.45) : Qt.darker(palette.window, 1.18)))
    readonly property color borderSoft: forcedDark ? "#313944" : (forcedLight ? "#dde1e6" : (dark ? Qt.lighter(palette.window, 1.28) : Qt.darker(palette.window, 1.10)))
    readonly property color text: forcedDark ? "#f1f3f5" : (forcedLight ? "#20252b" : palette.text)
    readonly property color textMuted: forcedDark ? "#aeb6c1" : (forcedLight ? "#626b75" : (dark ? "#a9adb2" : "#60666c"))
    readonly property color accent: forcedDark ? "#6ea8fe" : (forcedLight ? "#316dca" : palette.highlight)
    readonly property color accentHover: forcedDark ? "#8bb8ff" : (forcedLight ? "#285eae" : (dark ? Qt.lighter(palette.highlight, 1.16) : Qt.darker(palette.highlight, 1.08)))
    readonly property color accentText: forcedDark ? "#101722" : (forcedLight ? "#ffffff" : palette.highlightedText)
    readonly property color success: dark ? "#8bd5a0" : "#246b38"
    readonly property color warning: dark ? "#f0c477" : "#865b09"
    readonly property color error: dark ? "#f59999" : "#b52b35"
    readonly property int radius: 10
    readonly property int pageMargin: 22
}
