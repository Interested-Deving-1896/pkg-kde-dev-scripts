from frameworks_management import *
import salsa

IGNORE = ["changelog-should-mention-nmu", "source-nmu-has-incorrect-version-number", "extended-description-is-probably-too-short", "upstream-metadata-missing-bug-tracking", "copyright-refers-to-symlink-license usr/share/common-licenses/GPL", "testsuite-autopkgtest-missing", "spelling-error-in-binary", "duplicate-short-description", "description-synopsis-might-not-be-phrased-properly", "duplicate-long-description"]

def ignore(element):
    for i in IGNORE:
        if i in element:
            return True
    return False

tier = int(sys.argv[1])

for pkg in tiers[tier]:
    try:
        lintian = salsa.getLintian(pkg)
    except AttributeError:
        status = salsa.workdir.get(f"status/{pkg.path.name}", {})
        print(f"SKIPPING - {pkg.name} ({status['job']['status']},{status['lintian']['status']})")
        continue
    interessting = [i for i in lintian if not ignore(i)]
    if interessting:
        print(f"{pkg.name}:")
        print("\n".join(interessting))
        print("")

