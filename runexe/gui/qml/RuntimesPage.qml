import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Flickable {
    id: root
    contentWidth: width
    contentHeight: content.implicitHeight + 24
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
    WheelScrollHandler { flickable: root }

    property string pendingRemoval: ""
    property string pendingRemovalLabel: ""
    property string pendingRemovalDetail: ""

    function requestRemoval(key, label, detail) {
        pendingRemoval = key
        pendingRemovalLabel = label
        pendingRemovalDetail = detail
        removeDialog.open()
    }

    ColumnLayout {
        id: content
        width: root.width
        spacing: 12

        GridLayout {
            Layout.fillWidth: true
            columns: root.width >= 1080 ? 4 : (root.width >= 650 ? 2 : 1)
            columnSpacing: 10
            rowSpacing: 10
            MetricCard { Layout.fillWidth: true; title: "Wine"; metric: controller.wineMetric }
            MetricCard { Layout.fillWidth: true; title: "Proton"; metric: controller.protonMetric }
            MetricCard { Layout.fillWidth: true; title: "Winetricks"; metric: controller.winetricksMetric }
            MetricCard { Layout.fillWidth: true; title: "Vulkan / GPU"; metric: controller.vulkanMetric }
        }

        Card {
            Layout.fillWidth: true

            RowLayout {
                Layout.fillWidth: true
                SectionTitle {
                    Layout.fillWidth: true
                    title: "Runtime management"
                    description: "Install, remove, or refresh the components RunEXE uses to launch Windows software."
                }
                AppButton {
                    text: "Refresh detection"
                    primary: true
                    enabled: controller.interactionEnabled
                    onClicked: controller.refreshRuntimes()
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                RuntimeRow {
                    title: "Wine"
                    description: controller.wineInstalled && !controller.runexeManagedWineInstalled
                                 ? "System Wine detected. RunEXE can use it, but only removes Wine packages it installed itself."
                                 : "System Wine runtime used for desktop applications and Wine prefixes."
                    statusText: controller.wineInstalled ? "Detected" : "Not installed"
                    installed: controller.wineInstalled
                    removable: controller.runexeManagedWineInstalled
                    installText: "Install Wine"
                    removeText: "Remove Wine"
                    onInstallRequested: controller.installRuntimeComponent("wine")
                    onRemoveRequested: root.requestRemoval(
                                           "wine", "Wine",
                                           "This removes the Wine package through your Linux distribution's package manager. Existing RunEXE environments are kept, but they will not launch through Wine until it is installed again.")
                }

                RuntimeRow {
                    title: "GE-Proton"
                    description: controller.managedProtonInstalled
                                 ? "RunEXE-managed GE-Proton build. Steam and custom Proton installations are never removed here."
                                 : "Install a RunEXE-managed GE-Proton build without changing Steam-managed runtimes."
                    statusText: controller.managedProtonInstalled ? "Managed build installed" : "No managed build"
                    installed: controller.managedProtonInstalled
                    installText: "Install Proton"
                    removeText: "Remove managed Proton"
                    onInstallRequested: controller.installProton()
                    onRemoveRequested: root.requestRemoval(
                                           "proton", "managed GE-Proton",
                                           "This removes only Proton builds stored in RunEXE's own runtime directory. Steam Proton and custom compatibility tools are left untouched.")
                }

                RuntimeRow {
                    objectName: "installUmuButton"
                    title: "UMU Launcher"
                    description: controller.managedUmuInstalled
                                 ? "RunEXE-managed UMU launcher for GE-Proton outside Steam."
                                 : "Install UMU locally for reliable GE-Proton launches outside Steam."
                    statusText: controller.managedUmuInstalled ? "Managed launcher installed" : "No managed launcher"
                    installed: controller.managedUmuInstalled
                    installText: "Install UMU"
                    removeText: "Remove managed UMU"
                    onInstallRequested: controller.installUmuLauncher()
                    onRemoveRequested: root.requestRemoval(
                                           "umu", "managed UMU Launcher",
                                           "This removes only the UMU launcher installed inside RunEXE's user data. A system-installed umu-run is left untouched.")
                }

                RuntimeRow {
                    title: "Winetricks"
                    description: controller.winetricksInstalled && !controller.runexeManagedWinetricksInstalled
                                 ? "System Winetricks detected. RunEXE leaves pre-existing packages under system management."
                                 : "Optional helper used when an application needs extra Windows components."
                    statusText: controller.winetricksInstalled ? "Detected" : "Not installed"
                    installed: controller.winetricksInstalled
                    removable: controller.runexeManagedWinetricksInstalled
                    installText: "Install Winetricks"
                    removeText: "Remove Winetricks"
                    onInstallRequested: controller.installRuntimeComponent("winetricks")
                    onRemoveRequested: root.requestRemoval(
                                           "winetricks", "Winetricks",
                                           "This removes Winetricks through your Linux distribution's package manager. Existing prefixes and already-installed Windows components are not deleted.")
                }

                RuntimeRow {
                    title: "Vulkan tools"
                    description: controller.vulkanToolsInstalled && !controller.runexeManagedVulkanToolsInstalled
                                 ? "System Vulkan diagnostics detected. RunEXE never removes pre-existing Vulkan tools, GPU drivers, loaders, or ICDs."
                                 : "Host diagnostics used to verify Vulkan, DXVK, and VKD3D readiness."
                    statusText: controller.vulkanToolsInstalled ? "vulkaninfo detected" : "Not installed"
                    installed: controller.vulkanToolsInstalled
                    removable: controller.runexeManagedVulkanToolsInstalled
                    installText: "Install Vulkan tools"
                    removeText: "Remove Vulkan tools"
                    onInstallRequested: controller.installVulkanTools()
                    onRemoveRequested: root.requestRemoval(
                                           "vulkan", "Vulkan tools",
                                           "This removes the Vulkan diagnostic tools package through your Linux distribution. It does not remove your GPU driver or Vulkan ICD driver packages.")
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
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
                    Rectangle { anchors.fill: parent; radius: height / 2; color: Theme.field; border.color: Theme.borderSoft }
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

    component RuntimeRow: Rectangle {
        id: runtimeRow
        property string title: ""
        property string description: ""
        property string statusText: ""
        property bool installed: false
        property bool removable: installed
        property string installText: "Install"
        property string removeText: "Remove"
        signal installRequested()
        signal removeRequested()

        Layout.fillWidth: true
        implicitHeight: rowLayout.implicitHeight + 20
        radius: 8
        color: Theme.field
        border.color: Theme.borderSoft

        RowLayout {
            id: rowLayout
            anchors.fill: parent
            anchors.margins: 10
            spacing: 12

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                RowLayout {
                    Layout.fillWidth: true
                    Text { text: runtimeRow.title; color: Theme.text; font.weight: Font.DemiBold }
                    Rectangle {
                        implicitWidth: statusLabel.implicitWidth + 14
                        implicitHeight: 22
                        radius: 11
                        color: "transparent"
                        border.color: runtimeRow.installed ? Theme.success : Theme.border
                        Text {
                            id: statusLabel
                            anchors.centerIn: parent
                            text: runtimeRow.statusText
                            color: parent.border.color
                            font.pixelSize: 10
                        }
                    }
                    Item { Layout.fillWidth: true }
                }
                Text {
                    Layout.fillWidth: true
                    text: runtimeRow.description
                    color: Theme.textMuted
                    font.pixelSize: 11
                    wrapMode: Text.Wrap
                }
            }

            AppButton {
                text: runtimeRow.installed ? "Reinstall" : runtimeRow.installText
                enabled: controller.interactionEnabled
                onClicked: runtimeRow.installRequested()
            }
            AppButton {
                text: runtimeRow.removeText
                danger: true
                visible: runtimeRow.removable
                enabled: controller.interactionEnabled
                onClicked: runtimeRow.removeRequested()
            }
        }
    }

    AppDialog {
        id: removeDialog
        severity: "warning"
        title: "Remove " + root.pendingRemovalLabel + "?"
        width: Math.min(520, root.width - 40)
        footer: DialogButtonBox {
            AppButton {
                text: "Cancel"
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
                onClicked: removeDialog.close()
            }
            AppButton {
                text: "Remove"
                danger: true
                DialogButtonBox.buttonRole: DialogButtonBox.DestructiveRole
                onClicked: {
                    const component = root.pendingRemoval
                    removeDialog.close()
                    controller.uninstallRuntimeComponent(component)
                }
            }
        }
        Text {
            width: 450
            text: root.pendingRemovalDetail
            color: Theme.text
            wrapMode: Text.Wrap
        }
    }
}
