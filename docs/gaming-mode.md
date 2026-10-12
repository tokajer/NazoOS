# Gaming mode and handhelds

## Gaming mode (Steam)

Gaming mode is Steam's console interface (the one on the Steam Deck), running in Gamescope. It works on every NazoOS computer and is good for the TV in the living room or for playing with a controller only.

How to get there:

- **From the desktop**: start **Gaming Mode** from the application menu, or use **NazoOS Welcome → Gaming → Steam gaming mode → Switch now**. The desktop session ends (save your work first), and Steam starts.
- **From the login screen**: choose the session **Gaming Mode (Steam)** at the bottom left before logging in.

Back to the desktop: in Steam, press the **Steam** button (or the ☰ menu) → **Power** → **Switch to Desktop**.

Steam must be installed (NazoOS Welcome → Apps). On the very first start Steam downloads its update, which needs an internet connection.

## Start in gaming mode (like a console)

**NazoOS Welcome → Gaming → Start in gaming mode** logs you in automatically and starts Steam right away when the computer boots. "Switch to Desktop" then opens the desktop for one session; the next time you log out or restart, gaming mode is back. This is how the Steam Deck behaves.

Switch it off with the same switch in NazoOS Welcome (from the desktop). While it is on, logging out of the desktop goes straight back to gaming mode instead of the login screen.

## Handhelds (Steam Deck, ROG Ally, Legion Go, ...)

There is one NazoOS image for all computers. The installer asks for the **device type** and preselects **Handheld** on devices it recognises (Steam Deck and the handhelds supported by InputPlumber: ROG Ally, Legion Go, MSI Claw, AYANEO, GPD, OneXPlayer, Zotac Zone and others).

A handheld installation:

- starts in gaming mode (see above),
- keeps the handheld packages: InputPlumber (controller, buttons and gyro of non-Valve handhelds), and on the Steam Deck the fan control, the speaker/microphone sound processing, the OLED panel correction and the power button,
- puts a **Gaming Mode** shortcut on the desktop and turns on the on-screen keyboard (at the first desktop login).

A desktop/laptop installation leaves these packages out. You can add them later in **NazoOS Welcome → Gaming → Steam Deck and handheld support**.

## For advanced users

- Switching from a terminal: `nazoos-session-select gaming` or `nazoos-session-select desktop`.
- Start mode: `/etc/nazoos/session.conf` (`BOOT_MODE=gaming|desktop`), written by `/usr/libexec/nazoos-session/nazoos-session-ctl`. It sets SDDM's automatic login (`/etc/sddm.conf.d/zz-nazoos-session.conf`, `DISPLAYMANAGER_AUTOLOGIN` in `/etc/sysconfig/displaymanager`). Do not edit these by hand; use `sudo /usr/libexec/nazoos-session/nazoos-session-ctl boot-mode desktop` to switch gaming mode off without the GUI.
- If gaming mode crashes five times in a row within a minute, it switches to the desktop by itself.
- Gamescope options per device come from `gamescope-session-plus` (`/usr/share/gamescope-session-plus/device-quirks`); your own settings go into `~/.config/environment.d/*.conf`.
