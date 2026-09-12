import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.pageMargin
        spacing: 12

        MetricCard { Layout.fillWidth: true; title: "Backups"; metric: controller.backupMetric }

        Card {
            Layout.fillWidth: true
            Layout.fillHeight: true
            RowLayout {
                Layout.fillWidth: true
                SectionTitle {
                    Layout.fillWidth: true
                    title: "Environment backups"
                    description: "Restore a removed prefix without overwriting an existing environment."
                }
                AppButton {
                    text: "Refresh"
                    enabled: controller.libraryActionsEnabled && !controller.running
                    onClicked: controller.refreshLibrary()
                }
            }

            Text {
                Layout.fillWidth: true
                visible: backupList.count === 0
                text: "No environment backups are available yet."
                color: Theme.textMuted
                horizontalAlignment: Text.AlignHCenter
            }

            ModelListView {
                id: backupList
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 240
                model: controller.backupsModel
                currentIndex: controller.selectedBackupIndex
                delegate: ListRow {
                    required property int index
                    selected: backupList.currentIndex === index
                    onSelectedRequested: {
                        controller.selectBackup(index)
                        backupList.currentIndex = index
                    }
                    onActivated: {
                        controller.selectBackup(index)
                        backupList.currentIndex = index
                        restoreDialog.open()
                    }
                }
                Keys.onReturnPressed: restoreDialog.open()
                Keys.onEnterPressed: restoreDialog.open()
                Keys.onUpPressed: function(event) {
                    if (count > 0) controller.selectBackup(Math.max(0, currentIndex - 1))
                    event.accepted = true
                }
                Keys.onDownPressed: function(event) {
                    if (count > 0) controller.selectBackup(Math.min(count - 1, Math.max(0, currentIndex + 1)))
                    event.accepted = true
                }
            }

            RowLayout {
                Layout.fillWidth: true
                AppButton {
                    text: "Restore backup"
                    primary: true
                    enabled: controller.backupSelected && controller.libraryActionsEnabled && !controller.running
                    onClicked: restoreDialog.open()
                }
                AppButton {
                    text: "Delete backup"
                    danger: true
                    enabled: controller.backupSelected && controller.libraryActionsEnabled
                    onClicked: deleteDialog.open()
                }
                Item { Layout.fillWidth: true }
            }
        }
    }

    Dialog {
        id: restoreDialog
        anchors.centerIn: parent
        modal: true
        title: "Restore environment backup?"
        standardButtons: Dialog.Yes | Dialog.Cancel
        onAccepted: controller.restoreSelectedBackup()
        Text {
            width: 400
            property var selectedRow: controller.backupsModel.get(controller.selectedBackupIndex)
            text: "Restore “" + (selectedRow.application || "the selected application") + "” backup?\n\n"
                  + (selectedRow.detail || "")
                  + "\n\nRestore is allowed only when the original managed path is absent, so no live environment will be overwritten."
            color: Theme.text
            wrapMode: Text.Wrap
        }
    }

    Dialog {
        id: deleteDialog
        anchors.centerIn: parent
        modal: true
        title: "Delete environment backup?"
        standardButtons: Dialog.Yes | Dialog.Cancel
        onAccepted: controller.removeSelectedBackup()
        Text {
            width: 400
            property var selectedRow: controller.backupsModel.get(controller.selectedBackupIndex)
            text: "Permanently delete backup “" + (selectedRow.identifier || "selected backup")
                  + "”?\n\nThis does not remove a live environment."
            color: Theme.text
            wrapMode: Text.Wrap
        }
    }
}
