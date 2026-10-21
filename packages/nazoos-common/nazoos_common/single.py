# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""One window per app and user. A second start (autostart and Plasma's
session restore at the same login, a "Fix" button, a KRunner or menu
start) hands its page to the running window and quits.

The first process holds a flock for its whole life (freed by the kernel
when it dies, so no stale lock) and listens on a local socket; the lock
decides who is first even when two starts come within milliseconds.

On Wayland only the launcher (KRunner, the menu, a notification) may
give focus: it passes an XDG activation token to the process it starts.
The second process forwards that token, the first one puts it into its
environment, where Qt takes it on the next requestActivate()."""

import fcntl
import os
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

TOKEN = "XDG_ACTIVATION_TOKEN"


def _runtime_dir():
    return Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")


class Instance(QObject):
    # Page name from a later start; "" = only bring the window to the front
    pageRequested = Signal(str)

    def __init__(self, name):
        super().__init__()
        self._name = name
        self._socket_path = str(_runtime_dir() / f"{name}.socket")
        self._lock_file = None
        self._server = None

    def acquire(self):
        """True if this process is the first one."""
        f = open(_runtime_dir() / f"{self._name}.lock", "w")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            f.close()
            return False
        self._lock_file = f
        return True

    def listen(self):
        # A socket file left by a crashed instance; we hold the lock now
        QLocalServer.removeServer(self._socket_path)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_connection)
        self._server.listen(self._socket_path)

    def send(self, page, timeout=3.0):
        """Hand the page (and our activation token) to the first instance.
        It may still be starting (lock taken, not listening yet), so retry
        for a moment."""
        line = f"{page}\t{os.environ.get(TOKEN, '')}\n"
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            sock = QLocalSocket()
            sock.connectToServer(self._socket_path)
            if sock.waitForConnected(200):
                sock.write(line.encode())
                sock.waitForBytesWritten(500)
                sock.disconnectFromServer()
                return True
            time.sleep(0.1)
        return False

    def _on_connection(self):
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            sock.readyRead.connect(lambda s=sock: self._read(s))
            sock.disconnected.connect(sock.deleteLater)

    def _read(self, sock):
        while sock.canReadLine():
            text = bytes(sock.readLine()).decode(errors="replace").strip("\n")
            page, _, token = text.partition("\t")
            if token:
                # Qt reads (and clears) it in requestActivate()
                os.environ[TOKEN] = token
            self.pageRequested.emit(page.strip())
