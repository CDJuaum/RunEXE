import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Flickable {
    id: root
    objectName: "settingsPage"
    contentWidth: width
    contentHeight: content.implicitHeight + 32
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
    WheelScrollHandler { flickable: root }

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
                title: "Appearance"
                description: "Choose how RunEXE looks without changing your desktop theme."
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 14
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text { text: "Theme"; color: Theme.text; font.weight: Font.DemiBold }
                    Text {
                        Layout.fillWidth: true
                        text: "System follows your desktop. Light and Dark stay fixed until you change them."
                        color: Theme.textMuted
                        font.pixelSize: 11
                        wrapMode: Text.Wrap
                    }
                }
                StyledComboBox {
                    Layout.preferredWidth: 220
                    model: controller.themeOptions
                    currentIndex: root.optionIndex(controller.themeOptions, controller.themeMode)
                    onActivated: controller.setThemeMode(currentValue)
                }
            }
        }

        Card {
            Layout.fillWidth: true
            SectionTitle {
                Layout.fillWidth: true
                title: "Notifications"
                description: "Control whether RunEXE sends desktop notifications when background work finishes."
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 14
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text { text: "Desktop notifications"; color: Theme.text; font.weight: Font.DemiBold }
                    Text {
                        Layout.fillWidth: true
                        text: controller.notificationsEnabled ? "Enabled for installs, preparation, backups, and launches." : "Disabled. Status is still shown inside RunEXE."
                        color: Theme.textMuted
                        font.pixelSize: 11
                        wrapMode: Text.Wrap
                    }
                }
                AppButton {
                    text: controller.notificationsEnabled ? "Enabled" : "Disabled"
                    primary: controller.notificationsEnabled
                    onClicked: controller.setNotificationsEnabled(!controller.notificationsEnabled)
                }
            }
        }

        Card {
            Layout.fillWidth: true
            SectionTitle {
                Layout.fillWidth: true
                title: "About"
                description: "Application information for this RunEXE installation."
            }
            RowLayout {
                Layout.fillWidth: true
                Text { text: "Version"; color: Theme.textMuted }
                Item { Layout.fillWidth: true }
                Text { text: "RunEXE " + controller.version; color: Theme.text; font.weight: Font.DemiBold }
            }
        }
    }
}
