# NazoOS kernel

NazoOS starts with the openSUSE kernel (`kernel-default`). It works everywhere, also with Secure Boot. The NazoOS kernel (`kernel-nazoos`) is an optional extra with gaming patches. Install it in **NazoOS Welcome → Kernel**.

## What is different

- **BORE scheduler**: smoother frame times when the CPU is busy
- **BBRv3** network congestion control (module `bbr3`)
- **ACS override** (`pcie_acs_override=`) for passing GPUs to virtual machines
- **v4l2loopback**: virtual cameras, e.g. for OBS Studio
- **Handheld drivers**: Steam Deck, ROG Ally, MSI Claw, Zotac Zone, Ayaneo, GPD, OneXPlayer (screen rotation, buttons, sound, fans)
- **VRAM for the game in front**: when graphics memory runs short, other programs give way and the focused game keeps its data in fast VRAM (AMD graphics cards, not NVIDIA yet; see below)
- **Stable CPU clock after standby** (`tsc=directsync`): for the Steam Deck and AMD systems whose games stutter after waking up. Off by default; switch it on in **NazoOS Welcome → Gaming → Kernel options** (the switch only appears on CPUs that can use it)
- **HDMI 2.1 VRR for AMD**: variable refresh rate over HDMI also on TVs and monitors without FreeSync, and with more DisplayPort-to-HDMI adapters. It turns on by itself when the screen supports it
- **Waydroid** (Android apps) works: the needed Binder driver is built in. The openSUSE kernel does not have it
- **Controller poll rate**: wired controllers can be polled faster, e.g. PS4/PS5 controllers at 1000 Hz. For now only for advanced users as boot option `usbcore.interrupt_interval_override=054c:09cc:1` (vendor ID:product ID:milliseconds, see `lsusb`)
- **Hardware fixes**: ROG Ally fan and sensor readings, Logitech G923 (PlayStation version), some Bluetooth adapters, ASUS laptop keyboards, RX 5000/6000 series (RDNA1/RDNA2) standby, the Intel I226-V network chip on some ASUS X870 mainboards
- 1000 Hz timer and full preemption (same as the openSUSE kernel today)

`uname -r` ends with `-nazoos`.

## VRAM for the game in front

Two background services come with NazoOS: *dmemcg-booster* and *plasma-foreground-booster*. They mark the window you are using as important. With the NazoOS kernel, the graphics driver then moves other programs' data out of VRAM before the game's data, which helps most on graphics cards with 8 GB or less. With the openSUSE kernel the protection is weaker, but the services do no harm.

To switch the foreground booster off, put this into `~/.config/kcgroupsrc` and log in again:

```ini
[Foreground Booster]
autostart=false
```

## Step 1: install

**Install** adds the NazoOS kernel repository and installs the kernel next to the openSUSE kernel, together with the matching driver modules (NVIDIA open driver, Xbox controllers). The NazoOS kernel becomes the default in the boot menu. The openSUSE kernel stays under **Advanced options**.

The closed NVIDIA driver for older cards (GTX 750 – GTX 10) only exists for the openSUSE kernel. With that driver the NazoOS kernel cannot be installed.

### Secure Boot

With Secure Boot on, the computer only starts kernels signed with a trusted key. The NazoOS key is added once:

1. Restart after the installation. A blue screen appears: **MokManager**.
2. Choose **Enroll MOK** → **Continue** → **Yes**.
3. Type your administrator (root) password. Unless you changed it in the installer, it is the same as your user password.
4. Choose **Reboot**.

If you miss the screen, choose the openSUSE kernel in the boot menu, open **NazoOS Welcome → Kernel** and click **Enroll key**. Then restart.

## Step 2: remove the openSUSE kernel (optional)

After the NazoOS kernel has started cleanly three times in a row, a notification offers to remove the openSUSE kernel. Updates then never install it again. Older NazoOS kernel versions and snapshots stay as fallback.

## Going back

**Use openSUSE kernel** makes the openSUSE kernel the default again and reinstalls it if it was removed. Restart, then **Remove NazoOS kernel** removes the NazoOS kernel completely.

If the NazoOS kernel does not start at all: in the boot menu choose **Advanced options** and an entry ending with `-default`.
