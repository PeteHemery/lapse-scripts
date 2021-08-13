#!/usr/bin/python3
"""
Generate json config file for use with Audacity to ffmpeg converter script.

Select path to directory containing image files.
Resulting config file will consist of image files grouped by directory.


This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""
import argparse
import json
import mimetypes
import os
import subprocess


def populate_files(files, root, path, bytime, max_depth, current_depth=0):
  """
  Populate a dict by recursive search for image files from the root down to a maximum depth.
  """
  thisdir = os.path.relpath(path, start=root)
  if os.path.realpath(thisdir) == os.path.realpath(root):
    thisdir = os.path.basename(root) # Use the basename of the root dir, instead of '.'
    if thisdir in files and files[thisdir]["path"] == root:
      # Already processed root directory
      return
  else:
    if thisdir in files:
      if files[thisdir]["path"] == path:
        # Already processed this directory
        return
      raise RuntimeError("Cannot distinguish labels for directories with the same name:\n"
        "  {}\n  {}\n".format(files[thisdir]["path"], path))
  dirlist = sorted(os.listdir(path), key=lambda name:
                     os.path.getmtime(os.path.join(path, name))
                     ) if bytime else sorted(os.listdir(path))
  for item in dirlist:
    if os.path.isdir(os.path.join(path, item)):
      if current_depth < max_depth:
        populate_files(files, root, os.path.join(path, item), bytime, max_depth, current_depth + 1)
    if os.path.isfile(os.path.join(path, item)):
      type_guess = mimetypes.guess_type(item)
      if type_guess[0] and type_guess[0].startswith("image"):
        # Found an image file, if it's the first discovery of files in this
        # directory then create a new dict entry, else just append to it
        if thisdir not in files:
          files[thisdir] = {"count": 1, "path": path, "files": [item]}
        else:
          files[thisdir]["files"].append(item)
          files[thisdir]["count"] += 1


def main():
  parser = argparse.ArgumentParser(description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("-i", "--inpath", default=".",
                      help="Relative path to directory containing images (default: %(default)s (current directory))")
  parser.add_argument("-o", "--outpath", default="config.json",
                      help="Relative path to output file (default: %(default)s (under INPATH))\n"
                      "NOTE: Must be on the same file system for relative paths to work in ffmpeg script.")
  parser.add_argument("-d", "--depth", default="1", type=int,
                      help="Max depth of subdirectory search for files (default: %(default)s)")
  parser.add_argument("-t", "--time", dest="bytime", action="store_true",
                      help="Sort found images by time order, instead of name (default: %(default)s)")
  parser.add_argument("-n", "--dryrun", dest="dryrun", action="store_true",
                      help="Disable writing output file, only print (default: %(default)s)")
  parser.add_argument("-a", "--append", dest="append", action="store_true",
                      help="Append existing output file if it already exists (default: %(default)s)")
  parser.add_argument("-y", "--overwrite", dest="overwrite", action="store_true",
                      help="Over write output file if it already exists (default: %(default)s)")
  parser.set_defaults(bytime=False, dryrun=False, append=False, overwrite=False)
  args = parser.parse_args()

  files = dict()
  # Get logical (not physical) path of present working directory,
  # i.e. symlink path not realpath
  if os.name == "posix":
    pwd = "".join(chr(x) for x in subprocess.Popen(
      ["pwd","-L"], stdout=subprocess.PIPE, shell=True).communicate()[0].strip())
  elif os.name == "nt":
    pwd = "".join(chr(x) for x in subprocess.Popen(
      ["echo","%cd%"], stdout=subprocess.PIPE, shell=True).communicate()[0].strip())
  else:
    raise RuntimeError("Unhandled system, not posix or nt: {}".format(os.name))
  # Sanity checks
  inpath = args.inpath if os.path.isabs(args.inpath) else \
    os.path.abspath(os.path.join(pwd, args.inpath))
  if not os.path.exists(inpath):
    raise RuntimeError("Input path appears to be invalid: '{}'".format(inpath))
  outpath = os.path.normpath(os.path.join(inpath, args.outpath))
  if os.path.exists(outpath):
    if not args.dryrun and not args.overwrite:
      raise RuntimeError("Output file already exists '{}'\n"
                         "Add '-y' to enable automatic over writing".format(outpath))
    if args.append:
      with open(outpath, "r") as f:
        files = json.load(f)
  depth = args.depth
  if depth < 0:
    raise RuntimeError("Subdirectory depth must be a number 0 or higher")

  populate_files(files, os.path.dirname(outpath), inpath, args.bytime, depth)

  final_output = json.dumps(files, indent=2)
  if args.dryrun:
    print("{}\nDry run".format(final_output))
  else:
    with open(outpath, "w") as f:
      f.write(final_output)
    print("Written {}".format(outpath))


if __name__ == "__main__":
  main()
