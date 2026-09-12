import QtQuick
import QtQuick.Controls

Dialog {
    id: root

    property string severity: "info"

    modal: true
    anchors.centerIn: Overlay.overlay
    padding: 20
    leftPadding: 20
    rightPadding: 20
    topPadding: 16
    bottomPadding: 16
    closePolicy: Popup.CloseOnEscape

    Overlay.modal: Rectangle {
        color: Theme.dark ? "#99000000" : "#66000000"
    }

    background: Rectangle {
        radius: 12
        color: Theme.surface
        border.width: 1
        border.color: root.severity === "error" ? Theme.error
                      : root.severity === "warning" ? Theme.warning
                      : Theme.border
    }

    header: Rectangle {
        implicitHeight: 54
        color: "transparent"

        Row {
            anchors.fill: parent
            anchors.leftMargin: 20
            anchors.rightMargin: 20
            spacing: 10

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 8
                height: 8
                radius: 4
                color: root.severity === "error" ? Theme.error
                       : root.severity === "warning" ? Theme.warning
                       : root.severity === "success" ? Theme.success
                       : Theme.accent
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - 18
                text: root.title
                color: Theme.text
                font.pixelSize: 16
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: Theme.borderSoft
        }
    }
}
