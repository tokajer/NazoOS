// SPDX-FileCopyrightText: 2026 The NazoOS Contributors
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Slideshow shown while NazoOS is being installed

import QtQuick
import calamares.slideshow 1.0

Presentation {
    id: presentation

    Slide {
        Image {
            anchors.fill: parent
            source: "file:///usr/share/wallpapers/NazoOS/contents/images/1920x1080.png"
            fillMode: Image.PreserveAspectCrop
        }
        Text {
            anchors.centerIn: parent
            text: qsTr("NazoOS is being installed. This takes a few minutes.")
            color: "#FFFFFF"
            font.pixelSize: 24
            wrapMode: Text.WordWrap
            width: parent.width * 0.8
            horizontalAlignment: Text.AlignHCenter
        }
    }

    // Required by slideshowAPI 2
    function onActivate() { }
    function onLeave() { }
}
