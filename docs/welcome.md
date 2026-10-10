# NazoOS Welcome

NazoOS Welcome opens after the first login. It sets up everything that is not part of the base installation. You never need a terminal for it. Open it again any time from the application menu: **NazoOS Welcome**.

Whenever a step changes the system, a password dialog appears. Enter the password you chose during installation. It is remembered for a few minutes.

## Pages

| Page | What you can do |
|---|---|
| Welcome | First steps, disclaimer, switch "Show this window at login" |
| Drivers & codecs | Install the NVIDIA driver, install multimedia codecs from Packman, firmware updates |
| Gaming & performance | sched_ext CPU scheduler (scx), AMD GPU overclocking, CPU mitigations, Steam Deck/handheld support, Steam launch options |
| Kernel | Optional NazoOS kernel with gaming patches, Secure Boot key, way back to the openSUSE kernel ([details](kernel.md)) |
| Apps | Install popular apps with one click (Discord, OBS Studio, Heroic, ProtonUp-Qt, …) |
| Drives | Mount internal drives automatically, e.g. for a Steam library |
| System | Updates, snapshots, services (Bluetooth, LACT, CoolerControl, SSH, profile-sync-daemon), maintenance |
| Help | Links and system information for bug reports |

## NVIDIA

Choose the driver that matches your card:

- **GeForce GTX 16, RTX 20 and newer**: open kernel module, works with Secure Boot.
- **GeForce GTX 750 to GTX 10 series**: older driver. It is not signed for Secure Boot. Turn Secure Boot off in the firmware settings, or the driver will not load.

Restart after the installation.

## Codecs (Packman)

Packman is a community repository outside of NazoOS and openSUSE. It provides the full FFmpeg and GStreamer codecs. Read the notice in the dialog before you enable it. Installed multimedia packages are switched to Packman's versions.

## Kernel options

Kernel options take effect after a restart. The page shows "Restart the computer to apply the change" until then.

- **AMD GPU overclocking** unlocks clock and voltage controls in LACT.
- **Disable CPU mitigations** gives a little more performance on older CPUs, but removes protection against Spectre-type attacks. Leave it off unless you know the risk.

## Drives

"Mount automatically" adds the drive to the system so it is mounted under `/mnt/<name>` at every start. Nothing on the drive is changed. If the drive is missing, the computer still starts. "Stop mounting" undoes it. For a Steam library, use ext4 or Btrfs. NTFS works, but some Proton games have problems on it.

## Something went wrong

If an action fails, a dialog explains what happened. **Show details** shows the full output, and **Copy** copies it for a bug report. **Try again** repeats the action, e.g. after a network problem.

If the system misbehaves after a change, roll back. Restart, choose **Start bootloader from a read-only snapshot** in the boot menu and pick the state before the change. NazoOS Update then offers to make that state permanent ([details](update.md)).
