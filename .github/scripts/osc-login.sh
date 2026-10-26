#!/bin/bash
# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Writes the oscrc for the CI bot from OBS_USER / OBS_PASSWORD (kernel-update.yml,
# jobs check and upload).

set -euo pipefail

[ -n "${OBS_USER-}" ] && [ -n "${OBS_PASSWORD-}" ] ||
  { echo "::error::secrets OBS_USER / OBS_PASSWORD missing"; exit 1; }
umask 077
mkdir -p ~/.config/osc
printf '%s\n' \
  '[general]' \
  'apiurl = https://api.opensuse.org' \
  '[https://api.opensuse.org]' \
  "user = $OBS_USER" \
  "pass = $OBS_PASSWORD" \
  'credentials_mgr_class = osc.credentials.PlaintextConfigFileCredentialsManager' \
  > ~/.config/osc/oscrc
