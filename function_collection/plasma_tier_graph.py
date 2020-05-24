#! /usr/bin/env python3
from bs4 import BeautifulSoup
from debian import deb822
import git
import pathlib
import requests
import sys
import subprocess
import yaml

from dot import TierGraph
from functions import getPackage

curdir = pathlib.Path(__file__).parent

with (curdir/"config.yml").open() as f:
    CONFIG = yaml.safe_load(f)

basedir = pathlib.Path(CONFIG['basedir'])/'kde'

version = sys.argv[1]

REPLACE = {
    'discover': 'plasma-discover',
}

IGNORE = {
    "plasma-phone-components",
    "plasma-nano",
    "plasma-tests",
}

def get_plasma(version):
    r = requests.get(f"https://download.kde.org/stable/plasma/{version}/")
    soup = BeautifulSoup(r.text, features="lxml")
    for a in soup.find_all('a'):
        if a['href'].endswith('.tar.xz'):
            yield a

plasma = set()

for a in get_plasma(version):
    plasma.add('-'.join(a.text.split('-')[:-1]))

for package in plasma:
    if package in IGNORE:
        continue
    package = REPLACE.get(package, package)
    path = basedir/package
    if path.exists():
        continue
    print(f"Cloning {package} ...")
    git.Repo.clone_from(f'qt-kde-team:kde/{package}', path)


depends = dict()
packages = dict()

for package in plasma:
    if package in IGNORE:
        continue
    package = REPLACE.get(package, package)
    path = (basedir/package)
    control = path/'debian/control'
    pkg = getPackage(control)
    build = []
    for block in pkg.controlParagraphs():
        if block.get("Source"):
            rels = deb822.PkgRelation.parse_relations(block.get("Build-Depends"))
            deps = [i[0]['name'] for i in rels if i[0]['name']]
        else:
            p = block.get("Package")
            build.append(p)
            packages[p] = package

    depends[package] = {"build-depends":deps, "pkgs": build}

graph = {}
for package in plasma:
    if package in IGNORE:
        continue
    package = REPLACE.get(package, package)
    sDepends = set()
    for i in depends[package]['build-depends']:
        if i not in packages:
            continue
        sDepends.add(packages[i])
    graph[package] = sDepends

dotfile = curdir/f"plasma.{version}.tier.dot"
pngname = curdir/f"plasma.{version}.tier.png"

t = TierGraph(graph)
dotfile.write_text(t.createGraph("plasmaTier"))
subprocess.check_call(["dot", "-T","png", "-o", pngname, dotfile], cwd=curdir)
