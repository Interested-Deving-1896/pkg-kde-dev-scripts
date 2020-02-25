from functions import *

VERSION = Version(sys.argv[1])

#checkGitStatus(pkg)
createGitignoreForFiles(pkg)
prepareNewChangelogEntry(pkg)
bumpStandardsVersion(pkg, Version("4.5.0"))
updateVersion(pkg, VERSION)
updateVscToSalsa(pkg)
updateCopyrightFormat(pkg)
downloadTarball(pkg)
unpackTarball(pkg)
cmakeUpdateDeps(pkg)
