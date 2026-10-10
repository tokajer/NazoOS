# kernel-nazoos

Sources of the optional NazoOS kernel flavor (decisions: ADR 0007/0008,
user docs: [`docs/kernel.md`](../docs/kernel.md)).

The kernel is **not** a fork. It is SUSE's
[kernel-source](https://github.com/SUSE/kernel-source) (branch `stable` =
OBS `Kernel:stable`) plus:

| File | Purpose |
|---|---|
| `patches.list` | Gaming patches in apply order, with their upstream URL |
| `patches/` | The downloaded patches (GPL-2.0-only) |
| `config/nazoos.fragment` | Config differences to openSUSE's `x86_64/default` |
| `fetch-patches.sh` | Downloads the patches of `patches.list` |
| `make-obs-package.sh` | Builds the OBS source package of `kernel-nazoos` |

## Build the OBS package

```sh
# Tumbleweed (e.g. distrobox): build tools
sudo zypper in git curl quilt make gcc flex bison bc perl xz python3 perl-Text-Glob

./fetch-patches.sh                  # only after changing patches.list
./make-obs-package.sh --check       # do all patches apply? is the config complete?
./make-obs-package.sh               # -> ~/nazoos-kernel/kernel-source-nazoos/
```

`make-obs-package.sh` clones kernel-source into `~/nazoos-kernel/`, adds the
patches as `patches.addon/nazoos-*.patch`, creates `config/x86_64/nazoos`
(default config + fragment + `make olddefconfig` with SUSE's dummy tools for
options the patches add) and runs `scripts/tar-up` for that flavor only.

## Upload to OBS (project `home:Tokajer:nazoos:kernel`)

One time:

```sh
osc meta prj -e home:Tokajer:nazoos:kernel   # repository openSUSE_Tumbleweed,
                                             # path openSUSE:Factory/snapshot, arch x86_64,
                                             # debuginfo disabled
osc co home:Tokajer:nazoos:kernel && cd home:Tokajer:nazoos:kernel
osc mkpac kernel-source
# No links needed: kernel-source carries a _multibuild (written by
# make-obs-package.sh) that builds kernel-nazoos and kernel-syms as flavors
# Kernel modules: built for every flavor in kernel-syms -> *-kmp-nazoos
osc linkpac openSUSE:Factory nvidia-open-driver-G07-signed home:Tokajer:nazoos:kernel
osc linkpac openSUSE:Factory xone home:Tokajer:nazoos:kernel
osc linkpac openSUSE:Factory xpadneo home:Tokajer:nazoos:kernel
```

Every kernel update:

```sh
./make-obs-package.sh
cd home:Tokajer:nazoos:kernel/kernel-source && osc up
rsync -a --delete --exclude .osc ~/nazoos-kernel/kernel-source-nazoos/ .
osc addremove && osc ci -m "Update to $(sed -n 's/^SRCVERSION=//p' config.sh)"
```

The KMPs stay "unresolvable" (`nothing provides kernel-nazoos-devel`) until
the kernel build has finished; then OBS builds them on its own.

The spec carries `# needssslcertforbuild`: OBS signs the kernel with the
project's certificate. The certificate ends up in `/etc/uefi/certs/` and
the kernel's install script queues it for MokManager
(`mokutil --import … --root-pw`).

## New kernel series (e.g. 7.2 → 7.3)

1. CachyOS keeps one directory per series in
   [kernel-patches](https://github.com/CachyOS/kernel-patches) and branches
   `<series>/<topic>` in [CachyOS/linux](https://github.com/CachyOS/linux).
   Update the URLs/commits in `patches.list`.
2. `./fetch-patches.sh && ./make-obs-package.sh --check`
3. A patch that does not apply: refresh it with quilt in
   `~/nazoos-kernel/tree/linux-*-nazoos` (`quilt push -f`, fix, `quilt refresh`),
   copy it to `patches/` and mark it `local` in `patches.list`.
