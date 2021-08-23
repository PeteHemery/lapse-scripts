#!/usr/bin/python3

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
Call ffmpeg to generate video from instruction list
Optionally add music
Optionally preview with ffplay (only when 'safe' relative paths used.)

See ffmpeg documentation:
  https://ffmpeg.org/ffmpeg-devices.html
  https://x265.readthedocs.io/en/stable/cli.html
  https://trac.ffmpeg.org/wiki/Concatenate
  https://trac.ffmpeg.org/wiki/Scaling
  https://ffmpeg.org/ffmpeg-formats.html
  https://ffmpeg.org/ffmpeg-filters.html#concat
  https://ffmpeg.org/ffmpeg-filters.html#pad-1
  https://superuser.com/questions/991371/ffmpeg-scale-and-pad#991412
  https://superuser.com/questions/547296/resizing-videos-with-ffmpeg-avconv-to-fit-into-static-sized-player/1136305#1136305
"""
import argparse
import os
import subprocess
import sys

from math import ceil

def call_ffmpeg(list_file, output_name, safe=True, play=False, overwrite=False,
                audio_file=None, framerate=None, codec=None, width=None, height=None):
  if play:
    ffmpeg_cmd = "ffplay -autoexit "
  else:
    ffmpeg_cmd = "ffmpeg "
  ffmpeg_cmd += "-hide_banner "
  if play or safe:
    ffmpeg_cmd += "-f lavfi -i movie=filename={}:".format(list_file)
    ffmpeg_cmd += "f=concat,"
  else:
    if audio_file is not None:
      ffmpeg_cmd += "-i {} ".format(audio_file)
    ffmpeg_cmd += "-safe 0 "
    ffmpeg_cmd += "-f concat -i {} ".format(list_file)
    ffmpeg_cmd += "-vf "
  ffmpeg_cmd += "fps={},".format(framerate)
  ffmpeg_cmd += "scale={}:{}:force_original_aspect_ratio=decrease:eval=frame,".format(width, height)
  ffmpeg_cmd += "pad=w={}:h={}:x=-1:y=-1:color=black:eval=frame".format(width, height)
  if play or safe:
    ffmpeg_cmd += "[out0]"
    if audio_file is not None:
      ffmpeg_cmd += ";amovie={}[out1]".format(audio_file)
  if not play:
    ffmpeg_cmd += " -r {0} -framerate {0} ".format(framerate)
    ffmpeg_cmd += "-pixel_format yuv420p "
    ffmpeg_cmd += "-c:v {} ".format(codec)
    if codec == "libx265":
      ffmpeg_cmd += "-x265-params b-pyramid=0:scenecut=0:crf=24 "
    if overwrite is not None and overwrite:
      ffmpeg_cmd += "-y "
    ffmpeg_cmd += "{}".format(output_name)
  print("Running command: {}".format(ffmpeg_cmd))

  try:
    process = subprocess.Popen(ffmpeg_cmd.split(), stdout=subprocess.PIPE)
    for c in iter(lambda: process.stdout.read(1), b''):
      sys.stdout.write(str(c))
  except KeyboardInterrupt:
    process.terminate()
    sys.exit()

def main():

  parser = argparse.ArgumentParser(description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("-l", "--listfile", default="list.txt", required=True,
                      help="Path to input list file (default: %(default)s)")
  parser.add_argument("-o", "--outname", default="test.mp4", required=True,
                      help="Path to output file (default: %(default)s)")
  parser.add_argument("-a", "--audiofile", help="Path to audio file (optional)")
  parser.add_argument("-r", "--framerate", default="25", type=int,
                      help="Output file frame rate (default: %(default)s)")
  parser.add_argument("-c", "--codec", default="libx265",
                      help="Output file codec (default: %(default)s)")
  parser.add_argument("-w", "--width", default="1280", type=int,
                      help="Output scaled width in pixels (default: %(default)s)")
  parser.add_argument("-x", "--aspectratio", default="1.777", type=float,
                      help="Output aspect ratio (width/height) (default: %(default)s)")
  parser.add_argument("-s", "--safe", dest="safe", action="store_false",
                      help="Ignore problems with relative paths and use -safe 0 flag (for encoding only)"
                      "(Will cause problems with ffmpeg run script!) (default: %(default)s)")
  parser.add_argument("-p", "--play", dest="play", action="store_true",
                      help="Preview output with ffplay instead of encoding (default: %(default)s)")
  parser.add_argument("-y", "--overwrite", dest="overwrite", action="store_true",
                      help="Over write output file if it already exists (default: %(default)s)")
  parser.set_defaults(safe=True, play=False, overwrite=False)
  args = parser.parse_args()

  outname = args.outname
  audio_file = None
  if not os.path.exists(args.listfile):
    raise RuntimeError("Could not find list file '{}'".format(args.listfile))
  if args.audiofile is not None:
    audio_file = args.audiofile
    if not os.path.exists(audio_file):
      raise RuntimeError("Could not find audio file '{}'".format(audio_file))
  if os.path.exists(outname):
    if not args.overwrite:
      raise RuntimeError("Output file already exists '{}'\n"
                         "Add '-y' to enable automatic over writing".format(outname))
  height = ceil(round(args.width / args.aspectratio) / 2) * 2 # Round height to power of 2
  width = ceil(round(height * args.aspectratio) / 2) * 2 # Recalculate the width
  if width != args.width:
    raise RuntimeError("Width recalculation failed: {} != {}".format(width, args.width))
  call_ffmpeg(list_file=args.listfile, output_name=outname, safe=args.safe, play=args.play, overwrite=args.overwrite,
              audio_file=audio_file, framerate=args.framerate, codec=args.codec, width=width, height=height)

if __name__ == "__main__":
  main()
