#!/usr/bin/env python3
 # -*- coding: utf-8 -*-

# Copyright (C) 2017-2020 Sandro Knauß <hefee@debian.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import apt_pkg
from debian import deb822, changelog, copyright
from debian.debian_support import Version
from git import Git, Repo
import glob
import datetime
import itertools
import os
import paramiko
import pathlib
import pydot
import re
import requests
import shutil
import subprocess
import sys
import tarfile
import tempfile
import warnings
import yaml


# Updated version of deb822.PkgRelation.str that handles the 'archqual' field
def rels2str(rels):
    """Format to string structured inter-package relationships

    Perform the inverse operation of parse_relations, returning a string
    suitable to be written in a package stanza.
    """
    def pp_arch(arch_spec):
        return '%s%s' % (
            '' if arch_spec.enabled else '!',
            arch_spec.arch,
        )

    def pp_restrictions(restrictions):
        s = []
        for term in restrictions:
            s.append('%s%s' % (
                '' if term.enabled else '!',
                term.profile
            )
            )
        return '<%s>' % ' '.join(s)

    def pp_atomic_dep(dep):
        s = dep['name']
        if dep.get('archqual') is not None:
            s += ':%s' % dep['archqual']
        if dep.get('version') is not None:
            s += ' (%s %s)' % dep['version']
        if dep.get('arch') is not None:
            s += ' [%s]' % ' '.join(map(pp_arch, dep['arch']))
        if dep.get('restrictions') is not None:
            s += ' %s' % ' '.join(map(pp_restrictions, dep['restrictions']))
        return s

    def pp_or_dep(deps):
        return ' | '.join(map(pp_atomic_dep, deps))
    return ', '.join(map(pp_or_dep, rels))

class Package:
    def __init__(self, pkg):
        self.pkg = pkg
        self.name = pkg['Package']
        p = pathlib.Path(pkg['Vcs-Git'])
        self.upstreamName = p.stem
        self.subdir = pathlib.Path(*p.parts[3:-1], p.stem)
        if not self.path/".git":
            raise Exception(f"{self.path} is not a valid git clone")
        self.git = Repo(str(self.path))

    @property
    def path(self):
        return basedir/self.subdir

    @property
    def dirty(self):
        return self.git.commit().diff(None)

    @property
    def changelog(self):
        return changelog.Changelog(open(self.path/'debian/changelog'), encoding="utf-8")

    @property
    def version(self) -> Version:
        return self.changelog.version

    @property
    def upstream_version(self) -> str:
        return self.version.upstream_version

    @property
    def readyForChanges(self):
        return not self.dirty and self.changelog.distributions == "UNRELEASED"

    @property
    def dscName(self) -> str:
        version = self.version
        if version.epoch:
            version.epoch = None
        return f"{self.changelog.package}_{version}.dsc"

    @property
    def dscPath(self) -> pathlib.Path:
        return self.path.with_name(self.dscName)

    @property
    def tarball_path(self) -> pathlib.Path:
        return self.path.with_name(f"{self.name}_{self.upstream_version}.orig.tar.xz")

    def controlParagraphs(self):
        control = self.path/"debian/control"
        with control.open() as cf:
            for block in deb822.Deb822.iter_paragraphs(cf):
                yield block

    @property
    def standardsVersion(self):
        for block in self.controlParagraphs():
            if block.get("Source"):
                return Version(block['Standards-Version'])

    @property
    def upstreamVersion(self):
        return self.changelog.version.upstream_version

    @property
    def sourceName(self):
        for block in self.controlParagraphs():
            if block.get("Source"):
                return block.get("Source")

    @property
    def unpackPath(self):
        path = self.path.with_name(f"{self.sourceName}-{self.upstreamVersion}")
        if not path.exists():
            path = self.path.with_name(f'{self.name}-{self.upstreamVersion}')
            if not path.exists():
                path = self.path.with_name(f'{self.path.name}-{self.upstreamVersion}')
        return path

    def dpkgBuildpackage(self):
        self.call("dpkg-buildpackage", "-S", "-d")

    def call(self, *args):
        subprocess.call(args, cwd=self.path)

    def check_call(self, *args):
        subprocess.check_call(args, cwd=self.path)

    def __repr__(self):
        return f"Package<'{self.name}'>"

def addChangeForMainatiner(pkg, change, name=""):
    rmantainer = re.compile("^\s*\[\s+(.*)\s+\]\s*$")
    cl = pkg.changelog
    mantainers = [{'name': None, 'start': 0, 'end': None}]
    for i, line in enumerate(cl._blocks[0].changes()):
        m = rmantainer.match(line)
        if m:
            mantainers[-1]['end'] = i-1
            mantainers.append({'name': m.group(1), 'end':None, 'start': i})
    mantainers[-1]['end'] = i

    foundMantainer = False
    for m in mantainers:
        if m["name"] == name:
            m = next(filter(lambda x:x['name'] == name, mantainers))
            cl._blocks[0]._changes.insert(m['end'], change)
            break
    else:

        if name:
            cl.add_change(f"  [ {name} ]")
        cl.add_change(change)
        if name:
            cl.add_change("")

    with (pkg.path/'debian/changelog').open('w') as f:
        cl.write_to_open_file(f)

def prepareNewChangelogEntry(pkg):
    if pkg.dirty:
        printStageDiff(pkg)
        return

    if pkg.readyForChanges:
        print(f'Don\'t modify package("{pkg.name}"), there is an open changelog entry.')
        return

    msg = "prepare new changelog entry."
    cl = pkg.changelog

    v = cl.version
    v.debian_revision = int(v.debian_revision) + 1
    cl.new_block(
            version=v,
            distributions="UNRELEASED",
            package=pkg.name,
            urgency=cl.urgency,
            author="Debian Qt/KDE Maintainers <debian-qt-kde@lists.debian.org>",
            date=datetime.datetime.now(datetime.timezone.utc).astimezone().strftime("%a, %d %b %Y %H:%M:%S %z")
            )
    cl.add_change('')

    with (pkg.path/'debian/changelog').open('w') as f:
        cl.write_to_open_file(f)

    pkg.git.index.add(["debian/changelog",
                      ])
    pkg.git.index.commit(msg)

def fixEpoch(pkg):
    cl = pkg.changelog
    v1 = cl.versions[1]
    v2 = cl.versions[0]
    if v1.epoch != v2.epoch:
        print(f"epoch bump for {pkg.name}: {v1}->{v2}")
        v2.epoch = v1.epoch
        cl.set_version(v2)
        with open(pkg.path/'debian/changelog', 'w') as f:
            cl.write_to_open_file(f)

def updateVersion(pkg, version):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return
    msg = f'New upstream release ({version.upstream_version}).'
    cl = pkg.changelog
    v1 = version
    v2 = cl.versions[0]
    v1.epoch = v2.epoch
    if v1 != v2:
        cl.set_version(v1)
        with open(pkg.path/'debian/changelog', 'w') as f:
            cl.write_to_open_file(f)
        if v1.upstream_version != v2.upstream_version:
            addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
        else:
            msg = f"Bump to version {version}."
        pkg.git.index.add(["debian/changelog",
                          ])
        pkg.git.index.commit(msg)

def printStageDiff(pkg):
    if pkg.dirty:
        print(f"{pkg.name} stage not empty: ")
        if pkg.git.index.diff(None):
            print(pkg.git.git.diff())
        else:
            print(pkg.git.git.diff(staged=True))
        print()

def checkGitStatus(pkg, push=True):
    if pkg.dirty:
        printStageDiff(pkg)
        return

    pkg.git.remotes.origin.fetch()
    branch = pkg.git.active_branch.name
    #if not branch in ("experimental","debian/experimental"):
    #    print(f"{pkg.name}: argh someting went wrong")
    #    return
    if branch in pkg.git.remotes.origin.refs:
        logpull = pkg.git.git.log(f'--pretty=format:%h - %an(%ar): %s',f'{branch}..origin/{branch}')
        logpush = pkg.git.git.log(f'--pretty=format:%h - %an(%ar): %s',f'origin/{branch}..{branch}')
    else:
        logpull = pkg.git.git.log(f'--pretty=format:%h - %an(%ar): %s',f'{branch}..origin/master')
        logpush = pkg.git.git.log(f'--pretty=format:%h - %an(%ar): %s',f'origin/master..{branch}')

    if logpull:
        print(f"{pkg.name} not uptodate:\n{logpull}")
        if not logpush:
        #    ret = input("Do you want to pull y/n?")
        #    if ret.lower() == "y":
                pkg.git.remotes.origin.pull()

    if logpush:
        print(f"{pkg.name} not pushed:\n{logpush}")
        if not logpull and push:
              if logpull.find("\n") == -1:
                   pkg.git.remotes.origin.push()
#              else:
#                ret = input("Do you want to push y/n?")
#                if ret.lower() == "y":
#                    pkg.git.remotes.origin.push()

    v = str(pkg.changelog.version)
    if pkg.changelog.version.epoch:
        ver = pkg.changelog.version
        ver.epoch=None
        v=f"{pkg.changelog.version.epoch}%{ver}"
    t = f"debian/{v}"
    try:
        tag = pkg.git.tags[t]
        pkg.git.remotes.origin.push(tag)
    except IndexError:
        pass

def replaceDep(block, field, name, version):
    rels = deb822.PkgRelation.parse_relations(block.get(field))
    p = next(filter(lambda x:x[0]['name']==name, rels))
    v = p[0]['version']
    if v != version:
        p[0]['version'] = version
        block[field] = rels2str(rels)

def replaceOrAddDep(block, field, dependency):
    rels = deb822.PkgRelation.parse_relations(block.get(field))
    try:
        p = next(filter(lambda x:x[0]['name']==dependency['name'], rels))
        return replaceDep(block, field, dependency['name'], dependency['version'])
    except StopIteration:
        rels.append([dependency,])
        block[field] = rels2str(rels)

def removeDep(block, field, name):
    rels = deb822.PkgRelation.parse_relations(block.get(field))
    block[field] = rels2str(filter(lambda x:x[0]['name']!=name, rels))


class options:
    pass

options.wrap_and_sort_opt = ["-b", "-t"]
options.dput_opt = ["-f", "routin"]
#options.dput_opt = []

def wrap_and_sort(pkg, filename=None):
    cmd = ['wrap-and-sort']
    cmd += options.wrap_and_sort_opt
    if filename:
        cmd.extend(['-f', filename])
    return subprocess.call(cmd, cwd=pkg.path)

def dput(pkg):
    cmd = ['dput']
    cmd += options.dput_opt
    cmd += [pkg.dscPath.with_name(pkg.dscPath.stem + "_source.changes")]
    return subprocess.call(cmd)

def bumpCompat(pkg, compatlevel):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return
    msg = f"Bump compat level to {compatlevel}."
    control = pkg.path/"debian/control"

    with tempfile.NamedTemporaryFile() as tmpfile:
        with control.open() as cf:
            for block in deb822.Deb822.iter_paragraphs(cf):
                if block.get("Source"):
                    rels = deb822.PkgRelation.parse_relations(block.get("Build-Depends"))
                    try:
                        p = next(filter(lambda x:x[0]['name']=="debhelper", rels))
                    except StopIteration:
                        p = next(filter(lambda x:x[0]['name']=="debhelper-compat", rels))

                    _compatLevel = p[0]['version'][1]
                    if _compatLevel.endswith("~"):
                        _compatLevel = _compatLevel[:-1]
                    ac = int(_compatLevel)
                    if ac == compatlevel:
                        return
                    if ac > compatlevel:
                        print(f"Skipping {pkg.name}: The compatlevel({ac}) is higher than expected({compatlevel})")
                        return

                    removeDep(block, 'Build-Depends', 'debhelper')
                    dep = { 'name': 'debhelper-compat',
                            'version':  ("=", f"{compatlevel}"),
                            'archqual': None,
                            'arch': None,
                            'restrictions': None,}

                    replaceOrAddDep(block, 'Build-Depends', dep)
                    block.dump(tmpfile)
                    continue
                tmpfile.write(b'\n')
                block.dump(tmpfile)

        tmpfile.flush()
        shutil.copyfile(tmpfile.name, control)
        wrap_and_sort(pkg, "debian/control")

    addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
    if (pkg.path/"debian/compat").exists():
        (pkg.path/"debian/compat").unlink()
        pkg.git.index.remove(["debian/compat"])
    pkg.git.index.add(["debian/changelog",
                       "debian/control",
                      ])
    pkg.git.index.commit(msg)

def updateVscToSalsa(pkg):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return
    msg = f"Update Vcs links to salsa."
    url = f"https://salsa.debian.org/qt-kde-team/kde/{pkg.upstreamName}"
    control = pkg.path/"debian/control"

    pkg.git.remotes.origin.set_url(f"qt-kde-team:kde/{pkg.upstreamName}.git")

    changed = False

    with tempfile.NamedTemporaryFile() as tmpfile:
        with control.open() as cf:
            for block in deb822.Deb822.iter_paragraphs(cf):
                if block.get("Source"):
                    if block['Vcs-Browser'] != url:
                        block['Vcs-Browser'] = url
                        changed = True
                    if block['Vcs-Git'] != (url+".git"):
                        block['Vcs-Git'] = url+".git"
                        changed = True
                    block.dump(tmpfile)
                    continue
                tmpfile.write(b'\n')
                block.dump(tmpfile)

        tmpfile.flush()
        shutil.copyfile(tmpfile.name, control)

    if changed:
        addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
        pkg.git.index.add(["debian/changelog",
                           "debian/control",
                          ])
        pkg.git.index.commit(msg)

def bumpStandardsVersion(pkg, version, msg=None):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return

    if not msg:
        msg = f'Bump Standards-Version to {version} (No changes needed).'

    control = pkg.path/"debian/control"
    changed = False

    with tempfile.NamedTemporaryFile() as tmpfile:
        for block in pkg.controlParagraphs():
            if block.get("Source"):
                if Version(block['Standards-Version']) < Version(version):
                    block['Standards-Version'] = str(version)
                    changed = True
                block.dump(tmpfile)
                continue
            tmpfile.write(b'\n')
            block.dump(tmpfile)

        tmpfile.flush()
        shutil.copyfile(tmpfile.name, control)

    if changed:
        print(f"changed: {pkg.name}")
        addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
        pkg.git.index.add(["debian/changelog",
                           "debian/control",
                          ])
        pkg.git.index.commit(msg)

def listMissingSymbolsfiles(pkg):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return

    control = pkg.path/"debian/control"
    changed = False

    l = []

    with control.open() as cf:
        for block in deb822.Deb822.iter_paragraphs(cf):
            if block.get('Package'):
                if re.match(r'^lib.*[0-9]$', block.get('Package')):
                    if not (pkg.path/f"debian/{block.get('Package')}.symbols").exists():
                        l.append(block.get('Package'))
    return l

def cmakeUpdateDeps(pkg):
    cl = pkg.changelog
    version= cl.versions[0]
    cmd = [os.path.join(CONFIG['pkg-kde-jenkins'],'hooks/prepare/cmake_update_deps'),
          "-d", str(pkg.path),
          "-u", pkg.unpackPath]
    ret = subprocess.call(cmd, cwd=pkg.path)
    if ret == 0:
        commit = pkg.git.head.commit
        msg = "Update build-deps and deps with the info from cmake"
        if commit.message.startswith(msg):
            if not "debian/changelog" in commit.stats.files:
                addChangeForMainatiner(pkg, f'  * {msg}.', os.environ['DEBFULLNAME'])
                pkg.git.index.add(["debian/changelog"])
                pkg.git.git.commit("--amend",f"-m {msg}.")


def decopy(pkg):
    cl = pkg.changelog
    version= cl.versions[0]
    cmd = [ CONFIG['decopy'],
#           "--split-debian",
           "--copyright-file", f"{pkg.path/'debian/copyright'}",
           "-o", f"{pkg.path/'debian/copyright'}"
          ]
    return subprocess.call(cmd, cwd=pkg.unpackPath)

def getBuildlogs(pkg):
    return subprocess.call(['pkgkde-getbuildlogs'], cwd=pkg.path)

def downloadTarball(pkg):
    if not pkg.tarball_path.exists():
        return subprocess.call(['uscan', '--download-current'], cwd=pkg.path)

def unpackTarball(pkg):
    cl = pkg.changelog
    tarball = pkg.tarball_path.resolve()
    if not pkg.unpackPath.exists() and tarball.exists():
        subprocess.call(['tar','-xaf', str(tarball)], cwd=pkg.path.parent)
    tarball_path = pkg.unpackPath
    if tarball_path.exists() and not (tarball_path/"debian").exists():
        os.symlink(pkg.path/"debian", tarball_path/"debian")

def updateSymbols(pkg, version, files=None):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return -1
    msg = f"Update symbols from buildds for {version}"

    dirName = None
    if not files:
        dirName = pkg.name+'_experimental_logs'
        if not (pkg.path/dirName).exists():
            dirName = pkg.name+'_unstable_logs'
        files = [pkg.path/dirName]
    cmd = ['pkgkde-symbolshelper', 'batchpatch', '-v', version, *files]
    if subprocess.call(cmd, cwd=pkg.path) != 0:
        print("Appying from patches failed (see above).")
        if dirName:
            shutil.rmtree(pkg.path/dirName)
        return -2
    if dirName:
        shutil.rmtree(pkg.path/dirName)
    list(map(os.remove, glob.glob(str(pkg.path/"*.orig"))))
    addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
    pkg.git.index.add(["debian"])
    if (pkg.path/"debian/files").exists():
        pkg.git.index.remove(["debian/files"])
    pkg.git.index.commit(msg)

def checkForSymbolChanges(pkg, tmpfile=None):
    fpath = pathlib.Path('/var/www/build/')/(pkg.dscPath.stem+"_amd64.build")
    try:
        context = None
        if tmpfile:
            sftp_client.get(str(fpath), tmpfile)
            context = open(tmpfile, 'rb')
        else:
            context = sftp_client.open(str(fpath))

        with context as f:
            text = f.read()
            m = re.search(b"\n\s*---\s+.*\n\s*\+\+\+\s+",text)
            if m:
                return pkg
    except FileNotFoundError:
        return

def updateCurrentSymbols(pkg, fpath=None):
    if not fpath:
        fpath=(pkg.path.parent/f"{pkg.name}_{pkg.changelog.upstream_version}-{pkg.changelog.debian_version}_amd64.build")

    version = pkg.changelog.version.upstream_version
    msg = f"Update symbols from build for {version}."
    if pkg.changelog.version.epoch:
        version = pkg.changelog.version.epoch + ":"+ version

    content = fpath.read_text()
    m = re.search("\n\s*---\s+debian/.*\.symbols", content)
    if m:
        cmd = ['pkgkde-symbolshelper', 'batchpatch', '-v', version, fpath.absolute()]
        if subprocess.call(cmd, cwd=pkg.path) == 0:
            addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
            pkg.git.index.add(["debian/changelog"])
            pkg.git.index.add([str(i.relative_to(pkg.path)) for i in (pkg.path/"debian").glob("*symbols")])
            pkg.git.index.commit(msg)

def bumpABI(pkg, libname):
    version = pkg.changelog.version.upstream_version
    if pkg.changelog.version.epoch:
        version = pkg.changelog.version.epoch + ":"+ version


    control = pkg.path/"debian/control"
    with control.open() as cf:
        for block in deb822.Deb822.iter_paragraphs(cf):
            if block.get("Package"):
                name = block.get("Package")
                m = re.match(f"{libname}(?P<abi>[0-9]+)(abi(?P<dabi>[0-9]+))?", name)
                if m:
                    abi = int(m.group("abi"))
                    if block.get("X-Debian-ABI"):
                        dabi = int(block.get("X-Debian-ABI"))
                    else:
                        dabi = 0
                    break

    msg = f"Bump Debian-ABI for {libname}{abi} because of ABI breakage to {dabi+1}."

    fulllibname = f"{libname}{abi}"
    if dabi > 0:
        fulllibname += f"abi{dabi}"

    with tempfile.NamedTemporaryFile() as tmpfile:
        with control.open() as cf:
            for block in deb822.Deb822.iter_paragraphs(cf):
                name = block.get("Package")
                if name:
                    name = block.get("Package")
                    if name == fulllibname:
                        block["X-Debian-ABI"] = str(dabi + 1)
                        block["Package"] = f"{libname}{abi}abi{dabi+1}"
                    else:
                        rels = deb822.PkgRelation.parse_relations(block.get("Depends"))
                        try:
                            p = next(filter(lambda x:x[0]['name'].startswith(fulllibname), rels))
                            p[0]['name'] = f"{libname}{abi}abi{dabi+1}"
                            p[0]['version'] = ('=', '${binary:Version}')
                            block["Depends"] = rels2str(rels)
                        except StopIteration:
                            pass

                    tmpfile.write(b'\n')

                block.dump(tmpfile)
            tmpfile.flush()
            shutil.copyfile(tmpfile.name, control)
            wrap_and_sort(pkg, "debian/control")
            pkg.git.index.add(["debian/control"])


    for f in (pkg.path/"debian").glob(fulllibname+".*"):
        if f.suffix == ".symbols":
            content = f.read_text()
            if dabi > 0:
                content = re.sub(f"{abi}abi[0-9]+", f"{abi}abi{dabi+1}", content)
                content = re.sub(f"ABI_{abi}_[0-9]+", f"ABI_{abi}_{dabi+1}", content)
            else:
                content = re.sub(f"^(lib.*.so.{abi}) {libname}{abi} #MINVER#\n", f"\g<1>abi{dabi+1} {libname}{abi}abi{dabi+1} #MINVER#\n ABI_5_1@ABI_5_1 {version}\n", content, flags=re.M)
                content = re.sub(f"@Base", f"@ABI_{abi}_{dabi+1}", content)
            content = re.sub("^( .+) ([\d.:]+)$", f"\g<1> {version}", content, flags=re.M)
            content = re.sub("^#MISSING: ([\d.:]+)# .*\n", "", content, flags=re.M)
            f.write_text(content)
        newname = f"{libname}{abi}abi{dabi+1}{f.suffix}"
        f.rename(f.parent/newname)
        pkg.git.index.remove(["debian/"+ f.name])
        pkg.git.index.add(["debian/"+ newname])

    if dabi > 0:
        addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
        pkg.git.index.add(["debian/changelog"])
        pkg.git.index.commit(msg)
    else:
        """cd <pkg>-<version>
        ln -s ../<pkg>/debian .
        qulit push -a
        quilt new enable_debianabimanager.diff && quilt add CMakeLists.txt && cat << EOF >> CMakeLists.txt && quilt refresh

        include(/usr/share/pkg-kde-tools/cmake/DebianABIManager.cmake)
        EOF
        """
        tarball_path = pkg.unpackPath
        if tarball_path.exists():
            if not (tarball_path/"debian").exists():
                os.symlink(pkg.path/"debian", tarball_path/"debian")
            subprocess.call(["quilt","push","-a"], cwd=tarball_path)
            subprocess.check_call(["quilt","new","enable_debianabimanager.diff"], cwd=tarball_path)
            subprocess.check_call(["quilt","add","CMakeLists.txt"], cwd=tarball_path)
            with (tarball_path/"CMakeLists.txt").open("a") as f:
                f.write("\ninclude(/usr/share/pkg-kde-tools/cmake/DebianABIManager.cmake)")
            subprocess.check_call(["quilt","refresh"], cwd=tarball_path)
            pkg.git.index.add(["debian/patches/series",
                               "debian/patches/enable_debianabimanager.diff"])

def updateDevDepends(pkg):
    version = pkg.changelog.version.upstream_version
    if pkg.changelog.version.epoch:
        version = pkg.changelog.version.epoch + ":"+ version

    control = pkg.path/"debian/control"
    with tempfile.NamedTemporaryFile() as tmpfile:
        with control.open() as cf:
            for block in deb822.Deb822.iter_paragraphs(cf):
                if block.get("Source"):
                    buildDepends = deb822.PkgRelation.parse_relations(block.get("Build-Depends"))
                if block.get("Package"):
                    name = block.get("Package")

                    if name.strip().endswith("-dev"):
                        with tempfile.TemporaryDirectory() as d:
                            pd = pathlib.Path(d)
                            debname = f"{name}_{pkg.changelog.version.upstream_version}-{pkg.changelog.version.debian_version}_amd64.deb"
                            subprocess.check_call(["ar","x",str(pkg.path.with_name(debname))], cwd = pd)
                            t = tarfile.open(pd/'data.tar.xz')
                            for member in [i for i in t.getnames() if re.match('\./usr/lib/x86_64-linux-gnu/cmake/.*-debian\.cmake', i)]:
                                f = t.extractfile(member)
                                content = f.read()
                                m = re.search(b'^\s*IMPORTED_LINK_DEPENDENT_LIBRARIES_DEBIAN "([^"]+)"\s*$', content, flags=re.M)
                                if not m:
                                    continue
                                link_dependend_libraries = m.group(1)
                                link_dependend_libraries = set(link_dependend_libraries.decode().split(";"))
                                print(name, link_dependend_libraries)
                                rtd = cud.ReqToDebianPkg()
                                ldl = rtd.process({i.replace(":",""):cud.Dependency(None) for i in link_dependend_libraries})
                                for dep in rtd.optional:
                                    try:
                                        p = next(filter(lambda x:x[0]['name']==dep, buildDepends))
                                        print(p)
                                        replaceOrAddDep(block, "Depends", p[0])
                                    except StopIteration:
                                        replaceOrAddDep(block, "Depends", {'name': dep, 'version': None})
                                print("->", block.get("Depends"))
                    tmpfile.write(b'\n')

                block.dump(tmpfile)
            tmpfile.flush()
            shutil.copyfile(tmpfile.name, control)
            wrap_and_sort(pkg, "debian/control")


def createSymbolsFiles(pkg):
    version = pkg.changelog.version.upstream_version
    if pkg.changelog.version.epoch:
        version = pkg.changelog.version.epoch + ":"+ version

    control = pkg.path/"debian/control"
    with control.open() as cf:
        for block in deb822.Deb822.iter_paragraphs(cf):
            if block.get("Package"):
                name = block.get("Package")
                m = re.match(r"(?P<libname>lib.*?(?P<abi>[0-9]+(abi[0-9]+)?))$", name)
                if m:
                    libname = m.groups('libname')[0]
                    if libname == "libkf5":
                        continue
                    abi = m.groups('abi')[1]
                    if not (pkg.path/f"debian/{libname}").exists():
                        with tempfile.TemporaryDirectory() as d:
                            pd = pathlib.Path(d)
                            debname = f"{libname}_{pkg.changelog.version.upstream_version}-{pkg.changelog.version.debian_version}_amd64.deb"
                            subprocess.check_call(["ar","x",str(pkg.path.with_name(debname))], cwd = pd)
                            t = tarfile.open(pd/'data.tar.xz')
                            libfile = [i for i in t.getnames() if re.match(f"^\./usr/lib/x86_64-linux-gnu/lib.*\.so\.{abi}$", i)][0]
                            libpath = pathlib.Path(libfile)
                            reallibpath = libpath.parent/t.getmember(libfile).linkpath
                            templibpath = pd/reallibpath.name
                            templibpath.write_bytes(t.extractfile("./"+str(reallibpath)).read())
                            subprocess.check_call(["pkgkde-gensymbols",
                                f"-p{libname}",
                                f"-v{version}",
                                f"-O{pd/'symbols.amd64'}",
                                f"-e{templibpath}"])
                            subprocess.check_call(["pkgkde-symbolshelper",
                                "create",
                                "-o", f"debian/{libname}.symbols",
                                "-v", version,
                                str(pd/'symbols.amd64')], cwd=pkg.path)

def addMissingDependsPackageField(package):
    devPackage = ""
    failure = False
    libraries = []
    for block in package.controlParagraphs():
        name = block.get("Package")
        if not name:
            continue

        m = re.match(r"(?P<libname>lib.*?(?P<abi>[0-9]+(abi[0-9]+)?))$", name)
        if m:
            libname = m.groups('libname')[0]
            if libname == "libkf5":
                continue
            libraries.append(libname)
        elif name.endswith("-dev"):
            if devPackage:
                print(f'Muliple -dev packages found. Giving up: {devPackage}, {name}')
                failure = True
            devPackage = name

    if not devPackage:
        print('No devPacakge found. Gving up.')
        failure = True

    if failure:
        return sys.exit(-2)

    changed = False
    addFiles = []
    for libname in libraries:
        symbolsFile = f"debian/{libname}.symbols"
        symbolsPath = package.path/symbolsFile
        if not symbolsPath.exists():
            print(f"Error: Can't find symbols file for {libname}.")
            continue
        text = symbolsPath.read_text()
        changedFile = False
        for m in re.finditer(r"(\n[^\s].*?#MINVER#.*?\n)([^\n]*?\n)", text):
            if m.group(2) == f"* Build-Depends-Package: {devPackage}\n":
                continue
            changedFile = True
            text = text.replace(m.group(0), f"{m.group(1)}* Build-Depends-Package: {devPackage}\n{m.group(2)}")
        if changedFile:
            changed = True
            symbolsPath.write_text(text)
            addFiles.append(symbolsFile)

    if not changed:
        return

    msg = f"Add Build-Depends-Package to symbols file."
    addChangeForMainatiner(package, f'  * {msg}', os.environ['DEBFULLNAME'])
    addFiles.append("debian/changelog")
    package.git.index.add(addFiles)
    package.git.index.commit(msg)


def getLintian(pkg, tmpfile=None):
    fpath = pathlib.Path('/var/www/build/')/(pkg.dscPath.stem+"_amd64.build")
    try:
        context = None
        if tmpfile:
            sftp_client.get(str(fpath), tmpfile)
            context = open(tmpfile, 'rb')
        else:
            context = sftp_client.open(str(fpath))

        with context as f:
            text = f.read()
            m = re.search(b"\nSetting up sbuild-build-depends-lintian-dummy.*\n(?P<issues>(.*\n)+)\nI: Lintian run was successful.",text)
            if m:
                return m.group('issues').decode()
    except FileNotFoundError:
        return

def updateL10NPkgsVersion(pkg, version):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return -1
    msg = f"Set l10npkgs_firstversion_ok to {version}"
    regex = re.compile(r"\n(\s*l10npkgs_firstversion_ok\s*:=\s*)(.*)\n")
    rules = pkg.path/"debian/rules"

    text = rules.read_text()
    s = regex.search(text)
    if not s or s.group(2) == version:
        return -2

    rules.write_text(regex.sub(f"\n\g<1>{version}\n",text))
    addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
    pkg.git.index.add(["debian/changelog",
                       "debian/rules",
                      ])
    pkg.git.index.commit(msg)

def useVirtualPackage(pkg):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return -1

    control = pkg.path/"debian/control"

    changed = False

    with tempfile.NamedTemporaryFile() as tmpfile:
        with control.open() as cf:
            for block in deb822.Deb822.iter_paragraphs(cf):
                block.changed = False
                if "Package" in block:
                    name = block.get('Package').split("-")

                    try:
                        if block["Provides"] == "${ABI:VirtualPackage}":
                            continue
                    except KeyError:
                        pass

                    if name[0].startswith("lib") and (len(name) < 2 or not name[1] in ("dev", "doc", "dbg", "data", "bin", "plugins")):
                        block["Provides"] = "${ABI:VirtualPackage}"
                        block.changed = True

                if not block.get("Source"):
                    tmpfile.write(b'\n')
                if block.changed:
                    changed = True
                block.dump(tmpfile)

        if changed:
            tmpfile.flush()
            shutil.copyfile(tmpfile.name, control)

    for symbolfile in (pkg.path/"debian").glob("*.symbols"):
        changed = True
        pkg.git.index.remove([str(symbolfile.relative_to(pkg.path))])
        symbolfile.unlink()

    if not changed:
        return

    rules = pkg.path/"debian/rules"

    contents = rules.read_text()
    lines = [ "include /usr/share/dpkg/pkg-info.mk",
              """AbiVirtualPackageVersion = $(call dpkg_late_eval,AbiVirtualPackageVersion,echo '${DEB_VERSION_UPSTREAM}' | sed -e 's/\.[0-9]\+$$//')
pkgs_lib = $(filter-out %-dev %-doc %-dbg %-data %-bin %-plugins,$(filter lib%,$(shell dh_listpackages)))""",
              """override_dh_makeshlibs:
	for pkg in $(pkgs_lib); do \\
		name=$$( echo "$${pkg}" | sed -e 's/abi[0-9]\+\s*//'); \\
		echo "ABI:VirtualPackage=$${name}-${AbiVirtualPackageVersion}" >> debian/$${pkg}.substvars; \\
		$(overridden_command) -p$${pkg} -V "$${pkg} (>= $(DEB_VERSION_EPOCH_UPSTREAM)), $${name}-${AbiVirtualPackageVersion}"; \\
	done"""
            ]

    for nr, line in enumerate(lines):
        if "\n"+line in contents:
            continue
        changed = True

        def replace(m):
            return f"{m.group(1)}{line}\n\n{m.group(2)}"

        if nr == 0:
            if "\ninclude " in contents:
                contents = re.sub(r"(\n)(include )", f"\g<1>{line}\n\g<2>", contents, count=1)
            else:
                raise Exception("keine include zeile wo ich anbauen kann.")
        if nr == 1:
            if "\noverride" in contents:
                contents = re.sub(r"(\n)(override)", replace, contents, count=1)
            else:
                contents += "\n" + line
        if nr == 2:
            regex = re.compile(r"(\n)(override_(dh_strip|dh_auto_test))")
            if regex.search(contents):
                contents = regex.sub(replace, contents, count=1)
            else:
                contents += "\n\n"+line

    if changed:
        rules.write_text(contents)

    if changed:
        wrap_and_sort(pkg, "debian/control")
        wrap_and_sort(pkg, "debian/rules")
        msg = f"Use virtual packages to bundle KDEPIM."
        addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
        pkg.git.index.add(["debian/changelog",
                           "debian/control",
                           "debian/rules",
                          ])
        pkg.git.index.commit(msg)


def enforceVirtualPackage(pkg):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return -1

    libs = {}
    for p in packages.values():
        control = p.path/"debian/control"
        with control.open() as cf:
            for block in deb822.Deb822.iter_paragraphs(cf):
                if "Package" in block:
                     if block.get('Package').endswith("-dev"):
                         a_pkg = apt_cache[block.get('Package')]
                         unstable = next(itertools.chain.from_iterable([v for f in v.file_list if f[0].site == 'deb.debian.org' and f[0].archive == "unstable"] for v in a_pkg.version_list))
                         libs[block.get('Package')] = Version(unstable.ver_str)

    changed = False
    control = pkg.path/"debian/control"
    with tempfile.NamedTemporaryFile() as tmpfile:
        with control.open() as cf:
            for block in deb822.Deb822.iter_paragraphs(cf):
                if block.get("Source"):
                    rels = deb822.PkgRelation.parse_relations(block.get("Build-Depends"))
                    for rel in rels:
                        if rel[0]['name'] in libs:
                            if rel[0]['version'] != (">>", str(libs[rel[0]['name']])):
                                changed = True
                            rel[0]['version'] = (">>", str(libs[rel[0]['name']]))
                    block["Build-Depends"] = rels2str(rels)
                    block.dump(tmpfile)
                    continue
                tmpfile.write(b'\n')
                block.dump(tmpfile)
        if changed:
            tmpfile.flush()
            shutil.copyfile(tmpfile.name, control)
            wrap_and_sort(pkg, "debian/control")
            msg = f"Enforce depdendencies between KDEPIM packages to enable bundling."
            addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
            pkg.git.index.add(["debian/changelog",
                               "debian/control",
                              ])
            pkg.git.index.commit(msg)


def cleanupBreaknConflicts(pkg):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return -1

    def cleanup(rels):
        ret = []
        for rel in rels:
            if not rel[0]['name']:
                continue
            try:
                a_pkg = apt_cache[rel[0]['name']]
            except KeyError:
                ret.append(rel)
                continue

            # Find version in stable
            try:
                stable_version = next(itertools.chain.from_iterable([v for f in v.file_list if f[0].site == 'deb.debian.org' and f[0].archive == "stable"] for v in a_pkg.version_list))
            except StopIteration:
                block.changed  = True
                continue

            if rel[0]['version'][0] == "<<":
                if Version(rel[0]['version'][1]) < Version(stable_version.ver_str):
                    block.changed  = True
                    continue

            if rel[0]['version'][0] == "<=":
                if Version(rel[0]['version'][1]) <= Version(stable_version.ver_str):
                    block.changed  = True
                    continue
            ret.append(rel)
        return ret

    control = pkg.path/"debian/control"

    changed = False

    with tempfile.NamedTemporaryFile() as tmpfile:
        with control.open() as cf:
            for block in deb822.Deb822.iter_paragraphs(cf):
                block.changed  = False
                if "Breaks" in block:
                    rels = deb822.PkgRelation.parse_relations(block.get("Breaks"))
                    nrels = cleanup(rels)
                    if nrels:
                        block['Breaks'] = rels2str(nrels)
                    else:
                        del block['Breaks']
                if "Conflicts" in block:
                    rels = deb822.PkgRelation.parse_relations(block.get("Conflicts"))
                    nrels = cleanup(rels)
                    if nrels:
                        block['Conflicts'] = rels2str(nrels)
                    else:
                        del block['Conflicts']
                if "Replaces" in block:
                    rels = deb822.PkgRelation.parse_relations(block.get("Replaces"))
                    nrels = cleanup(rels)
                    if nrels:
                        block['Replaces'] = rels2str(nrels)
                    else:
                        del block['Replaces']
                if not block.get("Source"):
                    tmpfile.write(b'\n')
                if block.changed:
                    changed = True
                block.dump(tmpfile)

        if changed:
            tmpfile.flush()
            shutil.copyfile(tmpfile.name, control)

    if changed:
        wrap_and_sort(pkg, "debian/control")
        msg = f"Delete not needed Breaks/Confilcts."
        addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
        pkg.git.index.add(["debian/changelog",
                           "debian/control",
                          ])
        pkg.git.index.commit(msg)


def addMyselfToUploaders(pkg):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return -1
    msg = f"Add myself to Uploaders."
    control = pkg.path/"debian/control"

    with tempfile.NamedTemporaryFile() as tmpfile:
        with control.open() as cf:
            for block in deb822.Deb822.iter_paragraphs(cf):
                if block.get("Source"):
                    try:
                        next(filter(lambda x: x.startswith("Sandro Knau"),[i.strip() for i in re.split("[\n,]", block.get("Uploaders"))]))
                    except StopIteration:
                        block['Uploaders'] += ",\n    Sandro Knauß <hefee@debian.org>"
                        block.dump(tmpfile)
                        continue
                    else:
                        return
                tmpfile.write(b'\n')
                block.dump(tmpfile)

        tmpfile.flush()
        shutil.copyfile(tmpfile.name, control)
        wrap_and_sort(pkg, "debian/control")

    addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
    pkg.git.index.add(["debian/changelog",
                       "debian/control",
                      ])
    pkg.git.index.commit(msg)

def release(pkg, dist):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return -1

    if pkg.changelog.distributions != "UNRELEASED":
        print(f"Verweigere feige die Ausführung für {pkg.name}, weil distribution im changelog != UNRELEASED")
        return -2

    msg = f"release to {dist}"
    control = pkg.path/"debian/control"
    try:
        d = deb822.Deb822(control.open())
        next(filter(lambda x: x.startswith("Sandro Knau"),[i.strip() for i in re.split("[\n,]", d.get("Uploaders"))]))
    except StopIteration:
        addChangeForMainatiner(pkg, '', None)
        addChangeForMainatiner(pkg, f'  * Team upload.', None)
        msg += " as team upload."

    subprocess.call(["dch", "-r", "--distribution", dist], cwd=pkg.path)
    pkg.git.index.add(["debian/changelog"])
    pkg.git.index.commit(msg)
    subprocess.call(["pkgkde-vcs", "tag", "-s"], cwd=pkg.path)

multiarchhints=None

def updateMultiarchHints():
    with open(os.path.join(CONFIG['basedir'],'multiarch-hints.yaml'),'w') as f:
        f.write(requests.get('https://dedup.debian.net/static/multiarch-hints.yaml').text)

def updateUDD():
    with open(os.path.join(CONFIG['basedir'],'udd.yaml'),'w') as f:
        f.write(requests.get('https://udd.debian.org/dmd/?email1=debian-qt-kde%40lists.debian.org&format=yaml').text)

def checkForMultiarchHints(pkg):
    global multiarchhints
    if not multiarchhints:
        with open(os.path.join(CONFIG['basedir'], 'multiarch-hints.yaml'),'r') as f:
            dataMap = yaml.load(f)
        multiarchhints = dataMap['hints']

    hints = []
    for hint in multiarchhints:
        try:
            if hint["source"] == pkg.name: # and hint['version'] == pkg.changelog.version:
                hints.append(hint)
        except:
            pass
    return hints

def updateBritneyOutput():
    with open(os.path.join(CONFIG['basedir'],'update_output.txt'),'w') as f:
        f.write(requests.get('https://release.debian.org/britney/update_output.txt').text)

def checkForBritney(pkg):
    britney = open(os.path.join(CONFIG['basedir'], 'update_output.txt'),'r').read()
    ret = []
    for i in re.finditer(f"trying:.*\s{pkg.name}(\s+.*|)\nskipped:.*\n(    .*\n)*", britney):
        ret.append(i.group(0))
    return ret

def updateEpochInSymbols(pkg):
    for f in pkg.path.glob("debian/*.symbols"):
        updateSymbols = False
        text = f.read_text()
        for i in re.findall("^( .+ )([\d.:]+)$", text, re.M):
            v = Version(i[1])
            if v.epoch != p.changelog.version.epoch:
                updateSymbols = True
                v.epoch = p.changelog.version.epoch
                vs = v.upstream_version.split(".")
                if len(vs) == 2:
                    vs.append("0")
                    v.upstream_version = ".".join(vs)
                text = re.sub(rf"{re.escape(i[0])}{re.escape(i[1])}",f"{i[0]}{v}", text)
        if updateSymbols:
            print(f"Update symbols for {pkg.name} {f.name}")
            f.write_text(text)

def updateCopyrightFormat(pkg):
    msg = "Use secure copyright format uri."
    c = copyright.Copyright((pkg.path/"debian/copyright").open())
    if c.header.format == "http://www.debian.org/doc/packaging-manuals/copyright-format/1.0/":
        c.header.format="https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/"
        (pkg.path/"debian/copyright").write_text(c.dump())
        addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
        pkg.git.index.add(["debian/changelog",
                            "debian/copyright",
        ])
        pkg.git.index.commit(msg)
        print(f"update {pkg.name} copyright uri")

def createGitignoreForFiles(pkg):
    msg = "ignore debian/files."

    gitignore = pkg.path/"debian/.gitignore"

    if not gitignore.exists():
        gitignore.write_text("files\n")
        pkg.git.index.add(["debian/.gitignore"])
        pkg.git.index.commit(msg)

def removeACCTest(pkg):
    msg = "Removed acc autopkgtest."
    accControl = pkg.path/"debian/tests/control"
    changed = False
    first = True
    if accControl.exists():
        with tempfile.NamedTemporaryFile() as tmpfile:
            with accControl.open() as cf:
                for block in deb822.Deb822.iter_paragraphs(cf):
                    if block.get("Tests") == "acc":
                        changed = True
                        continue

                    if not first:
                        tmpfile.write(b'\n')

                    block.dump(tmpfile)
                    first = False

            if changed:
                tmpfile.flush()
                shutil.copyfile(tmpfile.name, accControl)

    if changed or (pkg.path/"debian/tests/acc").exists():
        addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
        pkg.git.index.add([
            "debian/changelog",
            str(accControl),
        ])
        if (pkg.path/"debian/tests/acc").exists():
            (pkg.path/"debian/tests/acc").unlink()
            pkg.git.index.remove(["debian/tests/acc"])

        accFiles = list(pkg.path.glob("debian/*.acc.*"))
        for f in accFiles:
            f.unlink()
        if accFiles:
            pkg.git.index.remove([str(i) for i in accFiles])

        pkg.git.index.commit(msg)

def removeTestsuiteTest(pkg):
    msg = "Removed testsuite autopkgtest."
    accControl = pkg.path/"debian/tests/control"
    changed = False
    first = True
    if accControl.exists():
        with tempfile.NamedTemporaryFile() as tmpfile:
            with accControl.open() as cf:
                for block in deb822.Deb822.iter_paragraphs(cf):
                    if block.get("Tests") == "testsuite":
                        changed = True
                        continue

                    if not first:
                        tmpfile.write(b'\n')

                    block.dump(tmpfile)
                    first = False

            if changed:
                tmpfile.flush()
                shutil.copyfile(tmpfile.name, accControl)

    if changed or (pkg.path/"debian/tests/testsuite").exists():
        addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
        pkg.git.index.add([
            "debian/changelog",
        ])

        if first:
            pkg.git.index.remove(["debian/tests/control"])
        else:
            pkg.git.index.add(["debian/tests/testsuite"])

        if (pkg.path/"debian/tests/testsuite").exists():
            (pkg.path/"debian/tests/testsuite").unlink()
            pkg.git.index.remove(["debian/tests/testsuite"])


        if (pkg.path/"debian/tests/testsuite.xsession").exists():
            (pkg.path/"debian/tests/testsuite.xsession").unlink()
            pkg.git.index.remove(["debian/tests/testsuite.xsession"])

        pkg.git.index.commit(msg)

def getPackage(control):
    global packages
    if control.exists():
        with control.open() as cf:
            for block in deb822.Deb822.iter_paragraphs(cf):
                block['Package'] = block['Source']
                pkg = Package(block)
                packages[block['Package']] = pkg
                return pkg

def createPackage(basedir, name):
    if not (basedir/name).exists():
        Git(basedir).clone("qt-kde-team:kde/"+name)
        pkg = getPackage((basedir/name)/"debian/control")
        with pkg.git.config_writer() as cw:
            cw.add_section("user")
            cw.set("user","email","hefee@debian.org")
        return pkg

def buildLocally(pkg):
    subprocess.call(["sbuild", "-d", "unstable",
        '--extra-repository', "deb [trusted=yes] file:///repo tuxin main",
        pkg.dscName], cwd=os.path.join(CONFIG['basedir'],'kde'))


summary=b"""+------------------------------------------------------------------------------+
| Summary                                                                      |
+------------------------------------------------------------------------------+"""

def getStatusLocal(pkg):
    state = None
    name = pkg.dscPath.stem + "_source.build"
    sourcePath = pkg.dscPath.with_name(name)
    name = pkg.dscPath.stem + "_amd64.build"
    amd64Path = pkg.dscPath.with_name(name)
    if sourcePath.exists():
        state = "waiting"
        if amd64Path.exists():
            if sourcePath.stat().st_atime > amd64Path.stat().st_atime:
                return state

    try:
        text = amd64Path.read_bytes()
        m = re.search(b"^Status:\s*(.*)$",text[text.find(summary):], re.M)
        if m:
            return m.group(1).decode()
        return "started"
    except FileNotFoundError:
            return state


def updateSalsaCI(pkg):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return -1
    addAnycase = False
    if not (pkg.path/"debian/salsa").exists() or not (pkg.path/"debian/salsa-ci.yml").exists():
        addAnycase = True

    salsaci = pathlib.Path(os.path.join(os.path.dirname(__file__),'salsaci'))
    shutil.rmtree(pkg.path/"debian/salsa", ignore_errors=True)
    shutil.copytree(salsaci, pkg.path/"debian", dirs_exist_ok=True)

    for d in pkg.git.index.diff(None):
        if d.a_path.startswith("debian/salsa"):
            break
    else:
        if not addAnycase:
            return

    msg = "enable team builder to be able to build on salsa."
    pkg.git.index.add(["debian/salsa",
                       "debian/salsa-ci.yml",
                      ])
    pkg.git.index.commit(msg)


def getRidOfDebugSymbolPacakge(pkg):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return -1

    rules = pkg.path/"debian/rules"

    m = re.search(r"--dbgsym-migration\s*=\s*['\"].*?\(<=\s*(.*)\)['\"]", rules.read_text())

    if m:
        migration_version = m.group(1)
        for block in pkg.controlParagraphs():
             if block.get('Package','').endswith("-dev"):
                a_pkg = apt_cache[block.get('Package')]
                stable = next(itertools.chain.from_iterable([v for f in v.file_list if f[0].site == 'deb.debian.org' and f[0].archive == "stable"] for v in a_pkg.version_list))
                if Version(stable.ver_str) < Version(m.group(1)):
                    return
                break
        text = re.sub(rf"\n\s*\noverride_dh_strip:\s*\n\s*.* {re.escape(m.group(0))}\s*\n","\n", rules.read_text())

        rules.write_text(text)
        msg = "Get rid of debug-symbol-migration package."
        addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
        pkg.git.index.add(["debian/rules",
                           "debian/changelog",
                          ])
        pkg.git.index.commit(msg)


def rulesRequireRoot(pkg):
    if not pkg.readyForChanges:
        print(f'Can\'t modify package("{pkg.name}"), cause stage is not clean or no open changelog entry.')
        return -1

    control = pkg.path/"debian/control"

    with tempfile.NamedTemporaryFile() as tmpfile:
        for block in pkg.controlParagraphs():
            if block.get("Source"):
                if block.get('Rules-Requires-Root', None) == "no":
                    return
                block['Rules-Requires-Root'] = "no"
                block.dump(tmpfile)
                continue
            tmpfile.write(b'\n')
            block.dump(tmpfile)
        tmpfile.flush()
        shutil.copyfile(tmpfile.name, control)
        wrap_and_sort(pkg, "debian/control")

    msg = "Add Rules-Requires-Root field to control."
    addChangeForMainatiner(pkg, f'  * {msg}', os.environ['DEBFULLNAME'])
    pkg.git.index.add(["debian/changelog",
                       "debian/control",
                      ])
    pkg.git.index.commit(msg)



def includePkgInRepo(pkg):
    name = pkg.dscPath.stem + "_amd64.changes"
    path = pkg.dscPath.with_name(name)
    if path.exists():
        subprocess.call(["reprepro", "include", "tuxin", str(path)], cwd=CONFIG['repopath'])
    else:
        print(f"{pkg.name} muss noch gebaut werden")

with open(os.path.join(os.path.dirname(__file__),'config.yml')) as f:
    CONFIG = yaml.safe_load(f)

warnings.filterwarnings("ignore", category=UserWarning, message="cannot parse package relationship \"\"")
warnings.filterwarnings("ignore", category=UserWarning, message='cannot parse package relationship "\${kde-l10n:all}"')

sys.path.insert(0, os.path.join(CONFIG['pkg-kde-jenkins'], 'hooks/prepare'))
import cmake_update_deps as cud

apt_cache = apt_pkg.Cache()

basedir = pathlib.Path(CONFIG['basedir'])

packages = {}

control = pathlib.Path("debian/control")
pkg = getPackage(control)

for p in (i for i in pathlib.Path(".").iterdir() if (i/"debian/control").exists()):
    control = p/"debian/control"
    getPackage(control)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.WarningPolicy())
client.load_system_host_keys()
#client.connect('routin.local', username='hefee')
#sftp_client = client.open_sftp()

## SAMPLES of how you can run a function to all packages

#check epoch
_ = map(fixEpoch, packages.values())
# list(_)

#check pushed?
_ = map(checkGitStatus, packages.values())
#list(_)

