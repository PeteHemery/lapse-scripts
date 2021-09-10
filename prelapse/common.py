# -*- coding: utf-8 -*-
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.

import logging


def setupLogger(component, verbose=False):
  """
  Return a logger object with the component name
  """
  logging.basicConfig(level=logging.INFO if verbose else logging.WARNING)
  return logging.getLogger(component)


def parseGroupSliceIndex(group):
  index = None
  sliceIndex = None
  if any(x in group for x in [":", "[", "]"]):
    tmp = group.split("[")
    assert len(tmp) == 2
    assert tmp[1][-1] == "]"
    firstLabel = tmp[0]
    tmp = tmp[1][:-1].split(":")
    numSplits = len(tmp)
    if numSplits > 2:
      raise RuntimeError("Only one ':' char allowed in slice definition: {}"
                         .format(group))
    elif numSplits < 1:
      raise RuntimeError("Invalid slice/index detected: {}"
                         .format(group))
    elif numSplits == 1:
      index = int(tmp[0])
      assert index >= 0
    elif numSplits == 2:
      start = None
      stop = None
      try:
        start = int(tmp[0])
      except ValueError:
        pass
      try:
        stop = int(tmp[1])
      except ValueError:
        pass
      if not (start or stop):
        raise RuntimeError("Cannot parse invalid slice label, "
          "must provide start and stop values: {}".format(group))
      sliceIndex = (start, stop)
    else:
      raise RuntimeError("How did you get here?")
    group = firstLabel
  return group, index, sliceIndex


def groupAppend(self, group, index=None, sliceIndex=None):
  thisgroup = {"name": group,
               "groupindex": list(self.config.keys()).index(group)}
  if "meta" in self.config[group]:
    thisgroup["grouptype"] = "meta"
    thisgroup["files"] = ["tbd"]
    thisgroup["numfiles"] = len(thisgroup["files"])
  else:
    thisgroup["grouptype"] = "pure"
    thisgroup["files"] = list(enumerate(self.config[group]["files"]))
    thisgroup["numfiles"] = len(thisgroup["files"])
    thisgroup["path"] = self.config[group]["path"]
  if index is not None:
    try:
      thisgroup["files"] = [thisgroup["files"][index],]
    except IndexError:
      self.logger.warning("Index {} not within range of group '{}': [0:{}]"
                          .format(index, thisgroup["name"],
                                  thisgroup["numfiles"] - 1))
      thisgroup["files"] = []
    thisgroup["grouptype"] = "index_{}".format(index)
    thisgroup["numfiles"] = len(thisgroup["files"])
  elif sliceIndex is not None:
    thisgroup["files"] = thisgroup["files"][sliceIndex[0]:sliceIndex[1]]
    if len(thisgroup["files"]) == 0:
      self.logger.warning("Slices {} not within range of group '{}' [0:{}]"
                          .format(sliceIndex, thisgroup["name"],
                                  thisgroup["numfiles"] - 1))

    thisgroup["grouptype"] = "slice_{}_{}".format(*sliceIndex)
    thisgroup["numfiles"] = len(thisgroup["files"])
  self.groups.append(thisgroup)


def parseGroupArgs(self, args):
  self.groups = []
  if "allgroups" in args and args.allgroups:
    for group in self.config:
      groupAppend(self, group)
  else:
    for group in args.groups:
      group, index, sliceIndex = parseGroupSliceIndex(group)
      if group not in self.config:
        raise RuntimeError("group '{}' not in config '{}'"
                           .format(group, args.config))
      groupAppend(self, group, index, sliceIndex)
    if not any(self.groups):
      raise RuntimeError("No groups found in config")


def writeListFile(outpath, files, duration):
  lastFile = ""
  # Write the output file
  with open(outpath, "w") as f:
    f.write("ffconcat version 1.0\n\n")
    for x in files:
      f.write("file '{}'\nduration {}\n".format(x, duration))
      lastFile = x
    f.write("file '{}'\n".format(lastFile))
