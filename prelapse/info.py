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

import json
import os

from pprint import pp, pformat

from .common import *


class LapseInfo():
  """ Group and image information class """
  def __init__(self):
    pass

  @staticmethod
  def addParserArgs(parser):
    parser.add_argument("-c", "--config", default="config.json",
                        help="json config file describing the picture groups\n(default: %(default)s)")
    mutexgroup = parser.add_mutually_exclusive_group(required=True)
    mutexgroup.add_argument("-a", "--allgroups", action="store_true",
                            help="access all groups\n(default: %(default)s)")
    mutexgroup.add_argument("-g", "--groups", nargs='?', action="append",
                            help="groups names within config from which to build new meta group. "
                            "(Can use index or slice, e.g. -g groupA[10] -g groupB[55:100])")
    parser.add_argument("-d", "--details", action="store_true",
                        help="show details for requested groups\n(default: %(default)s)")
    parser.add_argument("-i", "--filename", nargs='?', action="append",
                        help="show details for image filename within requested groups")
    parser.set_defaults(allgroups=False, details=False)
    return parser

  def parseArgs(self, args):
    self.verbose = args.verbose
    self.dryrun = args.dryrun
    self.overwrite = args.overwrite
    self.logger = setupLogger("Show Info", self.verbose)
    if not os.path.exists(args.config):
      raise RuntimeError("Could not find config file '{}'".format(args.config))
    with open(args.config, "r") as f:
      self.config = json.load(f)
    self.details = args.details
    parseGroupArgs(self, args)
    self.printgroup = True
    if args.filename is not None:
      self.imagefiles = args.filename
      self.printgroup = False

  def showInfo(self, args):
    self.parseArgs(args)
    output = ""
    if self.printgroup:
      if not self.details:
        for g in self.groups:
          del g["files"]
      groupoffsetwidth = len(str(len(self.groups)))
      for group in self.groups:
        if group["numfiles"] == 0:
          continue
        if output != "":
          output += "\n\n"
        output += "group index: {:0{}}\tgroup type: {}\tnumber of files: {}\tname: '{}'\n".format(
          group["groupindex"], groupoffsetwidth, group["grouptype"], group["numfiles"], group["name"])
        if "path" in group:
          output += "path: '{}'".format(group["path"])
        if self.details:
          output += "\noffset:\tfiles:\n"
          width = len(str(len(group["files"])))
          first = True
          for x, y in group["files"]:
            if first:
              first = False
            else:
              output += "\n"
            output += "  {:0{}}\t{}".format(x, width, y)

    else:
      if self.details:
        self.logger.warning("Ignoring request for details when searching for image info")
      notfoundimages = self.imagefiles
      for group in self.groups:
        if group["numfiles"] == 0:
          continue
        width = len(str(len(group["files"])))
        for f in group["files"]:
          if f[1] in self.imagefiles:
            if output != "":
              output += "\n"
            output += "offset {:0{}} for image '{}' in group index: {} name: '{}'".format(f[0], width, f[1], group["groupindex"], group["name"])
            if f[1] in notfoundimages:
              notfoundimages.remove(f[1])
      if notfoundimages:
        self.logger.warning("images {} could not be found in request groups:\n{}\n"
                            .format(notfoundimages, [x.get("name") for x in self.groups]))
    if output != "":
      print(output)
