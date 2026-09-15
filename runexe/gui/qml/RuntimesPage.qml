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
    WheelScrollHandler { flickable: root }

    ColumnLayout {
        id: content
        width: root.width - 2 * Theme.pageMargin
        x: Theme.pageMargin
        y: 16
        spacing: 12

        GridLayout {
            Layout.fillWidth: true
            columns: root.width >= 1250 ? 4 : (root.width >= 760 ? 2 : 1)
            columnSpacing: 10
            rowSpacing: 10
            MetricCard { Layout.fillWidth: true; title: "Wine"; metric: controller.wineMetric }
            MetricCard { Layout.fillWidth: true; title: "Proton"; metric: controller.protonMetric }
            MetricCard { Layout.fillWidth: true; title: "Winetricks"; metric: controller.winetricksMetric }
            MetricCard { Layout.fillWidth: true; title: "Vulkan / GPU"; metric: controller.vulkanMetric }
        }

        Card {
            Layout.fillWidth: true
            SectionTitle {
                Layout.fillWidth: true
                title: "Runtime management"
                description: "Install optional host tools or refresh RunEXE's runtime and graphics detection."
            }
            GridLayout {
                Layout.fillWidth: true
                columns: root.width >= 760 ? 2 : 1
                columnSpacing: 10
                rowSpacing: 10
                AppButton {
                    Layout.fillWidth: true
                    Layout.columnSpan: root.width >= 760 ? 2 : 1
                    text: "Refresh detection"
                    primary: true
                    enabled: controller.interactionEnabled
                    onClicked: controller.refreshRuntimes()
                }
                AppButton {
                    Layout.fillWidth: true
                    text: "Install Proton"
                    enabled: controller.interactionEnabled
                    onClicked: controller.installProton()
                }
                AppButton {
                    Layout.fillWidth: true
                    text: "Install Vulkan tools"
                    enabled: controller.interactionEnabled
                    onClicked: controller.installVulkanTools()
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.columnSpan: root.width >= 760 ? 2 : 1
                    visible: controller.taskProgressVisible
                    spacing: 7

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            Layout.fillWidth: true
                            text: controller.taskProgressLabel
                            color: Theme.text
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }
                        Text {
                            text: controller.taskProgressIndeterminate ? "Working…" : controller.taskProgressValue + "%"
                            color: Theme.textMuted
                            font.pixelSize: 11
                        }
                    }

                    Item {
                        id: installProgress
                        objectName: "runtimeInstallProgress"
                        Layout.fillWidth: true
                        implicitHeight: 8
                        clip: true

                        Rectangle {
                            anchors.fill: parent
                            radius: height / 2
                            color: Theme.field
                            border.color: Theme.borderSoft
                        }
                        Rectangle {
                            visible: !controller.taskProgressIndeterminate
                            width: parent.width * Math.max(0, Math.min(100, controller.taskProgressValue)) / 100
                            height: parent.height
                            radius: height / 2
                            color: Theme.accent
                            Behavior on width { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
                        }
                        Rectangle {
                            id: indeterminateBar
                            visible: controller.taskProgressIndeterminate
                            width: Math.max(48, parent.width * 0.28)
                            height: parent.height
                            radius: height / 2
                            color: Theme.accent
                            x: -width
                            NumberAnimation on x {
                                running: indeterminateBar.visible
                                loops: Animation.Infinite
                                from: -indeterminateBar.width
                                to: installProgress.width
                                duration: 950
                                easing.type: Easing.InOutQuad
                            }
                        }
                    }
                }
            }
        }
    }
}
