#!/usr/bin/env python

import os, sys, re

DEBUG = True
tree_base = None

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
    msvcProj.appendLineOpen('<ProjectConfiguration Include="GeckoImported|Win32">');
    msvcProj.appendLine('<Configuration>GeckoImported</Configuration>');
    msvcProj.appendLine('<Platform>Win32</Platform>');
    msvcProj.appendLineClose('</ProjectConfiguration>');
    msvcProj.appendLineClose('</ItemGroup>');
    msvcProj.appendLineOpen('<PropertyGroup Label="Globals">');
    msvcProj.appendLine('<ProjectGuid>{CDF26D50-0415-4FCF-8498-9FFB7592413A}</ProjectGuid>');
    msvcProj.appendLine('<RootNamespace>MozillaCentral</RootNamespace>');
    msvcProj.appendLineClose('</PropertyGroup>');

    msvcProj.appendLine('<Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" />');
    
    msvcProj.appendLineOpen('<PropertyGroup Condition="\'$(Configuration)|$(Platform)\'==\'GeckoImported|Win32\'" Label="Configuration">');
    msvcProj.appendLine('<ConfigurationType>DynamicLibrary</ConfigurationType>');
    #msvcProj.appendLine('<UseDebugLibraries>true</UseDebugLibraries>');
    msvcProj.appendLine('<CharacterSet>Unicode</CharacterSet>');
    msvcProj.appendLineClose('</PropertyGroup>');

    msvcProj.appendLine('<Import Project="$(VCTargetsPath)\Microsoft.Cpp.props" />');
    
    msvcProj.appendLine('<PropertyGroup Label="UserMacros" />');
    msvcProj.appendLineOpen('<PropertyGroup Condition="\'$(Configuration)|$(Platform)\'==\'GeckoImported|Win32\'">');
    msvcProj.appendLine('<LinkIncremental>true</LinkIncremental>');
    msvcProj.appendLine('<TargetPath>%s</TargetPath>' % escapeForMsvcXML(target["treeloc"]).replace("/","\\"));
    msvcProj.appendLine('<TargetName>%s</TargetName>' % escapeForMsvcXML(target["target"]).replace("/","\\")[:-4]);
    msvcProj.appendLine('<ProgramDatabaseFile>%s</ProgramDatabaseFile>' % escapeForMsvcXML(target["treeloc"] + "\\" + target["target"][:-4] + ".pdb").replace("/","\\"));
    msvcProj.appendLineClose('</PropertyGroup>');

    # Here we can either build with optimation or debug and continue but not both
    msvcProj.appendLineOpen('<ItemDefinitionGroup Condition="\'$(Configuration)|$(Platform)\'==\'GeckoImported|Win32\'">');
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
    return os.path.relpath(os.path.join(treeloc, name), basepath).replace("/","\\")

def genMsvcClCompile(msvcProj, tree_root, hackyMap, target):
    srcName = makeMsvcPath(target["treeloc"], target["srcfiles"][0])
    objName = makeMsvcPath(target["treeloc"], target["targetfile"])

    defines = []
    includeDirs = []
    extraConfigLines = []
    extraArgs = []

    # this is explicitly not going to handle quoting outside of a single arg,
    # because life is too short
    tokens = (target["cflags"].split(" ")).__iter__()
    midparse = False
    try:
        while True:
            midparse = False
            token = tokens.next()
            midparse = True
            m = None

            m = re.match(r"^[-/]D(.*)", token)
            if m:
                arg = m.group(1) or tokens.next()
                defines.append(arg)
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
                extraConfigLines.append("<ProgramDataBaseFileName>%s</ProgramDataBaseFileName>" % (path))
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

            extraArgs.append(token)
    except StopIteration:
        if midparse:
            print >>sys.stderr, "Failed parsing msvc cflags"
            sys.exit(1)

    folder = target["treeloc"]

    defines.append("%(PreprocessorDefinitions)")
    includeDirs.append("%(AdditionalIncludeDirectories)")
    extraArgs.append("%(AdditionalOptions)")

    msvcProj.appendLineOpen('<ClCompile Include="%s">' % escapeForMsvcXML(srcName))
    msvcProj.appendLine('<ObjectFileName>%s</ObjectFileName>' % escapeForMsvcXML(objName))
    msvcProj.appendLine('<PreprocessorDefinitions>%s</PreprocessorDefinitions>' % escapeForMsvcXML(";".join(defines)))
    msvcProj.appendLine('<AdditionalIncludeDirectories>%s;%%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>' % escapeForMsvcXML(";".join(includeDirs)))
    for config in extraConfigLines:
        msvcProj.appendLine(config)
    msvcProj.appendLine('<AdditionalOptions>%s</AdditionalOptions>' % escapeForMsvcXML(" ".join(extraArgs)))
    msvcProj.appendLineClose('</ClCompile>')

    msvcProj.filtersLineOpen('<ClCompile Include="%s">' % escapeForMsvcXML(srcName))
    msvcProj.filtersLine('<Filter>%s</Filter>' % escapeForMsvcXML(folder))
    msvcProj.folders[folder] = True
    msvcProj.filtersLineClose('</ClCompile>')

def genMsvcTargetCompile(msvcProj, tree_root, hackyMap, target):
    objdeps = target["ppDeps"]
    objsToLink = [] # Object

    msvcProj.appendLineOpen('<ItemGroup>');
    for objdep in objdeps:
        if objdep in hackyMap and "srcfiles" in hackyMap[objdep] and hackyMap[objdep]["srcfiles"]:
            #print hackyMap[objdep]["treeloc"] + "/" + hackyMap[objdep]["srcfiles"][0]
            genMsvcClCompile(msvcProj, tree_root, hackyMap, hackyMap[objdep])
        elif objdep.endswith(".desc"):
            print "Skipping desc: " + objdep
        else:
            print "Warning: Don't have srcdeps for: " + objdep.replace("\n","") + ", wont be updated with msbuild"
            objsToLink.append(objdep.replace("\n",""))
    msvcProj.appendLineOpen('</ItemGroup>');

    additionalDeps = escapeForMsvcXML(";".join(objsToLink))
    outFile = (target["treeloc"] + "/" + target["target"]).replace("/","\\")
    #if outFile.endswith(".dll"):
    #    outFile = outFile[:-4]
    msvcProj.appendLineOpen('<ItemDefinitionGroup>')
    msvcProj.appendLineOpen('<Link>')
    msvcProj.appendLine('<GenerateDebugInformation>true</GenerateDebugInformation>')
    msvcProj.appendLine('<OutputFile>%s</OutputFile>' % outFile)
    if additionalDeps != "":
        msvcProj.appendLine('<AdditionalDependencies>%s</AdditionalDependencies>' % additionalDeps)
    msvcProj.appendLineClose('</Link>')
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
        solution.append(('Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "%s", "%s.vcxproj", "{CDF26D50-0415-4FCF-8498-9FFB7592413A}"') % (project, project))
        solution.append('EndProject')

    solution.append('Global')
    solution.append('\tGlobalSection(SolutionConfigurationPlatforms) = preSolution')
    solution.append('\t\tGeckoImported|Win32 = GeckoImported|Win32')
    solution.append('\tEndGlobalSection')
    solution.append('\tGlobalSection(ProjectConfigurationPlatforms) = postSolution')
    solution.append('\t\t{CDF26D50-0415-4FCF-8498-9FFB7592413A}.GeckoImported|Win32.ActiveCfg = GeckoImported|Win32')
    solution.append('\t\t{CDF26D50-0415-4FCF-8498-9FFB7592413A}.GeckoImported|Win32.Build.0 = GeckoImported|Win32')
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

    tree_base = args.pop(0)

    hackyMap = readhacky(tree_base)

    solutionProjects = []
    for targetName in hackyMap:
        if targetName.endswith(".dll"):
            print "Generating: " + targetName
            solutionProjects.append(os.path.basename(targetName).encode("utf-8"))
            genMsvc(tree_base, hackyMap, hackyMap[targetName])

    genMsvcSolution(tree_base, solutionProjects)
