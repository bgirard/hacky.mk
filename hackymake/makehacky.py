#!/usr/bin/env python

import sys
import re
import os
from tokenize import tokenize, untokenize, NUMBER, STRING, NAME, OP

DEBUG = False
HACKY_BACKEND = os.getenv("HACKY_BACKEND") or "ninja"

#
# Note: We use Unix style path separators everywhere, and normalize DOS ones
# to Unix style.
#


makehackypy = None
objroot = None
hackydir = None
treeloc = None
hackyfilename = None

def gethackyext():
    global backend
    if backend == "ninja":
        return ".ninja"
    elif backend == "hacky":
        return ".hacky"
    elif backend == "make":
        return ".mk"
    else: # default Make
        print >>sys.stderr, ("Unkown backend: '%'" % backend)
        sys.exit(1)

def computepaths(depthstr, dotpath, target):
    global makehackypy, objroot, hackydir, treeloc, hackyfilename
    objroot = os.path.abspath(os.path.join(dotpath, depthstr)).replace("\\", "/")
    hackydir = os.path.join(objroot, ".hacky").replace("\\", "/")

    # figure out the path relative to the objroot (maybe abspath dotpath?)
    treeloc = os.path.relpath(dotpath, objroot).replace("\\", "/")
    hackybase = re.sub(r'[/\\]', '_', treeloc) + "_"
    # for things that are in the toplevel dir, the hacky files shouldn't
    # start with "._" because derp.
    if hackybase == "._":
        hackybase = ""
    hackyfilename = hackybase + os.path.basename(target) + gethackyext()

    # and fix up makehackypy
    makehackypy = os.path.relpath(makehackypy, dotpath).replace("\\", "/")

# given a ppfile in ppfile, the target's directory in targetdir, and
# an objroot in objroot, generate a new file in outfile that contains
# relative-to-objroot dependencies
def abspp(ppfile, outfile, targetdir, targetname):
    fpin = file(ppfile, "r")
    if outfile is None:
        fpout = sys.stdout
    else:
        fpout = file(outfile, "w")
    deps = []
    for line in fpin.readlines():
        # strip out the dep target; make sure to handle "foo : bar" (note extra space before the : -- some crap
        # generates this)
        # Damn windows, we also need to handle 'c:/foo/bar : foo'
        line = re.sub(r'^([a-z]:)?[^:]*:\s*', '', line)
        tokens = line.split()
        for i in range(len(tokens)):
            token = tokens[i]
            if token.endswith == ":":
                token = token[:-1]
            if token == "":
                continue
            if re.match('[\w\\.]\.*', token):
                # Some windows dependencies are poorly formed
                # in the original .pp file
                if not os.path.exists(token):
                    continue
                token = relpath(token, objroot).replace("\\", "/")
                deps.append(token)
            else:
                if token != " " and token != ":" and not os.path.exists(token):
                    continue
                deps.append(token)
    deps = list(set(deps))
    if targetdir == ".":
        dirprefix = ""
    else:
        dirprefix = targetdir + "/"
    print >>fpout, "%s%s: %s" % (dirprefix, targetname, " ".join(deps))
    fpin.close()
    fpout.close()

def relpath(p, root = None):
    if not root:
        root = objroot
    return os.path.relpath(p, root).replace("\\", "/")

def depstolist(deps, root=objroot):
    # get path names relative to root, but also use unix-style separators
    # even on Windows
    return map(lambda p: relpath(p, root).replace("\\", "/"), deps.split())

def openhacky():
    global hackyfilename
    # make the toplevel .hacky if it doesn't exist
    if not os.path.exists(hackydir): os.mkdir(hackydir)

    hackyfile = file(os.path.join(hackydir, hackyfilename), "w")
    #print >>sys.stderr, ("Open '%s'" % os.path.join(hackydir, hackyfilename))
    return hackyfile

def emit_common(hackyfile, treeloc, target, depfiles, srcfiles, build_command, depthstr, dotpath, ppfile = None, extra_info = []):
    global backend
    targetfile = os.path.basename(target)

    if backend == "ninja":
        print >>hackyfile, "build %s/%s: do_build | %s" % (treeloc, targetfile, " ".join(depfiles))
        # escape out the build_command
        build_command = build_command.replace("\\", "\\\\").replace("\"","\\\"")
        if ppfile:
            print >>hackyfile, "  depfile = %s" % (".hacky/" + hackyfilename + ".pp")
            build_command = build_command + " && ${PYTHON} %s pp %s %s %s %s" % (makehackypy, depthstr, dotpath, target, ppfile)
        print >>hackyfile, "  buildcommand = bash -c \"cd %s && %s\"" % (treeloc, build_command)

    if backend == "make":
        print >>hackyfile, "all: %s/%s" % (treeloc, targetfile)
        print >>hackyfile, "%s/%s: %s" % (treeloc, targetfile, " ".join(depfiles))
        print >>hackyfile, "\tcd %s && %s" % (treeloc, build_command)
        if ppfile:
            print >>hackyfile, "\t$(PYTHON) %s pp %s %s %s %s/%s" % (makehackypy, depthstr, dotpath, target, treeloc, ppfile)

        print >>hackyfile, "original::"
        print >>hackyfile, "\tcd %s && rm -f %s && $(MAKE) %s" % (treeloc, targetfile, targetfile)
        print >>hackyfile, "%s: %s/Makefile" % (os.path.join(hackydir, hackyfilename), treeloc)
        print >>hackyfile, "\tcd %s && $(MAKE) %s" % (treeloc, targetfile)

    if backend == "hacky":
        import json
        json_data = {
            "type": "emit_common",
            "treeloc": treeloc,
            "target": target,
            "depfiles": depfiles,
            "srcfiles": srcfiles,
            "build_command": build_command,
            "depthstr": depthstr,
            "dotpath": dotpath,
            "ppfile": ppfile,
        }
        for key in extra_info:
           json_data[key] = extra_info[key]
        print >>hackyfile, json.dumps(json_data)

    # if a ppfile is given, process it
    # NOTE: we don't ever include this pp file; it gets included in the toplevel hacky.mk!
    if ppfile:
        abspp(ppfile, os.path.join(hackydir, hackyfilename + ".pp"), treeloc, targetfile)

# This is used for generic rules, everything other than compilation
# These likely won't have any repeated arguments or anything similar.
def makehacky(depthstr, dotpath, target, deps, build_command, ppfile = None):
    computepaths(depthstr, dotpath, target)
    hackyfile = openhacky()

    if DEBUG and not backend == "hacky":
        print >>hackyfile, "#TARGET:   %s" % (target)
        print >>hackyfile, "#DEPTH:    %s" % (depthstr)
        print >>hackyfile, "#DOTPATH:  %s" % (dotpath)
        print >>hackyfile, "#DEPS:     %s" % (deps)
        print >>hackyfile, "#COMMAND:  %s" % (build_command)
        print >>hackyfile, "#PPFILE:   %s" % (ppfile)

    depfiles = depstolist(deps, objroot)
    srcfiles = None

    emit_common(hackyfile, treeloc, target, depfiles, srcfiles, build_command, depthstr, dotpath, ppfile)

    hackyfile.close()

# This is used for compilation targets, and gets some extra separated args.
def makecchacky(depthstr, dotpath, target, sources, compiler, outoption, cflags, local_flags, ppfile):
    computepaths(depthstr, dotpath, target)
    hackyfile = openhacky()

    if DEBUG and not backend == "hacky":
        print >>hackyfile, "#CCTARGET: %s" % (target)
        print >>hackyfile, "#DEPTH:    %s" % (depthstr)
        print >>hackyfile, "#DOTPATH:  %s" % (dotpath)
        print >>hackyfile, "#SOURCES:  %s" % (sources)
        print >>hackyfile, "#COMPILER: %s" % (compiler)
        print >>hackyfile, "#OUTOPT:   %s" % (outoption)
        print >>hackyfile, "#CFLAGS:   %s" % (cflags)
        print >>hackyfile, "#LFLAGS:   %s" % (local_flags)
        print >>hackyfile, "#PPFILE:   %s" % (ppfile)

    depfiles = depstolist(sources, objroot)
    srcfiles = depstolist(sources, os.path.join(objroot, treeloc))
    targetfile = os.path.basename(target)

    build_command = "%s %s%s -c %s %s %s" % (compiler, outoption, targetfile, cflags, local_flags, " ".join(srcfiles))

    extra_info = {
        "compiler": compiler,
        "outoption": outoption,
        "targetfile": targetfile,
        "cflags": cflags,
        "local_flags": local_flags,
        "srcfiles": srcfiles,
    }

    emit_common(hackyfile, treeloc, target, depfiles, srcfiles, build_command, depthstr, dotpath, ppfile, extra_info=extra_info)

    hackyfile.close()

def makepp(depthstr, dotpath, target, ppfile):
    computepaths(depthstr, dotpath, target)
    targetfile = os.path.basename(target)
    abspp(ppfile, os.path.join(hackydir, hackyfilename + ".pp"), treeloc, targetfile)

def makeinstall(depthstr, category, source, destdir):
    global backend
    # we only care about Windows for now
    if os.name is not 'nt':
        return

    # we only care about EXPORT* categories
    if category.find("EXPORT") != 0:
        return

    targetfile = os.path.basename(source)
    computepaths(depthstr, ".", targetfile)

    target = relpath(os.path.join(destdir, targetfile))

    # hack -- redo this since we computed a proper target file now
    global hackyfilename
    hackybase = re.sub(r'[/\\]', '_', treeloc)
    hackyfilename = hackybase + "_" + os.path.basename(target) + gethackyext()

    hackyfile = openhacky()

    source = relpath(source)

    if backend == "ninja":
        print >>hackyfile, "build %s: do_install %s" % (target, source)

    if backend == "make":
        print >>hackyfile, "%s: %s" % (target, source)
        print >>hackyfile, "\tcp -f $< $@"

    if backend == "hacky":
        import json
        json_data = {
            "type": "makeinstall",
            "depthstr": depthstr,
            "category": category,
            "source": source,
            "destdir": destdir,
        }
        print >>hackyfile, json.dumps(json_data)

    hackyfile.close()

if __name__ == "__main__":
    global backend
    backend = None

    args = sys.argv

    # save script name
    makehackypy = os.path.abspath(args.pop(0))

    # we use "^^" as a " char to avoid weird quoting problems, e.g.
    # if someone's already escaping " via \"
    args = map(lambda s: s.replace('^^', '"'), args)

    backendsStr = os.getenv("HACKY_BACKEND") or "all"
    if backendsStr is "all":
        backendsStr = "ninja,hacky,make"

    backends = backendsStr.split(",")

    for currBackend in backends:
        backend = currBackend.strip()
        #print >>sys.stderr, ("Generating: backend '%s'" % backend)
        if not backend in ('ninja', 'hacky', 'make'):
            print >>sys.stderr, ("HACKY_BACKEND must be ninja, hacky or make but is '%s'" % backend)
            sys.exit(1)

        if args[0] == "cc":
            makecchacky(*args[1:])
        elif args[0] == "pp":
            makepp(*args[1:])
        elif args[0] == "install":
            makeinstall(*args[1:])
        else:
            makehacky(*args)
