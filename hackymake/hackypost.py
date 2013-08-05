#!/usr/bin/env python

import os
import sys

DEBUG = True

def readpp(ppfile):
    deps = []
    ppString = open(ppfile).read()
    ppWords = ppString.split(" ")
    for ppWord in ppWords:
        if ppWord.endswith(":"):
            continue;
        deps.append(ppWord)
    deps.sort()
    return deps

# Returns a hackyMap which maps
# target -> hacky json notation
def readhacky(tree_base):
    import json
    hackydir = os.path.join(tree_base, ".hacky")

    hackyMap = {}
    for f in os.listdir(hackydir):
        if f.endswith(".hacky"):
            #if DEBUG:
            #    print "Reading: " + f
            hacky_path = os.path.join(hackydir, f)
            fJson = json.loads(open(hacky_path, "r").read())
            if "target" in fJson:
                # os.join will add \ instead of / on windows
                targetName = fJson["treeloc"] + "/" + fJson["target"]
                hackyMap[targetName] = fJson
                ppPath = hacky_path + ".pp"
                if os.path.isfile(ppPath):
                    fJson['ppDeps'] = readpp(ppPath)
                    if DEBUG and fJson["target"].endswith(".dll"):
                        print "Adding target: " + fJson["target"] + " as: " + targetName
    return hackyMap

def genbuild(tree_root, hackyMap, target):
    import json
    gypRoot = {
        "targets": []
    }
    gypRoot["targets"].append(gypTargetLibrary(tree_root, hackyMap, target))

    gypfile = open(os.path.join(tree_root, ".hacky", target["target"] + ".gyp"), "w")
    # Pretty print gypRoot
    print >>gypfile, json.dumps(gypRoot, sort_keys=True, indent=4, separators=(',', ': '))

def objdeps_to_srcdeps(objdeps, hackyMap):
    srcdeps = []
    for objdep in objdeps:
        objdep = objdep
        if objdep in hackyMap and "srcfiles" in hackyMap[objdep]:
            srcdeps.append(hackyMap[objdep]["srcfiles"])
        else:
            print "ERROR: Don't have srcdeps for: " + objdep
    return srcdeps

def gypTargetLibrary(tree_root, hackyMap, target):
    gypTarget = {
        "target_name": target["target"],
        "type": "shared_library",
        "sources": objdeps_to_srcdeps(target["ppDeps"], hackyMap),
    }
    return gypTarget

if __name__ == "__main__":
    args = sys.argv

    # save script name
    makehackypy = os.path.abspath(args.pop(0))

    tree_base = args.pop(0)

    hackyMap = readhacky(tree_base)

    genbuild(tree_base, hackyMap, hackyMap["layout/media/gkmedias.dll"])