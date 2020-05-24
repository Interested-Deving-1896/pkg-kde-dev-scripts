#!/usr/bin/env python3

import frameworks_management
import pim_management
import salsa

import itertools
import sys

IGNORE = ["changelog-should-mention-nmu",
        "source-nmu-has-incorrect-version-number",
        "extended-description-is-probably-too-short",
        "upstream-metadata-missing-bug-tracking",
        "testsuite-autopkgtest-missing",
        "spelling-error-in-binary",
        "duplicate-short-description",
        "description-synopsis-might-not-be-phrased-properly",
        "duplicate-long-description",
        "package-uses-experimental-debhelper-compat-version",
]

IGNORE_FRAMEWORKS = ["copyright-refers-to-symlink-license usr/share/common-licenses/GPL",
]

IGNORE_PIM = ["no-dh-sequencer",
        "binary-without-manpage",
        "desktop-entry-lacks-keywords-entry",
        "public-upstream-key-not-minimal",
        "no-symbols-control-file",
]

def ignore(element):
    for i in IGNORE_FULL:
        if i in element:
            return True
    return False

product = sys.argv[1]
tier = sys.argv[2]

IGNORE_FULL = IGNORE

if product == "frameworks":
    tiers = frameworks_management.tiers
    IGNORE_FULL += IGNORE_FRAMEWORKS
elif product == "kdepim":
    tiers = pim_management.tiers
    IGNORE_FULL += IGNORE_PIM

else:
    print("Unknown product.")
    sys.exit(-2)

if ":" in tier:
    _mn,_mx = tier.split(":")
    if _mn:
        _min = int(_mn)
    else:
        _min = None

    if _mx:
        _max = int(_mx)
    else:
        _max = None
    packages = itertools.chain(*tiers[_min:_max])
else:
    packages = tiers[int(tier)]

for p in packages:
    pkg = salsa.SalsaPackage(p)
    try:
        pkg.getLintianPath()
        lintian = pkg.getLintian()
    except AttributeError:
        status = pkg._status
        job_status = status.get('job',{'status':'unknown'})
        lintian_status = status.get('lintian',{'status':'unknown'})
        print(f"SKIPPING - {pkg.name} ({job_status['status']},{lintian_status['status']})")
        continue
    interessting = [i for i in lintian if not ignore(i)]
    if interessting:
        print(f"{pkg.name}:")
        print("\n".join(interessting))
        print("")

