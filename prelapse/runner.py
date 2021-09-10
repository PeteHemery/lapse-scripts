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


def callShellCmd(cmd, exitOnError=True):
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
  callShellCmd(parser.runParser(args, run=run, out=out))
  if out:
    print("Written '{}'".format(parser.outpath))
