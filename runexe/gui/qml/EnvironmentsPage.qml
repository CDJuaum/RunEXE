import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.pageMargin
        spacing: 12

        MetricCard { Layout.fillWidth: true; title: "Managed storage"; metric: controller.storageMetric }

        Card {
            Layout.fillWidth: true
            Layout.fillHeight: true
            RowLayout {
                Layout.fillWidth: true
                SectionTitle {
                    Layout.fillWidth: true
                    title: "Isolated environments"
                    description: "Storage used by each application."
                }
                AppButton {
                    text: "Refresh"
                    enabled: controller.libraryActionsEnabled && !controller.running
                    onClicked: controller.refreshLibrary()
                }
            }

            Text {
                Layout.fillWidth: true
                visible: environmentList.count === 0
                text: "No managed environments have been created yet."
                color: Theme.textMuted
                horizontalAlignment: Text.AlignHCenter
            }

            ModelListView {
                id: environmentList
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 240
                model: controller.environmentsModel
                currentIndex: controller.selectedEnvironmentIndex
                delegate: ListRow {
                    required property int index
                    selected: environmentList.currentIndex === index
                    onSelectedRequested: {
                        controller.selectEnvironment(index)
                        environmentList.currentIndex = index
                    }
                    onActivated: {
                        controller.selectEnvironment(index)
                        environmentList.currentIndex = index
                        controller.openSelectedEnvironmentFolder()
                    }
                }
                Keys.onReturnPressed: controller.openSelectedEnvironmentFolder()
                Keys.onEnterPressed: controller.openSelectedEnvironmentFolder()
                Keys.onUpPressed: function(event) {
                    if (count > 0) controller.selectEnvironment(Math.max(0, currentIndex - 1))
                    event.accepted = true
                }
                Keys.onDownPressed: function(event) {
                    if (count > 0) controller.selectEnvironment(Math.min(count - 1, Math.max(0, currentIndex + 1)))
                    event.accepted = true
                }
            }

            Flow {
                Layout.fillWidth: true
                spacing: 8
                AppButton {
                    text: "Open folder"
                    enabled: controller.environmentSelected && controller.libraryActionsEnabled
                    onClicked: controller.openSelectedEnvironmentFolder()
                }
                AppButton {
                    text: "Configure…"
                    enabled: controller.environmentSelected && controller.libraryActionsEnabled && !controller.running
                    onClicked: configMenu.open()
                    Menu {
                        id: configMenu
                        Repeater {
                            model: controller.configurationTools
                            delegate: MenuItem {
                                required property var modelData
                                text: modelData.label
                                onTriggered: controller.configureSelectedEnvironment(modelData.key)
                            }
                        }
                    }
                }
                AppButton {
                    text: "Back up"
                    enabled: controller.environmentSelected && controller.libraryActionsEnabled
                    onClicked: controller.backupSelectedEnvironment()
                }
                AppButton {
                    text: "Remove environment"
                    danger: true
                    enabled: controller.environmentSelected && controller.libraryActionsEnabled && !controller.running
                    onClicked: removeDialog.open()
                }
            }
        }
    }

    Dialog {
        id: removeDialog
        anchors.centerIn: parent
        modal: true
        title: "Remove isolated environment?"
        footer: DialogButtonBox {
            Button { text: "Back up and remove"; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole; onClicked: { removeDialog.close(); controller.removeSelectedEnvironment(true) } }
            Button { text: "Remove without backup"; DialogButtonBox.buttonRole: DialogButtonBox.DestructiveRole; onClicked: { removeDialog.close(); controller.removeSelectedEnvironment(false) } }
            Button { text: "Cancel"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole; onClicked: removeDialog.close() }
        }
        Text {
            width: 420
            property var selectedRow: controller.environmentsModel.get(controller.selectedEnvironmentIndex)
            text: "This permanently removes “" + (selectedRow.application || "the selected application")
                  + "” environment (" + (selectedRow.subtitle || "managed environment") + ").\n\n"
                  + (selectedRow.path || "")
                  + "\n\nWindows-side settings, saves, and installed components inside the prefix may be lost. The original application file is not removed."
            color: Theme.text
            wrapMode: Text.Wrap
        }
    }
}
