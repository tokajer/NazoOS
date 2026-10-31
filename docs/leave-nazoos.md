# Leaving NazoOS

NazoOS is openSUSE Tumbleweed with extras, so you can turn it into plain Tumbleweed without reinstalling. Your files, your other apps and your Flatpaks stay. This also works when the NazoOS project is gone and its repositories no longer exist.

## With NazoOS Welcome

1. Open **NazoOS Welcome → System** and scroll to **Leave NazoOS**.
2. Click **Switch to Tumbleweed**, read the summary and confirm with your password. You need a working internet connection.
3. If the NazoOS kernel is running, this first step only moves to the openSUSE kernel. Restart the computer, open NazoOS Welcome again and click **Switch to Tumbleweed** a second time.
4. A snapshot is taken, then the NazoOS packages are replaced. When NazoOS Welcome tells you, restart the computer. Other pages of NazoOS Welcome may stay empty until then, because the program itself has been removed.

If the check before the change finds a problem, or the change cannot start, no packages are changed and NazoOS keeps working. A few settings (the default firewall zone, the gaming start mode) may already be back at their openSUSE or desktop values. Try again later, a new Tumbleweed snapshot often solves it.

## What is removed and what comes back

- **Removed:** every package built by NazoOS, like NazoOS Welcome, NazoOS Update, the gaming tweaks, the NazoOS kernel, gaming mode and Waydroid, and the NazoOS repositories with their signing key.
- **Changed to the openSUSE build:** packages Tumbleweed has too, like the Xbox controller drivers `xone` and `xpadneo`.
- **Back to openSUSE:** look of the desktop, boot splash and boot menu. Discover now also installs system updates.
- **Firewall:** the default zone goes back to `public`.
- **Gaming mode:** the computer starts with the normal login screen again.

## What stays

- **The Secure Boot key** of the NazoOS kernel stays enrolled. It does no harm. To remove it you would need `mokutil --delete` and a MokManager step at the next start.
- **The boot menu name "NazoOS"**: `GRUB_DISTRIBUTOR` stays on purpose, because the path of the boot files on the EFI partition depends on it. Tumbleweed works the same under this name.
- **Your kernel options** from NazoOS Welcome stay in `/etc/default/grub`.
- **The Wayland login screen**: two small files keep it working, `/etc/sddm.conf.d/10-wayland-greeter.conf` and `/etc/systemd/system/display-manager-legacy.service.d/10-wayland-tty1.conf`. They belong to you now.
- **Your Plasma settings**: a theme you chose before stays in your home folder, so the desktop may still look like NazoOS. Pick another one in **System Settings → Colors & Themes**.
- **Packman**, if you added it, and all other repositories you added yourself.
- **Sudo and password dialogs** keep asking for your own password; root stays locked.

## Going back

The snapshot from before the switch stays only until snapper's automatic cleanup removes it, once enough newer snapshots exist. If you may want to go back, do it soon. Restart, choose **Start bootloader from a read-only snapshot** in the boot menu and pick the newest snapshot from before the switch (it can be listed as **Before channel switch**). That state still has NazoOS Update, which then offers to make it permanent ([details](update.md)). Do this as well if the switch stops half-way.

## With the console (for advanced users)

The steps NazoOS Welcome does, for a start from the openSUSE kernel (`uname -r` ends with `-default`). Check the list of packages first.

```sh
# Take the snapshot and switch off the NazoOS repositories
sudo snapper -c root create --type single --cleanup-algorithm number \
  --description "before switching to Tumbleweed"
for f in $(grep -l 'home:/Tokajer' /etc/zypp/repos.d/*.repo); do
  sudo zypper modifyrepo --disable "$(basename "$f" .repo)"
done

# Packages built by NazoOS
rpm -qa --qf '%{NAME}\t%{VENDOR}\n' | grep 'home:Tokajer$' | cut -f1

# Firewall, gaming mode, NVIDIA on Wayland, login screen
sudo firewall-cmd --set-default-zone=public
sudo /usr/libexec/nazoos-session/nazoos-session-ctl boot-mode desktop
echo 'options nvidia_drm modeset=1 fbdev=1' |
  sudo tee /etc/modprobe.d/50-nvidia-wayland.conf
sudo mkdir -p /etc/sddm.conf.d /etc/systemd/system/display-manager-legacy.service.d
printf '[General]\nDisplayServer=wayland\n' |
  sudo tee /etc/sddm.conf.d/10-wayland-greeter.conf
printf '[Unit]\nConflicts=getty@tty1.service\nAfter=getty@tty1.service\n' |
  sudo tee /etc/systemd/system/display-manager-legacy.service.d/10-wayland-tty1.conf

# Replace the packages. Add "-name" for every package of the list above
# that "zypper search --match-exact name" does not find in repo-oss
sudo zypper install plasma6-branding-openSUSE plymouth-branding-openSUSE \
  grub2-branding-openSUSE sudo-policy-wheel-auth-self \
  discover6-backend-packagekit -nazoos-welcome -nazoos-tweaks ...

# Packages Tumbleweed has too; the alias of repo-oss is in "zypper repos"
sudo zypper install --oldpackage --force --from openSUSE:repo-oss xone xpadneo

# Clean up
sudo zypper removelock plasma6-session-x11
sudo zypper removerepo nazoos-kernel
# The same for any other repository under home:/Tokajer
for f in $(grep -l 'home:/Tokajer' /etc/zypp/repos.d/*.repo); do
  sudo zypper removerepo "$(basename "$f" .repo)"
done
sudo sed -i '/^GRUB_TOP_LEVEL=/d' /etc/default/grub
sudo grub2-mkconfig -o /boot/grub2/grub.cfg
sudo rpm -e --allmatches gpg-pubkey-a686e7d6
```

Keep `sudo-policy-wheel-auth-self` and never use `zypper remove --clean-deps` here: root is locked on NazoOS, and without that package nobody gets administrator rights any more.
