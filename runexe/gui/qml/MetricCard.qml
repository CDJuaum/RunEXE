import QtQuick
import QtQuick.Layouts

Card {
    id: root
    property string title: ""
    property var metric: ({ value: "-", detail: "", state: "neutral" })

    function stateColor(state) {
        if (state === "success") return Theme.success
        if (state === "warning") return Theme.warning
        if (state === "error") return Theme.error
        return Theme.text
    }

    implicitHeight: 116

    Text {
        Layout.fillWidth: true
        text: root.title
        color: Theme.textMuted
        font.pixelSize: 12
    }
    Text {
        Layout.fillWidth: true
        text: root.metric && root.metric.value !== undefined ? root.metric.value : "-"
        color: root.stateColor(root.metric ? root.metric.state : "neutral")
        font.pixelSize: 22
        font.weight: Font.DemiBold
        elide: Text.ElideRight
    }
    Text {
        Layout.fillWidth: true
        text: root.metric && root.metric.detail !== undefined ? root.metric.detail : ""
        color: Theme.textMuted
        font.pixelSize: 11
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
    }
}
