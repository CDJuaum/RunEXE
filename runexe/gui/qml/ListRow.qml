import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    required property bool selected
    required property string headline
    required property string subtitle
    required property string detail
    signal selectedRequested()
    signal activated()

    width: ListView.view ? ListView.view.width : 400
    height: 82
    radius: 8
    color: selected ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, Theme.dark ? 0.34 : 0.18)
                    : (mouse.containsMouse ? Theme.surfaceRaised : Theme.field)
    border.color: selected ? Theme.accent : Theme.borderSoft
    border.width: 1
    Accessible.role: Accessible.ListItem
    Accessible.name: headline + ", " + subtitle
    Accessible.focusable: true

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 11
        spacing: 3
        Text {
            Layout.fillWidth: true
            text: root.headline
            color: Theme.text
            font.pixelSize: 13
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        Text {
            Layout.fillWidth: true
            text: root.subtitle
            color: Theme.textMuted
            font.pixelSize: 11
            elide: Text.ElideRight
        }
        Text {
            Layout.fillWidth: true
            text: root.detail
            color: Theme.textMuted
            font.pixelSize: 10
            elide: Text.ElideMiddle
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        onClicked: root.selectedRequested()
        onDoubleClicked: root.activated()
    }
}
