import QtQuick
import QtQuick.Controls

ListView {
    id: root
    clip: true
    spacing: 6
    focus: true
    keyNavigationEnabled: true
    boundsBehavior: Flickable.StopAtBounds
    reuseItems: true
    highlightMoveDuration: 120
    ScrollBar.vertical: ScrollBar {
        id: verticalBar
        policy: ScrollBar.AsNeeded
        active: hovered || pressed || root.moving
    }
}
