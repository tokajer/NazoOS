# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""nazoos_common.kernel: grub.cfg parsing, module rebuilds, default entry."""

import xml.etree.ElementTree as ET

from nazoos_common import kernel, kernelstate

GRUB_CFG = """\
### BEGIN /etc/grub.d/10_linux ###
menuentry 'NazoOS' --class opensuse $menuentry_id_option 'gnulinux-simple-1234' {
	load_video
	linux	/@/boot/vmlinuz-7.2.11-1-nazoos root=UUID=1234 splash
	initrd	/@/boot/initrd-7.2.11-1-nazoos
}
submenu 'Advanced options for NazoOS' $menuentry_id_option 'gnulinux-advanced-1234' {
	menuentry 'NazoOS, with Linux 7.2.9-1-default' $menuentry_id_option 'gnulinux-7.2.9-1-default-advanced-1234' {
		linux	/@/boot/vmlinuz-7.2.9-1-default root=UUID=1234
	}
}
"""


def test_set_var_adds_replaces_and_removes():
    text = 'GRUB_TIMEOUT=8\nGRUB_DEFAULT=0\n'
    text = kernel._set_var(text, "GRUB_DEFAULT", "saved")
    assert text == 'GRUB_TIMEOUT=8\nGRUB_DEFAULT=saved\n'
    text = kernel._set_var(text, "GRUB_TOP_LEVEL", '"/boot/vmlinuz-x"')
    assert text.endswith('GRUB_TOP_LEVEL="/boot/vmlinuz-x"\n')
    text = kernel._set_var(text, "GRUB_TOP_LEVEL", None)
    assert text == 'GRUB_TIMEOUT=8\nGRUB_DEFAULT=saved\n'
    # Removing a missing variable changes nothing
    assert kernel._set_var(text, "GRUB_TOP_LEVEL", None) == text


def test_set_var_only_matches_whole_names_at_line_start():
    text = '#GRUB_DEFAULT=0\nGRUB_DEFAULT_X=1\n'
    assert kernel._set_var(text, "GRUB_DEFAULT", "saved") == \
        text + "GRUB_DEFAULT=saved\n"


def test_top_entry():
    assert kernel.top_entry(GRUB_CFG) == (
        "gnulinux-simple-1234", "/@/boot/vmlinuz-7.2.11-1-nazoos")
    assert kernel.top_entry("") == (None, "")


def test_cmdline_re():
    text = 'A=1\nGRUB_CMDLINE_LINUX_DEFAULT="splash quiet"\n'
    m = kernel.CMDLINE_RE.search(text)
    assert m.group(2).split() == ["splash", "quiet"]


def test_newest_kernel_compares_versions_not_text(tmp_path):
    for v in ("7.2.9-1", "7.2.11-1", "7.10.0-1"):
        (tmp_path / f"vmlinuz-{v}-nazoos").touch()
    (tmp_path / "vmlinuz-7.11.0-1-default").touch()
    assert kernel.newest_kernel("nazoos", tmp_path) == \
        "/boot/vmlinuz-7.10.0-1-nazoos"
    assert kernel.newest_kernel("longterm", tmp_path) == ""


def test_kmp_rebuilds_finds_a_new_build_of_the_same_module():
    xml = ET.fromstring("""<stream><search-result><solvable-list>
      <solvable name="xone-kmp-nazoos" edition="0.3_k7.2.11_1-29.1"/>
      <solvable name="xone-kmp-nazoos" edition="0.3_k7.2.11_1-20.1"/>
      <solvable name="xone-kmp-nazoos" edition="0.3_k7.2.12_1-1.1"/>
      <solvable name="acpi_call-kmp-nazoos" edition="1.2_k7.2.11_1-2.8"/>
    </solvable-list></search-result></stream>""")
    installed = {"xone-kmp-nazoos": {"0.3_k7.2.11_1-20.1"},
                 "acpi_call-kmp-nazoos": {"1.2_k7.2.11_1-2.8"}}
    # Only the rebuild for the installed kernel version; the build for
    # the next kernel comes with the kernel update itself
    assert kernel.rebuilds(xml, installed) == [
        "xone-kmp-nazoos = 0.3_k7.2.11_1-29.1"]


def test_keep_default(monkeypatch, tmp_path):
    prefer = tmp_path / "kernel-prefer"
    monkeypatch.setattr(kernelstate, "PREFER", prefer)
    # The default argument of newest_kernel() is fixed at import
    real = kernel.newest_kernel
    monkeypatch.setattr(kernel, "newest_kernel",
                        lambda flavor: real(flavor, tmp_path))
    flavors = []
    monkeypatch.setattr(kernel, "ensure_grub_default",
                        lambda log, flavor: flavors.append(flavor))
    # Neither preferred nor installed: nothing to keep
    assert kernel.keep_default() is None
    assert flavors == []
    # kernel-nazoos installed, but not preferred: pin kernel-default
    (tmp_path / "vmlinuz-7.2.11-1-nazoos").touch()
    assert kernel.keep_default() == "default"
    prefer.touch()
    assert kernel.keep_default() == "nazoos"
    assert flavors == ["default", "nazoos"]
