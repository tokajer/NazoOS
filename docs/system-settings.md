# System settings

NazoOS has no YaST. Everything YaST does on openSUSE is done by these apps:

| Task | Where |
|---|---|
| Install and remove software | **Discover** (apps, Flatpak), **Myrlyn** (all packages, repositories) |
| Updates | **NazoOS Update** (system tray) |
| Drivers, codecs, optional apps, services | **NazoOS Welcome** |
| Kernel options, NazoOS kernel | **NazoOS Welcome → Kernel / Gaming** |
| Snapshots, going back | **Btrfs Assistant**, boot menu ([NazoOS Update](update.md)) |
| Users, date and time, language, keyboard | **System Settings** |
| Network, Wi-Fi, VPN | **System Settings → Wi-Fi & Networking** (OpenVPN: install it in **NazoOS Welcome → Apps**) |
| Firewall | **System Settings → Firewall** |
| Printers | **System Settings → Printers** |
| Bluetooth | **System Settings → Bluetooth** |
| Disks and partitions | **KDE Partition Manager**; drive health in **System Settings → Disks & Cameras** |
| Share folders on the network | **Dolphin**: right-click a folder → **Properties → Share** |
| Scanner | **Skanpage** (install it in **NazoOS Welcome → Apps**) |
| Hardware information | **Info Center** |

## Firewall

The firewall is on. NazoOS uses its own zone **nazoos**:

- Ports **1025 and above** are open. Games, Steam Remote Play, Steam local game transfer, KDE Connect and voice chat work without changes.
- Below 1025 only these answer: **SSH** and **Samba** (folder sharing). Both only when you switch them on yourself (NazoOS Welcome → System, Dolphin → Share).
- Everything else below 1025 is closed, so system services that are started by accident cannot be reached from the network.

To close or open more, use **System Settings → Firewall**. A stricter zone such as **public** can be selected there as well.

## Advanced: console

Only needed for settings without a graphical tool. Every `sudo` command asks for your password.

### Boot menu timeout and default entry

```sh
sudoedit /etc/default/grub          # GRUB_TIMEOUT=<seconds>
sudo grub2-mkconfig -o /boot/grub2/grub.cfg
sudo grub2-set-default <number>     # 0 = first entry
```

Kernel options are easier in **NazoOS Welcome → Kernel / Gaming**: it keeps the file consistent.

### Services

```sh
systemctl list-unit-files --state=enabled
sudo systemctl disable --now <name>.service
```

### Firewall

```sh
sudo firewall-cmd --list-all                       # active zone
sudo firewall-cmd --permanent --zone=nazoos --remove-service=ssh
sudo firewall-cmd --set-default-zone=public        # stricter: only ssh and dhcpv6-client
sudo firewall-cmd --reload
```

### YaST

YaST can be installed if you want it: install `yast2-control-center-qt` and the modules you need (for example `yast2-bootloader`) in Myrlyn. NazoOS does not test its tools together with YaST.
