import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

ApplicationWindow {
    id: window
    visible: true
    width: controller.initialWindowWidth
    height: controller.initialWindowHeight
    minimumWidth: 920
    minimumHeight: 680
    color: Theme.window
    title: pageTitles[currentPage].title + " — RunEXE"

    property int currentPage: 0
    readonly property bool compactSidebar: width < 1040
    readonly property var pageTitles: [
        { title: "Overview", description: "Inspect an application and launch it with a clear compatibility plan.", icon: "▶", section: "RUN", startsSection: true },
        { title: "Launch setup", description: "Choose how the selected application should run and prepare its environment.", icon: "⚙", section: "RUN", startsSection: false },
        { title: "Runtimes", description: "Inspect and manage Wine, Proton, Winetricks, Vulkan, and GPU readiness.", icon: "◉", section: "SYSTEM", startsSection: true },
        { title: "Applications", description: "Reopen recent software with its saved launch settings.", icon: "▦", section: "MANAGE", startsSection: true },
        { title: "Environments", description: "Inspect, configure, back up, and remove isolated application environments.", icon: "◇", section: "MANAGE", startsSection: false },
        { title: "Backups", description: "Restore or remove saved environment snapshots.", icon: "↶", section: "MANAGE", startsSection: false },
        { title: "Activity", description: "Review analysis, preparation, launch output, and errors.", icon: "≡", section: "SUPPORT", startsSection: true }
    ]
    readonly property var pageSources: [
        "OverviewPage.qml", "LaunchSetupPage.qml", "RuntimesPage.qml", "ApplicationsPage.qml",
        "EnvironmentsPage.qml", "BackupsPage.qml", "ActivityPage.qml"
    ]

    function showPage(index) {
        if (index < 0 || index >= pageSources.length || currentPage === index)
            return
        pageLoader.opacity = 0
        currentPage = index
        pageLoader.source = pageSources[index]
        pageLoader.opacity = 1
    }

    function cyclePage(offset) {
        showPage((currentPage + offset + pageSources.length) % pageSources.length)
    }

    onWidthChanged: saveSizeTimer.restart()
    onHeightChanged: saveSizeTimer.restart()
    onClosing: function(close) {
        close.accepted = false
        controller.saveWindowSize(width, height)
        controller.requestClose()
    }

    Timer {
        id: saveSizeTimer
        interval: 350
        repeat: false
        onTriggered: controller.saveWindowSize(window.width, window.height)
    }

    FileDialog {
        id: openDialog
        title: "Choose Windows software"
        fileMode: FileDialog.OpenFile
        nameFilters: ["Windows software (*.exe *.appx *.msix *.appxbundle *.msixbundle)", "All files (*)"]
        onAccepted: controller.analyzePath(selectedFile.toString())
    }

    FolderDialog {
        id: prefixDialog
        title: "Choose environment folder"
        onAccepted: controller.setPrefix(selectedFolder.toString())
    }

    FileDialog {
        id: exportDialog
        title: "Export RunEXE support report"
        fileMode: FileDialog.SaveFile
        selectedFile: controller.suggestedReportUrl
        defaultSuffix: "json"
        nameFilters: ["JSON report (*.json)", "All files (*)"]
        onAccepted: controller.exportSupportReport(selectedFile.toString())
    }

    Dialog {
        id: messageDialog
        property string severity: "info"
        property string body: ""
        anchors.centerIn: Overlay.overlay
        modal: true
        width: Math.min(480, window.width - 80)
        standardButtons: Dialog.Ok
        contentItem: Text {
            width: messageDialog.availableWidth
            text: messageDialog.body
            color: Theme.text
            wrapMode: Text.Wrap
        }
    }

    Dialog {
        id: closeDialog
        anchors.centerIn: Overlay.overlay
        modal: true
        title: "Application still running"
        standardButtons: Dialog.Yes | Dialog.Cancel
        onAccepted: controller.confirmClose()
        Text {
            width: 400
            text: "Closing RunEXE will also stop the launched application. Close anyway?"
            color: Theme.text
            wrapMode: Text.Wrap
        }
    }

    Connections {
        target: controller
        function onNavigateRequested(index) { window.showPage(index) }
        function onProfileFocusRequested() {
            window.showPage(0)
            Qt.callLater(function() {
                if (pageLoader.item && pageLoader.item.focusProfile)
                    pageLoader.item.focusProfile()
            })
        }
        function onMessageRequested(severity, title, body) {
            messageDialog.severity = severity
            messageDialog.title = title
            messageDialog.body = body
            messageDialog.open()
        }
        function onCloseConfirmationRequested() { closeDialog.open() }
    }

    Shortcut { sequence: "Ctrl+O"; context: Qt.ApplicationShortcut; onActivated: openDialog.open() }
    Shortcut {
        sequence: "Ctrl+R"
        context: Qt.ApplicationShortcut
        onActivated: controller.sourceSelected ? controller.analyzeSelected() : openDialog.open()
    }
    Shortcut { sequence: "Ctrl+Return"; context: Qt.ApplicationShortcut; onActivated: controller.launchApplication() }
    Shortcut { sequence: "Ctrl+Enter"; context: Qt.ApplicationShortcut; onActivated: controller.launchApplication() }
    Shortcut { sequence: "Ctrl+Tab"; context: Qt.ApplicationShortcut; onActivated: window.cyclePage(1) }
    Shortcut { sequence: "Ctrl+Shift+Tab"; context: Qt.ApplicationShortcut; onActivated: window.cyclePage(-1) }
    Shortcut { sequence: "Ctrl+L"; context: Qt.ApplicationShortcut; onActivated: window.showPage(6) }
    Shortcut { sequence: "Ctrl+Shift+L"; context: Qt.ApplicationShortcut; onActivated: window.showPage(3) }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            id: sidebar
            Layout.fillHeight: true
            Layout.preferredWidth: window.compactSidebar ? 76 : 204
            color: Theme.sidebar
            border.color: Theme.borderSoft
            border.width: 0

            Behavior on Layout.preferredWidth { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    spacing: 9
                    Image {
                        source: "../../assets/runexe-logo.png"
                        sourceSize.width: 27
                        sourceSize.height: 27
                        fillMode: Image.PreserveAspectFit
                    }
                    Text {
                        visible: !window.compactSidebar
                        text: "RunEXE"
                        color: Theme.text
                        font.pixelSize: 18
                        font.weight: Font.DemiBold
                    }
                }

                Repeater {
                    model: window.pageTitles
                    delegate: ColumnLayout {
                        id: navEntry
                        required property int index
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 4

                        Text {
                            Layout.fillWidth: true
                            visible: navEntry.modelData.startsSection && !window.compactSidebar
                            text: navEntry.modelData.section
                            color: Theme.textMuted
                            font.pixelSize: 9
                            font.weight: Font.DemiBold
                            topPadding: navEntry.index === 0 ? 6 : 8
                        }

                        Button {
                            id: navButton
                            Layout.fillWidth: true
                            Layout.preferredHeight: 42
                            flat: true
                            checkable: true
                            checked: window.currentPage === navEntry.index
                            ToolTip.visible: hovered && window.compactSidebar
                            ToolTip.text: navEntry.modelData.title + "\n" + navEntry.modelData.description
                            Accessible.name: navEntry.modelData.title
                            onClicked: window.showPage(navEntry.index)

                            contentItem: RowLayout {
                                spacing: 10
                                Text {
                                    Layout.preferredWidth: 26
                                    text: navEntry.modelData.icon
                                    color: navButton.checked ? Theme.accent : Theme.textMuted
                                    font.pixelSize: 17
                                    horizontalAlignment: Text.AlignHCenter
                                }
                                Text {
                                    Layout.fillWidth: true
                                    visible: !window.compactSidebar
                                    text: navEntry.modelData.title
                                    color: navButton.checked ? Theme.text : Theme.textMuted
                                    font.weight: navButton.checked ? Font.DemiBold : Font.Normal
                                    elide: Text.ElideRight
                                }
                            }
                            background: Rectangle {
                                radius: 8
                                color: navButton.checked ? Theme.surfaceRaised : (navButton.hovered ? Theme.surface : "transparent")
                                border.color: navButton.activeFocus ? Theme.accent : "transparent"
                                border.width: navButton.activeFocus ? 1 : 0
                                Rectangle {
                                    visible: navButton.checked
                                    width: 3
                                    height: parent.height - 12
                                    anchors.left: parent.left
                                    anchors.verticalCenter: parent.verticalCenter
                                    radius: 2
                                    color: Theme.accent
                                }
                            }
                        }
                    }
                }

                Item { Layout.fillHeight: true }
                Text {
                    Layout.fillWidth: true
                    text: window.compactSidebar ? "v" + controller.version : "RunEXE  v" + controller.version
                    color: Theme.textMuted
                    font.pixelSize: 10
                    horizontalAlignment: window.compactSidebar ? Text.AlignHCenter : Text.AlignLeft
                    elide: Text.ElideRight
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.window

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 74
                    color: Theme.window
                    border.color: Theme.borderSoft
                    border.width: 0

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 24
                        anchors.rightMargin: 24
                        spacing: 10

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                Layout.fillWidth: true
                                text: window.pageTitles[window.currentPage].title
                                color: Theme.text
                                font.pixelSize: 20
                                font.weight: Font.DemiBold
                            }
                            Text {
                                Layout.fillWidth: true
                                visible: window.width >= 980
                                text: window.pageTitles[window.currentPage].description
                                color: Theme.textMuted
                                font.pixelSize: 11
                                elide: Text.ElideRight
                            }
                        }

                        AppButton { text: "Open…"; enabled: controller.interactionEnabled; onClicked: openDialog.open() }
                        AppButton { text: "Analyze"; enabled: controller.analyzeEnabled; onClicked: controller.analyzeSelected() }
                        Rectangle {
                            implicitWidth: statusText.implicitWidth + 22
                            implicitHeight: 30
                            radius: 15
                            color: "transparent"
                            border.color: controller.headerState === "ready" ? Theme.success
                                          : controller.headerState === "error" ? Theme.error
                                          : controller.headerState === "warning" ? Theme.warning : Theme.border
                            Text {
                                id: statusText
                                anchors.centerIn: parent
                                text: controller.headerStatus
                                color: parent.border.color
                                font.pixelSize: 11
                            }
                        }
                        AppButton { text: "Launch"; primary: true; enabled: controller.launchEnabled; onClicked: controller.launchApplication() }
                    }

                    Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.borderSoft }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: controller.busy ? 3 : 0
                    color: Theme.accent
                    visible: height > 0
                    Behavior on Layout.preferredHeight { NumberAnimation { duration: 120 } }
                    SequentialAnimation on opacity {
                        running: controller.busy
                        loops: Animation.Infinite
                        NumberAnimation { from: 0.35; to: 1.0; duration: 650 }
                        NumberAnimation { from: 1.0; to: 0.35; duration: 650 }
                    }
                }

                Loader {
                    id: pageLoader
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    source: window.pageSources[window.currentPage]
                    asynchronous: false
                    opacity: 1
                    Behavior on opacity { NumberAnimation { duration: 110 } }
                    onLoaded: {
                        if (!item) return
                        if (item.openFileDialog !== undefined) item.openFileDialog = openDialog
                        if (item.prefixDialog !== undefined) item.prefixDialog = prefixDialog
                        if (item.exportDialog !== undefined) item.exportDialog = exportDialog
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    color: Theme.window
                    border.color: Theme.borderSoft
                    border.width: 0
                    Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; height: 1; color: Theme.borderSoft }
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 20
                        anchors.rightMargin: 20
                        Text { Layout.fillWidth: true; text: controller.taskStatus; color: Theme.textMuted; font.pixelSize: 11; elide: Text.ElideRight }
                        Text { Layout.fillWidth: true; text: controller.environmentStatus; color: Theme.textMuted; font.pixelSize: 11; horizontalAlignment: Text.AlignRight; elide: Text.ElideLeft }
                    }
                }
            }
        }
    }
}
