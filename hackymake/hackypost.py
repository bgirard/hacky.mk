#!/usr/bin/env python

import os, sys, re, uuid

DEBUG = True
tree_base = None

# only matters for VS solutions, for now
is64Bit = False
msvcPlatform = "Win32"
msvcVersion = None

def relpath(p, root = None):
    if not root:
        root = tree_base
    return os.path.relpath(p, root).replace("\\", "/")

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

def gypRoot(tree_root, hackyMap, target):
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

def genMsvcHeader(msvcProj, target):
    msvcProj.appendLine('<?xml version="1.0" encoding="utf-8"?>');
    msvcProj.appendLineOpen('<Project DefaultTargets="Build" ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">')
    msvcProj.appendLineOpen('<ItemGroup Label="ProjectConfigurations">');
    msvcProj.appendLineOpen('<ProjectConfiguration Include="GeckoImported|%s">' % msvcPlatform);
    msvcProj.appendLine('<Configuration>GeckoImported</Configuration>');
    msvcProj.appendLine('<Platform>%s</Platform>' % msvcPlatform);
    msvcProj.appendLineClose('</ProjectConfiguration>');
    msvcProj.appendLineClose('</ItemGroup>');
    msvcProj.appendLineOpen('<PropertyGroup Label="Globals">');
    msvcProj.appendLine('<ProjectGuid>{%s}</ProjectGuid>' % target['projectGuid']);
    msvcProj.appendLine('<RootNamespace>MozillaCentral</RootNamespace>');
    msvcProj.appendLineClose('</PropertyGroup>');

    msvcProj.appendLine('<Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" />');

    # These are global settings for the project.  Some things should specifically NOT be included here:
    #     <CharacterSet>Unicode</CharacterSet> -- CharacterSet should be unset.
    # Including this defines _UNICODE/UNICODE.
    msvcProj.appendLineOpen('<PropertyGroup Condition="\'$(Configuration)|$(Platform)\'==\'GeckoImported|%s\'" Label="Configuration">' % msvcPlatform);
    msvcProj.appendLine('<ConfigurationType>DynamicLibrary</ConfigurationType>');
    #msvcProj.appendLine('<UseDebugLibraries>true</UseDebugLibraries>');
    msvcProj.appendLineClose('</PropertyGroup>');

    msvcProj.appendLine('<Import Project="$(VCTargetsPath)\Microsoft.Cpp.props" />');
    
    msvcProj.appendLine('<PropertyGroup Label="UserMacros" />');
    msvcProj.appendLineOpen('<PropertyGroup Condition="\'$(Configuration)|$(Platform)\'==\'GeckoImported|%s\'">' % msvcPlatform);
    msvcProj.appendLine('<TargetPath>%s</TargetPath>' % escapeForMsvcXML(target["treeloc"]).replace("/","\\"));
    msvcProj.appendLine('<TargetName>%s</TargetName>' % escapeForMsvcXML(target["target"]).replace("/","\\")[:-4]);
    msvcProj.appendLine('<ProgramDatabaseFile>%s</ProgramDatabaseFile>' % escapeForMsvcXML(target["treeloc"] + "\\" + target["target"][:-4] + ".pdb").replace("/","\\"));
    msvcProj.appendLineClose('</PropertyGroup>');

    # Here we can either build with optimation or debug and continue but not both
    msvcProj.appendLineOpen('<ItemDefinitionGroup Condition="\'$(Configuration)|$(Platform)\'==\'GeckoImported|%s\'">' % msvcPlatform);
    msvcProj.appendLineOpen('<ClCompile>')
    msvcProj.appendLine('<Optimization>MinSpace</Optimization>');
    msvcProj.appendLine('<ExceptionHandling>false</ExceptionHandling>');
    msvcProj.appendLineClose('</ClCompile>')
    msvcProj.appendLineClose('</ItemDefinitionGroup>')

    # Use the filters file for olders
    msvcProj.filtersLine('<?xml version="1.0" encoding="utf-8"?>');
    msvcProj.filtersLineOpen('<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">');
    msvcProj.filtersLineOpen('<ItemGroup>');

def genMsvcFooter(msvcProj):
    msvcProj.appendLine('<Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />');
    msvcProj.appendLineOpen('<ImportGroup Label="ExtensionTargets">');
    msvcProj.appendLineClose('</ImportGroup>');
    msvcProj.appendLineClose('</Project>');
    
    msvcProj.filtersLineClose("</ItemGroup>");
    msvcProj.generateFolders();
    msvcProj.filtersLineClose("</Project>");

class MsvcPrinter:
    def __init__(self):
        self.msvcOut = []
        self.indent = ""
        self.filtersOut = []
        self.filtersIndent = ""
        self.folders = {} # Use a map as a set, values are meaningless
    def filtersLine(self, line):
        self.filtersOut.append(self.filtersIndent + line)
    def filtersLineOpen(self, line):
        self.filtersLine(line)
        self.filtersIndent = self.filtersIndent + "  "
    def filtersLineClose(self, line):
        self.filtersIndent = self.filtersIndent[:-2]
        self.filtersLine(line)
    def appendLine(self, line):
        self.msvcOut.append(self.indent + line)
    def appendLineOpen(self, line):
        self.appendLine(line)
        self.indent = self.indent + "  "
    def appendLineClose(self, line):
        self.indent = self.indent[:-2]
        self.appendLine(line)
    def get(self):
        return "\n".join(self.msvcOut)
    def generateFolders(self):
        self.filtersLineOpen('<ItemGroup>')
        for folder in self.folders:
            self.filtersLineOpen('<Filter Include="%s">' % folder)
            self.filtersLineClose('</Filter>')
        self.filtersLineClose('</ItemGroup>')
    def getFilters(self):
        return "\n".join(self.filtersOut)

def escapeForMsvcXML(str):
    str = str.replace("<", "&lt;")
    str = str.replace(">", "&gt;")
    return str

def makeMsvcPath(treeloc, name, basepath=None):
    if basepath is None:
        basepath = tree_base
    return os.path.relpath(os.path.join(tree_base, treeloc, name), basepath).replace("/","\\")

# turn first-level quote escaping (\" -> ", \\ -> \) back into
def unescapeQuotesOnce(arg):
    return arg.replace("\\\"", "\"").replace("\\\\", "\\")

def genMsvcClCompile(msvcProj, tree_root, clCompileMap):
    for key in clCompileMap:
        msvcProj.appendLineOpen('<ClCompile Include="%s">' % escapeForMsvcXML(";".join(clCompileMap[key]["files"])))
        for xmlLine in clCompileMap[key]["xmlLines"]:
            msvcProj.appendLine(xmlLine)
        msvcProj.appendLineClose('</ClCompile>')

def genMsvcClCompileGroup(msvcProj, tree_root, hackyMap, target, clCompileMap):
    srcName = makeMsvcPath(target["treeloc"], target["srcfiles"][0])
    objName = makeMsvcPath(target["treeloc"], target["targetfile"])

    defines = []
    quotedDefines = []
    includeDirs = []
    extraConfigLines = []
    extraArgs = []
    disabledWarnings = []
    enabledWarnings = []

    # We don't do much with quoting, only hangling it where
    # we must -- specifically in -D flags.  That will break
    # if those args have embedded spaces in them.
    import shlex
    tokens = (shlex.split(str(target["cflags"]))).__iter__()
    midparse = False
    try:
        while True:
            midparse = False
            token = tokens.next()
            midparse = True

            m = re.match(r"^[-/]D(.*)", token)
            if m:
                arg = m.group(1) or tokens.next()
                if "=" in arg and ("\"" in arg or "'" in arg):
                    # VS does some stupid things with quoted defines.  If it sees one,
                    # it expands out its /D NAME=value to /D "NAME=quoted_value".  So
                    # instead of NAME="\"Foo\"", you get "NAME=\"\\\"Foo\\\"\"".  This
                    # totally breaks any code that then does #include NAME.  If we see
                    # one of these, we just add it as an "extra arg" so that we can
                    # not do that external quoting ourselves.  Hopefully this won't make
                    # it invisible to IntelliSense and similar.

                    # fix up arg to remove outer ''s, we have some code, e.g.
                    # OPUS_VERSION that uses single quotes thus:
                    # -DOPUS_VERSION='"draft-11-mozilla"'.  We should fix the source
                    # Makefile for this!
                    m = re.match(r"^([^=]*)=(.*)$", arg)
                    defname = m.group(1)
                    defval = m.group(2)
                    if defval.startswith("'\"") and defval.endswith("\"'"):
                        arg = defname + "=\"\\\"" + defval[2:-2] + "\\\"\""

                    quotedDefines.append("/D " + arg)
                else:
                    defines.append(arg)
                continue

            m = re.match(r"^[-/]U(.*)", token)
            if m:
                arg = m.group(1) or tokens.next()
                while True:
                    try:
                        defines.remove(arg)
                    except ValueError:
                        break # Keep removing until there are no more elements in the list

                # We don't support undefining a quotedDefine

                continue

            m = re.match(r"[-/]I(.*)", token)
            if m:
                path = m.group(1) or tokens.next()
                includeDirs.append(makeMsvcPath(target["treeloc"], path))
                continue

            m = re.match(r"[-/]W([0-5])$", token)
            if m:
                extraConfigLines.append("<WarningLevel>Level%s</WarningLevel>" % (m.group(1)))
                continue

            m = re.match(r"[-/]O([12d])$", token)
            if m:
                arg = m.group(1)
                if arg == "1":   arg = "MinSpace"
                elif arg == "2": arg = "MaxSpeed"
                elif arg == "d": arg = "Disabled"
                extraConfigLines.append("<Optimization>%s</Optimization>" % (arg))
                continue

            m = re.match(r"[-/]Z([Ii7])$", token)
            if m:
                arg = m.group(1)
                if arg == "i":   arg = "ProgramDatabase"
                elif arg == "7": arg = "OldStyle"
                elif arg == "I": arg = "EditAndContinue"
                extraConfigLines.append("<DebugInformationFormat>%s</DebugInformationFormat>" % (arg))
                continue

            m = re.match(r"[-/](MT|MTd|MD|MDd)$", token)
            if m:
                arg = m.group(1)
                if   arg == "MT":  arg = "MultiThreaded"
                elif arg == "MTd": arg = "MultiThreadedDebug"
                elif arg == "MD":  arg = "MultiThreadedDLL"
                elif arg == "MDd": arg = "MultiThreadedDebugDLL"
                extraConfigLines.append("<RuntimeLibrary>%s</RuntimeLibrary>" % (arg))
                continue

            m = re.match(r"[-/]Fd(.*)", token)
            if m:
                path = m.group(1) or tokens.next()
                path = makeMsvcPath(target["treeloc"], path)
                # Disable this for now because we don't want to override the PDBs
                #extraConfigLines.append("<ProgramDataBaseFileName>%s</ProgramDataBaseFileName>" % (path))
                continue

            m = re.match(r"[-/]FI(.*)", token)
            if m:
                path = m.group(1) or tokens.next()
                path = makeMsvcPath(target["treeloc"], path, target["treeloc"])
                extraConfigLines.append("<ForcedIncludeFiles>%s</ForcedIncludeFiles>" % (path))
                continue

            m = re.match(r"[-/]T([CP])$", token)
            if m:
                arg = m.group(1)
                if arg == "C": arg = "CompileAsC"
                else:          arg = "CompileAsCpp"
                extraConfigLines.append("<CompileAs>%s</CompileAs>" % (arg))
                continue

            m = re.match(r"[-/]Gy(-?)$", token)
            if m:
                arg = m.group(1)
                if arg == "-": arg = "false"
                else:          arg = "true"
                extraConfigLines.append("<FunctionLevelLinking>%s</FunctionLevelLinking>" % (arg))
                continue

            m = re.match(r"[-/]GR(-?)$", token)
            if m:
                arg = m.group(1)
                if arg == "-": arg = "false"
                else:          arg = "true"
                extraConfigLines.append("<RuntimeTypeInfo>%s</RuntimeTypeInfo>" % (arg))
                continue

            m = re.match(r"[-/]Oy(-?)$", token)
            if m:
                arg = m.group(1)
                if arg == "-": arg = "false"
                else:          arg = "true"
                extraConfigLines.append("<OmitFramePointers>%s</OmitFramePointers>" % (arg))
                continue

            m = re.match(r"[-/]wd([0-9]+)", token)
            if m:
                arg = m.group(1)
                disabledWarnings.append(arg)
                continue

            m = re.match(r"[-/]we([0-9]+)", token)
            if m:
                arg = m.group(1)
                enabledWarnings.append(arg)
                continue

            m = re.match(r"(?i)[-/]nologo", token)
            if m:
                continue

            extraArgs.append(token)
    except StopIteration:
        if midparse:
            print >>sys.stderr, "Failed parsing msvc cflags, target %s" % target["target"]
            sys.exit(1)

    folder = target["treeloc"]

    defines.append("%(PreprocessorDefinitions)")
    includeDirs.append("%(AdditionalIncludeDirectories)")

    extraArgStr = " ".join(extraArgs).strip()

    clCompileHash = {}
    clCompileHash["files"] = [srcName]
    clCompileHash["xmlLines"] = []

    #clCompileHash.xmlLines.appen('<ObjectFileName>%s</ObjectFileName>' % escapeForMsvcXML(objName))
    clCompileHash["xmlLines"].append('<PreprocessorDefinitions>%s</PreprocessorDefinitions>' % escapeForMsvcXML(";".join(defines)))
    clCompileHash["xmlLines"].append('<AdditionalIncludeDirectories>%s</AdditionalIncludeDirectories>' % escapeForMsvcXML(";".join(includeDirs)))
    clCompileHash["xmlLines"].append('<MultiProcessorCompilation>true</MultiProcessorCompilation>')

    for config in extraConfigLines:
        clCompileHash["xmlLines"].append(config)

    if extraArgStr:
        print "EXTRA CC ARGS for %s: %s" % (target["target"], extraArgStr)
    if quotedDefines:
        extraArgStr = " ".join(quotedDefines) + " " + extraArgStr
    if extraArgStr:
        clCompileHash["xmlLines"].append('<AdditionalOptions>%s %%(AdditionalOptions)</AdditionalOptions>' % escapeForMsvcXML(extraArgStr))

    if disabledWarnings:
        clCompileHash["xmlLines"].append('<DisableSpecificWarnings>%s</DisableSpecificWarnings>' % ";".join(disabledWarnings))
    if enabledWarnings:
        clCompileHash["xmlLines"].append('<EnableSpecificWarnings>%s</EnableSpecificWarnings>' % ";".join(enabledWarnings))

    key = str(clCompileHash["xmlLines"])
    if key in clCompileMap:
        clCompileMap[key]["files"].append(srcName)
    else: # insert it
        clCompileMap[key] = clCompileHash

    msvcProj.filtersLineOpen('<ClCompile Include="%s">' % escapeForMsvcXML(srcName))
    msvcProj.filtersLine('<Filter>%s</Filter>' % escapeForMsvcXML(folder))
    msvcProj.folders[folder] = True
    msvcProj.filtersLineClose('</ClCompile>')

def genMsvcTargetCompile(msvcProj, tree_root, hackyMap, target):
    objdeps = target["ppDeps"]
    objsToLink = [] # Object
    clCompileMap = {}

    for objdep in objdeps:
        if objdep in hackyMap and "srcfiles" in hackyMap[objdep] and hackyMap[objdep]["srcfiles"]:
            #print hackyMap[objdep]["treeloc"] + "/" + hackyMap[objdep]["srcfiles"][0]
            genMsvcClCompileGroup(msvcProj, tree_root, hackyMap, hackyMap[objdep], clCompileMap)
        elif objdep.endswith(".desc"):
            #print "Skipping desc: " + objdep
            pass
        else:
            print "Warning: Don't have srcdeps for: " + objdep.replace("\n","") + ", wont be updated with msbuild"
            # append it here, and hope that it matches the extra .obj/.res in the command line
            objsToLink.append(objdep.replace("\n",""))

    msvcProj.appendLineOpen('<ItemGroup>');
    genMsvcClCompile(msvcProj, tree_root, clCompileMap)
    msvcProj.appendLineOpen('</ItemGroup>');

    outFile = (target["treeloc"] + "/" + target["target"]).replace("/","\\")
    extraConfigLines = []
    delayLoadDLLs = []
    libPaths = []
    extraArgs = []
    importLibrary = None

    # parse libraries and args from the build command
    cmdline = target["build_command"]
    if "expandlibs_exec" in cmdline:
        # if it was called via expandlibs_exec, we'll have a "-- link" where the real command starts.  skip all that.
        cmdline = cmdline[cmdline.find("-- link") + 7:]
    tokens = (cmdline.split(" ")).__iter__()
    midparse = False
    try:
        while True:
            midparse = False
            token = tokens.next()
            utoken = token.upper()
            midparse = True

            m = re.match(r"(?i)^[-/]SUBSYSTEM:(.*)", token)
            if m:
                arg = m.group(1)
                if arg == "WINDOWS":   arg = "Windows"
                elif arg == "CONSOLE": arg = "Console"
                elif arg == "NATIVE":  arg = "Native"
                extraConfigLines.append("<SubSystem>%s</SubSystem>" % arg)
                continue

            m = re.match(r"(?i)^[-/]LARGEADDRESSAWARE(.*)", token)
            if m:
                arg = m.group(1)
                if arg == ":NO": arg = "false"
                else:            arg = "true"
                extraConfigLines.append("<LargeAddressAware>%s</LargeAddressAware>" % arg)
                continue

            m = re.match(r"(?i)^[-/]NXCOMPAT(.*)", token)
            if m:
                arg = m.group(1)
                if arg == ":NO": arg = "false"
                else:            arg = "true"
                extraConfigLines.append("<DataExecutionPrevention>%s</DataExecutionPrevention>" % arg)
                continue

            m = re.match(r"(?i)^[-/]SAFESEH(.*)", token)
            if m:
                arg = m.group(1)
                if arg == ":NO": arg = "false"
                else:            arg = "true"
                extraConfigLines.append("<ImageHasSafeExceptionHandlers>%s</ImageHasSafeExceptionHandlers>" % arg)
                continue

            m = re.match(r"(?i)^[-/]DYNAMICBASE(.*)", token)
            if m:
                arg = m.group(1)
                if arg == ":NO": arg = "false"
                else:            arg = "true"
                extraConfigLines.append("<RandomizedBaseAddress>%s</RandomizedBaseAddress>" % arg)
                continue

            m = re.match(r"(?i)^[-/]DELAYLOAD:(.*)", token)
            if m:
                arg = m.group(1)
                delayLoadDLLs.append(arg)
                continue

            m = re.match(r"(?i)^[-/]LIBPATH:(.*)", token)
            if m:
                arg = m.group(1)
                if arg.startswith("\"") and arg.endswith("\""): arg = arg[1:-1]
                libPaths.append(makeMsvcPath(target["treeloc"], arg))
                continue

            m = re.match(r"(?i)^[-/]DEF:(.*)", token)
            if m:
                arg = m.group(1)
                path = makeMsvcPath(target["treeloc"], arg)
                extraConfigLines.append("<ModuleDefinitionFile>%s</ModuleDefinitionFile>" % path)
                continue

            m = re.match(r"(?i)^[-/]PDB:(.*)", token)
            if m:
                arg = m.group(1)
                path = makeMsvcPath(target["treeloc"], arg)
                extraConfigLines.append("<ProgramDatabaseFile>%s</ProgramDatabaseFile>" % path)
                continue

            m = re.match(r"(?i)^[-/]RELEASE", token)
            if m:
                extraConfigLines.append("<SetChecksum>true</SetChecksum>")
                continue

            if utoken.startswith("-MANIFEST") and utoken is not "-MANIFEST:NO":
                print "Warning: Saw %s flag, but we unilaterally disable manifests, fix hacky!" % token

            m = re.match(r"(?i)^[-/]IMPLIB:(.*)", token)
            if m:
                importLibrary = m.group(1)
                continue

            # These had better be set in the global project settings properly
            if utoken.startswith("-DLL") or utoken.startswith("-MACHINE"):
                continue
            if utoken.startswith("-DEBUG") or utoken.startswith("-OUT:"):
                continue

            if utoken.startswith("-NOLOGO"):
                continue

            if utoken.endswith(".LIB") or utoken.endswith(".LIB\""):
                if utoken.startswith("\"") and utoken.endswith("\""):
                    token = token[1:-1]
                    utoken = utoken[1:-1]
                # if it's not absolute, add it to the extra libs list
                # otherwise it's something that will get expanded
                tokenpath = os.path.join(target["treeloc"], token)
                if os.path.exists(tokenpath):
                    relpath = makeMsvcPath(target["treeloc"], token)
                    # If relpath starts with a '.', that means it's outside of the objdir.
                    # Thus, it should get treated as global and we should use its original name.
                    if relpath[0] != '.':
                        # objdir-relative library
                        objsToLink.append(relpath)
                    else:
                        objsToLink.append(os.path.abspath(token))
                elif not ("/" in token or "\\" in token):
                    # global library with no path, will be searched for in library search path
                    objsToLink.append(token)
                elif not os.path.exists(tokenpath + ".desc"):
                    print "Warning: non-local lib, but it doesn't exist and no .desc file: %s for target %s" % (token, target["target"])
                continue

            # Hack: Skip these; these are objs that are directly linked in to
            # the library from the current dir (e.g. they didn't come from
            # an import lib).  We should double check that we're already
            # linking them and complain if we're not
            if utoken.endswith(".RES") or utoken.endswith(".OBJ"):
                continue

            extraArgs.append(token)
    except StopIteration:
        if midparse:
            print >>sys.stderr, "Failed parsing msvc link flags, target %s" % target["target"]
            sys.exit(1)


    #if outFile.endswith(".dll"):
    #    outFile = outFile[:-4]

    if importLibrary:
        importLibrary = makeMsvcPath(target["treeloc"], importLibrary)
    else:
        importLibrary = makeMsvcPath(target["treeloc"], target["target"].replace(".dll", ".lib"))

    libPaths.append("$(LibraryPath)")

    msvcProj.appendLineOpen('<PropertyGroup Condition="\'$(Configuration)|$(Platform)\'==\'GeckoImported|%s\'">' % msvcPlatform)
    msvcProj.appendLine('<LinkIncremental>true</LinkIncremental>')
    msvcProj.appendLine('<LibraryPath>%s</LibraryPath>' % (";".join(libPaths)))
    # we may need to change this if we ever see a manifest
    msvcProj.appendLine('<GenerateManifest>false</GenerateManifest>')
    msvcProj.appendLineClose('</PropertyGroup>')

    msvcProj.appendLineOpen('<ItemDefinitionGroup>')
    msvcProj.appendLineOpen('<Link>')
    msvcProj.appendLine('<GenerateDebugInformation>true</GenerateDebugInformation>')
    msvcProj.appendLine('<OutputFile>%s</OutputFile>' % outFile)
    msvcProj.appendLine('<ImportLibrary>%s</ImportLibrary>' % importLibrary)
    msvcProj.appendLine('<AdditionalDependencies>%s</AdditionalDependencies>' % ";".join(objsToLink))
    for config in extraConfigLines:
        msvcProj.appendLine(config)
    if delayLoadDLLs:
        msvcProj.appendLine('<DelayLoadDLLs>%s</DelayLoadDLLs>' % ";".join(delayLoadDLLs))

    extraArgStr = " ".join(extraArgs).strip()
    if extraArgStr:
        print "Leftover Additional Args for %s: %s" % (target["target"], extraArgStr)
        msvcProj.appendLine('<AdditionalOptions>%s</AdditionalOptions>' % extraArgStr)

    # don't generate a /TLBID arg for us
    msvcProj.appendLine('<TypeLibraryResourceID></TypeLibraryResourceID>')
    msvcProj.appendLineClose('</Link>')

    msvcProj.appendLineOpen('<PostBuildEvent>')
    msvcProj.appendLine('<Command>copy %s dist\\lib\ncopy %s dist\\bin</Command>' % (outFile.replace(".dll", ".lib"), outFile))
    msvcProj.appendLineClose('</PostBuildEvent>')

    msvcProj.appendLineClose('</ItemDefinitionGroup>')
            

def genMsvc(tree_root, hackyMap, target):
    msvcProj = MsvcPrinter()
    genMsvcHeader(msvcProj, target)
    genMsvcTargetCompile(msvcProj, tree_root, hackyMap, target)
    genMsvcFooter(msvcProj)
    msvcfile = open(os.path.join(tree_root, target["target"] + ".vcxproj"), "w")
    print >>msvcfile, msvcProj.get()
    filtersfile = open(os.path.join(tree_root, target["target"] + ".vcxproj.filters"), "w")
    print >>filtersfile, msvcProj.getFilters()

def genMsvcSolution(tree_root, projects):
    solution = []

    # Solution files have magic leading bits
    # 00000000: efbb bf0d 0a4d 6963 726f 736f 6674 2056  .....Microsoft V
    solution.append(str(chr(239)) + str(chr(187)) + str(chr(191)))
    solution.append('Microsoft Visual Studio Solution File, Format Version 11.00')
    solution.append('# Visual Studio 2010')
    for project in projects:
        # The 8BC9... uuid here is magic(a type? global solution?) and is constant
        solution.append(('Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "%s", "%s.vcxproj", "{%s}"') % (project["path"], project["path"], project["guid"]))
# TODO: to say that this project depends on others:
#		ProjectSection(ProjectDependencies) = postProject
#			{other_project_guid} = {other_project_guid}
#		EndProjectSection
        solution.append('EndProject')

    solution.append('Global')
    solution.append('\tGlobalSection(SolutionConfigurationPlatforms) = preSolution')
    solution.append('\t\tGeckoImported|%s = GeckoImported|%s' % (msvcPlatform, msvcPlatform))
    solution.append('\tEndGlobalSection')
    solution.append('\tGlobalSection(ProjectConfigurationPlatforms) = postSolution')
    for project in projects:
        solution.append('\t\t{%s}.GeckoImported|%s.ActiveCfg = GeckoImported|%s' % (project["guid"], msvcPlatform, msvcPlatform))
        solution.append('\t\t{%s}.GeckoImported|%s.Build.0 = GeckoImported|%s' % (project["guid"], msvcPlatform, msvcPlatform))
    solution.append('\tEndGlobalSection')
    solution.append('\tGlobalSection(SolutionProperties) = preSolution')
    solution.append('\t\tHideSolutionNode = FALSE')
    solution.append('\tEndGlobalSection')
    solution.append('EndGlobal')

    data = "\n".join(solution)

    msvcSlnfile = open(os.path.join(tree_root, "gecko.sln"), "w")
    print >>msvcSlnfile, data

if __name__ == "__main__":
    args = sys.argv

    # save script name
    makehackypy = os.path.abspath(args.pop(0))

    tree_base = os.path.abspath(args.pop(0))

    conffile = open(os.path.join(tree_base, "config/autoconf.mk"), "r")
    for line in conffile:
        m = re.match(r"([A-Z0-9_]+) *= *(.*)", line.strip())
        if m:
            arg = m.group(1)
            val = m.group(2)
            if arg == "CPU_ARCH" and val == "x86_64":
                is64Bit = True
                msvcPlatform = "x64"
            elif arg == "CC_VERSION":
                if val.find("16.") == 0:
                    msvcVersion = "2010"
                elif val.find("17.") == 0:
                    msvcVersion = "2012"
                elif val.find("18.") == 0:
                    msvcVersion = "2013"

    hackyMap = readhacky(tree_base)

    # generate guids for each project
    for targetName in hackyMap:
        if targetName.endswith(".dll"):
            hackyMap[targetName]["projectGuid"] = str(uuid.uuid1())

    # then go through them all
    solutionProjects = []
    for targetName in hackyMap:
        if targetName.endswith(".dll"):
            #if not targetName.endswith("gkmedias.dll"): continue
            print "Generating: " + targetName
            solutionProjects.append({ "guid": hackyMap[targetName]["projectGuid"], "path": os.path.basename(targetName).encode("utf-8") })
            genMsvc(tree_base, hackyMap, hackyMap[targetName])

    genMsvcSolution(tree_base, solutionProjects)
