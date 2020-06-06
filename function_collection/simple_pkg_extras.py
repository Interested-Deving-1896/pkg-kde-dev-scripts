from functions_plasma import *
 
def simple_package(pkg, version):
   addMyselfToUploaders(pkg)
   updateHomepagetoInvent(pkg, 'libraries')
   updateCopyrightSourcetoInvent(pkg,'libraries')
   #updateCopyrightFormat(pkg)
   #updateUpstreamContact(pkg,'libraries')
   addMissingBugMetadatafields(pkg)
   #cleanupMetadataObsoleteFields(pkg)
   #rules_uses_as_needed_linker_flags(pkg)
   #updateDevDepends(pkg)
   #getRidOfDebugSymbolPacakge(pkg)
   #updateDevDepends(pkg) 
   #listMissingSymbolsfiles(pkg)
   #checkForSymbolChanges(pkg)
   #getBuildlogs(pkg)
   #createSymbolsfiles(pkg)
   #updateSymbols(pkg)
   #addMissingDependsPackageField(pkg)
  

  
   

   #bumpABI(pkg)
  

   
if __name__ == "__main__":
    import sys
    VERSION = Version(sys.argv[1])
    #checkGitStatus(pkg)
    simple_package(pkg, VERSION)

