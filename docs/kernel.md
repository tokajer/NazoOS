# NazoOS kernel

NazoOS starts with the openSUSE kernel (`kernel-default`). It works everywhere, also with Secure Boot. The NazoOS kernel (`kernel-nazoos`) is an optional extra with gaming patches. Install it in **NazoOS Welcome → Kernel**.

## What is different

- **BORE scheduler**: smoother frame times when the CPU is busy
- **BBRv3** network congestion control (module `bbr3`)
- **ACS override** (`pcie_acs_override=`) for passing GPUs to virtual machines
- **v4l2loopback**: virtual cameras, e.g. for OBS Studio
- **Handheld drivers**: Steam Deck, ROG Ally, MSI Claw, Zotac Zone, Ayaneo, GPD, OneXPlayer (screen rotation, buttons, sound, fans)
- 1000 Hz timer and full preemption (same as the openSUSE kernel today)

`uname -r` ends with `-nazoos`.

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
