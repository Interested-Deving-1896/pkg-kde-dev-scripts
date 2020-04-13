from bs4 import BeautifulSoup
import copy
from debian import deb822
import git
import os
import pathlib
import requests
import sys
import yaml

from functions import getPackage

with open(os.path.join(os.path.dirname(__file__),'config.yml')) as f:
    CONFIG = yaml.safe_load(f)

basedir = pathlib.Path(CONFIG['basedir'])/'kde'

version = sys.argv[1]

REPLACE = {
        "kcalendarcore": "kcalcore",
        "kquickcharts": "kqtquickcharts",
}

r = requests.get(f"https://download.kde.org/stable/frameworks/{version}/")
soup = BeautifulSoup(r.text, features="lxml")

frameworks = set()

for a in soup.find_all('a'):
    if a['href'].endswith('.tar.xz'):
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

sgraph = {}     # minimized graph
ograph = graph
fgraph = {}     # full dependency graph

for i in range(10):
    changed = False
    for pkg in ograph:
        deps = copy.copy(ograph[pkg])
        for dep in ograph[pkg]:
            deps |= ograph[dep]
        if deps != ograph[pkg]:
            changed = True
        fgraph[pkg] = deps

    if not changed:
        break
    ograph = fgraph

for pkg in fgraph:
    deps = copy.copy(graph[pkg])
    for dep in graph[pkg]:
        deps -= fgraph[dep]
    sgraph[pkg] = deps

pkgs = set(graph.keys())     # packages to order into tiers
tiers = []                   # each tier will be one entry
deps = set()                 # All deps from lower tiers

while pkgs:
    tD = set()
    if tiers:
        deps |= tiers[-1]
    tiers.append(set())
    for pkg in pkgs:
        if not (sgraph[pkg] - deps):
            tiers[-1].add(pkg)
            tD.add(pkg)
    pkgs -= tD

__fresh_id = 0

def get_id():
    global __fresh_id
    __fresh_id += 1
    return ("NODE_%d" % __fresh_id)

def emit_arc(node1, node2):
    print('  "%s" -> "%s";' % (node1, node2))
def emit_node(node, dsc=None):
    if dsc is None:
          print('  "%s";' % (node))
    else:
          print('  "%s" [label="%s"];' % (node, dsc))
def emit_nodecolor(node, color):
    print('  "%s" [fillcolor="%s", style="filled"];' % (node, color))

print("digraph frameworksTier {")
#print("    node [shape=diamond,fillcolor=lightblue,style=filled];")
#for pkg in ends:    # all end notes
#    emit_node(pkg)
print("    node [shape=ellipse,fillcolor=darkgreen];")
for pkg in tiers[0]:    #   all dependency free packages - aka tier 0
    emit_node(pkg)
print("    node [shape=ellipse,fillcolor=white];")
for index, tier in enumerate(tiers):
    print("  subgraph cluster_{} {{".format(index))
    print("     style=filled;")
    print("     color=lightgrey;")
    print('     label = "Tier {}";'.format(index))
    for pkg in tier:
        emit_node(pkg)
    print("  }")
    if index > 0:
        subTier = tiers[index-1]
        for pkg in tier:
            for dep in (sgraph[pkg] & subTier):
                emit_arc(dep, pkg)
print("}")


