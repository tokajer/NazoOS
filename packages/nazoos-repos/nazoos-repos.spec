# SPDX-FileCopyrightText: 2026 The NazoOS Contributors
# SPDX-License-Identifier: GPL-3.0-or-later

%define servicedir %{_datadir}/zypp/local/service/nazoos

Name:           nazoos-repos
# Version is set by OBS (set_version) from the git state
Version:        0
Release:        0
Summary:        Repository definitions for NazoOS
License:        GPL-3.0-or-later
URL:            https://github.com/tokajer/NazoOS
Source0:        %{name}-%{version}.tar.xz
BuildArch:      noarch
# Manages repo-oss/non-oss/update as zypp service "openSUSE"; replaces the
# repo files the old images added
Requires:       openSUSE-repos-Tumbleweed
Requires(post): coreutils
Requires(posttrans): coreutils
Requires(posttrans): zypper
Requires(postun): zypper

%description
The NazoOS OBS repositories as zypp service "nazoos". The channel is
beta (:devel) or stable (:release), chosen by the symlink
repoindex.xml. Switch with: ln -sf nazoos-stable-repoindex.xml
%{servicedir}/repo/repoindex.xml && zypper refresh-services

%prep
%autosetup

%install
install -Dm0644 -t %{buildroot}%{servicedir}/repo \
  repo/nazoos-beta-repoindex.xml repo/nazoos-stable-repoindex.xml
ln -s nazoos-beta-repoindex.xml %{buildroot}%{servicedir}/repo/repoindex.xml

%post
# Release ISO installs had alias "nazoos" (:release); keep them on stable.
# %posttrans keeps an existing link
if grep -q '/nazoos:/release/' /etc/zypp/repos.d/nazoos.repo 2>/dev/null \
  && [ ! -L %{servicedir}/repo/repoindex.xml ]; then
  ln -s nazoos-stable-repoindex.xml %{servicedir}/repo/repoindex.xml || :
fi
# Images before nazoos-repos added these with zypper addrepo in config.sh;
# no package owns them, the service replaces them
for repo_file in nazoos-devel.repo nazoos.repo; do
  if [ -f /etc/zypp/repos.d/$repo_file ]; then
    echo "Content of $repo_file will be newly managed by zypp-services."
    echo "Storing old copy as /etc/zypp/repos.d/$repo_file.rpmsave"
    mv /etc/zypp/repos.d/$repo_file /etc/zypp/repos.d/$repo_file.rpmsave || :
  fi
done

%posttrans
# The channel is the admin's choice and survives updates. Default beta:
# images before nazoos-repos came from :devel (release installs are
# handled in %post); the release ISO's config.sh switches to stable
[ -L %{servicedir}/repo/repoindex.xml ] || \
  ln -s nazoos-beta-repoindex.xml %{servicedir}/repo/repoindex.xml || :
# We hereby declare that running this will not influence existing transaction
if [ ! -e /etc/zypp/services.d/nazoos.service ]; then
  ZYPP_READONLY_HACK=1 zypper --non-interactive addservice %{servicedir} nazoos || :
fi
ZYPP_READONLY_HACK=1 zypper --non-interactive refresh-services || :

%postun
# Only on removal: the postun of the old package runs after the post of the
# new one, so posttrans (not post) re-adds the service on updates
if [ "$1" = 0 ]; then
  ZYPP_READONLY_HACK=1 zypper --non-interactive removeservice nazoos || :
fi

%files
# Co-owned on purpose: OBS checks for directories without an owner, and
# Requires does not count at build time
%dir %{_datadir}/zypp
%dir %{_datadir}/zypp/local
%dir %{_datadir}/zypp/local/service
%dir %{servicedir}
%dir %{servicedir}/repo
%{servicedir}/repo/nazoos-beta-repoindex.xml
%{servicedir}/repo/nazoos-stable-repoindex.xml
%ghost %{servicedir}/repo/repoindex.xml

%changelog
