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

import argparse

from .genconfig import LapseGenerator
from .modifier import LapseModifier
from .parser import LapseParser
from .runner import runner, addRunnerParserArgs
from .info import LapseInfo


def setupArgParsing():
  commonArgs = argparse.ArgumentParser(
    formatter_class=argparse.RawTextHelpFormatter,
    add_help=False)
  commonArgs.add_argument(
    "-n", "--dryrun", dest="dryrun", action="store_true",
    help="disable writing output, only print\n(default: %(default)s)")
  commonArgs.add_argument(
    "-y", "--overwrite", dest="overwrite", action="store_true",
    help="over write output file if it already exists\n(default: %(default)s)")
  commonArgs.add_argument(
    "-v", "--verbose", dest="verbose", action="store_true",
    help="enable verbose prints\n(default: %(default)s)")
  commonArgs.set_defaults(dryrun=False, overwrite=False, verbose=False)

  parser = argparse.ArgumentParser(
    description="Script for creating image sequence based music videos.\n"
    "Explore the sub commands with -h for more details on options available.",
    formatter_class=argparse.RawTextHelpFormatter,
    parents=[commonArgs])
  subparsers = parser.add_subparsers(dest="cmd", help="sub-commands help")

  spgen = subparsers.add_parser(
    "gen", help="generate config command",
    description="JSON group config generator.\n"
    "TODO how to use",
    formatter_class=argparse.RawTextHelpFormatter, parents=[commonArgs])
  spgen.set_defaults(cmd = "gen")
  spgen = LapseGenerator.addParserArgs(spgen)

  spmod = subparsers.add_parser(
    "mod", help="modify images or groups",
    description="Modify images or groups.\n"
    "TODO how to use",
    formatter_class=argparse.RawTextHelpFormatter, parents=[commonArgs])
  spmod.set_defaults(cmd = "mod")
  spmod = LapseModifier.addParserArgs(spmod, commonArgs)

  sprun = subparsers.add_parser(
    "play", help="preview output with ffplay command",
    description="Preview output with ffplay command.\n"
    "TODO how to use",
    formatter_class=argparse.RawTextHelpFormatter, parents=[commonArgs])
  sprun.set_defaults(cmd = "play")
  sprun = addRunnerParserArgs(sprun, run=True)

  spout = subparsers.add_parser(
    "enc", help="create encoded mp4 output with ffmpeg command",
    description="Create encoded mp4 output with ffmpeg command.\n"
    "TODO how to use",
    formatter_class=argparse.RawTextHelpFormatter, parents=[commonArgs])
  spout.set_defaults(cmd = "enc")
  spout = addRunnerParserArgs(spout, out=True)

  spinfo = subparsers.add_parser(
    "info", help="show info about groups and files",
    description="Show info about groups and files.\n"
    "TODO how to use",
    formatter_class=argparse.RawTextHelpFormatter, parents=[commonArgs])
  spinfo.set_defaults(cmd = "info")
  spinfo = LapseInfo.addParserArgs(spinfo)

  parser.set_defaults(verbose=False)
  return parser


def handleParsedArgs(parser, args):
  cmd = args.cmd
  if cmd == "gen":
    gen = LapseGenerator()
    gen.runGenerator(args)
    return
  elif cmd == "mod":
    mod = LapseModifier()
    mod.runModifier(args)
  elif cmd == "play":
    runner(args, run=True)
  elif cmd == "enc":
    runner(args, out=True)
    pass
  elif cmd == "info":
    info = LapseInfo()
    info.showInfo(args)
    pass
  else:
    print(parser.format_help())
    return
