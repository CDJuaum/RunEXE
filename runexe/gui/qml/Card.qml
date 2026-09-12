import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    color: Theme.surface
    border.color: Theme.border
    border.width: 1
    radius: Theme.radius
    implicitHeight: content.implicitHeight + 28
    implicitWidth: 280

    default property alias contentData: content.data

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: 14
        spacing: 10
    }
}
