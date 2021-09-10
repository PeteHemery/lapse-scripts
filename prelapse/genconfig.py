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
"""
Generate json config file for use with Audacity to ffmpeg converter script.

Select path to directory containing image files.
Resulting config file will consist of image files grouped by directory.
"""
import argparse
import json
import mimetypes
import os
import subprocess

from .common import setupLogger


class LapseGenerator():
  """ Group config generator class """

  def __init__(self):
    pass

  @staticmethod
  def addParserArgs(parser):
    parser.add_argument("-i", "--inpath", default=".",
                        help="relative path to directory containing images (default: %(default)s (current directory))")
    parser.add_argument("-o", "--outpath", default="config.json",
                        help="relative path to output file (default: %(default)s (under INPATH))\n"
                        "NOTE: Must be on the same file system for relative paths to work in ffmpeg script.")
    parser.add_argument("-d", "--depth", default="1", type=int,
                        help="depth of subdirectory search for image files\n"
                        "(default: %(default)s)")
    parser.add_argument("-t", "--time", dest="bytime", action="store_true",
                        help="sort found images by time order, instead of name\n"
                        "(default: %(default)s)")
    parser.add_argument("-a", "--append", dest="append", action="store_true",
                        help="append existing output file if it already exists\n"
                        "(default: %(default)s)")
    parser.set_defaults(bytime=False, append=False)
    return parser

  def parseArgs(self, args):
    self.verbose = args.verbose
    self.dryrun = args.dryrun
    self.overwrite = args.overwrite
    self.logger = setupLogger("JSON Generator", self.verbose)
    self.files = dict()
    # Get logical (not physical) path of present working directory,
    # i.e. symlink path not realpath
    if os.name == "posix":
      pwd = "".join(chr(x) for x in subprocess.Popen(
        ["pwd", "-L"], stdout=subprocess.PIPE, shell=True).communicate()[0].strip())
    elif os.name == "nt":
      pwd = "".join(chr(x) for x in subprocess.Popen(
        ["echo", "%cd%"], stdout=subprocess.PIPE, shell=True).communicate()[0].strip())
    else:
      raise RuntimeError("Unhandled system, not posix or nt: {}".format(os.name))
    # Sanity checks
    inpath = args.inpath if os.path.isabs(args.inpath) else \
      os.path.abspath(os.path.join(pwd, args.inpath))
    if not os.path.exists(inpath):
      raise RuntimeError("Input path appears to be invalid: '{}'".format(inpath))
    self.inpath = inpath
    outpath = os.path.normpath(os.path.join(inpath, args.outpath))
    if os.path.exists(outpath):
      if not self.dryrun and not self.overwrite:
        raise RuntimeError("Output file already exists '{}'\n"
                          "Add '-y' to enable automatic over writing".format(outpath))
      if args.append:
        with open(outpath, "r") as f:
          self.files = json.load(f)
    self.outpath = outpath
    self.root = os.path.dirname(outpath)
    depth = args.depth
    if depth < 0:
      raise RuntimeError("Subdirectory search depth must be a number 0 or higher")
    self.depth = depth
    self.bytime = args.bytime
    self.append = args.append

  def populateFiles(self, path, currentDepth=0):
    """
    Populate a dict with recursive search for image files from the root down to a maximum depth.
    """
    thisdir = os.path.relpath(path, start=self.root)
    if os.path.realpath(thisdir) == os.path.realpath(self.root):
      thisdir = os.path.basename(self.root) # Use the basename of the root dir, instead of '.'
      if thisdir in self.files and self.files[thisdir]["path"] == self.root:
        # Already processed root directory
        return
    else:
      if thisdir in self.files:
        if self.files[thisdir]["path"] == path:
          # Already processed this directory
          return
        raise RuntimeError("Cannot distinguish labels for directories with the same name:\n"
          "  {}\n  {}\n".format(files[thisdir]["path"], path))
    dirlist = sorted(os.listdir(path), key=lambda name:
                      os.path.getmtime(os.path.join(path, name))
                      ) if self.bytime else sorted(os.listdir(path))
    for item in dirlist:
      itemPath = os.path.join(path, item)
      if os.path.isdir(itemPath):
        if currentDepth < self.depth:
          self.populateFiles(itemPath, currentDepth + 1)
      if os.path.isfile(itemPath):
        typeGuess = mimetypes.guess_type(item)
        if typeGuess[0] and typeGuess[0].startswith("image"):
          # Found an image file, if it's the first discovery of files in this
          # directory then create a new dict entry, else just append to it
          if thisdir not in self.files:
            self.files[thisdir] = {
              "path": path,
              "files": [item]}
          else:
            self.files[thisdir]["files"].append(item)

  def runGenerator(self, args):
    """
    Populate the files dict with group info
    """
    self.parseArgs(args)
    self.populateFiles(self.inpath)

    if self.files:
      finalOutput = json.dumps(self.files, indent=2)
      if self.dryrun:
        print("{}\nDry run".format(finalOutput))
      else:
        with open(self.outpath, "w") as f:
          f.write(finalOutput)
        print("Written {}".format(self.outpath))
    else:
      print("No image files found in depth of {}. No file written".format(self.depth))
