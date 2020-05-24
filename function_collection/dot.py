import copy

__fresh_id = 0
def get_id():
    global __fresh_id
    __fresh_id += 1
    return f"NODE_{__fresh_id}"

def emit_arc(node1, node2):
    return f'"{node1}" -> "{node2}";'

def emit_node(node, dsc=None):
    if dsc is None:
          return f'"{node}";'
    else:
          return f'"{node}" [label="{dsc}"];'

def emit_nodecolor(node, color):
    return f'"{node}" [fillcolor="{color}", style="filled"];'

class TierGraph:
    def __init__(self, graph):
        self.graph = graph

        self.minimized = {}
        self.full = {}
        self.tiers = []

        ograph = graph

        for i in range(10):
            changed = False
            for pkg in ograph:
                deps = copy.copy(ograph[pkg])
                for dep in ograph[pkg]:
                    deps |= ograph[dep]
                deps -= {pkg}
                if deps != ograph[pkg]:
                    changed = True
                self.full[pkg] = deps

            if not changed:
                break
            ograph = self.full

        for pkg in self.full:
            deps = copy.copy(graph[pkg])
            for dep in graph[pkg]-{pkg}:
                deps -= self.full[dep]
            self.minimized[pkg] = deps-{pkg}

        pkgs = set(graph.keys())     # packages to order into tiers
        deps = set()                 # All deps from lower tiers

        while pkgs:
            tD = set()
            if self.tiers:
                deps |= self.tiers[-1]
            self.tiers.append(set())
            for pkg in pkgs:
                if not (self.minimized[pkg] - deps):
                    self.tiers[-1].add(pkg)
                    tD.add(pkg)
            pkgs -= tD

        self.ends = set()

        for pkg in graph:
            name = pkg
            sDeps = self.minimized[pkg]
            if sDeps:
                for p in self.minimized:
                    if p == pkg:
                        continue
                    if pkg in self.minimized[p]:
                        break
                else:
                    self.ends.add(name)



    def createGraph(self, name):
        lines = []
        if self.ends:
            lines.append('node [shape=diamond,fillcolor=lightblue,style=filled];')
            for pkg in sorted(self.ends):
                lines.append(emit_node(pkg))

        lines.append('node [shape=ellipse,fillcolor=darkgreen,style=filled];')
        for pkg in sorted(self.tiers[0]):    #   all dependency free packages - aka tier 0
            lines.append(emit_node(pkg))

        lines.append('node [shape=ellipse,fillcolor=white,style=filled];')

        for index, tier in enumerate(self.tiers):
            subgraph = []
            subgraph.append('style=filled;')
            subgraph.append('color=lightgrey;')
            subgraph.append(f'label = "Tier {index}";')
            for pkg in sorted(tier):
                subgraph.append(emit_node(pkg))

            lines.append(f'subgraph cluster_{index} {{')
            for l in subgraph:
                lines.append(f'  {l}')
            lines.append('}')

            if index > 0:
                subTier = self.tiers[index-1]
                for pkg in sorted(tier):
                    for dep in (self.minimized[pkg] & subTier):
                        lines.append(emit_arc(dep, pkg))

        ret = []
        ret.append(f"digraph {name} {{")
        for l in lines:
            ret.append(f"  {l}")
        ret.append("}")

        return "\n".join(ret)
