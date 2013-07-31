#!/usr/bin/env python

import sys
import re
import os
from tokenize import tokenize, untokenize, NUMBER, STRING, NAME, OP

from abspp import abspp

def depstolist(deps):
    # get absolute path names, but also use unix-style separators
    # even on Windows
    return map(lambda p: os.path.abspath(p).replace("\\", "/"), deps.split())

def openhacky(dotpath, depthstr, target):
    # make the toplevel .hacky if it doesn't exist
    hackydir = os.path.abspath(os.path.join(depthstr, ".hacky"))
    if not os.path.exists(hackydir): os.mkdir(hackydir)

    curdir = os.path.abspath(dotpath)
    objdir = os.path.abspath(os.path.join(dotpath, depthstr))
    treeloc = os.path.relpath(curdir, objdir)
    hackybase = re.sub(r'[/\\]', '_', treeloc)
    
    hackyfile = file(os.path.join(hackydir, hackybase + "_" + os.path.basename(target) + ".hacky"), "w")
    return hackyfile

# This is used for generic rules, everything other than compilation
# These likely won't have any repeated arguments or anything similar.
def makehacky(depthstr, dotpath, target, deps, build_command, ppfile = None):
    hackyfile = openhacky(dotpath, depthstr, target)

    print >>hackyfile, "#TARGET:   %s" % (target)
    print >>hackyfile, "#DEPTH:    %s" % (depthstr)
    print >>hackyfile, "#DOTPATH:  %s" % (dotpath)
    print >>hackyfile, "#DEPS:     %s" % (deps)
    print >>hackyfile, "#COMMAND:  %s" % (build_command)
    print >>hackyfile, "#PPFILE:   %s" % (ppfile)

    depfiles = depstolist(deps)
    targetfile = os.path.basename(target)
    targetdir = os.path.dirname(target)

    print >>hackyfile, "all: %s/%s" % (dotpath, targetfile)
    print >>hackyfile, "%s/%s: %s/Makefile %s" % (dotpath, targetfile, dotpath, " ".join(depfiles))
    print >>hackyfile, "\tcd %s && %s" % (dotpath, build_command)

    print >>hackyfile, "original:"
    print >>hackyfile, "\tcd %s && $(MAKE) %s" % (dotpath, targetfile)

    if ppfile:
        ppdeps = abspp(file(os.path.join(dotpath, ppfile), "r"), dotpath)
        print >>hackyfile, "%s/%s: %s" % (dotpath, targetfile, " ".join(ppdeps))

    hackyfile.close()

# This is used for compilation targets, and gets some extra separated args.
def makecchacky(depthstr, dotpath, target, sources, compiler, outoption, cflags, local_flags, ppfile):
    hackyfile = openhacky(dotpath, depthstr, target)

    print >>hackyfile, "#CCTARGET: %s" % (target)
    print >>hackyfile, "#DEPTH:    %s" % (depthstr)
    print >>hackyfile, "#DOTPATH:  %s" % (dotpath)
    print >>hackyfile, "#SOURCES:  %s" % (sources)
    print >>hackyfile, "#COMPILER: %s" % (compiler)
    print >>hackyfile, "#OUTOPT:   %s" % (outoption)
    print >>hackyfile, "#CFLAGS:   %s" % (cflags)
    print >>hackyfile, "#LFLAGS:   %s" % (local_flags)
    print >>hackyfile, "#PPFILE:   %s" % (ppfile)

    srcfiles = depstolist(sources)
    targetfile = os.path.basename(target)
    targetdir = os.path.dirname(target)

    print >>hackyfile, "all: %s/%s" % (dotpath, targetfile)
    print >>hackyfile, "%s/%s: %s/Makefile %s" % (dotpath, targetfile, dotpath, " ".join(srcfiles))
    print >>hackyfile, "\tcd %s && %s %s%s -c %s %s %s" % (dotpath, compiler, outoption, targetfile, cflags, local_flags, " ".join(srcfiles))

    print >>hackyfile, "original:"
    print >>hackyfile, "\tcd %s && $(MAKE) %s" % (dotpath, targetfile)

    if ppfile:
        ppdeps = abspp(file(os.path.join(dotpath, ppfile), "r"), dotpath)
        print >>hackyfile, "%s/%s: %s" % (dotpath, targetfile, " ".join(ppdeps))

    hackyfile.close()

if __name__ == "__main__":
    args = sys.argv

    # skip script name
    args.pop(0)

    # we use "^^" as a " char to avoid weird quoting problems, e.g.
    # if someone's already escaping " via \"
    args = map(lambda s: s.replace('^^', '"'), args)

    if args[0] == "cc":
        args.pop(0)
        makecchacky(*args)
    else:
        makehacky(*args)
