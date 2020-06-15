from functions_plasma import *
 
def simple_package(pkg, version):
   cleanupBreaknConflicts(pkg)
   addMyselfToUploaders(pkg)
   rules_uses_as_needed_linker_flags(pkg)
   updateHomepagetoInvent(pkg, 'kde', 'plasma')
   updateCopyrightSourcetoInvent(pkg, 'kde', 'plasma')
   updateUpstreamContact(pkg,'kde')
   #updateDevDepends(pkg)
   #addMissingDependsPackageField(pkg)
   #listMissingSymbolsfiles(pkg)
   #getBuildlogs(pkg)
   #updateSymbols(pkg)
   #bumpABI(pkg)
   #updateDevDepends(pkg) 

   
if __name__ == "__main__":
    import sys
    VERSION = Version(sys.argv[1])
    #checkGitStatus(pkg)
    simple_package(pkg, VERSION)

