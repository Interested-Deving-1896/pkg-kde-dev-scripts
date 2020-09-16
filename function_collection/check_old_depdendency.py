import deb822
from debian.debian_support import Version
import warnings

warnings.filterwarnings("ignore", category=UserWarning, message="cannot parse package relationship")

def check_unnessary_dependencies(pkg, binaryPackages, minVer):
    for block in pkg.controlParagraphs():
         ownBinaryPackages = set(i.get("Package") for i in pkg.controlParagraphs() if i.get("Package"))

         deps = None
         if block.get("Source"):
             deps = block.get('Build-Depends')
         else:
             deps = block.get('Depends')

         if not deps:
             continue

         rels = deb822.PkgRelation.parse_relations(deps)
         for rel in rels:
             if rel[0]['name'].endswith(' (= ${binary:Version})'):
                 rel[0]['name'] = rel[0]['name'][:-len(' (= ${binary:Version})')]
                 rel[0]['version'] = '(= ${binary:Version})'
             if rel[0]['name'].endswith(' (= ${source:Version})'):
                 rel[0]['name'] = rel[0]['name'][:-len(' (= ${source:Version})')]
                 rel[0]['version'] = '(= ${source:Version})'

         for rel in rels:
             name = rel[0]['name']
             version = rel[0]['version']
             if name not in binaryPackages:
                 continue
             if name in ownBinaryPackages:
                 continue

             if not version or len(version)!=2 or version[0] != '>=' or Version(version[1]).upstream_version != minVer:
                 print(block.get('Source',block.get('Package')), name, rel)

