import QtQuick
import QtQuick.Controls

ComboBox {
    id: root
    implicitHeight: 38
    textRole: "label"
    valueRole: "value"
    wheelEnabled: false
    leftPadding: 10
    rightPadding: 30

    delegate: ItemDelegate {
        width: ListView.view ? ListView.view.width : root.width
        text: modelData.label
        highlighted: root.highlightedIndex === index
    }

    contentItem: Text {
        leftPadding: 2
        rightPadding: 2
        text: root.displayText
        color: root.enabled ? Theme.text : Theme.textMuted
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: 7
        color: Theme.field
        border.color: root.activeFocus ? Theme.accent : Theme.border
        border.width: root.activeFocus ? 2 : 1
    }

    popup: Popup {
        y: root.height + 4
        width: root.width
        implicitHeight: Math.min(contentItem.implicitHeight + 8, 320)
        padding: 4
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: root.popup.visible ? root.delegateModel : null
            currentIndex: root.highlightedIndex
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        }
        background: Rectangle {
            color: Theme.surfaceRaised
            border.color: Theme.border
            radius: 8
        }
    }
}
