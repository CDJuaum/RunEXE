import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    objectName: "settingsPage"

    function optionIndex(options, value) {
        for (let i = 0; i < options.length; ++i)
            if (options[i].value === value) return i
        return 0
    }

    function selectTab(section) {
        const target = String(section || "general").toLowerCase()
        if (target === "runtimes") tabs.currentIndex = 1
        else if (target === "environments") tabs.currentIndex = 2
        else tabs.currentIndex = 0
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.pageMargin
        spacing: 12

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            radius: 10
            color: Theme.surface
            border.color: Theme.borderSoft

            TabBar {
                id: tabs
                anchors.fill: parent
                anchors.margins: 5
                spacing: 4
                background: Item {}

                Repeater {
                    model: ["General", "Runtimes", "Environments"]
                    TabButton {
                        required property int index
                        required property string modelData
                        text: modelData
                        HoverHandler { cursorShape: Qt.ArrowCursor }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Theme.text : Theme.textMuted
                            font.weight: parent.checked ? Font.DemiBold : Font.Normal
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            radius: 7
                            color: parent.checked ? Theme.surfaceRaised : (parent.hovered ? Theme.field : "transparent")
                            border.color: parent.checked ? Theme.border : "transparent"
                        }
                    }
                }
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabs.currentIndex

            Flickable {
                id: generalPage
                contentWidth: width
                contentHeight: generalContent.implicitHeight + 16
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                WheelScrollHandler { flickable: generalPage }

                ColumnLayout {
                    id: generalContent
                    width: generalPage.width
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

            RuntimesPage {}
            EnvironmentsPage {}
        }
    }
}
