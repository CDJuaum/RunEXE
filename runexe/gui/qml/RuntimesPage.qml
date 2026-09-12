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
            }
        }
    }
}
