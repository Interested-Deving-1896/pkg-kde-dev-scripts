from functions import *

for pkg in deb822.Sources.iter_paragraphs(open('/home/hefee/debian/graph/Sources')):
    if pkg['Package'] not in packages:
        packages[pkg['Package']] = Package(pkg)

#Read tier data
tiers=[]
for subgraph in pydot.graph_from_dot_file("/home/hefee/debian/graph/tier.dot")[0].get_subgraph_list():
    tier=set()
    for node in subgraph.get_nodes():
        tier.add(packages[node.get_name()[1:-1]])
    tiers.append(tier)

#endlist for 17.12
endlist = set(['kblog', 'knotes','kdepim-runtime','kmail-account-wizard','pim-sieve-editor','kontact','kaddressbook','akregator','grantlee-editor', 'akonadiconsole','akonadi-calendar-tools','kalarm','kmail','mbox-importer','pim-data-exporter','kdepim-addons','korganizer', 'kgpg', 'kleopatra'])

endlist = set([packages[i] for i in endlist])

# for pkg in tiers[6]:
#     if pkg in endlist:
#         continue
#     print(pkg.name)
#     bumpCompat(pkg, 10)
#     pkg.dpkgBuildpackage()
#     dput(pkg)


# for pkg in packages.values():
#     with tempfile.NamedTemporaryFile() as tmpfile:
#         if checkForSymbolChanges(pkg, tmpfile.name):
#             version = (f"{pkg.changelog.epoch}:"if pkg.changelog.epoch else "") + str(pkg.changelog.versions[0].upstream_version)
#             if updateSymbols(pkg, version, [tmpfile.name]) is None:
#                 pkg.dpkgBuildpackage()
#                 dput(pkg)
