# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""nazoos_welcome.kernel: /etc/default/grub and grub.cfg parsing."""

from nazoos_welcome import kernel

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
