# Disclaimer

## Short version

> NazoOS is a hobby project, provided "as is" without warranty of any kind. Use it at your own risk and keep backups of your data. NazoOS is independent and not affiliated with openSUSE, SUSE or any other company.

The short version above is shown in the installer and in the NazoOS Welcome app.

## No warranty

NazoOS is developed in spare time by volunteers. To the extent permitted by applicable law, it comes without any warranty and the contributors are not liable for damages arising from its use. This includes data loss, hardware issues and failed updates. Sections 15 and 16 of the [GNU General Public License v3](LICENSES/GPL-3.0-or-later.txt) apply.

NazoOS changes system defaults for gaming performance. It uses a patched kernel, adjusted sysctl and udev settings and optional third-party drivers. These changes are tested, but they may behave differently on your hardware.

Recommendations:

- Keep backups of important data.
- Use snapshots: NazoOS creates a Btrfs snapshot before each update. You can roll back from the GRUB boot menu or with Btrfs Assistant.

## Independence

NazoOS is based on openSUSE Tumbleweed but is **not** an official openSUSE product. It is not affiliated with, endorsed by or supported by the openSUSE Project or SUSE LLC. Please report NazoOS problems to [NazoOS](https://github.com/tokajer/NazoOS/issues), not to openSUSE.

NazoOS is also not affiliated with Valve, NVIDIA, AMD, KDE or any other vendor whose software it ships or supports. All trademarks belong to their respective owners.

## Third-party repositories

NazoOS uses the official openSUSE repositories. During first-time setup you can **optionally** enable:

- **Packman**: a third-party repository with multimedia codecs (e.g. full FFmpeg, GStreamer plugins, VA-API drivers). Packman is run by an independent community, not by NazoOS or openSUSE. Some codecs may be subject to software patents in certain countries. You are responsible for checking whether you may use them where you live.
- **NVIDIA**: NVIDIA's repository for its graphics drivers. These drivers are subject to NVIDIA's own license terms.

Nothing from these repositories is installed unless you choose to enable it.

## Your rights

This notice does not restrict any rights granted by the licenses in [`LICENSES/`](LICENSES/). Where this notice and a license disagree, the license prevails. Use of the NazoOS name and logo is covered separately in [`TRADEMARK.md`](TRADEMARK.md).
