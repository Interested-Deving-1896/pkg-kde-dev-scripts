#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2019 Sandro Knauß <hefee@debian.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from collections import defaultdict
from debian.debian_support import Version
import pathlib
import pydot
import re
import sys

from functions import basedir, getPackage
import salsa

product = sys.argv[1]
version = sys.argv[2]

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

#getStatus = getStatusLocal
getStatus = salsa.getBuildStatus

STATUS={"waiting":"blue",
        "started":"yellow",
        "running":"yellow",
        "successful":"green",
        "success":"green",
        "attempted":"red",
        "failed":"red",
        "given-back":"red",
       }


fname = f"{product}.{version}.tier.dot"
buildname = f"{product}.{version}.tier.status.dot"
curdir = pathlib.Path(__file__).parent

graph = pydot.graph_from_dot_file(curdir/fname)[0]

kdedir = basedir/"kde"

#Read tier data
packages=set()
for subgraph in graph.get_subgraph_list():
    for node in subgraph.get_nodes():
        pkg_name = node.get_name()[1:-1]
        pkg_path = kdedir/pkg_name
        control = pkg_path/"debian/control"
        packages.add(getPackage(control))

_statuse = None
def _getStatus(pkg):
    if pkg.changelog.version.upstream_version < Version(version):
        return (pkg, None)
    _ = getStatus(pkg)
    print(f"{pkg.name} - {_}")
    return (pkg, _)

# sftp_client do not like multipocessing , that's why we can't use it atm (2017-12-19)
_statuse = map(_getStatus, packages)

statuses = defaultdict(set)
for pkg, status in _statuse:
        statuses[status].add(pkg)

for status in statuses:
    if not status:
        continue
    color = STATUS[status]
    for pkg in statuses[status]:
        n = pydot.Node(f'"{pkg.path.name}"',color=color, penwidth=3)
        graph.add_node(n)

graph.write(curdir/buildname)
