#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# group_breaks, add breaks for the reverse dependencies in the release
# group

#  Copyright © 2016 Maximiliano Curia <maxy@gnuservers.com.ar>

#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.

#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.

#  You should have received a copy of the GNU General Public License
#  along with this program; if not, see <http://www.gnu.org/licenses/>.

''' Add breaks for the reverse dependencies in the release group
'''

# This is intended to be used in group releases that are considered to be one
# single release upstream and that share a common version number.
# In particular it's needed for the KDE Frameworks releases, as upstream
# breaks the internal abis regularly, in ways that are only visible when
# mixing different versions (see the amount of reports for mixing 5.22 and
# 5.23)

import argparse
import logging
import os
import subprocess
import shutil
import sys
import tempfile

import apt
import debian.deb822 as deb822
from debian.debian_support import Version, version_compare


def process_options():
    ''' Initialize logging and process args '''

    kw = {
        'format': '[%(levelname)s] %(message)s',
    }

    arg_parser = argparse.ArgumentParser(description=__doc__,
                                         fromfile_prefix_chars='@')

    arg_parser.add_argument('paths', nargs='+',
                            help='Paths to the package dirs to process')
    arg_parser.add_argument('--debug', action='store_true')
    arg_parser.add_argument('--no-act', action='store_true')
    arg_parser.add_argument('--output', '-o', type=argparse.FileType('w'))
    arg_parser.add_argument('--wrap-and-sort-opt', action='append', default=[])

    args = arg_parser.parse_args()

    if args.debug:
        kw['level'] = logging.DEBUG

    logging.basicConfig(**kw)

    return args


def source_name(path):
    ''' Obtain the package source name '''

    logging.debug('source_name: path={}'.format(path))

    control_file = os.path.join(path, 'debian/control')
    with open(control_file) as f:
        source_control = deb822.Deb822(f)

    return source_control.get('Source')


def list_packages(path):
    ''' List binary packages '''

    logging.debug('list_packages: path={}'.format(path))

    out = subprocess.check_output(['dh_listpackages'],
                                  universal_newlines=True,
                                  cwd=path)
    packages = list(filter(lambda x: x != '', out.split('\n')))
    return packages


# A bit hacky, it uses the internal representation of the module
def python_apt_rdepends(package, cache):
    ''' Obtain reverse dependencies

    Only Depends are considered. This function uses the python apt module to
    obtain the reverse dependencies.
    '''
    rdepends = set()
    try:
        full_rdepends = cache[package]._pkg.rev_depends_list
    except KeyError:
        return rdepends

    for dep in full_rdepends:
        if dep.dep_type in ('Breaks', 'Conflicts', 'Enhances', 'Pre-Depends',
                            'Recommends', 'Replaces', 'Suggests'):
            continue
        rdepends.add(dep.parent_pkg.name)
    return rdepends


# Way too slow
def apt_cache_rdepends(package, cache):
    ''' Obtain reverse dependencies

    Only Depends are considered. This function calls apt-cache to obtain the
    reverse dependencies.
    '''

    logging.debug('apt_rdepends: package={}'.format(package))

    cmd = ['apt-cache', 'rdepends', '--no-recommends', '--no-suggests',
           '--no-conflicts', '--no-breaks', '--no-replaces', '--no-enhances']
    cmd.append(package)
    out = subprocess.check_output(cmd, universal_newlines=True)
    return set(p.strip() for p in out.splitlines() if p.startswith(' '))


apt_rdepends = python_apt_rdepends


def version(path):
    ''' Obtain package version '''

    logging.debug('versions: path={}'.format(path))

    cmd = ['dpkg-parsechangelog', '-S', 'version']
    return subprocess.check_output(
        cmd, cwd=path, universal_newlines=True).strip()


def get_packages(paths):
    ''' Obtain package information for each package dir '''

    packages = {}
    all = set()

    for path in paths:
        logging.info("get_packages: current path = {}".format(path))
        source_package = {}
        binaries = list_packages(path)
        source_package['binaries'] = binaries
        all.update(binaries)
        source_package['path'] = path
        source_package['version'] = Version(version(path))
        packages[source_name(path)] = source_package
    return packages, all


def get_binsrc_map(packages):
    ''' Inverted dictionary to ease lookups '''

    binaries = {}
    for source_name, source_package in packages.items():
        for package in source_package['binaries']:
            # TODO: We would probably need to store the version of the binary
            # package, to handle the cases when we tweak them.
            binaries[package] = {'source': source_name}
    return binaries


def get_group_upstream_version(packages):
    ''' Return the upstream version in the group '''

    return min(
        v['version'].upstream_version for k, v in packages.items())


def major_minor_version(version):
    ''' Get MAJOR.minor version '''

    return '.'.join(version.split('.')[:2])


def obtain_rdepends(packages, all, cache):
    ''' Add rdepends information of each package

    We only keep the rdepends that are in produced in this group
    '''

    for source_name, source_package in packages.items():
        rdepends = {}
        for package in source_package['binaries']:
            group_rdepends = apt_rdepends(package, cache) & all
            # Ignore dependencies in the same source package
            rdepends[package] = group_rdepends.difference(
                source_package['binaries'])
        source_package['rdepends'] = rdepends


def update_rels(rels, breaks_update):
    ''' Modify the rels from the Breaks in the binary package '''

    changes = 0
    d = dict(breaks_update)
    for rel in rels:
        for i in rel:
            if i['name'] in d:
                # Update existing value
                version = d[i['name']].full_version
                del(d[i['name']])
                if not i['version']:
                    i['version'] = ('<<', version)
                    changes += 1
                    continue
                cur_version = i['version'][1]
                if cur_version.startswith('$'):
                    # subst var, leave alone
                    continue
                if version_compare(cur_version, version) < 0:
                    i['version'] = ('<<', version)
                    changes += 1
    for name, version in d.items():
        i = {
            'name': name,
            'version': ('<<', version),
            'arch': None,
            'archqual': None,
            'restrictions': None,
        }
        rels.append([i])
        changes += 1
    return changes


def update_control(path, breaks, simulate):
    ''' Update the control file '''

    logging.debug('list_control: path={}, breaks={}'.format(path, breaks))

    def update_section(section, breaks_update):
        changes = 0
        if not breaks_update:
            return changes
        rels = deb822.PkgRelation.parse_relations(section.get('Breaks', ''))
        changes = update_rels(rels, breaks_update)
        if changes:
            section['Breaks'] = deb822.PkgRelation.str(rels)
        return changes

    filename = os.path.join(path, 'debian/control')
    changes = 0
    with open(filename) as control_file, \
            tempfile.NamedTemporaryFile() as tmpfile:
        for i, section in enumerate(
                deb822.Deb822.iter_paragraphs(control_file)):
            if i:
                tmpfile.write(b'\n')
            binary = section.get('Package')
            changes += update_section(section, breaks.get(binary))
            section.dump(tmpfile)
        if not simulate and changes:
            tmpfile.flush()
            shutil.copyfile(tmpfile.name, filename)
    return changes


def commit(path, msg, options):
    ''' Commit the changes '''

    logging.debug('commit: path={}, msg={}'.format(path, msg))

    def changes():
        status = subprocess.check_output(
            ['git', 'status', '--porcelain'], cwd=path,
            universal_newlines=True)
        return status.strip()

    def wrap_and_sort(filename=None):
        cmd = ['wrap-and-sort']
        cmd += options.wrap_and_sort_opt
        if filename:
            cmd.extend(['-f', filename])
        subprocess.call(cmd, cwd=path)

    if not changes():
        return
    filename = os.path.join(path, 'debian/control')
    wrap_and_sort(filename)
    if not changes():
        return

    subprocess.call(['git', 'add', filename], cwd=path)
    subprocess.call(['git', 'commit', '-m', msg],
                    cwd=path)


def update_breaks(packages, binaries, options):
    ''' Update the 'Breaks' fields for each binary package '''

    def _get_version(source_name):

        v = packages[source_name]['version']
        version = Version(
            '.'.join(v.upstream_version.split('.')[:2])
        )
        version.epoch = v.epoch

    # Package names of the updated ones
    modified = []
    simulate = options.no_act

    for source_name, source_package in packages.items():
        breaks = {}
        for package, rdepends in source_package['rdepends'].items():
            if not rdepends:
                continue
            for rdepend in rdepends:
                rdepend_version = _get_version(binaries[rdepend]['source'])
                breaks.setdefault(package, []).append(
                    (rdepend, rdepend_version))
        changes = update_control(source_package['path'], breaks, simulate)
        if changes:
            if not simulate:
                commit(source_package['path'],
                       'Bump group breaks ({})'.format(_get_version(source_name)),
                       options)
            modified.append(source_name)
    return modified


def report(packages, modified, output):

    if modified:
        logging.info('Modified packages:')
    for name in modified:
        s = '{}\t{}\n'.format(name, packages[name]['path'])
        if output:
            logging.info(s)
            output.write(s)
        else:
            sys.stdout.write(s)


def main():

    options = process_options()
    cache = apt.Cache()

    logging.info("Processing: {}".format(options.paths))

    packages, all_binaries = get_packages(options.paths)

    binaries = get_binsrc_map(packages)

    obtain_rdepends(packages, all_binaries, cache)

    modified = update_breaks(packages, binaries, options)

    report(packages, modified, options.output)


if __name__ == "__main__":
    main()
