#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""What should happen with the release ISO in :release now? (ADR 0025)

The build of repository "images" stays disabled, so the last built ISO
stays as it is ("frozen"). An ISO built against openSUSE:Factory/snapshot
is often one snapshot ahead of the mirrors; if OBS kept rebuilding it on
every snapshot, it would never be publishable (2026-10-24). A frozen ISO
does not move, so the mirrors catch up with it.

- No ISO, or it is stale (its nazoos-* packages differ from :release, or
  its Tumbleweed snapshot is REFRESH_DAYS behind the mirrors): build=enable
  (the workflow enables the build and starts a rebuild).
- Build enabled and finished: build=disable (freeze it again).
- Frozen ISO not published yet and the mirrors have its snapshot or a
  newer one (an ISO newer than the mirrors breaks fresh installs, see
  notes/kiwi.md): publish=true.
Prints key=value lines for $GITHUB_OUTPUT: build=enable|disable|keep,
publish=true|false, sha=<sha256 of the built ISO>, reason=<text>.
Needs OBS_USER/OBS_PASSWORD (any account can read public projects).
"""

import base64
import datetime
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
PACKAGES = f"{API}/build/{PROJECT}/openSUSE_Tumbleweed/x86_64"
PUBLISHED = ("https://download.opensuse.org/repositories/home:/Tokajer:/"
             "nazoos:/release/images/iso/NazoOS.x86_64-release.iso.sha256")
MIRROR = "https://download.opensuse.org/tumbleweed/repo/oss/media.1/products"
REFRESH_DAYS = 7
# Build states that end by themselves; "disabled" = frozen
RUNNING = {"scheduled", "dispatching", "building", "signing", "finished",
           "blocked"}


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


def days_between(old, new):
    parse = datetime.date.fromisoformat
    return (parse(f"{new[:4]}-{new[4:6]}-{new[6:]}")
            - parse(f"{old[:4]}-{old[4:6]}-{old[6:]}")).days


def rpm_nvr(filename):
    """("nazoos-branding-plymouth", "0.1.0+git…-102.1") from its .rpm."""
    m = re.fullmatch(r"(.+)-([^-]+-[^-]+)\.noarch\.rpm", filename)
    return (m.group(1), m.group(2)) if m else None


def released_packages():
    """{name: version-release} of the nazoos-* RPMs in :release."""
    found = {}
    sources = ET.fromstring(get(PACKAGES)).findall("entry")
    for src in (e.get("name") for e in sources):
        if not src.startswith("nazoos-") or src.startswith("nazoos-image"):
            continue
        for b in ET.fromstring(get(f"{PACKAGES}/{src}")).findall("binary"):
            nvr = rpm_nvr(b.get("filename"))
            if nvr:
                found[nvr[0]] = nvr[1]
    return found


def collect():
    """Everything decide() needs, read from OBS and the mirrors."""
    result = ET.fromstring(get(f"{API}/build/{PROJECT}/_result?"
                               f"package={PACKAGE}&repository=images"
                               "&multibuild=1"))
    res = result.find("result")
    status = res.find("status") if res is not None else None
    state = {"code": status.get("code") if status is not None else "missing",
             "dirty": res is not None and bool(res.get("dirty"))}
    names = [b.get("filename") for b in
             ET.fromstring(get(BINARIES)).findall("binary")]
    iso = next((n for n in names if n.endswith(".iso")), None)
    cdx = next((n for n in names if n.endswith(".cdx.json")), None)
    state["iso"] = iso if iso and cdx else None
    if state["iso"]:
        state["sha"] = get(f"{BINARIES}/{iso}.sha256").decode().split()[0]
        components = json.loads(get(f"{BINARIES}/{cdx}")).get("components", [])
        state["image_tw"] = next((c["version"] for c in components
                                  if c.get("name") == "openSUSE-release"), "")
        state["image_pkgs"] = {c["name"]: c["version"] for c in components
                               if c.get("name", "").startswith("nazoos-")}
    try:
        state["published"] = get(PUBLISHED, auth=False).decode().split()[0]
    except (urllib.error.URLError, IndexError):
        state["published"] = ""
    state["mirror"] = snapshot_date(get(MIRROR, auth=False).decode())
    state["released"] = released_packages()
    return state


def decide(s):
    """(build, publish, reason) for the state from collect()."""
    code = s["code"]
    if code in RUNNING or s["dirty"]:
        return "keep", False, f"image build running ({code})"
    if code not in ("succeeded", "disabled"):
        # failed/unresolvable: leave the build on, OBS retries on changes
        return "keep", False, f"image build {code}, nothing to publish"
    # A finished build is frozen again in any case
    build = "disable" if code == "succeeded" else "keep"
    if not s["iso"]:
        return "enable", False, "no ISO in :release, building one"

    image = snapshot_date(s["image_tw"])
    mirror = s["mirror"]
    if not image or not mirror:
        return build, False, f"snapshot unknown (image {s['image_tw']!r})"
    old = sorted(n for n, v in s["image_pkgs"].items()
                 if n in s["released"] and s["released"][n] != v)
    if old:
        return "enable", False, ("ISO has older NazoOS packages than "
                                 f":release ({', '.join(old)}), rebuilding")
    if days_between(image, mirror) >= REFRESH_DAYS:
        return "enable", False, (f"ISO has Tumbleweed {image}, mirrors "
                                 f"{mirror}: refreshing")
    if s["sha"] == s["published"]:
        return build, False, f"{s['iso']} is already published"
    if image > mirror:
        return build, False, (f"{s['iso']} has Tumbleweed {image}, mirrors "
                              f"only {mirror}: waiting")
    return build, True, f"{s['iso']} (Tumbleweed {image}, mirrors {mirror})"


def main():
    state = collect()
    build, publish, reason = decide(state)
    print(f"build={build}")
    print(f"publish={'true' if publish else 'false'}")
    print(f"sha={state.get('sha', '')}")
    print(f"reason={reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
