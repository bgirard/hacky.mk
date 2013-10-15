#!/usr/bin/env python

import sys
import re
import os
from cStringIO import StringIO
from tokenize import tokenize, untokenize, NUMBER, STRING, NAME, OP

DEBUG = False

#
# Note: We use Unix style path separators everywhere, and normalize DOS ones
# to Unix style.
#

makehackypy = None
objroot = None
hackydir = None
treeloc = None
hackyfilename = None
hackyppfilename = None

# NOTE: We have to pass in unicode strings here, because that will
# trigger long path name handling in Python on Win32.  Otherwise
# we'll be limited to very short paths, and we'll bomb out with
# some of the long paths in the tree.
def relpath(p, root = None):
    if not root:
        root = objroot
    return str(os.path.relpath(unicode(p), unicode(root))).replace("\\", "/")

def abspath(p):
    return str(os.path.abspath(unicode(p))).replace("\\", "/")

def joinpath(*ps):
    return str(os.path.join(*map(lambda p: unicode(p), ps))).replace("\\", "/")

def basename(p):
    return str(os.path.basename(unicode(p))).replace("\\", "/")

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
    global makehackypy, objroot, hackydir, treeloc, hackyfilename, hackyppfilename
    objroot = abspath(joinpath(dotpath, depthstr))
    hackydir = joinpath(objroot, ".hacky")

    # figure out the path relative to the objroot (maybe abspath dotpath?)
    treeloc = relpath(dotpath, objroot)
    hackybase = re.sub(r'[/\\]', '_', treeloc) + "_"
    # for things that are in the toplevel dir, the hacky files shouldn't
    # start with "._" because derp.
    if hackybase == "._":
        hackybase = ""
    hackyfilename = hackybase + basename(target) + gethackyext()
    hackyppfilename = hackybase + basename(target) + ".hacky.pp"

    # and fix up makehackypy
    makehackypy = relpath(makehackypy, dotpath)

def ensuredirexists(d):
    '''Ensure that the given d exists, in a race-safe way.'''
    # Unicodeify for windows
    d = unicode(d)
    if os.path.exists(d) and not os.path.isdir(d):
        raise Exception("Can't create dectory %d because it exists, "
                        "and is not a dectory!" % str(d))

    if not os.path.exists(d):
        try:
            # mkdir will raise an OSError if the d exists.  We can't catch
            # specifically this exception, but we can catch OSErrors in general
            # and then check whether the d now exists.
            os.mkdir(d)
        except OSError as e:
            pass

    if not os.path.exists(d):
        raise e

# given a ppfile in ppfile, the target's directory in targetdir, and
# an objroot in objroot, generate a new file in outfile that contains
# relative-to-objroot dependencies
def abspp(ppfile, outfile, targetdir, targetname):
    ensuredirexists(os.path.dirname(outfile))

    try:
        fpin = file(ppfile, "r")
    except:
        # if it doesn't exist, pretend it's empty
        fpin = StringIO("")

    if outfile is None:
        fpout = sys.stdout
    else:
        fpout = file(outfile, "w")

    deps = []
    for line in fpin:
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
                if not os.path.exists(unicode(token)):
                    continue
                token = relpath(token, objroot)
                deps.append(token)
            else:
                if token != " " and token != ":" and not os.path.exists(unicode(token)):
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

def depstolist(deps, root=objroot):
    # get path names relative to root, but also use unix-style separators
    # even on Windows
    return map(lambda p: relpath(p, root), deps.split())

def openhacky():
    global hackyfilename
    # make the toplevel .hacky if it doesn't exist
    ensuredirexists(hackydir)
    ensuredirexists(joinpath(hackydir, backend))

    hackyfile = file(joinpath(hackydir, backend, hackyfilename), "w")
    #print >>sys.stderr, ("Open '%s'" % joinpath(hackydir, backend, hackyfilename))
    return hackyfile

def emit_common(hackyfile, treeloc, target, depfiles, srcfiles, build_command, extra_outputs, depthstr, dotpath, ppfile = None, extra_info = []):
    global backend
    targetfile = basename(target)

    extra_outs = ""
    if extra_outputs:
        if type(extra_outputs) is str:
            extra_outputs = re.split(r"\s+", extra_outputs)
        extra_outs = " " + " ".join(map(relpath, extra_outputs))

    if backend == "ninja":
        print >>hackyfile, "build %s/%s%s: do_build | %s" % (treeloc, targetfile, extra_outs, " ".join(depfiles))
        # escape out the build_command
        build_command = build_command.replace("\\", "\\\\").replace("\"","\\\"")
        if ppfile:
            print >>hackyfile, "  depfile = .hacky/pp/%s" % hackyppfilename
            build_command = build_command + " && ${PYTHON} %s pp %s %s %s %s" % (makehackypy, depthstr, dotpath, target, ppfile)
        print >>hackyfile, "  buildcommand = bash -c \"cd %s && %s\"" % (treeloc, build_command)

    if backend == "make":
        print >>hackyfile, "all: %s/%s" % (treeloc, targetfile)
        print >>hackyfile, "%s/%s%s: %s" % (treeloc, targetfile, " ".join(depfiles), extra_outs)
        print >>hackyfile, "\tcd %s && %s" % (treeloc, build_command)
        if ppfile:
            print >>hackyfile, "\t$(PYTHON) %s pp %s %s %s %s/%s" % (makehackypy, depthstr, dotpath, target, treeloc, ppfile)

        print >>hackyfile, "original::"
        print >>hackyfile, "\tcd %s && rm -f %s && $(MAKE) %s" % (treeloc, targetfile, targetfile)
        print >>hackyfile, "%s: %s/Makefile" % (joinpath(hackydir, "make", hackyfilename), treeloc)
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
            "extra_outputs": extra_outputs,
            "depthstr": depthstr,
            "dotpath": dotpath,
            "ppfile": ppfile,
        }
        for key in extra_info:
           json_data[key] = extra_info[key]
        print >>hackyfile, json.dumps(json_data)

        # if a ppfile is given, process it
        # NOTE: we don't ever include this pp file; it gets included in the toplevel hacky.mk!
        # NOTE: we only generate this for the "hacky" backend, but everything depends on it!
        if ppfile:
            abspp(ppfile, joinpath(hackydir, "pp", hackyppfilename), treeloc, targetfile)

# This is used for generic rules, everything other than compilation
# These likely won't have any repeated arguments or anything similar.
def makehacky(depthstr, dotpath, target, deps, build_command, extra_outputs = "", ppfile = None):
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

    emit_common(hackyfile, treeloc, target, depfiles, srcfiles, build_command, extra_outputs, depthstr, dotpath, ppfile)

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
    srcfiles = depstolist(sources, joinpath(objroot, treeloc))
    targetfile = basename(target)

    build_command = "%s %s%s -c %s %s %s" % (compiler, outoption, targetfile, cflags, local_flags, " ".join(srcfiles))

    extra_info = {
        "compiler": compiler,
        "outoption": outoption,
        "targetfile": targetfile,
        "cflags": cflags,
        "local_flags": local_flags,
        "srcfiles": srcfiles,
    }

    emit_common(hackyfile, treeloc, target, depfiles, srcfiles, build_command, None, depthstr, dotpath, ppfile, extra_info=extra_info)

    hackyfile.close()

def makepp(depthstr, dotpath, target, ppfile):
    computepaths(depthstr, dotpath, target)
    targetfile = basename(target)
    abspp(ppfile, joinpath(hackydir, "pp", hackyppfilename), treeloc, targetfile)

def makeinstall(depthstr, category, source, destdir):
    global backend
    # we only care about Windows for now
    if os.name is not 'nt':
        return

    targetfile = basename(source)
    computepaths(depthstr, ".", targetfile)

    target = relpath(joinpath(destdir, targetfile))
    reldest = relpath(destdir)

    # hack -- redo this since we computed a proper target file now
    global hackyfilename
    hackybase = re.sub(r'[/\\]', '_', reldest)
    hackyfilename = hackybase + "_" + basename(target) + gethackyext()

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
    makehackypy = abspath(args.pop(0))

    # we use "^^" as a " char to avoid weird quoting problems, e.g.
    # if someone's already escaping " via \"
    args = map(lambda s: s.replace('^^', '"'), args)
    args = map(str.strip, args)

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
