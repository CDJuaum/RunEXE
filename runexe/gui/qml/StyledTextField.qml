import QtQuick
import QtQuick.Controls

TextField {
    id: root
    implicitHeight: 38
    color: Theme.text
    placeholderTextColor: Theme.textMuted
    selectionColor: Theme.accent
    selectedTextColor: Theme.palette.highlightedText
    leftPadding: 10
    rightPadding: 10

    background: Rectangle {
        radius: 7
        color: Theme.field
        border.color: root.activeFocus ? Theme.accent : Theme.border
        border.width: root.activeFocus ? 2 : 1
    }
}
