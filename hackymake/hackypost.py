#!/usr/bin/env python

import os
import sys

DEBUG = True

def readhacky(tree_base):
    import json
    hackydir = os.path.join(tree_base, ".hacky")

    hackyMap = {}
    for f in os.listdir(hackydir):
        if f.endswith(".hacky"):
            #if DEBUG:
            #    print "Reading: " + f
            fJson = json.loads(open(os.path.join(hackydir, f), "r").read())
            if "target" in fJson:
                hackyMap[fJson["target"]] = fJson
                if DEBUG and fJson["target"].endswith(".dll"):
                    print "Adding target: " + fJson["target"]


if __name__ == "__main__":
    args = sys.argv

    # save script name
    makehackypy = os.path.abspath(args.pop(0))

    tree_base = args.pop(0)

    readhacky(tree_base)