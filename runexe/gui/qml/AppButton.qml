import QtQuick
import QtQuick.Controls

Button {
    id: root
    property bool primary: false
    property bool danger: false

    implicitHeight: 36
    leftPadding: 14
    rightPadding: 14
    font.weight: primary ? Font.DemiBold : Font.Normal

    HoverHandler { cursorShape: Qt.ArrowCursor }

    contentItem: Text {
        text: root.text
        color: root.enabled
               ? (root.primary ? Theme.accentText : (root.danger ? Theme.error : Theme.text))
               : Theme.textMuted
        font: root.font
        verticalAlignment: Text.AlignVCenter
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: 7
        color: {
            if (!root.enabled) return Theme.field
            if (root.primary)
                return root.down ? Qt.darker(Theme.accent, 1.12) : (root.hovered ? Theme.accentHover : Theme.accent)
            return root.down ? Qt.darker(Theme.surfaceRaised, 1.10)
                             : (root.hovered ? (Theme.dark ? Qt.lighter(Theme.surfaceRaised, 1.08) : Qt.darker(Theme.surfaceRaised, 1.04)) : Theme.surfaceRaised)
        }
        border.color: root.activeFocus ? Theme.accent : Theme.border
        border.width: root.activeFocus ? 2 : 1
    }
}
