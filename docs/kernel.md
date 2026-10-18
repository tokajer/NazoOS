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
- **Waydroid** (Android apps) works: the needed Binder driver is built in. The openSUSE kernel does not have it. Install it in **NazoOS Welcome → Apps** (the button is active while the NazoOS kernel runs)
- **Controller poll rate**: wired controllers can be polled faster, e.g. PS4/PS5 controllers at 1000 Hz. Set it per device in **NazoOS Welcome → Gaming → Controllers and mice**, then unplug the device and plug it in again
- **Laptop speakers**: sound from the built-in speakers of Samsung Galaxy Book 4 and 5, Lenovo Legion Pro (AW88399 amplifier) and Razer Blade 16 (2025)
- **acpi_call** for handheld tools: Handheld Daemon and SimpleDeckyTDP use it to set the power limit (TDP) on devices like the Lenovo Legion Go. Installed together with the NazoOS kernel
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

**Install** adds the NazoOS kernel repository and installs the kernel next to the openSUSE kernel, together with the matching driver modules (NVIDIA open driver, Xbox controllers, acpi_call). The first boot menu entry **NazoOS** then starts the NazoOS kernel. The openSUSE kernel stays in the menu as **NazoOS (openSUSE kernel)** and under **Advanced options**.

The closed NVIDIA driver for older cards (GTX 750 – GTX 10) only exists for the openSUSE kernel, and so does the older open driver series 580 (`nvidia-open-driver-G06-signed`). With either of them the NazoOS kernel cannot be installed; on GTX 16 / RTX 20 and newer switch to the open driver on the **Drivers** page first.

### Secure Boot

With Secure Boot on, the computer only starts kernels signed with a trusted key. The NazoOS key is added once. On computers with UEFI this also happens with Secure Boot off: kernel updates expect the key, and you can turn Secure Boot on later.

1. When you click **Install**, NazoOS Welcome asks for a password for the blue screen, suggested: `nazoos`. Keep it or pick your own (4 to 16 letters or digits) and remember it until the next restart.
2. Restart after the installation. A blue screen appears: **MokManager**. It waits only a few seconds, press a key in time.
3. Choose **Enroll MOK** → **Continue** → **Yes**.
4. Type the password from step 1. The blue screen uses the US keyboard layout: on a German keyboard **Z and Y are swapped**, so for `nazoos` type `nayoos` (NazoOS Welcome shows what to type).
5. Choose **Reboot**.

If you miss the screen, the computer starts the openSUSE kernel by itself after a few seconds (boot menu entry **NazoOS (openSUSE kernel)**): the NazoOS kernel cannot start before its key is enrolled. Open **NazoOS Welcome → Kernel**, click **Enroll key**, enter the password again and restart.

## Step 2: remove the openSUSE kernel (optional)

After the NazoOS kernel has started cleanly three times in a row, a notification offers to remove the openSUSE kernel. Updates then never install it again. Older NazoOS kernel versions and snapshots stay as fallback.

## Updates

The NazoOS kernel follows new Linux stable releases within about a day, like Tumbleweed itself. It is not part of the tested NazoOS release channel: it is built from SUSE's newest stable kernel (before Tumbleweed's own tests) plus the gaming patches above, and goes out without a waiting period, so security fixes arrive fast. If a new version causes problems, choose the previous NazoOS kernel in the boot menu (**Advanced options**), use the openSUSE kernel, or roll back a snapshot. Please report it as a GitHub issue.

## Going back

**Use openSUSE kernel** makes the openSUSE kernel the default again and reinstalls it if it was removed. Restart, then **Remove NazoOS kernel** removes the NazoOS kernel completely.

If the NazoOS kernel does not start at all: choose **NazoOS (openSUSE kernel)** in the boot menu (or **Advanced options** and an entry ending with `-default`).
