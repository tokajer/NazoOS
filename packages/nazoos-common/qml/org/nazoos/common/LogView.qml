// SPDX-FileCopyrightText: 2026 The NazoOS Contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

// Log text that follows new lines like `tail -f`, unless the user scrolled
// up to read; scrolling back to the end follows again. The caller sets the
// size: a view as tall as its text would grow a Kirigami.Dialog with every
// line (binding loop, and only the dialog's outer view could scroll)
QQC2.ScrollView {
    id: root

    property string text: ""
    property real lastHeight: 0

    function toEnd() {
        const f = contentItem
        f.contentY = Math.max(0, f.contentHeight - f.height)
    }

    Connections {
        target: root.contentItem
        function onContentHeightChanged() {
            const f = root.contentItem
            if (f.contentY + f.height >= root.lastHeight - Kirigami.Units.gridUnit * 2)
                root.toEnd()
            root.lastHeight = f.contentHeight
        }
    }

    // TextEdit, not TextArea: a TextArea scrolls back to its cursor
    // (the start) whenever the text changes
    TextEdit {
        width: root.availableWidth
        padding: Kirigami.Units.smallSpacing
        readOnly: true
        selectByMouse: true
        wrapMode: TextEdit.Wrap
        font.family: "monospace"
        color: Kirigami.Theme.textColor
        selectionColor: Kirigami.Theme.highlightColor
        selectedTextColor: Kirigami.Theme.highlightedTextColor
        text: root.text
    }
}
