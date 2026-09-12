import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    property string title: ""
    property string description: ""
    spacing: 3

    Text {
        Layout.fillWidth: true
        text: root.title
        color: Theme.text
        font.pixelSize: 17
        font.weight: Font.DemiBold
        wrapMode: Text.Wrap
    }
    Text {
        Layout.fillWidth: true
        visible: text.length > 0
        text: root.description
        color: Theme.textMuted
        font.pixelSize: 12
        wrapMode: Text.Wrap
    }
}
