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

import locale
import os
import subprocess
import sys

from .common import setupLogger
from .parser import LapseParser


def addRunnerParserArgs(parser, run=False, out=False):
  if run and out:
    raise RuntimeError("Cannot combine run and out")
  parser = LapseParser.addParserArgs(parser, run=run, out=out)
  return parser


def callShellCmd(cmd, exitOnError=True, dryrun=False):
  if dryrun:
    print("Dry run, not executing command:\n{}".format(" ".join(cmd)))
    return 0
  try:
    if cmd[0] in ["ffmpeg", "ffplay"]:
      os.environ["AV_LOG_FORCE_COLOR"] = "1" # Force colored output while piping stderr
    print("Running:\n{}\n".format(" ".join(cmd)))
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE)
    output = ""
    while True:
      # Only print stderr. When stdout is read it prevents realtime printing,
      # and nothing is printed with ffmpeg or mogrify on stdout (one believes)
      char = process.stderr.read(1).decode(locale.getpreferredencoding(False))
      if char == "" and process.poll() is not None:
        if output != "":
          sys.stdout.write("\n")
        sys.stdout.flush()
        break
      if char != "":
        output += char
        if char in ["\n", "\r"]:
          # Catch pixel format change, avoid hanging.
          if "Format changed yuvj" in output:
            #First line clears formatting of the terminal from aborted command
            sys.stdout.write("""
{}\033[00m
WARNING:
Encountered unsolvable problem with pixel format.
ffconcat is expecting files that share similar properties.
Pixel format/chroma sub-sampling format should remain constant for all groups.

See this link for information about this:
  https://matthews.sites.wfu.edu/misc/jpg_vs_gif/JpgCompTest/JpgChromaSub.html

ffplay will repeat this message a lot, consume CPU as it does and cause a hang.
Bailing out early prevents this annoying behaviour.

Find the group at the time stamp above and view the metadata of the images
(using e.g. exiftool) to examine pictures and look for
  Y Cb Cr Sub Sampling
Examples may include:
  YCbCr4:4:4 (1 1)
  YCbCr4:2:0 (2 2)

Using mogrify to make the formats match pictures from the other groups:
Modify the pictures in place:
  mogrify -sampling-factor 4:2:0 *.jpg

Or to preserve the original format, create copies in a new directory:
  mkdir resampled
  mogrify -path resampled -sampling-factor 4:2:0 *.jpg
Remembering to update the group's path with "/resampled" appended.

""".format(output))
            sys.stdout.flush()
            process.terminate()
            raise RuntimeError("Encountered unsolvable problem with pixel format")
          # Avoid printing annoying warning, that can be ignored anyway
          if "deprecated pixel format used" not in output:
            sys.stdout.write(output)
            sys.stdout.flush()
          output = ""
    process.terminate()
    if process.returncode != 0:
      exitMsg = "Process:\n'{}'\nterminated with status: {}".format(
        " ".join(cmd), process.returncode)
      if exitOnError:
        raise RuntimeError(exitMsg)
        sys.exit(process.returncode)
      else:
        print(exitMsg)
  except KeyboardInterrupt:
    process.terminate()
    sys.stdout.write("\n")
    if process.returncode != 0:
      raise RuntimeError("Process:\n'{}'\nterminated with status: {}"
                          .format(" ".join(cmd), process.returncode))
    sys.exit()
  return process.returncode


def runner(args, run=False, out=False):
  parser = LapseParser()
  callShellCmd(parser.runParser(args, run=run, out=out), dryrun=args.dryrun)
  if out:
    print("Written '{}'".format(parser.outpath))
