import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    WheelScrollHandler { flickable: applicationList }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.pageMargin
        spacing: 12

        MetricCard {
            Layout.fillWidth: true
            title: "Recent applications"
            metric: controller.applicationMetric
        }

        Card {
            Layout.fillWidth: true
            Layout.fillHeight: true

            RowLayout {
                Layout.fillWidth: true
                SectionTitle {
                    Layout.fillWidth: true
                    title: "Application library"
                    description: "Open an application with its saved settings."
                }
                AppButton {
                    text: "Refresh"
                    enabled: controller.libraryActionsEnabled && !controller.running
                    onClicked: controller.refreshLibrary()
                }
            }

            StyledTextField {
                Layout.fillWidth: true
                text: controller.applicationSearch
                placeholderText: "Search applications by name or path"
                onTextEdited: controller.setApplicationSearch(text)
            }

            Text {
                Layout.fillWidth: true
                visible: applicationList.count === 0
                text: controller.applicationSearch.length > 0
                      ? "No applications match your search."
                      : "Your recent applications will appear here after analysis."
                color: Theme.textMuted
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
            }

            ModelListView {
                id: applicationList
                objectName: "applicationList"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 240
                model: controller.applicationsModel
                currentIndex: controller.selectedApplicationIndex
                delegate: ListRow {
                    required property int index
                    selected: applicationList.currentIndex === index
                    onSelectedRequested: {
                        controller.selectApplication(index)
                        applicationList.currentIndex = index
                    }
                    onActivated: {
                        controller.selectApplication(index)
                        applicationList.currentIndex = index
                        controller.openSelectedApplication()
                    }
                }
                Keys.onReturnPressed: controller.openSelectedApplication()
                Keys.onEnterPressed: controller.openSelectedApplication()
                Keys.onUpPressed: function(event) {
                    if (count > 0) controller.selectApplication(Math.max(0, currentIndex - 1))
                    event.accepted = true
                }
                Keys.onDownPressed: function(event) {
                    if (count > 0) controller.selectApplication(Math.min(count - 1, Math.max(0, currentIndex + 1)))
                    event.accepted = true
                }
            }

            RowLayout {
                Layout.fillWidth: true
                AppButton {
                    text: "Open and analyze"
                    primary: true
                    enabled: controller.applicationSelected && controller.libraryActionsEnabled && !controller.running
                    onClicked: controller.openSelectedApplication()
                }
                AppButton {
                    text: "Forget entry"
                    enabled: controller.applicationSelected && controller.libraryActionsEnabled
                    onClicked: forgetDialog.open()
                }
                Item { Layout.fillWidth: true }
                AppButton {
                    text: "Prune missing"
                    enabled: controller.libraryActionsEnabled
                    onClicked: pruneDialog.open()
                }
            }
        }
    }

    AppDialog {
        id: forgetDialog
        severity: "warning"
        title: "Forget application?"
        standardButtons: Dialog.Yes | Dialog.Cancel
        onAccepted: controller.forgetSelectedApplication()
        Text {
            width: 360
            property var selectedRow: controller.applicationsModel.get(controller.selectedApplicationIndex)
            text: "Remove “" + (selectedRow.displayName || selectedRow.headline || "this application")
                  + "” from the RunEXE library?\n\n" + (selectedRow.path || "")
                  + "\n\nThe original file will not be deleted."
            color: Theme.text
            wrapMode: Text.Wrap
        }
    }

    AppDialog {
        id: pruneDialog
        severity: "warning"
        title: "Prune missing applications?"
        standardButtons: Dialog.Yes | Dialog.Cancel
        onAccepted: controller.pruneMissingApplications()
        Text {
            width: 360
            text: "Remove every library entry whose source file no longer exists?"
            color: Theme.text
            wrapMode: Text.Wrap
        }
    }
}
