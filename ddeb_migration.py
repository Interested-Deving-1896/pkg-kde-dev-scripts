#!/usr/bin/env python
# -*- coding: utf-8 -*-

import debian.deb822 as deb822
import debian.changelog as changelog
import re
import subprocess
import sys

out = subprocess.check_output(['dh_listpackages'])

packages = filter(lambda x: x != '', out.split('\n'))

dbg_packages = filter(lambda x: x.endswith('-dbg'), packages)

if len(dbg_packages) == 0:
    print "No dbg package, nothing to do."
    sys.exit(0)
if len(dbg_packages) > 1:
    print "Too many dbg packages in this package, migrate manually"
    sys.exit(1)

if (len(packages) - len(dbg_packages)) == 1:
    print "A single binary is produced now, needs to be installed in debian/tmp"

    with open('debian/rules') as rules_file:
        for line in rules_file:
            m = re.search('--destdir=debian/tmp', line)
            if m:
                print "Already there."
                break
        else:
            print "Please add manually."
            sys.exit(2)

with open('debian/control') as control_file:
    control = list(deb822.Deb822.iter_paragraphs(control_file))

new_control = []
for block in control:
    if block.get('Package') not in dbg_packages:
        new_control.append(unicode(block))

with open('debian/changelog') as changelog_file:
    chlog = changelog.Changelog(changelog_file)

version = chlog.version

subprocess.call(['sed', '-i', 's/--dbg-package=' + re.escape(dbg_packages[0])
                 + '/--ddeb-migration=\'' + dbg_packages[0] + ' (<= ' +
                 unicode(version) + '~)\'/', 'debian/rules'])

with open('debian/control', 'w') as f:
    b = u'\n'.join(new_control).encode('utf-8')
    f.write(b)
