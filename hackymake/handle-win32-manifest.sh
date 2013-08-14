#!/bin/bash

tool=$1
target=$2
manifest=$3
srcmanifest=$4

# No manifest tool?  Nothing to do.
if [ -z "$tool" ] ; then
    exit 0
fi

MANIFESTS=""

# Add each manifest in order, if it exists
if [ -f "${srcmanifest}" ] ; then
    MANIFESTS="${MANIFESTS} ${srcmanifest}"
fi

if [ -f "${manifest}" ] ; then
    MANIFESTS="${MANIFESTS} ${manifest}"
fi

if [ -z "$MANIFESTS" ] ; then
    exit 0
fi

echo "Embedding manifest from ${MANIFESTS}"
mt.exe -NOLOGO -MANIFEST ${MANIFESTS} -OUTPUTRESOURCE:"${target}"\;1
