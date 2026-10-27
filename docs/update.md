# NazoOS Update and rollback

NazoOS Update keeps the system and your Flatpak apps up to date. You never need a terminal for it. Open it from the application menu: **NazoOS Update**.

## Notifications

NazoOS checks for updates in the background every few hours. When updates are ready, a notification appears. Click **Update now** to open the window.

Other notifications:

| Notification | What it means | What to do |
|---|---|---|
| Updates available | New versions of system packages or Flatpak apps | **Update now** |
| Restart required | Updates were installed that need a restart (kernel, graphics driver, desktop) | Restart when it suits you |
| Update needs your decision | Two packages conflict, the update cannot run on its own | **Fix** opens the window; **Open Myrlyn** shows the conflict and offers solutions |
| Repository key needs your decision | A package source offers a signing key NazoOS does not trust yet, so it gets no updates | **Check key** opens NazoOS Welcome → Repair. Compare the fingerprint shown there with the one on the provider's website, and only then click **Trust key** |
| Update check does not work | No successful check for several days | Check the internet connection, then **Check now** |
| Started from a snapshot | The computer runs an older state from the boot menu | See "Going back to a snapshot" below |

Discover's own update notifications are switched off, so you only get one notification per update.

## Updating

**Update now** asks for your password and then installs all system updates (`zypper dist-upgrade`) and all Flatpak updates. Keep the computer on until it is done. If a restart is needed, the window shows **Restart now**.

Before every update a **snapshot** of the system is taken automatically, and one after it. NazoOS does not take snapshots on a timer: they are made before and after updates and software changes, and when you create one yourself. Your files in your home folder are not part of snapshots and are never changed by a rollback.

## Going back to a snapshot

If the system does not start or misbehaves after an update:

1. Restart the computer.
2. In the boot menu choose **Start bootloader from a read-only snapshot**.
3. Pick the snapshot from before the update. The newest is at the top; every entry ends with its date and time, for example **Before update 2026-10-11 22:39**. The names mean:
   - **Before update** / **After update**: around an update with NazoOS Update.
   - **Before software change** / **After software change**: programs were installed or removed.
   - **Before channel switch**: taken before you changed between stable and beta.
   - **Manual snapshot**: you created it in NazoOS Welcome.
   - **Before rollback** / **After rollback**: around making a snapshot permanent.
4. The system starts in that older state. It is read-only: nothing can be installed or changed until you make it permanent.
5. If everything works, NazoOS Update shows a notification **Started from a snapshot**. Click **Make permanent** and confirm. The broken state is kept as a snapshot too, so this can be undone.
6. Restart.

**Btrfs Assistant** (application menu, or **Snapshots** in NazoOS Update) shows all snapshots, can create and delete them and restore single files.

## Stable and beta

NazoOS has two update channels for its own packages (Welcome, Update, settings, branding):

- **Stable** (default): updates arrive after they were tested.
- **Beta**: updates arrive right away. You get new features first and help find problems, but something can break.

Switch in **NazoOS Welcome → System → Update channel**. A snapshot is taken first. Going back to stable can make some NazoOS packages a bit older again, that is expected. Tumbleweed itself and the NazoOS kernel are the same in both channels.

## For advanced users

- Background check: `nazoos-update-check.timer` (system), result in `/var/lib/nazoos-update/status.json`.
- Notifications: `nazoos-update-notify.timer` (user).
- "Make permanent" runs `snapper --ambit classic rollback`.
- The boot menu names come from the snapper userdata `bootloader`, set by `nazoos-update-label.path` as soon as a snapshot appears and by NazoOS Update after each update (`snapper list` shows the original descriptions).
- When the download servers still have an older Tumbleweed snapshot than the installed system (right after installing from a new image), no system update is offered: `zypper dup` would only go back to the older versions.
- In a terminal, `sudo zypper dup` does not have this check: in the first hours after installing it may list many packages going *down* a version (compare `VERSION_ID` in `/etc/os-release` with `curl -sL https://download.opensuse.org/tumbleweed/repo/oss/media.1/products`). That is harmless – the system just matches the servers again and the next update moves forward – but you can also simply wait. `zypper up` never downgrades, but on Tumbleweed `dup` is the right command. Do not set `solver.dupAllowDowngrade = false`: Tumbleweed sometimes goes back a version on purpose when a new one was broken.
- Update channel: `/usr/share/zypp/local/service/nazoos/repo/repoindex.xml` (from `nazoos-repos`) links to `nazoos-stable-repoindex.xml` or `nazoos-beta-repoindex.xml`. The switch changes the link, runs `zypper refresh-services` (repo `nazoos:nazoos` ↔ `nazoos:nazoos-devel`) and `zypper dup --from <that repo>`. The link survives package updates.
