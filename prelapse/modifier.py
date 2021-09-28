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
import copy
import mimetypes
import os
import json

from pprint import pformat

from .common import *
from .runner import callShellCmd


class LapseModifier():
  """ Group and image modifier class """
  def __init__(self):
    pass

  @staticmethod
  def addParserArgs(parser, commonArgs=None):
    modsubparser = parser.add_subparsers(
      dest="modcmd", help="mod sub-commands help")
    commonModArgs = argparse.ArgumentParser(
      formatter_class=argparse.RawTextHelpFormatter,
      add_help=False,
      parents=[commonArgs])
    commonModArgs.add_argument(
      "-c", "--config", default="config.json",
      help="json config file describing the picture groups\n"
      "(default: %(default)s)")

    commonImageArgs = argparse.ArgumentParser(
      formatter_class=argparse.RawTextHelpFormatter,
      add_help=False,
      parents=[commonModArgs])
    mutexgroup = commonImageArgs.add_mutually_exclusive_group(required=True)
    mutexgroup.add_argument(
      "-a", "--allgroups", action="store_true",
      help="access all groups\n(default: %(default)s)")
    mutexgroup.add_argument(
      "-g", "--groups", nargs="?", action="append",
      #"-g", "--groups", nargs="*",
      help="groups names within config from which to build new meta group.\n"
      "(NOTE: Can use index or slice, e.g. -g groupA[10] -g groupB[55:100])")
    commonImageArgs.set_defaults(allgroups=False)

    commonImageGenArgs = argparse.ArgumentParser(
      formatter_class=argparse.RawTextHelpFormatter,
      add_help=False)
    imagegenmutexgroup = commonImageGenArgs.add_mutually_exclusive_group(required=True)
    imagegenmutexgroup.add_argument(
      "-o", "--outmod", action="store_true",
      help="save modified files to separate directory within group path.\n"
      "Specifying a group, modified images will be saved in a subdirectory structure\n"
      " that represents the parameters passed with the sub-command.\n"
      "'mod' in the group path to , inside a subdirectory based on command used.\n"
      "e.g. running:\n"
      "  prelapse.py mod image resize -g _GROUP-NAME_ -p 25 -o\n"
      "would result in image files being stored in:\n"
      "  _GROUP-PATH_{0}mod-resize-p25{0}_RESIZED-FILES_.jpg\n"
      "The new files will be appended and written to the json group"
      " config file".format(os.sep))
    imagegenmutexgroup.add_argument(
      "-i", "--inplace", action="store_true",
      help="modify and overwrite files in place\n"
      "(default: %(default)s)")
    commonImageGenArgs.add_argument(
      "--gravity", type=str, default="Center",
      help="horizontal and vertical text placement.\n"
      "run 'mogrify -list gravity' to see options\n"
      "(default: %(default)s)")
    commonImageGenArgs.set_defaults(inplace=False, outmod=False)

    # Image modifier
    modimgparser = modsubparser.add_parser(
      "image", help="modify image options")
    modimgsubparser = modimgparser.add_subparsers(
      dest="modimg", help="modify image sub-commands help")

    modimgresize = modimgsubparser.add_parser(
      "resize", help="resize image options",
      formatter_class=argparse.RawTextHelpFormatter,
      parents=[commonImageArgs, commonImageGenArgs])
    resizemutexgroup = modimgresize.add_mutually_exclusive_group(required=True)
    resizemutexgroup.add_argument(
      "-m", "--max", type=int,
      help="maximum dimensions (height or width) in pixels\n"
      "(default: %(default)s)")
    resizemutexgroup.add_argument(
      "-p", "--percent", type=int,
      help="scale height and width by specified percentage\n"
      "(default: %(default)s)")
    resizemutexgroup.add_argument(
      "-G", "--geometry", type=str,
      help="image geometry specifying width and height and other quantites\n"
      "e.g. 800x600\n"
      "see full instructions:\n"
      "  https://imagemagick.org/script/command-line-processing.php#geometry")

    modimgscale = modimgsubparser.add_parser(
      "scale", help="scale image options",
      formatter_class=argparse.RawTextHelpFormatter,
      parents=[commonImageArgs, commonImageGenArgs])
    scalemutexgroup = modimgscale.add_mutually_exclusive_group(required=True)
    scalemutexgroup.add_argument(
      "-m", "--max", type=int,
      help="maximum dimensions (height or width) in pixels for resized image")
    scalemutexgroup.add_argument(
      "-p", "--percent", type=int,
      help="scale height and width by specified percentage")
    scalemutexgroup.add_argument(
      "-G", "--geometry", type=str,
      help="image geometry specifying width and height and other quantites\n"
      "e.g. 800x600\n"
      "see full instructions:\n"
      "  https://imagemagick.org/script/command-line-processing.php#geometry")

    modimgcrop = modimgsubparser.add_parser(
      "crop", help="crop image options",
      formatter_class=argparse.RawTextHelpFormatter,
      parents=[commonImageArgs, commonImageGenArgs])
    modimgcrop.add_argument(
      "-G", "--geometry", type=str, required=True,
      help="image geometry specifying width and height and other quantites\n"
      "e.g. 800x600\n"
      "see full instructions:\n"
      "  https://imagemagick.org/script/command-line-processing.php#geometry")

    modimgcolor = modimgsubparser.add_parser(
      "color", help="color image options",
      formatter_class=argparse.RawTextHelpFormatter,
      parents=[commonImageArgs, commonImageGenArgs])
    modimgcolor.add_argument(
      "--normalize", action="store_true",
      help="increase the contrast in an image by stretching the range of intensity values\n"
      "(default: %(default)s)")
    modimgcolor.add_argument(
      "--autolevel", action="store_true",
      help="automagically adjust color levels of image\n"
      "(default: %(default)s)")
    modimgcolor.add_argument(
      "--autogamma", action="store_true",
      help="automagically adjust gamma level of image\n"
      "(default: %(default)s)")
    modimgcolor.set_defaults(normalize=False, autolevel=False, autogamma=False)

    modimgrotate = modimgsubparser.add_parser(
      "rotate", help="rotate image options",
      formatter_class=argparse.RawTextHelpFormatter,
      parents=[commonImageArgs, commonImageGenArgs])
    rotatemutexgroup = modimgrotate.add_mutually_exclusive_group(required=True)
    rotatemutexgroup.add_argument(
      "-R", "--autoorient", action="store_true",
      help="auto rotate image using exif metadata suitable for viewing\n"
      "(default: %(default)s)")
    rotatemutexgroup.add_argument(
      "-C", "--clockwise", action="store_true",
      help="rotate image 90 degrees clockwise\n"
      "(default: %(default)s)")
    rotatemutexgroup.add_argument(
      "-A", "--anticlockwise", action="store_true",
      help="rotate image 90 degrees anticlockwise\n"
      "(default: %(default)s)")
    rotatemutexgroup.add_argument(
      "-D", "--degrees", type=str,
      help="rotate image arbitrary number of degrees\n"
      "Use > to rotate the image only if its width exceeds the height.\n"
      "< rotates the image only if its width is less than the height.\n"
      "For example, if you specify -rotate '-90>' and the image size is 480x640,\n"
      " the image is not rotated. However, if the image is 640x480,"
      " it is rotated by -90 degrees.\n"
      "If you use > or <, enclose it in quotation marks to prevent it from"
      " being misinterpreted as a file redirection.\n"
      "\nEmpty triangles in the corners, left over from rotating the image,"
      " are filled with the background color.")
    modimgrotate.set_defaults(autoorient=False, clockwise=False, anticlockwise=False)

    modimgstab = modimgsubparser.add_parser(
      "stab", help="stabilize image options",
      formatter_class=argparse.RawTextHelpFormatter)

    commonImgStabArgs = argparse.ArgumentParser(
      formatter_class=argparse.RawTextHelpFormatter,
      add_help=False)
    commonImgStabArgs.add_argument(
      "--fps", "--framerate", type=float, default=25,
      help="preview and output video frame rate per second\n"
      "(default: %(default)s)")
    commonImgStabArgs.add_argument(
      "--ffloglevel", type=str, default="info",
      choices=["quiet", "panic", "fatal", "error", "warning",
              "info", "verbose", "debug", "trace"],
      help="log level for ffplay/ffmpeg\n"
      "(default: %(default)s)")

    modstabphase1 = argparse.ArgumentParser(
      formatter_class=argparse.RawTextHelpFormatter,
      add_help=False)
    modstabphase1.add_argument(
      "--result", type=str,
      help="Set the path to the file used to write the transforms information.\n"
      "Default value is transforms.trf")
    modstabphase1.add_argument(
      "--shakiness", default=5, type=int,
      help="Set how shaky the video is and how quick the camera is.\n"
      "It accepts an integer in the range 1-10, a value of 1 means little shakiness,\n"
      "a value of 10 means strong shakiness.\n"
      "(default: %(default)s)")
    modstabphase1.add_argument(
      "--accuracy", default=15, type=int,
      help="Set the accuracy of the detection process.\n"
      "It must be a value in the range 1-15. A value of 1 means low accuracy,\n"
      "a value of 15 means high accuracy. Default value is 15.\n"
      "(default: %(default)s)")
    modstabphase1.add_argument(
      "--stepsize", default=6, type=int,
      help="Set stepsize of the search process.\n"
      "The region around minimum is scanned with 1 pixel resolution.\n"
      "(default: %(default)s)")
    modstabphase1.add_argument(
      "--mincontrast", default=0.3, type=float,
      help="Set minimum contrast. Below this value a local measurement field is discarded.\n"
      "Must be a floating point value in the range 0-1.\n"
      "(default: %(default)s)")
    modstabphase1.add_argument(
      "--tripod", default=0, type=int,
      help="Set reference frame number for tripod mode.\n"
      "If enabled, the motion of the frames is compared to a reference frame in\n"
      "the filtered stream, identified by the specified number.\n"
      "The idea is to compensate all movements in a more-or-less static scene\n"
      "and keep the camera view absolutely still.\n"
      "If set to 0, it is disabled. The frames are counted starting from 1.\n"
      "(default: %(default)s)")
    modstabphase1.add_argument(
      "--show", default=2, type=int,
      help="Show fields and transforms in the resulting frames.\n"
      "It accepts an integer in the range 0-2.\n"
      "Value 0 disables any visualization.\n(default: %(default)s)")
    modstabphase1.add_argument(
      "-p", "--play", action="store_true", help="preview stabilization detection\n"
      "(default: %(default)s)")
    modstabphase1.set_defaults(play=False)

    modstabphase2 = argparse.ArgumentParser(
      formatter_class=argparse.RawTextHelpFormatter,
      add_help=False)
    modstabphase2.add_argument(
      "--input", type=str,
      help="Set path to the file used to read the transforms.\n"
      "Default value is transforms.trf")
    modstabphase2.add_argument(
      "--smoothing", default=0, type=int,
      help="Set the number of frames (value*2 + 1) "
      "used for lowpass filtering the camera movements.\n"
      "Default value is 10.\n"
      "For example a number of 10 means that 21 frames are used "
      "(10 in the past and 10 in the future) to\n"
      "smoothen the motion in the video. A larger value leads to a smoother video,\n"
      "but limits the acceleration of the camera (pan/tilt movements).\n"
      "0 is a special case where a static camera is simulated.\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--optalgo", default="gauss", type=str,
      help="Set the camera path optimization algorithm.\n"
      "Accepted values are:\n"
      "'gauss' gaussian kernel low-pass filter on camera motion (default)\n"
      "'avg'   averaging on transformations\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--maxshift", default=1, type=int,
      help="Set maximal number of pixels to translate frames.\n"
      "Default value is -1, meaning no limit.\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--maxangle", default=-1, type=float,
      help="Set maximal angle in radians (degree*PI/180) to rotate frames.\n"
      "Default value is -1, meaning no limit.\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--crop", default="black", type=str,
      help="Specify how to deal with borders that may be visible due to movement "
      "compensation.\nAvailable values are:\n"
      "'keep'  keep image information from previous frame (default)\n"
      "'black' fill the border black\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--invert", default=0, type=int,
      help="Invert transforms if set to 1. Default value is 0.\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--relative", default=0, type=int,
      help="Consider transforms as relative to previous frame if set to 1,\n"
      "absolute if set to 0. Default value is 0.\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--zoom", default=0, type=int,
      help="Set percentage to zoom. A positive value will result in a zoom-in effect,\n"
      "a negative value in a zoom-out effect.\n"
      "Default value is 0 (no zoom).\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--optzoom", default=1, type=int,
      help="Set optimal zooming to avoid borders.\n"
      "Accepted values are:\n"
      "'0' disabled\n"
      "'1' optimal static zoom value is determined"
      " (only very strong movements will lead to visible borders) (default)\n"
      "'2' optimal adaptive zoom value is determined"
      " (no borders will be visible), see zoomspeed\n"
      "Note that the value given at zoom is added to the one calculated here.\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--zoomspeed", default=0.1, type=float,
      help="Set percent to zoom maximally each frame"
      " (enabled when optzoom is set to 2).\n"
      "Range is from 0 to 5, default value is 0.25.\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--interpol", default="bilinear", type=str,
      help="Specify type of interpolation.\n"
      "Available values are:\n"
      "'no'       no interpolation\n"
      "'linear'   linear only horizontal\n"
      "'bilinear' linear in both directions (default)\n"
      "'bicubic'  cubic in both directions (slow)\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--virtualtripod", default=0, type=int,
      help="Enable virtual tripod mode if set to 1, which is equivalent to "
      "relative=0:smoothing=0.\nDefault value is 0.\n"
      "Use also tripod option of vidstabdetect.\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--debug", default=0, type=int,
      help="Increase log verbosity if set to 1.\n"
      "Also the detected global motions are written to the"
      " temporary file global_motions.trf.\n"
      "Default value is 0.\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--unsharp", action="store_true",
      help="Sharpen or blur the input video.\n"
      "All parameters are optional and default to the "
      "equivalent of the string '5:5:0.0:5:5:0.0'\n"
      "(NOTE: This option does nothing and is just for diplaying this information)")
    modstabphase2.add_argument(
      "--lx", default=5, type=int,
      help="Set the luma matrix horizontal size.\n"
      "It must be an odd integer between 3 and 23. The default value is 5.\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--ly", default=5, type=int,
      help="Set the luma matrix vertical size.\n"
      "It must be an odd integer between 3 and 23. The default value is 5.\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--la", default=0.0, type=float,
      help="Set the luma effect strength.\n"
      "It must be a floating point number, reasonable values lay between "
      "-1.5 and 1.5.\n"
      "Negative values will blur the input video, "
      "while positive values will sharpen it,\n"
      "a value of zero will disable the effect. Default value is 1.0.\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--cx", default=5, type=int,
      help="Set the chroma matrix horizontal size.\n"
      "It must be an odd integer between 3 and 23. The default value is 5.\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--cy", default=5, type=int,
      help="Set the chroma matrix vertical size.\n"
      "It must be an odd integer between 3 and 23. The default value is 5.\n"
      "(default: %(default)s)")
    modstabphase2.add_argument(
      "--ca", default=0.0, type=float,
      help="Set the chroma effect strength.\n"
      "It must be a floating point number, reasonable values lay between "
      "-1.5 and 1.5.\n"
      "Negative values will blur the input video, "
      "while positive values will sharpen it,\n"
      "a value of zero will disable the effect. Default value is 1.0.\n"
      "(default: %(default)s)")

    stabmutexgroup = modstabphase2.add_mutually_exclusive_group(required=True)
    stabmutexgroup.add_argument(
      "-p", "--play", action="store_true",
      help="ffplay stabilized images")
    stabmutexgroup.add_argument(
      "-w", "--writejpgs", action="store_true",
      help="output stabilized images")
    modstabphase2.set_defaults(unsharp=True, play=False, writejpgs=False)

    modstabsubparser = modimgstab.add_subparsers(
      dest="modstabphase",
      help="mod stab sub-commands help")
    modstabphase1parser = modstabsubparser.add_parser(
      "1", help="perform first phase of stabilization (vidstabdetect)",
      parents=[commonImageArgs, commonImgStabArgs, modstabphase1],
      formatter_class=argparse.RawTextHelpFormatter)
    modstabphase2parser = modstabsubparser.add_parser(
      "2", help="perform second phase of stabilization (vidstabtransform)",
      parents=[commonImageArgs, commonImgStabArgs, modstabphase2],
      formatter_class=argparse.RawTextHelpFormatter)
    modstabphase12parser = modstabsubparser.add_parser(
      "12", help="perform both phases of stabilization (vidstabdetect then vidstabtransform)",
      parents=[commonImageArgs,
               commonImgStabArgs,
               copy.deepcopy(modstabphase1), # Avoid mangling "--play" help for the original parser
               modstabphase2],
      formatter_class=argparse.RawTextHelpFormatter,
      conflict_handler="resolve")

    # Group modifier
    modgrpparser = modsubparser.add_parser("group", help="modify group option")
    modgrpsubparser = modgrpparser.add_subparsers(
      dest="modgrp", help="modify group sub-commands help")

    modgrpresize = modgrpsubparser.add_parser(
      "rename", help="rename group",
      formatter_class=argparse.RawTextHelpFormatter,
      parents=[commonModArgs])
    modgrpresize.add_argument("fromgroup", help="old group name")
    modgrpresize.add_argument("togroup", help="new group name")

    modgrpdel = modgrpsubparser.add_parser(
      "del", help="delete group",
      formatter_class=argparse.RawTextHelpFormatter,
      parents=[commonModArgs])
    modgrpdel.add_argument(
      "groups", nargs="*",
      help="groups names within config to delete.\n"
      "(NOTE: Can NOT use index or slice, e.g. groupA groupB)")

    modgrpnew = modgrpsubparser.add_parser(
      "new", help="new meta group",
      formatter_class=argparse.RawTextHelpFormatter,
      parents=[commonModArgs])
    modgrpnew.add_argument("groupname", help="new group name")
    modgrpnew.add_argument(
      "-g", "--groups", nargs="?", action="append",
      help="groups names within config from which to build new meta group.\n"
      "(NOTE: Can use index or slice, e.g. -g groupA[10] -g groupB[55:100])")

    modgrpfixunsafe = modgrpsubparser.add_parser(
      "fixunsafe", help="fix unsafe filenames in group",
      formatter_class=argparse.RawTextHelpFormatter,
      parents=[commonModArgs])

    return parser

  def runModifier(self, args):
    self.verbose = args.verbose
    self.dryrun = args.dryrun
    self.overwrite = args.overwrite
    self.logger = setupLogger("Modifier", self.verbose)
    if not os.path.exists(args.config):
      raise RuntimeError("Could not find config file '{}'".format(args.config))
    self.configfile = args.config
    with open(args.config, "r") as f:
      self.config = json.load(f)
    if args.modcmd is None:
      raise RuntimeError("Must select a sub-command. See usage with -h")
    if args.modcmd == "image":
      if args.modimg is None:
        raise RuntimeError("Must select a sub-command. See usage with -h")
      if args.modimg == "resize":
        self.runMogrifyCmd(args)
        self.logger.info("parsed resize")
      elif args.modimg == "scale":
        self.runMogrifyCmd(args)
        self.logger.info("parsed scale")
      elif args.modimg == "crop":
        self.runMogrifyCmd(args)
        self.logger.info("parsed crop")
      elif args.modimg == "color":
        self.runMogrifyCmd(args)
        self.logger.info("parsed color")
      elif args.modimg == "rotate":
        self.runMogrifyCmd(args)
        self.logger.info("parsed rotate")
      elif args.modimg == "stab":
        if args.modstabphase is None:
          raise RuntimeError("Must select a sub-command. See usage with -h")
        self.runImageStab(args)
        self.logger.info("parsed stab")
      self.logger.info(args)

    elif args.modcmd == "group":
      if args.modgrp is None:
        raise RuntimeError("Must select a sub-command. See usage with -h")
      if args.modgrp == "rename":
        fromGroup = args.fromgroup
        toGroup = args.togroup
        if fromGroup not in self.config:
          raise RuntimeError("'From' group name not in config: '{}'".format(fromGroup))
        if toGroup in self.config:
          raise RuntimeError("'To' group name already in config: '{}'".format(toGroup))
        newconfig = {}
        for group in self.config:
          if group != fromGroup:
            newconfig[group] = copy.deepcopy(self.config[group])
          else:
            newconfig[toGroup] = copy.deepcopy(self.config[group])
        self.config = newconfig
        if self.dryrun:
          self.logger.warning("Dry run: Not renaming groups in config.\n"
            "Use -v to see updated config")
          self.logger.info(pformat(self.config, compact=True, sort_dicts=False))
        else:
          with open(self.configfile, "w") as f:
            f.write(json.dumps(self.config, indent=2))
          print("Written {}".format(self.configfile))

        self.logger.info("parsed rename")
      elif args.modgrp == "del":
        if args.groups is None:
          raise RuntimeError("Must specify at least one group")
        print(args.groups)
        for group in args.groups:
          if group not in self.config:
            raise RuntimeError("Group name not in config: '{}'".format(group))
          del self.config[group]
        if self.dryrun:
          self.logger.warning("Dry run: Not deleting groups from config.\n"
            "Use -v to see updated config")
          self.logger.info(pformat(self.config, compact=True, sort_dicts=False))
        else:
          with open(self.configfile, "w") as f:
            f.write(json.dumps(self.config, indent=2))
          print("Written {}".format(self.configfile))
        self.logger.info("parsed del")
      elif args.modgrp == "new":
        if args.groupname in self.config:
          raise RuntimeError("New group name already in config: '{}'"
                             .format(args.groupname))
        if args.groups is None:
          raise RuntimeError("Must specify at least one group")
        parseGroupArgs(self, args)
        newGroup = []
        for group in self.groups:
          newGroup.append({"group": group["name"], "type": group["grouptype"]})
        self.config[args.groupname] = { "meta": True, "collection": newGroup}
        if self.dryrun:
          self.logger.warning("Dry run: Not writing new group to config.\n"
            "Use -v to see updated config")
          self.logger.info(pformat(self.config, compact=True, sort_dicts=False))
        else:
          with open(self.configfile, "w") as f:
            f.write(json.dumps(self.config, indent=2))
          print("Written {}".format(self.configfile))
        self.logger.info("parsed new")
      elif args.modgrp == "fixunsafe":
        print("parsed fixunsafe")
    else:
      raise RuntimeError("Unknown mod command")

  def runMogrifyCmd(self, args):
    parseGroupArgs(self, args)
    instruction = args.modimg
    if instruction == "color" and not any([args.normalize, args.autolevel,
                                           args.autogamma]):
      raise RuntimeError("No color action requested. See -h for usage")
    suffix = instruction if args.outmod else ""
    if any([x in instruction for x in ["resize", "scale", "crop"]]):
      if args.outmod:
        if args.geometry is not None:
          suffix += "-G{}".format(args.geometry)
        elif args.max is not None:
          suffix += "-m{}".format(args.max)
        elif args.percent is not None:
          suffix += "-p{}".format(args.percent)
        else:
          raise RuntimeError("Unknown {} option".format(instruction))
    elif instruction == "color":
      if args.outmod:
        if args.normalize:
          suffix += "-normalize"
        if args.autolevel:
          suffix += "-autolevel"
        if args.autogamma:
          suffix += "-autogamma"
    elif instruction == "rotate":
      if args.outmod:
        if args.autoorient:
          suffix += "-autoorient"
        elif args.clockwise:
          suffix += "-clockwise"
        elif args.anticlockwise:
          suffix += "-anticlockwise"
        elif args.degrees:
          suffix += "-degrees"
        else:
          raise RuntimeError("Unknown {} option".format(instruction))
    else:
      raise RuntimeError("Unknown instuction: {}".format(instruction))
    cmd = []
    for group in self.groups:
      groupName = group["name"]
      if suffix:
        groupName += "-{}".format(suffix)
      print("Processing group '{}':\n{}".format(groupName, pformat(group)))
      cmd += ["mogrify", "-verbose"]
      if args.outmod:
        modpath = os.path.join(group["path"], "mod-{}".format(suffix))
        if not self.dryrun:
          # Create the new directory tree if it doesn't exist
          os.makedirs(modpath, exist_ok=True)
        cmd += ["-path", modpath]
        group["modpath"] = modpath
      if instruction != "color":
        cmd += ["-{}".format(instruction)]
      if any([x in instruction for x in ["resize", "scale", "crop"]]):
        if args.geometry is not None:
          sizeAmount = "{}".format(args.geometry)
        elif args.max is not None:
          sizeAmount = "{0}x{0}".format(args.max)
        elif args.percent is not None:
          sizeAmount = "{}%".format(args.percent)
        else:
          raise RuntimeError("Unknown {} option".format(instruction))
        cmd += [sizeAmount]
        if instruction == "scale":
          cmd += ["-background", "black", "-extent", sizeAmount]
      elif instruction == "color":
        if args.normalize:
          cmd += ["-normalize"]
        if args.autolevel:
          cmd += ["-auto-level"]
        if args.autogamma:
          cmd += ["-auto-gamma"]
      elif instruction == "rotate":
        if args.autoorient:
          cmd += ["-auto-orient"]
        elif args.clockwise:
          cmd += ["-rotate", "90"]
        elif args.anticlockwise:
          cmd += ["-rotate", "-90"]
        elif args.degrees:
          cmd += ["-degrees", args.degrees]
        else:
          raise RuntimeError("Unknown {} option".format(instruction))
      cmd += ["-gravity", args.gravity]
      for f in group["files"]:
        cmd += [os.path.join(group["path"], f[1])]
      if self.dryrun:
        self.logger.warning("Dry run: Not running command:\n '{}'"
                            .format(" ".join(cmd)))
      else:
        callShellCmd(cmd)
        if args.outmod:
          genFiles = []
          dirlist = sorted(os.listdir(group["modpath"]))
          for item in dirlist:
            if os.path.isfile(os.path.join(group["modpath"], item)):
              typeGuess = mimetypes.guess_type(item)
              if typeGuess[0] and typeGuess[0].startswith("image"):
                genFiles.append(item)
          if groupName in self.config:
            assert self.config[groupName]["path"] == group["modpath"]
            for f in genFiles:
              if f not in self.config[groupName]["files"]:
                self.config[groupName]["files"].append(f)
            self.config[groupName]["files"] = sorted(self.config[groupName]["files"])
          else:
            self.config[groupName] = {
              "path": group["modpath"],
              "files": genFiles}
          with open(self.configfile, "w") as f:
            f.write(json.dumps(self.config, indent=2))
          print("Written {}".format(self.configfile))
      cmd = []

  def buildPhase1Cmd(self, args, group):
    listFile = os.path.join(self.config[group["name"]]["path"],
                   group["name"] + ".ffconcat")
    if not self.dryrun:
      writeListFile(listFile, [f[1] for f in group["files"]], 1.0 / args.fps)
      self.logger.info("Written list file: {}".format(listFile))
    cmd = []
    if args.play:
      cmd += ["ffplay", "-autoexit"]
    else:
      cmd += ["ffmpeg"]
    cmd += ["-loglevel", args.ffloglevel]
    cmd += ["-hide_banner"]
    cmd += ["-f", "lavfi", "-i"]
    optionsString = "movie={},".format(listFile)
    optionsString += "vidstabdetect="
    if args.result:
      optionsString += "result={}:".format(args.result)
    else:
      transformsPath = os.path.join(
        self.config[group["name"]]["path"], "stable", "transforms.trf")
      optionsString += "result={}:".format(transformsPath)
      if not self.dryrun:
        os.makedirs(os.path.dirname(transformsPath), exist_ok=True)
    optionsString += "shakiness={}:".format(args.shakiness)
    optionsString += "accuracy={}:".format(args.accuracy)
    optionsString += "stepsize={}:".format(args.stepsize)
    optionsString += "mincontrast={}:".format(args.mincontrast)
    optionsString += "tripod={}:".format(args.tripod)
    optionsString += "show={}".format(args.show)
    cmd += [optionsString]
    if not args.play:
      cmd += ["-f", "null", "-"]
    return cmd

  def buildPhase2Cmd(self, args, group):
    outpath = self.config[group["name"]]["path"]
    listFile = os.path.join(outpath, "stabilize.ffconcat")
    if not self.dryrun:
      writeListFile(listFile, [f[1] for f in group["files"]], 1.0 / args.fps)
      self.logger.info("Written list file: {}".format(listFile))
    cmd = []
    if args.play:
      cmd += ["ffplay", "-autoexit"]
    else:
      cmd += ["ffmpeg"]
    cmd += ["-loglevel", args.ffloglevel]
    cmd += ["-hide_banner"]
    cmd += ["-f", "lavfi", "-i"]
    optionsString = "movie={},".format(listFile)
    optionsString += "vidstabtransform="
    if args.input:
      transformsPath = args.input
    else:
      transformsPath = os.path.join(outpath, "stable", "transforms.trf")
    if not os.path.exists(transformsPath):
      raise RuntimeError("transforms file does not exist: {}"
                          .format(transformsPath))
    optionsString += "input={}:".format(transformsPath)
    optionsString += "smoothing={}:".format(args.smoothing)
    optionsString += "optalgo={}:".format(args.optalgo)
    optionsString += "maxshift={}:".format(args.maxshift)
    optionsString += "maxangle={}:".format(args.maxangle)
    optionsString += "crop={}:".format(args.crop)
    optionsString += "invert={}:".format(args.invert)
    optionsString += "relative={}:".format(args.relative)
    optionsString += "zoom={}:".format(args.zoom)
    optionsString += "optzoom={}:".format(args.optzoom)
    optionsString += "zoomspeed={}:".format(args.zoomspeed)
    optionsString += "interpol={}:".format(args.interpol)
    optionsString += "tripod={}:".format(args.virtualtripod)
    optionsString += "debug={},".format(args.debug)
    optionsString += "unsharp="
    optionsString += "lx={}:".format(args.lx)
    optionsString += "ly={}:".format(args.ly)
    optionsString += "la={}:".format(args.la)
    optionsString += "cx={}:".format(args.cx)
    optionsString += "cy={}:".format(args.cy)
    optionsString += "ca={}:".format(args.ca)
    cmd += [optionsString]
    if args.writejpgs:
      cmd += ["-qscale:v", "2"]
      cmd += ["{}".format(
        os.path.join(
          outpath, "stable",
          "output_%0{}d.jpg".format(len(str(len(group["files"]))))))]
    return cmd

  def runImageStab(self, args):
    parseGroupArgs(self, args)
    for group in self.groups:
      if "1" in args.modstabphase:
        cmd = self.buildPhase1Cmd(args, group)
        callShellCmd(cmd)
        print("parsed stab 1")
      if "2" in args.modstabphase:
        cmd = self.buildPhase2Cmd(args, group)
        callShellCmd(cmd)
        print("parsed stab 2")

  def runGroup(self, args):
    pass
