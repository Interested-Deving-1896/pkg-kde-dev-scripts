#! /usr/bin/env python3
from bs4 import BeautifulSoup
import copy
from debian import deb822
import git
import os
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
        "kcalendarcore": "kcalcore",
        "kquickcharts": "kqtquickcharts",
        "kirigami2": "kirigami",
}

def get_framework(version):
    r = requests.get(f"https://download.kde.org/stable/frameworks/{version}/")
    soup = BeautifulSoup(r.text, features="lxml")
    for a in soup.find_all('a'):
        if a['href'].endswith('.tar.xz'):
            yield a
    r = requests.get(f"https://download.kde.org/stable/frameworks/{version}/portingAids/")
    soup = BeautifulSoup(r.text, features="lxml")
    for a in soup.find_all('a'):
        if a['href'].endswith('.tar.xz'):
            yield a


frameworks = set()

for a in get_framework(version):
    frameworks.add('-'.join(a.text.split('-')[:-1]))

for framework in frameworks:
    framework = REPLACE.get(framework, framework)
    path = basedir/framework
    if path.exists():
        continue
    print(f"Cloning {framework} ...")
    git.Repo.clone_from(f'qt-kde-team:kde/{framework}', path)


depends = dict()
packages = dict()

for framework in frameworks:
    framework = REPLACE.get(framework, framework)
    path = (basedir/framework)
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
            packages[package] = framework

    depends[framework] = {"build-depends":deps, "pkgs": build}

graph = {}
for framework in frameworks:
    framework = REPLACE.get(framework, framework)
    sDepends = set()
    for i in depends[framework]['build-depends']:
        if i not in packages:
            continue
        sDepends.add(packages[i])
    graph[framework] = sDepends

dotfile = curdir/f"frameworks.{version}.tier.dot"
pngname = curdir/f"frameworks.{version}.tier.png"

t = TierGraph(graph)
dotfile.write_text(t.createGraph("frameworksTier"))
subprocess.check_call(["dot", "-T","png", "-o", pngname, dotfile], cwd=curdir)
