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
| Update check does not work | No successful check for several days | Check the internet connection, then **Check now** |
| Started from a snapshot | The computer runs an older state from the boot menu | See "Going back to a snapshot" below |

Discover's own update notifications are switched off, so you only get one notification per update.

## Updating

**Update now** asks for your password and then installs all system updates (`zypper dist-upgrade`) and all Flatpak updates. Keep the computer on until it is done. If a restart is needed, the window shows **Restart now**.

Before every update a **snapshot** of the system is taken automatically. Your files in your home folder are not part of snapshots and are never changed by a rollback.

## Going back to a snapshot

If the system does not start or misbehaves after an update:

1. Restart the computer.
2. In the boot menu choose **Start bootloader from a read-only snapshot**.
3. Pick the snapshot from before the update (the list shows date and description, e.g. "zypp(zypper) pre").
4. The system starts in that older state. It is read-only: changes are lost at the next restart.
5. If everything works, NazoOS Update shows a notification **Started from a snapshot**. Click **Make permanent** and confirm. The broken state is kept as a snapshot too, so this can be undone.
6. Restart.

**Btrfs Assistant** (application menu, or **Snapshots** in NazoOS Update) shows all snapshots, can create and delete them and restore single files.

## For advanced users

- Background check: `nazoos-update-check.timer` (system), result in `/var/lib/nazoos-update/status.json`.
- Notifications: `nazoos-update-notify.timer` (user).
- "Make permanent" runs `snapper --ambit classic rollback`.
