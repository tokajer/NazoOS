#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Should the release ISO built in :release be published now? (ADR 0025)

Yes when OBS has a successfully built nazoos-image:release that differs
from the published one, and the Tumbleweed mirrors have its snapshot or a
newer one (an ISO newer than the mirrors breaks fresh installs, see
notes/kiwi.md). Prints key=value lines for $GITHUB_OUTPUT: publish=true|
false, sha=<sha256 of the built ISO>, reason=<text>.
Needs OBS_USER/OBS_PASSWORD (any account can read public projects).
"""

import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

API = "https://api.opensuse.org"
PROJECT = "home:Tokajer:nazoos:release"
PACKAGE = "nazoos-image:release"
BINARIES = f"{API}/build/{PROJECT}/images/x86_64/{PACKAGE}"
PUBLISHED = ("https://download.opensuse.org/repositories/home:/Tokajer:/"
             "nazoos:/release/images/iso/NazoOS.x86_64-release.iso.sha256")
MIRROR = "https://download.opensuse.org/tumbleweed/repo/oss/media.1/products"


def get(url, auth=True):
    req = urllib.request.Request(url)
    if auth:
        token = f"{os.environ['OBS_USER']}:{os.environ['OBS_PASSWORD']}"
        req.add_header("Authorization",
                       "Basic " + base64.b64encode(token.encode()).decode())
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def snapshot_date(text):
    """20261017 from "20261017-4356.1" or "openSUSE 20261017-1"."""
    m = re.search(r"\b(\d{8})\b", text)
    return m.group(1) if m else None


def decide():
    result = ET.fromstring(get(f"{API}/build/{PROJECT}/_result?"
                               f"package={PACKAGE}&repository=images"
                               "&multibuild=1"))
    res = result.find("result")
    status = res.find("status") if res is not None else None
    code = status.get("code") if status is not None else "missing"
    if res is None or res.get("dirty") or code != "succeeded":
        return False, "", f"image not ready in :release ({code})"

    names = [b.get("filename") for b in
             ET.fromstring(get(BINARIES)).findall("binary")]
    iso = next((n for n in names if n.endswith(".iso")), None)
    cdx = next((n for n in names if n.endswith(".cdx.json")), None)
    if not iso or not cdx:
        return False, "", "no ISO/SBOM in the build results"
    sha = get(f"{BINARIES}/{iso}.sha256").decode().split()[0]

    try:
        published = get(PUBLISHED, auth=False).decode().split()[0]
    except (urllib.error.URLError, IndexError):
        published = ""
    if sha == published:
        return False, sha, f"{iso} is already published"

    sbom = json.loads(get(f"{BINARIES}/{cdx}"))
    tw = next((c["version"] for c in sbom.get("components", [])
               if c.get("name") == "openSUSE-release"), "")
    image_date = snapshot_date(tw)
    mirror_date = snapshot_date(get(MIRROR, auth=False).decode())
    if not image_date or not mirror_date:
        return False, sha, f"snapshot unknown (image {tw!r})"
    if image_date > mirror_date:
        return False, sha, (f"{iso} has Tumbleweed {image_date}, mirrors "
                            f"only {mirror_date}: waiting")
    return True, sha, (f"{iso} (Tumbleweed {image_date}, mirrors "
                       f"{mirror_date})")


def main():
    publish, sha, reason = decide()
    print(f"publish={'true' if publish else 'false'}")
    print(f"sha={sha}")
    print(f"reason={reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
