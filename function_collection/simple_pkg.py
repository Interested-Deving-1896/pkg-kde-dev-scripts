from functions import *

def simple_package(pkg, version):
    createGitignoreForFiles(pkg)
    prepareNewChangelogEntry(pkg)
    bumpCompat(pkg, 13)
    bumpStandardsVersion(pkg, Version("4.5.0"))
    updateSalsaCI(pkg)
    getRidOfDebugSymbolPacakge(pkg)
    rulesRequireRoot(pkg)
    updateVersion(pkg, version)
    updateVscToSalsa(pkg)
    updateCopyrightFormat(pkg)
    downloadTarball(pkg)
    unpackTarball(pkg)
    cmakeUpdateDeps(pkg)

if __name__ == "__main__":
    import sys
    VERSION = Version(sys.argv[1])
    #checkGitStatus(pkg)
    simple_package(pkg, VERSION)
