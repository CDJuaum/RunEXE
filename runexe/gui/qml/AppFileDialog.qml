import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt.labs.folderlistmodel

AppDialog {
    id: root

    enum Mode { OpenFile, OpenFolder, SaveFile }

    property int mode: AppFileDialog.OpenFile
    property var fileNameFilters: ["*"]
    property string initialUrl: ""
    property string defaultFileName: ""
    property string acceptLabel: mode === AppFileDialog.SaveFile ? "Save" : (mode === AppFileDialog.OpenFolder ? "Choose folder" : "Open")
    signal acceptedUrl(string url)

    width: Math.min(960, Overlay.overlay ? Overlay.overlay.width - 56 : 960)
    height: Math.min(680, Overlay.overlay ? Overlay.overlay.height - 56 : 680)
    padding: 0
    closePolicy: Popup.CloseOnEscape

    property string selectedUrl: ""
    property string selectedName: ""
    property bool showAllFiles: false

    function openAt(url) {
        selectedUrl = ""
        selectedName = ""
        saveName.text = defaultFileName
        if (url && url.length > 0)
            folderModel.folder = url
        else if (controller.filePickerLocations.length > 0)
            folderModel.folder = controller.filePickerLocations[0].url
        open()
    }

    function acceptSelection() {
        if (mode === AppFileDialog.OpenFolder) {
            acceptedUrl(folderModel.folder.toString())
            close()
            return
        }
        if (mode === AppFileDialog.SaveFile) {
            const name = saveName.text.trim()
            if (!name.length)
                return
            acceptedUrl(controller.joinFileUrl(folderModel.folder.toString(), name))
            close()
            return
        }
        if (selectedUrl.length > 0) {
            acceptedUrl(selectedUrl)
            close()
        }
    }

    FolderListModel {
        id: folderModel
        showDirs: true
        showFiles: root.mode !== AppFileDialog.OpenFolder
        showDirsFirst: true
        showDotAndDotDot: false
        nameFilters: root.showAllFiles || root.mode === AppFileDialog.OpenFolder ? ["*"] : root.fileNameFilters
        sortField: FolderListModel.Name
        sortReversed: false
    }

    contentItem: ColumnLayout {
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 50
            color: Theme.surfaceRaised

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                spacing: 8

                AppButton {
                    text: "↑"
                    implicitWidth: 42
                    enabled: folderModel.parentFolder && folderModel.parentFolder.toString() !== folderModel.folder.toString()
                    ToolTip.visible: hovered
                    ToolTip.text: "Parent folder"
                    onClicked: {
                        root.selectedUrl = ""
                        root.selectedName = ""
                        folderModel.folder = folderModel.parentFolder
                    }
                }

                StyledTextField {
                    id: pathField
                    Layout.fillWidth: true
                    text: controller.localPathFromUrl(folderModel.folder.toString())
                    selectByMouse: true
                    onAccepted: {
                        root.selectedUrl = ""
                        root.selectedName = ""
                        folderModel.folder = controller.localFileUrl(text)
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.surface

            RowLayout {
                anchors.fill: parent
                spacing: 0

                Rectangle {
                    Layout.fillHeight: true
                    Layout.preferredWidth: 190
                    color: Theme.field

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 6

                        Text {
                            Layout.fillWidth: true
                            text: "PLACES"
                            color: Theme.textMuted
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                            leftPadding: 6
                            topPadding: 4
                        }

                        ListView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            spacing: 3
                            model: controller.filePickerLocations
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            delegate: Button {
                                required property var modelData
                                width: ListView.view.width
                                height: 38
                                flat: true
                                onClicked: {
                                    root.selectedUrl = ""
                                    root.selectedName = ""
                                    folderModel.folder = modelData.url
                                }
                                contentItem: Text {
                                    text: modelData.label
                                    color: Theme.text
                                    elide: Text.ElideRight
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: 8
                                }
                                background: Rectangle {
                                    radius: 7
                                    color: parent.hovered ? Theme.surfaceRaised : "transparent"
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                    color: Theme.borderSoft
                }

                ListView {
                    id: fileList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.margins: 10
                    clip: true
                    spacing: 4
                    model: folderModel
                    currentIndex: -1
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    WheelScrollHandler { flickable: fileList }

                    delegate: ItemDelegate {
                        required property int index
                        required property string fileName
                        required property url fileUrl
                        required property bool fileIsDir
                        width: ListView.view.width
                        height: 42
                        highlighted: fileList.currentIndex === index

                        onClicked: {
                            fileList.currentIndex = index
                            root.selectedUrl = fileUrl.toString()
                            root.selectedName = fileName
                            if (root.mode === AppFileDialog.SaveFile && !fileIsDir)
                                saveName.text = fileName
                        }
                        onDoubleClicked: {
                            if (fileIsDir) {
                                root.selectedUrl = ""
                                root.selectedName = ""
                                folderModel.folder = fileUrl
                                fileList.currentIndex = -1
                            } else if (root.mode === AppFileDialog.OpenFile) {
                                root.selectedUrl = fileUrl.toString()
                                root.acceptSelection()
                            }
                        }

                        contentItem: RowLayout {
                            spacing: 10
                            Text {
                                Layout.preferredWidth: 28
                                text: fileIsDir ? "▰" : "▱"
                                color: fileIsDir ? Theme.accent : Theme.textMuted
                                font.pixelSize: 15
                                horizontalAlignment: Text.AlignHCenter
                            }
                            Text {
                                Layout.fillWidth: true
                                text: fileName
                                color: Theme.text
                                elide: Text.ElideRight
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                        background: Rectangle {
                            radius: 7
                            color: parent.highlighted ? Theme.surfaceRaised : (parent.hovered ? Theme.field : "transparent")
                            border.color: parent.highlighted ? Theme.accent : "transparent"
                            border.width: parent.highlighted ? 1 : 0
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.mode === AppFileDialog.OpenFolder ? 58 : 76
            color: Theme.surfaceRaised

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 6

                RowLayout {
                    Layout.fillWidth: true
                    visible: root.mode === AppFileDialog.SaveFile
                    spacing: 8
                    Text { text: "File name"; color: Theme.textMuted; font.pixelSize: 11 }
                    StyledTextField {
                        id: saveName
                        Layout.fillWidth: true
                        onAccepted: root.acceptSelection()
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    CheckBox {
                        visible: root.mode === AppFileDialog.OpenFile && root.fileNameFilters.length > 0 && root.fileNameFilters[0] !== "*"
                        text: "Show all files"
                        checked: root.showAllFiles
                        onToggled: root.showAllFiles = checked
                        palette.windowText: Theme.textMuted
                    }
                    Item { Layout.fillWidth: true }
                    AppButton { text: "Cancel"; onClicked: root.close() }
                    AppButton {
                        text: root.acceptLabel
                        primary: true
                        enabled: root.mode === AppFileDialog.OpenFolder
                                 || (root.mode === AppFileDialog.SaveFile && saveName.text.trim().length > 0)
                                 || root.selectedUrl.length > 0
                        onClicked: root.acceptSelection()
                    }
                }
            }
        }
    }
}
