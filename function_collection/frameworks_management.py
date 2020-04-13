from functions import *

kdedir = basedir/"kde"

#Read tier data
tiers=[]
for subgraph in pydot.graph_from_dot_file("frameworks.tier.dot")[0].get_subgraph_list():
    tier=set()
    for node in subgraph.get_nodes():
        pkg_name = node.get_name()[1:-1]
        pkg_path = kdedir/pkg_name
        control = pkg_path/"debian/control"
        tier.add(getPackage(control))
    tiers.append(tier)
