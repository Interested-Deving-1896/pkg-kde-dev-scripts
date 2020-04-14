from functions import *

VERSION = Version(sys.argv[1])

#checkGitStatus(pkg)
createGitignoreForFiles(pkg)
prepareNewChangelogEntry(pkg)
bumpCompat(pkg, 12)
bumpStandardsVersion(pkg, Version("4.5.0"))
updateSalsaCI(pkg)
getRidOfDebugSymbolPacakge(pkg)
rulesRequireRoot(pkg)
updateVersion(pkg, VERSION)
updateVscToSalsa(pkg)
updateCopyrightFormat(pkg)
downloadTarball(pkg)
unpackTarball(pkg)
cmakeUpdateDeps(pkg)
