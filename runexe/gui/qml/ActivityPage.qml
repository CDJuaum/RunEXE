import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property var exportDialog
    WheelScrollHandler { flickable: activityList }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.pageMargin
        spacing: 12

        ColumnLayout {
            Layout.fillWidth: true
            SectionTitle {
                Layout.fillWidth: true
                title: "Session activity"
                description: "Analysis results and application output for this session."
            }
            RowLayout {
                Layout.fillWidth: true
                Switch {
                    text: "Desktop notifications"
                    checked: controller.notificationsEnabled
                    onToggled: controller.setNotificationsEnabled(checked)
                }
                Item { Layout.fillWidth: true }
                AppButton { text: "Export report"; onClicked: root.exportDialog.open() }
                AppButton { text: "Copy"; onClicked: controller.copyActivity() }
                AppButton { text: "Clear"; onClicked: clearDialog.open() }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.field
            border.color: Theme.border
            radius: 8

            ListView {
                id: activityList
                objectName: "activityList"
                property bool followTail: true
                property bool positioningAtTail: false
                anchors.fill: parent
                anchors.margins: 8
                clip: true
                spacing: 2
                model: controller.activityModel
                boundsBehavior: Flickable.StopAtBounds
                WheelScrollHandler { flickable: activityList }
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                onContentYChanged: {
                    if (!positioningAtTail && count > 0)
                        followTail = atYEnd
                }
                onContentHeightChanged: {
                    if (followTail && !positioningAtTail)
                        Qt.callLater(positionAtTail)
                }
                function positionAtTail() {
                    positioningAtTail = true
                    positionViewAtEnd()
                    positioningAtTail = false
                    followTail = true
                }
                delegate: Item {
                    required property string text
                    width: activityList.width
                    height: activityLine.implicitHeight
                    Text {
                        id: activityLine
                        width: parent.width
                        text: parent.text
                        color: Theme.text
                        font.family: "monospace"
                        font.pixelSize: 12
                        wrapMode: Text.WrapAnywhere
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: controller.activityModel.count === 0
                text: "Analysis and runtime output will appear here."
                color: Theme.textMuted
            }

            Connections {
                target: controller.activityModel
                function onCountChanged() {
                    if (activityList.count === 0) {
                        activityList.followTail = true
                    } else if (activityList.followTail) {
                        Qt.callLater(activityList.positionAtTail)
                    }
                }
            }
        }
    }

    AppDialog {
        id: clearDialog
        severity: "warning"
        title: "Clear session activity?"
        standardButtons: Dialog.Yes | Dialog.Cancel
        onAccepted: controller.clearActivity()
        Text {
            width: 340
            text: "Clear all activity currently shown in this session?"
            color: Theme.text
            wrapMode: Text.Wrap
        }
    }
}
