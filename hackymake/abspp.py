#!/usr/bin/env python

import sys
import re
import os
from tokenize import tokenize, untokenize, NUMBER, STRING, NAME, OP

def abspp(fpin, base = None):
  if not base:
    base = "."
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
        token = os.path.realpath(os.path.join(base, token))
        # Some windows dependencies are poorly formed
        # in the original .pp file
        if not os.path.exists(token):
          continue
        token = token.replace("\\", "/")
        deps.append(token)
      else:
        if token != " " and token != ":" and not os.path.exists(token):
          continue
        deps.append(token)
  # go through a set to remove duplicates
  return list(set(deps))

if __name__ == "__main__":
  if len(sys.argv) > 1:
    basepath = sys.argv[1]
  else:
    basepath = None
  deps = abspp(sys.stdin, basepath)
  print " ".join(deps)
