# Installing NazoOS

Start the computer from the live medium (USB stick with `NazoOS.x86_64-live.iso`). The live desktop opens and the installer starts by itself. If you closed it, start it again from the application menu (**Install NazoOS**).

NazoOS needs a computer with UEFI, at least 30 GB of disk space and 4 GB of RAM. Secure Boot can stay on.

## Steps

1. **Welcome:** language of the installer and of the installed system.
2. **License:** read the notice (NazoOS is a hobby project without warranty) and accept it.
3. **Location** and **Keyboard:** time zone, language settings and keyboard layout.
4. **Device:** *Desktop PC* or *Handheld*. On a Steam Deck, ROG Ally, Legion Go, MSI Claw and similar devices *Handheld* is already selected: the computer then starts in Steam's gaming mode like a console ([Gaming mode](gaming-mode.md)).
5. **Partitions:** *Erase disk* puts NazoOS on the whole disk. NazoOS uses btrfs, so that it can go back to a snapshot after an update ([NazoOS Update](update.md)). *Encrypt system* is optional, see below.
6. **Users:** your name, user name and password. The same password is used for administrator tasks (password dialogs).
7. **Summary:** check everything, then **Install**. Afterwards restart and remove the USB stick.

## Encrypt system

With **Encrypt system** the whole NazoOS partition is encrypted. Without the passphrase nobody can read your files, for example when a laptop gets stolen.

- At every start the computer asks for the passphrase **once**, on a black screen before the boot menu ("Enter passphrase for hd0,gpt2"). After typing it, wait a few seconds: unlocking takes a moment.
- **Keyboard layout:** this screen always uses the **US layout**. On a German keyboard **Z and Y are swapped** there, and most special characters are on other keys. The easiest way: a passphrase made of letters (without Y and Z) and digits. With Y or Z, type them swapped (for "Zeitung" type "Yeitung").
- Starting an older snapshot from the boot menu asks for the passphrase the same way.
- Keep the passphrase safe: **without it the data cannot be recovered**, not even by reinstalling.

## After the installation

At the first login **NazoOS Welcome** opens: drivers, codecs, apps and gaming settings ([NazoOS Welcome](welcome.md)).
