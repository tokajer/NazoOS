# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Sourced by gamescope-session-plus after its own sessions.d/steam.
# mangoapp dies by abort when gamescope takes its X connection away, which
# leaves a coredump at every exit. End it first, the parent before the child:
# the parent is the session's loop that restarts mangoapp.

post_client_shutdown() {
  local pid
  for pid in $(pgrep -x -u "$(id -u)" mangoapp); do
    kill $(ps -o ppid= -p "$pid") "$pid"
  done
}
