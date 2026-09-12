pragma Singleton
import QtQuick

QtObject {
    readonly property SystemPalette palette: SystemPalette { colorGroup: SystemPalette.Active }
    readonly property bool dark: palette.window.hslLightness < 0.5
    readonly property color window: palette.window
    readonly property color sidebar: dark ? Qt.lighter(palette.window, 1.08) : Qt.darker(palette.window, 1.025)
    readonly property color surface: palette.base
    readonly property color surfaceRaised: dark ? Qt.lighter(palette.base, 1.14) : Qt.darker(palette.base, 1.035)
    readonly property color field: dark ? Qt.darker(palette.base, 1.06) : Qt.lighter(palette.base, 1.02)
    readonly property color border: dark ? Qt.lighter(palette.window, 1.45) : Qt.darker(palette.window, 1.18)
    readonly property color borderSoft: dark ? Qt.lighter(palette.window, 1.28) : Qt.darker(palette.window, 1.10)
    readonly property color text: palette.text
    readonly property color textMuted: dark ? "#a9adb2" : "#60666c"
    readonly property color accent: palette.highlight
    readonly property color accentHover: dark ? Qt.lighter(palette.highlight, 1.16) : Qt.darker(palette.highlight, 1.08)
    readonly property color success: dark ? "#8bd5a0" : "#246b38"
    readonly property color warning: dark ? "#f0c477" : "#865b09"
    readonly property color error: dark ? "#f59999" : "#b52b35"
    readonly property int radius: 10
    readonly property int pageMargin: 22
}
