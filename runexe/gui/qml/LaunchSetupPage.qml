import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

Flickable {
    id: root
    objectName: "launchSetupPage"
    contentWidth: width
    contentHeight: content.implicitHeight + 32
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
    WheelScrollHandler { flickable: root }
    property var prefixDialog: null

    function optionIndex(options, value) {
        for (let i = 0; i < options.length; ++i)
            if (options[i].value === value) return i
        return 0
    }

    ColumnLayout {
        id: content
        width: root.width - 2 * Theme.pageMargin
        x: Theme.pageMargin
        y: 16
        spacing: 12

        Card {
            Layout.fillWidth: true
            SectionTitle {
                Layout.fillWidth: true
                title: "Runtime strategy"
                description: "Automatic mode prefers Proton for games and Wine for desktop applications."
            }
            GridLayout {
                Layout.fillWidth: true
                columns: root.width >= 880 ? 2 : 1
                columnSpacing: 16
                rowSpacing: 10

                ColumnLayout {
                    Layout.fillWidth: true
                    Text { text: "Backend"; color: Theme.textMuted }
                    StyledComboBox {
                        Layout.fillWidth: true
                        model: controller.backendOptions
                        currentIndex: root.optionIndex(controller.backendOptions, controller.backend)
                        enabled: controller.interactionEnabled
                        onActivated: controller.setBackend(currentValue)
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Text { text: "Proton build"; color: Theme.textMuted }
                    StyledComboBox {
                        Layout.fillWidth: true
                        model: controller.protonOptions
                        currentIndex: root.optionIndex(controller.protonOptions, controller.proton)
                        enabled: controller.protonChoiceEnabled
                        onActivated: controller.setProton(currentValue)
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Text { text: "Proton tuning"; color: Theme.textMuted }
                    StyledComboBox {
                        Layout.fillWidth: true
                        model: controller.tuningOptions
                        currentIndex: root.optionIndex(controller.tuningOptions, controller.protonTuning)
                        enabled: controller.protonTuningEnabled
                        onActivated: controller.setProtonTuning(currentValue)
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Text { text: "Windows version"; color: Theme.textMuted }
                    StyledComboBox {
                        Layout.fillWidth: true
                        model: controller.windowsOptions
                        currentIndex: root.optionIndex(controller.windowsOptions, controller.windowsVersion)
                        enabled: controller.interactionEnabled
                        onActivated: controller.setWindowsVersion(currentValue)
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.columnSpan: root.width >= 880 ? 2 : 1
                    Text { text: "Dependencies"; color: Theme.textMuted }
                    StyledComboBox {
                        Layout.fillWidth: true
                        model: controller.dependencyOptions
                        currentIndex: root.optionIndex(controller.dependencyOptions, controller.dependencyMode)
                        enabled: controller.interactionEnabled
                        onActivated: controller.setDependencyMode(currentValue)
                    }
                }
            }
        }

        Card {
            Layout.fillWidth: true
            SectionTitle {
                Layout.fillWidth: true
                title: "Isolated environment"
                description: "Leave this empty for RunEXE's stable per-application location."
            }
            RowLayout {
                Layout.fillWidth: true
                StyledTextField {
                    Layout.fillWidth: true
                    text: controller.prefix
                    placeholderText: "Automatic per-application path"
                    enabled: controller.interactionEnabled
                    onEditingFinished: controller.setPrefix(text)
                }
                AppButton {
                    text: "Choose folder"
                    enabled: controller.interactionEnabled && root.prefixDialog !== null
                    onClicked: root.prefixDialog.openAt(controller.prefix ? controller.localFileUrl(controller.prefix) : "")
                }
            }
            Text {
                Layout.fillWidth: true
                text: controller.environmentPreview
                color: Theme.textMuted
                wrapMode: Text.Wrap
            }
        }

        Card {
            Layout.fillWidth: true
            SectionTitle {
                Layout.fillWidth: true
                title: "Setup actions"
                description: "Prepare the environment without launching, or open runtime settings for this application."
            }
            GridLayout {
                Layout.fillWidth: true
                columns: root.width >= 760 ? 2 : 1
                columnSpacing: 10
                rowSpacing: 10
                AppButton {
                    Layout.fillWidth: true
                    Layout.columnSpan: root.width >= 760 ? 2 : 1
                    text: "Prepare automatically"
                    primary: true
                    enabled: controller.prepareEnabled
                    onClicked: controller.prepareSelectedEnvironment()
                }
                AppButton {
                    Layout.fillWidth: true
                    text: "Open Wine settings"
                    enabled: controller.wineConfigEnabled
                    onClicked: controller.openRuntimeSettings("wine")
                }
                AppButton {
                    Layout.fillWidth: true
                    text: "Open Proton settings"
                    enabled: controller.protonConfigEnabled
                    onClicked: controller.openRuntimeSettings("proton")
                }
            }
        }
    }
}
