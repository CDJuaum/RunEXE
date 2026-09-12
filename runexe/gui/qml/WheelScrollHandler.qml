import QtQuick

WheelHandler {
    id: root

    required property var flickable
    property real step: 54

    target: null
    acceptedDevices: PointerDevice.Mouse
    blocking: true

    onWheel: function(event) {
        const minimum = flickable.originY
        const maximum = Math.max(minimum, minimum + flickable.contentHeight - flickable.height)
        if (maximum <= minimum) {
            event.accepted = false
            return
        }

        const notches = event.angleDelta.y / 120
        const delta = notches !== 0 ? notches * step : event.pixelDelta.y
        flickable.contentY = Math.max(minimum, Math.min(maximum, flickable.contentY - delta))
        event.accepted = true
    }
}
