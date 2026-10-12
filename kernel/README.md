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
| `upload-obs.sh` | Commits that package to OBS |
| `check-update.sh` | Compares kernel-source `stable` with the version in OBS |
| [`../.github/workflows/kernel-update.yml`](../.github/workflows/kernel-update.yml) | Does all of it automatically |

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
# Our own KMP (not in Tumbleweed, kernel-nazoos only): spec from GitHub
osc mkpac acpi_call && cp <NazoOS repo>/packages/acpi_call/_service acpi_call/
(cd acpi_call && osc add _service && osc ci -m "acpi_call: obs_scm")
```

Every kernel update (by hand; normally the workflow below does it):

```sh
./check-update.sh          # upstream=7.2.10 obs=7.2.9 → update available
./make-obs-package.sh
./upload-obs.sh            # osc checkout in ~/nazoos-kernel/obs/, rsync, osc ci
```

The KMPs stay "unresolvable" (`nothing provides kernel-nazoos-devel`) until
the kernel build has finished; then OBS builds them on its own.

The spec carries `# needssslcertforbuild`: OBS signs the kernel with the
project's certificate. The certificate ends up in `/etc/uefi/certs/` and
the kernel's install script queues it for MokManager
(`mokutil --import … --root-pw`).

## Automatic updates (GitHub workflow `kernel-update.yml`)

| When | What happens |
|---|---|
| Daily 04:17 UTC, new stable release (7.2.9 → 7.2.10) | build + upload, OBS builds kernel and KMPs |
| Daily, kernel-source `stable` moved to a new series | issue "Kernel 7.3: update patches.list", nothing uploaded |
| Push to `main` that changes `kernel/` | build + upload |
| Actions → Kernel update → Run workflow | build + upload if newer (`force`: always) |
| A step fails (patch does not apply, OBS login …) | issue "Kernel update failed", later failures comment on it |

OBS keeps the last good kernel when an upload fails or a build breaks.

One time:

1. Create a second openSUSE account for the bot
   (<https://idp-portal.suse.com/>), log in once on build.opensuse.org.
   Password without `%` (osc's config parser treats it specially).
2. Make the bot maintainer of the package kernel-source only:
   `osc meta pkg -e home:Tokajer:nazoos:kernel kernel-source` →
   `<person userid="BOT" role="maintainer"/>` (web: package → Users → Add User)
3. GitHub → NazoOS → Settings → Secrets and variables → Actions:
   `OBS_USER` = bot name, `OBS_PASSWORD` = its password.

GitHub stops scheduled workflows after 60 days without a commit in the
repo; it shows a banner on the Actions page, "Enable workflow" restarts it.

## New kernel series (e.g. 7.2 → 7.3)

1. CachyOS keeps one directory per series in
   [kernel-patches](https://github.com/CachyOS/kernel-patches) and branches
   `<series>/<topic>` in [CachyOS/linux](https://github.com/CachyOS/linux).
   Update the URLs/commits in `patches.list`, set `KERNEL_SERIES` in
   `make-obs-package.sh` to the new series.
2. `./fetch-patches.sh && ./make-obs-package.sh --check`
3. A patch that does not apply: refresh it with quilt in
   `~/nazoos-kernel/tree/linux-*-nazoos` (`quilt push -f`, fix, `quilt refresh`),
   copy it to `patches/` and mark it `local` in `patches.list`.
4. Push: the workflow builds and uploads.
