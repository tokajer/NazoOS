#!/bin/bash
# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# curl with the OBS login from OBS_USER / OBS_PASSWORD.
# The password goes to curl on stdin (-K -), never on a command line.
set -euo pipefail
user=${OBS_USER//\\/\\\\}
pass=${OBS_PASSWORD//\\/\\\\}
user=${user//\"/\\\"}
pass=${pass//\"/\\\"}
printf 'user = "%s:%s"\n' "$user" "$pass" | curl -K - "$@"
