from functions_plasma import *
 
def simple_package(pkg, version):
   #updateDevDepends(pkg)
   #addMissingDependsPackageField(pkg)
   #cleanupBreaknConflicts(pkg)
   #addMyselfToUploaders(pkg)
   #getRidOfDebugSymbolPacakge(pkg)
   #rules_uses_as_needed_linker_flags(pkg)
   #updateVscToSalsa(pkg)
   #listMissingSymbolsfiles(pkg)
   #getBuildlogs(pkg)
   #updateSymbols(pkg)
   #bumpABI(pkg)
   #updateDevDepends(pkg) 
   updateHomepagetoInvent(pkg)
   
if __name__ == "__main__":
    import sys
    VERSION = Version(sys.argv[1])
    #checkGitStatus(pkg)
    simple_package(pkg, VERSION)

