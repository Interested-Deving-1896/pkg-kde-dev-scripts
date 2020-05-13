#! /usr/bin/env python3
from bs4 import BeautifulSoup
from debian import deb822
import git
import glob
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

pim = set()

repo_metadata=basedir/'repo-metadata'

if repo_metadata.exists():
    subprocess.check_call(['git','pull'],cwd=repo_metadata)
else:
    subprocess.check_call(['git','clone', 'kde:sysadmin/repo-metadata'],cwd=basedir)

for pkg in (repo_metadata/"projects/kde/pim").iterdir():
    if pkg.name == "metadata.yaml":
        continue
    pim.add(pkg.name)

for pkg in pim:
    path = basedir/pkg
    if path.exists():
        continue
    print(f"Cloning {pkg} ...")
    git.Repo.clone_from(f'qt-kde-team:kde/{pkg}', path)


depends = dict()
packages = dict()

for name in pim:
    path = (basedir/name)
    control = path/'debian/control'
    pkg = getPackage(control)
    build = []
    for block in pkg.controlParagraphs():
        if block.get("Source"):
            rels = deb822.PkgRelation.parse_relations(block.get("Build-Depends"))
            deps = [i[0]['name'] for i in rels]
        else:
            package = block.get("Package")
            build.append(package)
            packages[package] = name

    depends[name] = {"build-depends":deps, "pkgs": build}

graph = {}
for pkg in pim:
    sDepends = set()
    for i in depends[pkg]['build-depends']:
        if i not in packages:
            continue
        sDepends.add(packages[i])
    graph[pkg] = sDepends

dotfile = curdir/f"kdepim.{version}.tier.dot"
pngname = curdir/f"kdepim.{version}.tier.png"

t = TierGraph(graph)
dotfile.write_text(t.createGraph("pimTier"))
subprocess.check_call(["dot", "-T","png", "-o", pngname, dotfile], cwd=curdir)
