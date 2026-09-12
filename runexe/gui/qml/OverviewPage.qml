import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Flickable {
    id: root
    contentWidth: width
    contentHeight: content.implicitHeight + 32
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

    property var openFileDialog

    function focusProfile() {
        if (!profileCard.visible)
            return
        contentY = Math.max(0, Math.min(profileCard.y - 18, contentHeight - height))
    }

    ColumnLayout {
        id: content
        width: root.width - 2 * Theme.pageMargin
        x: Theme.pageMargin
        y: 16
        spacing: 12

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 130
            radius: 12
            color: drop.containsDrag
                   ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, Theme.dark ? 0.22 : 0.10)
                   : Theme.surface
            border.color: drop.containsDrag ? Theme.accent : Theme.border
            border.width: drop.containsDrag ? 2 : 1

            ColumnLayout {
                anchors.centerIn: parent
                width: Math.min(parent.width - 48, 620)
                spacing: 6
                Text {
                    Layout.fillWidth: true
                    text: controller.sourceSelected ? controller.selectedName : "Drop Windows software here"
                    color: Theme.text
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideMiddle
                }
                Text {
                    Layout.fillWidth: true
                    text: controller.sourceSelected ? controller.selectedPath : "EXE, AppX, MSIX, or bundle"
                    color: Theme.textMuted
                    font.pixelSize: 12
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideMiddle
                }
                AppButton {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Choose file"
                    enabled: controller.interactionEnabled
                    onClicked: root.openFileDialog.open()
                }
            }

            DropArea {
                id: drop
                anchors.fill: parent
                enabled: controller.interactionEnabled
                onDropped: function(event) {
                    if (event.urls.length > 0)
                        controller.analyzePath(event.urls[0].toString())
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: root.width >= 1250 ? 4 : (root.width >= 760 ? 2 : 1)
            columnSpacing: 10
            rowSpacing: 10
            MetricCard { Layout.fillWidth: true; title: "File format"; metric: controller.fileMetric }
            MetricCard { Layout.fillWidth: true; title: "Architecture"; metric: controller.architectureMetric }
            MetricCard { Layout.fillWidth: true; title: "Selected runtime"; metric: controller.runtimeMetric }
            MetricCard { Layout.fillWidth: true; title: "Readiness"; metric: controller.readinessMetric }
        }

        Card {
            id: profileCard
            Layout.fillWidth: true
            visible: controller.profileVisible
            border.color: Theme.warning
            SectionTitle {
                Layout.fillWidth: true
                title: controller.profileTitle
                description: controller.profileSummary
            }
            Text {
                Layout.fillWidth: true
                text: controller.profileRequirements
                color: Theme.textMuted
                wrapMode: Text.Wrap
            }
            AppButton {
                Layout.alignment: Qt.AlignRight
                text: controller.profileButtonText
                primary: true
                enabled: controller.profileButtonEnabled && controller.interactionEnabled
                onClicked: controller.applyProfileRecommendation()
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: root.width >= 980 ? 2 : 1
            columnSpacing: 12
            rowSpacing: 12

            Card {
                Layout.fillWidth: true
                Layout.fillHeight: true
                SectionTitle { Layout.fillWidth: true; title: "Application details"; description: "File and runtime requirements." }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: 18
                    rowSpacing: 8
                    Text { text: "Source"; color: Theme.textMuted }
                    Text { Layout.fillWidth: true; text: controller.selectedPath || "Not selected"; color: Theme.text; elide: Text.ElideMiddle }
                    Text { text: "Product"; color: Theme.textMuted }
                    Text { Layout.fillWidth: true; text: controller.product; color: Theme.text; wrapMode: Text.Wrap }
                    Text { text: "Subsystem"; color: Theme.textMuted }
                    Text { Layout.fillWidth: true; text: controller.subsystem; color: Theme.text }
                    Text { text: "Dependencies"; color: Theme.textMuted }
                    Text { Layout.fillWidth: true; text: controller.dependencyText; color: Theme.text; wrapMode: Text.Wrap }
                }
            }

            Card {
                Layout.fillWidth: true
                Layout.fillHeight: true
                SectionTitle { Layout.fillWidth: true; title: "Compatibility"; description: "Review warnings before launching." }
                Repeater {
                    model: controller.guidance
                    delegate: Rectangle {
                        required property string modelData
                        Layout.fillWidth: true
                        implicitHeight: guidanceText.implicitHeight + 14
                        radius: 7
                        color: Theme.field
                        border.color: modelData.startsWith("BLOCKED") ? Theme.error
                                      : modelData.startsWith("WARNING") ? Theme.warning : Theme.borderSoft
                        Text {
                            id: guidanceText
                            anchors.fill: parent
                            anchors.margins: 7
                            text: modelData
                            color: Theme.text
                            wrapMode: Text.Wrap
                        }
                    }
                }
            }
        }

        Card {
            Layout.fillWidth: true
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Text { text: "Arguments"; color: Theme.textMuted }
                StyledTextField {
                    Layout.fillWidth: true
                    text: controller.arguments
                    placeholderText: "Optional, e.g. --portable"
                    enabled: controller.interactionEnabled
                    onEditingFinished: controller.setArguments(text)
                    onAccepted: controller.launchApplication()
                }
            }
        }
    }
}
