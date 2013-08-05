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

def genMsvcHeader(msvcProj):
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
    msvcProj.appendLineClose('</PropertyGroup>');

    # Here we can either build with optimation or debug and continue but not both
    msvcProj.appendLineOpen('<ItemDefinitionGroup Condition="\'$(Configuration)|$(Platform)\'==\'GeckoImported|Win32\'">');
    msvcProj.appendLineOpen('<ClCompile>')
    msvcProj.appendLine('<Optimization>MinSpace</Optimization>');
    msvcProj.appendLine('<ExceptionHandling>false</ExceptionHandling>');
    msvcProj.appendLineClose('</ClCompile>')
    msvcProj.appendLineClose('</ItemDefinitionGroup>')

    msvcProj.appendLineOpen('<ItemGroup>');

    # Use the filters file for olders
    msvcProj.filtersLine('<?xml version="1.0" encoding="utf-8"?>');
    msvcProj.filtersLineOpen('<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">');
    msvcProj.filtersLineOpen('<ItemGroup>');

def genMsvcFooter(msvcProj):
    msvcProj.appendLineClose('</ItemGroup>');
    msvcProj.appendLine('<Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />');
    msvcProj.appendLineOpen('<ImportGroup Label="ExtensionTargets">');
    msvcProj.appendLineClose('</ImportGroup>');
    msvcProj.appendLineClose('</Project>');
    
    msvcProj.filtersLineClose("</ItemGroup>");
    msvcProj.generateFolders();
    msvcProj.filtersLineClose("</Project>");

class MsvcPrinter:
    msvcOut = []
    indent = ""
    filtersOut = []
    filtersIndent = ""
    folders = {} # Use a map as a set, values are meaningless
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

def parseDefines(cflags):
    defines = []
    for flag in cflags.split(" "):
        if flag.startswith("-D"):
            defines.append(flag[2:])
    return ";".join(defines)


def additionalInclude(tree_root, target, cflags):
    includes = []
    for flag in cflags.split(" "):
        if flag.startswith("-I"):
            includeDir = flag[2:]
            includes.append(os.path.join(tree_root, target['treeloc'], includeDir).replace("/","\\"))
    return ";".join(includes)

def additionalFlags(tree_root, target, cflags):
    flags = []
    fixPathForNextFlag = False
    for flag in cflags.split(" "):
        if flag.startswith("-D") or flag.startswith("-I") or flag == "":
            continue
        if fixPathForNextFlag:
            fixPathForNextFlag = False
            flag = os.path.join(tree_root, target['treeloc'], flag).replace("/","\\")
        if flag == "-FI":
            fixPathForNextFlag = True
        flags.append(flag)

    return " ".join(flags)

def genMsvcClCompile(msvcProj, tree_root, hackyMap, target):
    targetName = target["treeloc"] + "/" + target["srcfiles"][0]
    preprocessorDef = parseDefines(target["cflags"])
    includeDirs = additionalInclude(tree_root, target, target["cflags"])
    flags = additionalFlags(tree_root, target, target["cflags"])
    folder = target["treeloc"]
    msvcProj.appendLineOpen('<ClCompile Include="%s">' % targetName.replace("/","\\"));
    msvcProj.appendLine('<PreprocessorDefinitions>%s</PreprocessorDefinitions>' % preprocessorDef);
    if includeDirs != "":
        msvcProj.appendLine('<AdditionalIncludeDirectories>%s;%%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>' % includeDirs);
    if flags != "":
        msvcProj.appendLine('<AdditionalOptions>%s %%(AdditionalOptions)</AdditionalOptions>' % flags);
    #msvcProj.appendLine('');
    msvcProj.appendLineClose('</ClCompile>');

    msvcProj.filtersLineOpen('<ClCompile Include="%s">' % targetName.replace("/","\\"));
    msvcProj.filtersLine('<Filter>%s</Filter>' % folder);
    msvcProj.folders[folder] = True
    msvcProj.filtersLineClose('</ClCompile>');

def genMsvcTargetCompile(msvcProj, tree_root, hackyMap, target):
    objdeps = target["ppDeps"]
    for objdep in objdeps:
        if objdep in hackyMap and "srcfiles" in hackyMap[objdep] and hackyMap[objdep]["srcfiles"]:
            #print hackyMap[objdep]["treeloc"] + "/" + hackyMap[objdep]["srcfiles"][0]
            genMsvcClCompile(msvcProj, tree_root, hackyMap, hackyMap[objdep])
        else:
            print "ERROR: Don't have srcdeps for: " + objdep
            

def genMsvc(tree_root, hackyMap, target):
    msvcProj = MsvcPrinter()
    genMsvcHeader(msvcProj)
    genMsvcTargetCompile(msvcProj, tree_root, hackyMap, target)
    genMsvcFooter(msvcProj)
    msvcfile = open(os.path.join(tree_root, target["target"] + ".vcxproj"), "w")
    print >>msvcfile, msvcProj.get()
    filtersfile = open(os.path.join(tree_root, target["target"] + ".vcxproj.filters"), "w")
    print >>filtersfile, msvcProj.getFilters()

if __name__ == "__main__":
    args = sys.argv

    # save script name
    makehackypy = os.path.abspath(args.pop(0))

    tree_base = args.pop(0)

    hackyMap = readhacky(tree_base)

    genMsvc(tree_base, hackyMap, hackyMap["layout/media/gkmedias.dll"])