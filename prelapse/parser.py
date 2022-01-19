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
Parser class

Translate Audacity labels and group configurations into ffconcat files.
"""

import argparse
import json
import logging
import numpy as np
import os
import subprocess
import sys

from math import ceil
from pprint import pformat

from .common import setupLogger

DEFAULT_DELIMITER = "|"


class LapseParser():
  """ Parser class """
  def __init__(self):
    pass

  @staticmethod
  def addParserArgs(parser, run=False, out=False):
    parser.add_argument("-c", "--config", default="config.json",
                        help="json config file describing the picture groups\n(default: %(default)s)")
    parser.add_argument("-L", "--labels", default="labels.txt",
                        help="path to input Audacity labels file\n(default: %(default)s)")
    parser.add_argument("-l", "--listfile", default="prelapse.ffconcat",
                        help="path to output list file used by ffmpeg concat. "
                        "Image paths will be relative to list file and should be 'safe'.\n(default: %(default)s)")
    parser.add_argument("-d", "--delimiter", default=DEFAULT_DELIMITER,
                        help="delimiter used in labels to separate instructions (default: '%(default)s')\n"
                        "NOTE: Cannot use letters or any of the following: '[]:\\/#.\'")
    parser.add_argument("-R", "--relative", dest="relative", action="store_false",
                        help="disable relative paths and use absolute paths\n(default: %(default)s)")
    parser.set_defaults(relative=True)
    if run or out:
      parser.add_argument("-a", "--audiofile", help="path to audio file (optional)")
      parser.add_argument("-f", "--framerate", default="25", type=float,
                          help="output file frame rate\n(default: %(default)s)")
      parser.add_argument("-w", "--width", default="1280", type=int,
                          help="output scaled width in pixels\n(default: %(default)s)")
      parser.add_argument("-x", "--aspectratio", default="16/9", type=str,
                          help="output aspect ratio (width/height) in form '1.777' or '16/9'\n(default: %(default)s)")
      parser.add_argument("-t", "--tempo", default="1.0", type=float,
                          help="output tempo adjustment\n(default: %(default)s)")
      parser.add_argument("-H", "--histogram", dest="histogram", action="store_true",
                          help="stack a visual representation of the audio under the video\n(default: %(default)s)")
      parser.set_defaults(audiofile=None, histogram=False)
      if out:
        parser.add_argument("-s", "--safe", dest="safe", action="store_false",
                            help="ignore problems with relative paths and use -safe 0 flag "
                            "(for encoding only)\n(default: %(default)s)")
        parser.add_argument("-C", "--codec", default="libx265",
                            help="output file codec\n(default: %(default)s)")
        parser.add_argument("-Q", "--crf", default="24", type=int,
                            help="constant Rate Factor. Quality value between 0-51, "
                          "lowest value being highest quality\n(default: %(default)s)")
        parser.add_argument("-o", "--outpath", type=str, required=True, help="path to encoded output file")
        parser.set_defaults(safe=True, outpath=None)
    return parser

  def split_label_content(self, labels):
    """
    Split instructions and gather durations
    """
    current_group = ""
    for i, x in enumerate(reversed(labels)):
      label = x["label"]
      if "comment_only" in x: # Ignore comment labels
        continue
      if "comment" in x: # Remove the trailing comment
        label = label.split("#")[0]
      instructions = [tmp.strip() for tmp in label.split(self.delimiter)]
      first_label = instructions[0]
      if len(first_label.split()) != 1:
        raise RuntimeError("First label must be 'mark', 'end' or group name. "
          "Invalid label: '{}'".format(first_label))
      if first_label == "mark":
        x["mark"] = True
        x["group"] = first_label
      elif first_label == "end":
        x["end"] = True
      else:
        # Parse "group_name[index/slice]"
        indexed = first_label.split("[")
        if len(indexed) == 1:
          if first_label not in self.config:
            raise RuntimeError("First label must be 'mark', 'end' or group name. "
              "Invalid label: '{}'".format(first_label))
        elif len(indexed) == 2:
          # We have an index or a slice
          if indexed[0] not in self.config:
            raise RuntimeError("First label must be 'mark', 'end' or group name. "
              "Invalid label: '{}'".format(first_label))
          if indexed[1][-1] != "]":
            raise RuntimeError("Missing closing square bracket for index/slice. "
              "Invalid label: '{}'".format(first_label))
          first_label = indexed[0]
          index = indexed[1][:-1] # Remove the ']' char from the second string
          sliced = index.split(":") # Search for the slice char
          if len(sliced) > 2:
            raise RuntimeError("Only one ':' allowed when defining group slice."
              "Invalid label: '{}'".format(first_label))
          if len(sliced) == 1:
            # We have an index
            try:
              x["index"] = int(index)
            except ValueError:
              raise RuntimeError("Cannot parse invalid index label: '{}[{}]'"
                                .format(first_label, index))
            try: # See if we can access the index
              f = self.config[first_label]["files"][x["index"]]
            except IndexError:
              raise RuntimeError("IndexError raised during parsing index label: '{}[{}]'"
                                .format(first_label, index))
          elif len(sliced) == 2:
            # We have a slice
            x["slice"] = sliced
            start = None
            stop = None
            try:
              start = int(sliced[0])
            except ValueError:
              pass
            try:
              stop = int(sliced[1])
            except ValueError:
              pass
            if not (start or stop):
              raise RuntimeError("Cannot parse invalid slice label, "
                "must have start or stop value: '{}[{}]'".format(first_label, index))
            x["sliced_files"] = self.config[first_label]["files"][start:stop]
            if len(self.config[first_label]["files"][start:stop]) == 0:
              raise RuntimeError("Cannot parse invalid slice label, "
                "list produced no files: '{}[{}]'".format(first_label, index))
        else:
          raise RuntimeError("Cannot parse invalid index/slice label: '{}'".format(first_label))
        x["group"] = first_label
        current_group = first_label
      x["instructions"] = instructions
      if i != 0:
        x["duration"] = "{:0.6f}".format(float(last) - float(x["timestamp_begin"]))
      last = x["timestamp_begin"]
    return labels

  def process_labels(self, content):
    """
    Parse the labels for timestamps
    """
    labels = []
    last = 0.0
    for x in content:
      entry = x.split("\t")
      if len(entry) != 3:
        raise RuntimeError("Invalid entry encountered: {}".format(entry))
      timestamp = float(entry[0])
      timestamp_end = float(entry[1])
      if timestamp != timestamp_end:
        raise RuntimeError("Timestamps for beginning and end do not match: {}"
                          .format(x))
      timestamp -= timestamp % (1 / self.framerate) # Align the timestamp with the framerate
      label = entry[2].strip()
      labels.append({"label": label,
                     "timestamp_begin": "{:0.6f}".format(timestamp),
                     "timestamp_end": "{:0.6f}".format(timestamp)})
      if label.startswith("#"): # Ignore comment labels
        labels[-1]["comment_only"] = True
      else:
        labels[-1]["diff"] = "{:0.6f}".format(timestamp - last)
        if "#" in label:
          splits = [tmp.lstrip() for tmp in label.split("#")] # Split comments
          labels[-1]["comment"] = " #".join(splits[1:])
        if timestamp > 0.0 and float(labels[-1]["diff"]) == 0.0:
          raise RuntimeError("Difference of 0 calculated. Duplicated mark for same timestamp?:\n"
            "{}\n{}".format(pformat(labels[-1]), pformat(labels[-2])))

        last = timestamp
    self.labels = self.split_label_content(labels)

  def decode_group_instruction(self, files, instructions):
    """
    Decode instructions from labels for top level groups
    """
    hold_present = False
    tempo = 1.0
    for ins in instructions:
      if ins.startswith("rep"):
        rep = int(ins[3:])
        if rep > 1:
          # Copy all the files, taking care not to show visible repetition
          files += (rep - 1) * (files[:] if files[0] != files[-1] else files[1:])
        else:
          raise RuntimeError("Invalid repeat request with number less than 2: {}"
                            .format(rep))
      elif ins.startswith("rev"):
        files = files[::-1]
      elif ins.startswith("boom"):
        # Append reversed list, excluding last item to avoid visible duplication
        files += list(files[:-1])[::-1]
      elif ins.startswith("hold"):
        hold_present = True
      elif ins.startswith("tempo"):
        tempo = float(ins[5:])
      else:
        raise RuntimeError("Invalid instruction: '{}'".format(ins))
    return tempo, hold_present, files

  def decode_mark_instruction(self, mark_entry, tempo):
    """
    Decode instructions from labels for marks between groups
    """
    instructions = mark_entry["instructions"][1:]
    hold_present = False
    for ins in instructions:
      if ins.startswith("hold"):
        hold_present = True
      elif ins.startswith("tempo"):
        tempo = float(ins[5:])
      else:
        raise RuntimeError("Invalid instruction: '{}'".format(ins))
    output = {"duration": float(mark_entry["duration"]),
              "timestamp_begin": mark_entry["timestamp_begin"],
              "hold": hold_present,
              "tempo": tempo,
              "label_entry": mark_entry
              }
    return tempo, output

  def build_groups_from_labels(self):
    """
    Construct a list of dicts called groups,
    combining the information from Audacity labels file and the JSON file.
    """
    tempo = 1.0
    groups = []
    for x in self.labels:
      if any(y in x for y in ["comment_only", "end"]):
        # If label is a pure comment or 'end' just skip without processing
        continue
      if "instructions" not in x:
        raise RuntimeError("No instructions detected: {}".format(x))
      if "mark" in x:
        tempo, mark = self.decode_mark_instruction(x, tempo)
        groups[-1]["marks"].append(mark)
      elif "group" in x:
        group = self.config[x["group"]]
        if "index" in x:
          files = [group["files"][x["index"]],] # single file in the list
          #TODO forbid index and hold, tempo, marks?
        elif "slice" in x:
          files = x["sliced_files"]
        else:
          files = group["files"][:] # Make a local copy
        # Apply modifier instructions for the group
        tempo, hold_present, files = self.decode_group_instruction(files, x["instructions"][1:])

        groups.append({"name": x["group"],
                      "group": group,
                      "count": len(files),
                      "files": files,
                      "marks": [{"duration": float(x["duration"]),
                                  "timestamp_begin": x["timestamp_begin"],
                                  "hold": hold_present,
                                  "tempo": tempo,
                                  "label_entry": x
                                  }]
                      })

        if "index" in x:
          groups[-1]["index"] = x["index"]
        elif "slice" in x:
          groups[-1]["slice"] = x["slice"]
      else:
        raise RuntimeError("First label must be 'mark', 'end' or group name. "
          "Invalid label: '{}'".format(x))
    self.groups = groups

  def build_tempos_from_group(self, group):
    """
    Count the number of holds, and deduct that time from the relative play duration
    for each mark in the group; to be used in calculating the scale ratio for each tempo,
    and therefore how many files to allocate for each mark.
    """
    tempos = {}
    play_duration = 0.0
    for m in group["marks"]:
      t = m["tempo"]
      if t not in tempos:
        tempos[t] = {"marks": [m]}
        tempos[t]["total_duration"] = m["duration"]
        if m["hold"]:
          tempos[t]["play_duration"] = 0.0
          tempos[t]["holds"] = 1
        else:
          tempos[t]["play_duration"] = m["duration"]
          tempos[t]["holds"] = 0
          play_duration += m["duration"]
      else:
        tempos[t]["marks"].append(m)
        tempos[t]["total_duration"] += m["duration"]
        if m["hold"]:
          tempos[t]["holds"] += 1
        else:
          tempos[t]["play_duration"] += m["duration"]
          play_duration += m["duration"]
    return tempos, play_duration

  def skip_to_valid_list_of_files(self, marks):
    j = 0
    while marks[j]["hold"] or \
      marks[j]["label_entry"]["num_files"] < 2 or \
        any(y in marks[j]["label_entry"] for y in ["index", "slice"]):
      j += 1
    if j >= len(marks):
      raise RuntimeError("Cannot find valid mark slot to correct file count in group {}"
                        .format(mark[0]["label_entry"]["group"]))
    return j

  def build_scaled_durations(self, g, tempos, play_duration):
    """
    Calculate the number of files and durations for groups.
    Account for:
      marks representing instructions or splits within the group
      tempo changes
      holds (displaying a single image for a duration)
      honouring index/slice count values
    """
    count = g["count"]
    count_without_holds = count
    scaled_duration = 0.0
    for t in tempos:
      count_without_holds -= tempos[t]["holds"]
      tempos[t]["scaled_duration"] = tempos[t]["play_duration"] * t
      scaled_duration += tempos[t]["scaled_duration"]
      self.logger.info("tempo: {}\nplay duration ratio: {} scaled duration: {}"
            .format(t, tempos[t]["play_duration"], tempos[t]["scaled_duration"]))
    self.logger.info("count: {}  count_without_holds: {}".format(count, count_without_holds))
    scale_ratio = play_duration / scaled_duration
    self.logger.info("scaled_duration pre adjust: {}\nscale_ratio {}".format(scaled_duration, scale_ratio))
    scaled_duration *= scale_ratio
    self.logger.info("scaled_duration: {}".format(scaled_duration))
    calc_files = 0
    files_ratio_total = 0
    for h, t in enumerate(tempos):
      tempos[t]["scaled_duration"] *= scale_ratio
      tempos[t]["scaled_duration_ratio"] = tempos[t]["scaled_duration"] / scaled_duration
      # Handle an odd number of files with an equal ratio
      tmp = count_without_holds * tempos[t]["scaled_duration_ratio"]
      if h == 0 and count_without_holds % 2 == 1:
        self.logger.info("Using ceiling for files_ratio {} for odd num_files: {}".format(tmp, count_without_holds))
        files_ratio = int(ceil(tmp))
      else:
        files_ratio = int(round(tmp))
      files_ratio_total += files_ratio
      if files_ratio_total > count_without_holds:
        files_ratio -= files_ratio_total - count_without_holds
      self.logger.info("tempo: {}\nscaled duration ratio: {} scaled duration: {}"
            .format(t, tempos[t]["scaled_duration_ratio"], tempos[t]["scaled_duration"]))
      self.logger.info("files ratio: {}".format(files_ratio))
      tempo_file_count = 0
      nfilestotal = 0
      nholdstotal = 0
      last_mark = len(tempos[t]["marks"]) - 1
      for i, m in enumerate(tempos[t]["marks"]):
        if m["hold"]:
          num_files = 1
          nholdstotal += 1
        else:
          num_files = int(round(files_ratio * m["duration"] / tempos[t]["play_duration"]))
          tempo_file_count += num_files
          if tempo_file_count > files_ratio:
            self.logger.info("tempo_file_count {} > files_ratio {}"
                    .format(tempo_file_count, files_ratio))
            num_files -= tempo_file_count - files_ratio
          nfilestotal += num_files
        self.logger.info("\n" + pformat(m))
        self.logger.info("{}num files: {}, files_ratio {} * (m duration {} / tempo play_duration {})"
              .format("hold " if m["hold"] else "", num_files,
                      files_ratio, m["duration"], tempos[t]["play_duration"]))
        if num_files == 0:
          raise RuntimeError("Number of files for mark is been calculated as 0.\n"
            "Duplicated mark for same timestamp?\n{}".format(pformat(m)))
        calc_files += num_files
        # Check if we've under/over used files available in the group during scaling calculations
        if i == last_mark:
          if nfilestotal < files_ratio:
            diff = files_ratio - nfilestotal
            j = self.skip_to_valid_list_of_files(tempos[t]["marks"])
            tempos[t]["marks"][j]["label_entry"]["num_files"] += diff
            self.logger.warning("Adjusting group '{}' mark '{}' num_files by +{}\n{}"
                  .format(tempos[t]["marks"][0]["label_entry"]["group"],
                          j, diff, pformat(tempos[t]["marks"][j])))
            nfilestotal += diff
            calc_files += diff
          if calc_files > count:
            self.logger.warning("Calculated number of files {} "
                                "does not match expected count {}. Auto adjusting.".format(calc_files, count))
            diff = calc_files - count
            j = self.skip_to_valid_list_of_files(tempos[t]["marks"])
            num_files -= diff
            self.logger.warning("Adjusting group '{}' mark '{}' num_files by -{}\n{}"
                  .format(tempos[t]["marks"][0]["label_entry"]["group"],
                          j, diff, pformat(tempos[t]["marks"][j])))
            calc_files -= diff
        m["label_entry"]["num_files"] = num_files
      self.logger.info("num files total: {}\tfiles {}\tholds {}"
            .format(nfilestotal + nholdstotal, nfilestotal, nholdstotal))
      tempos[t]["files_ratio"] = files_ratio
    self.logger.info("calc_files: {}".format(calc_files))
    self.logger.info("total scaled_duration: {}\n".format(sum(tempos[t]["scaled_duration"] for t in tempos)))
    if calc_files != count:
      raise RuntimeError("Calculated number of files {} does not match expected count {}."
                         .format(calc_files, count))

  def allocate_files_to_groups(self):
    """
    Distribute the file allocation between the marks in each group
    """
    for g in self.groups:
      idx = 0
      count = g["count"]
      for x in g["marks"]:
        num_files = x["label_entry"]["num_files"]
        duration = x["duration"] / num_files
        end_idx = int(idx+num_files)
        files = g["files"][idx:end_idx]
        goal_files = int(round(x["duration"]  * self.framerate))
        goal_duration = x["duration"] / goal_files
        if num_files > goal_files:
          # Reduce the number files and durations of groups that have more than the specified framerate.

          # Select N number of files evenly spaced from existing list of files.
          arr = np.array(files)
          filtered_idx = np.round(np.linspace(0, len(arr) - 1, goal_files)).astype(int)
          files = [x for x in arr[filtered_idx]]
          new_num_files = len(files)
          new_duration = x["duration"]  / new_num_files
          self.logger.info("Processing '{}'\ntimestamp {} duration {}\n"
                      "num_files {} files_duration {:0.06f}\n"
                      "goal_files {}, new num_files {}, new_duration {:0.06f}\n"
                      .format(x["label_entry"]["label"], x["label_entry"]["timestamp_begin"], x["label_entry"]["duration"],
                              num_files, duration,
                              goal_files, new_num_files, new_duration))
          x["label_entry"]["num_files"] = new_num_files
          duration = new_duration
        else:
          if len(files) != end_idx - idx:
            self.logger.warning("Group: '{}', slice {}:{}\nExpected number of files: {}\nActual files in slice: {}"
                          .format(g["name"], idx, end_idx, num_files, len(files)))
            num_files = len(files)
        x["label_entry"]["files"] = files
        x["label_entry"]["files_duration"] = duration
        x["label_entry"]["path"] = g["group"]["path"]
        idx += num_files
      if idx != count:
        raise RuntimeError("Slice index {} does not match file count in group {}\n"
                           "Try adjusting distance between labels".format(idx, count))

  def build_timings(self):
    """
    Build up the timing info by parsing instructions
    """
    self.build_groups_from_labels()
    for g in self.groups:
      tempos, play_duration = self.build_tempos_from_group(g)
      self.build_scaled_durations(g, tempos, play_duration)
    self.allocate_files_to_groups()

    timings = []
    for x in self.labels:
      if any(y in x for y in ["comment_only", "end"]):
        # If label is a pure comment or 'end' just append it
        timings.append({"label": "{}\t{}\t{}"
                        .format(x["timestamp_begin"], x["timestamp_end"], x["label"])})
        continue

      timings.append({"label": "{}\t{}\t{}".format(x["timestamp_begin"],
                                                  x["timestamp_end"], x["label"])})
      #print(pformat(x))
      dur = float(x["files_duration"])
      for i, f in enumerate(range(x["num_files"])):
        timestamp = float(x["timestamp_begin"])
        timings.append({"file": os.path.join(x["path"], x["files"][f]),
                        "duration": "{:0.6f}".format(dur),
                        "inpoint": "{:0.6f}".format(timestamp + (i * dur)),
                        "outpoint": "{:0.6f}".format(timestamp + ((i + 1) * dur))
                        })
    #print(pformat(timings))
    self.timings = timings

  def parse_labels_and_config(self):
    """
    Convert Audacity labels file to ffmpeg image sequence using info from json file.
    """
    with open(self.labels) as f:
      content = f.readlines()

    # Sanity checks
    if len(content) < 2:
      raise RuntimeError("Must be more than 2 labels present in file, marking start and end")
    if float(content[0].split("\t")[0]) != 0.0:
      raise RuntimeError("First label must start at 0.0")
    if content[-1].split("\t")[2].strip() != "end":
      raise RuntimeError("Last label must be 'end'")
    self.process_labels(content)
    self.build_timings()

    # Make sure the last image duration is set by copying the last image at the end.
    last_file = ""
    duration = float(self.timings[-1]["label"].split('\t')[0])

    # Write the output file
    with open(self.listfile, "w") as f:
      f.write("ffconcat version 1.0\n\n")
      unsafe = None
      for t in self.timings:
        if "label" in t:
          f.write("# {}\n".format(t["label"]))
        else:
          if self.relative:
            dirname = os.path.dirname(self.listfile)
            image = os.path.relpath(t["file"], start=os.path.dirname(self.listfile))
            relpath = os.path.dirname(image)
            if os.path.commonpath([dirname, os.path.dirname(t["file"])]) != dirname:
              # If relative path goes upwards it is considered unsafe
              if unsafe:
                if relpath not in unsafe:
                  unsafe.append(relpath)
              else:
                unsafe = [relpath]
          else:
            image = t["file"]
          # Write posix paths for ffmpeg list file.
          image = "/".join(os.path.normpath(image).split(os.sep))
          f.write("file '{}'\nduration {}\n".format(image, t["duration"]))
          #print(pformat(t))
          #f.write("file '{}'\ninpoint {}\noutpoint {}\n".format(image, t["inpoint"], t["outpoint"]))
          #f.write("file '{}'\ninpoint {}\n".format(image, t["inpoint"]))
          last_file = image
      if unsafe:
        self.logger.warning("Relative paths detected that may be 'unsafe' for previewing:\n"
          "{}".format(pformat(unsafe)))
      #f.write("file '{}'\n".format(last_file))
      f.write("file '{}'\n".format(last_file))
    print("Written '{}'".format(self.listfile))
    return duration

  def parseArgs(self, args, run=False, out=False):
    self.verbose = args.verbose
    self.dryrun = args.dryrun
    self.overwrite = args.overwrite
    self.logger = setupLogger("Parser", self.verbose)

    if not os.path.exists(args.config):
      raise RuntimeError("Could not find config file '{}'".format(args.config))
    with open(args.config, "r") as f:
      self.config = json.load(f)
    if not os.path.exists(args.labels):
      raise RuntimeError("Could not find input labels file '{}'".format(args.labels))
    if os.path.exists(args.listfile):
      self.logger.warning("Overwriting existing list file: '{}'".format(args.listfile))
    self.labels = args.labels
    if os.path.isabs(args.listfile):
      self.listfile = args.listfile
    else:
      # Get logical (not physical) path of present working directory,
      # i.e. symlink path not realpath
      if os.name == "posix":
        pwd = "".join(chr(x) for x in subprocess.Popen(
          ["pwd","-L"], stdout=subprocess.PIPE, shell=True).communicate()[0].strip())
      elif os.name == "nt":
        pwd = "".join(chr(x) for x in subprocess.Popen(
          ["echo","%cd%"], stdout=subprocess.PIPE, shell=True).communicate()[0].strip())
      else:
        raise RuntimeError("Unhandled system, not posix (Linux) or nt (Windows): {}".format(os.name))
      self.listfile = os.path.abspath(os.path.join(pwd, args.listfile))

    self.delimiter = args.delimiter
    self.relative = args.relative
    self.framerate = args.framerate

    if run or out:
      aspectratio_parse_success = False
      try:
        aspectratio = float(args.aspectratio)
        aspectratio_parse_success = True
      except ValueError:
        pass
      if not aspectratio_parse_success:
        tmp = args.aspectratio.split('/')
        if len(tmp) != 2:
          raise RuntimeError("Cannot parse aspect ratio: {}".format(args.aspectratio))
        try:
          aspectratio = float(tmp[0]) / float(tmp[1])
          aspectratio_parse_success = True
        except ValueError:
          pass
      if not aspectratio_parse_success:
        raise RuntimeError("Cannot parse aspect ratio: {}".format(args.aspectratio))
      height = ceil(round(args.width / aspectratio) / 2) * 2 # Round height to power of 2
      width = ceil(round(height * aspectratio) / 2) * 2 # Recalculate the width
      if width != args.width:
        raise RuntimeError("Width recalculation failed: {} != {}\n"
                           "Try adjusting width or aspect ratio.".format(args.width, width))
      self.aspectratio = aspectratio
      self.height = height
      self.width = width
      self.tempo = args.tempo
      audiofile = None
      if args.audiofile is not None:
        audiofile = args.audiofile
        if not os.path.exists(audiofile):
          raise RuntimeError("Could not find audio file '{}'".format(audiofile))
      self.audiofile = audiofile
    if out:
      outpath = args.outpath
      if outpath and os.path.exists(outpath):
        if not self.overwrite:
          raise RuntimeError("Output file already exists '{}'\n"
                             "Add '-y' to enable automatic over writing".format(outpath))
      self.outpath = outpath
      crf = args.crf
      if crf < 0 or crf > 51:
        raise RuntimeError("Invalid crf value. Must be between 0 and 51: {}".format(crf))
      self.crf = crf
      self.codec = args.codec
    else:
      self.outpath = None
      self.codec = None
      self.crf = None

  def runParser(self, args, run=False, out=False):
    self.parseArgs(args, run=run, out=out)

    duration = self.parse_labels_and_config()
    self.logger.info(self.listfile)
    if run or out:
      runcmd = []
      #Possible levels:
      #"quiet", "panic", "fatal", "error", "warning", "info", "verbose", "debug", "trace"
      if run:
        cmd = "ffplay -autoexit "
      else:
        cmd = "ffmpeg "
      cmd += "-hide_banner "
      cmd += "-loglevel "
      cmd += "repeat+" # uncompressed log
      if not self.verbose:
        #cmd += "error "
        #cmd += "warning "
        cmd += "info "
      else:
        cmd += "debug "
        #cmd += "trace "

      if run or args.safe:
        if self.verbose:
          cmd += "-dumpgraph 1 "
        cmd += "-f lavfi -i movie={},".format(self.listfile)
      else:
        if self.audiofile is not None:
          cmd += "-i"
          runcmd += cmd.split()
          cmd = ""
          runcmd.append("{}".format(self.audiofile))
        cmd += "-safe 0 "
        cmd += "-f concat -i {} ".format(self.listfile)
        cmd += "-filter "
      cmd += "settb=1/{:0.3f},".format(self.framerate)
      cmd += "setpts={:0.6f}*PTS-STARTPTS,".format(1.0 / self.tempo)
      cmd += "fps={:0.3f},".format(self.framerate)
      cmd += "scale={}:{}:force_original_aspect_ratio=decrease:eval=frame,".format(
        self.width, int(round(self.height * 2 / 3)) if args.histogram else self.height)
      cmd += "pad=w={}:h={}:x=-1:y=-1:color=black:eval=frame,".format(
        self.width, int(round(self.height * 2 / 3)) if args.histogram else self.height)
      cmd += "trim=duration={:0.3f}".format(duration / self.tempo)
      #cmd += ",format=yuv420p"
      #cmd += ",vectorscope"
      #cmd += ",zmq"
      #cmd += ",edgedetect"
      #cmd += ",fade=in:0:100"
      if run or args.safe:
        cmd += "[vid]" if args.histogram else "[out0]"
        if self.audiofile is not None:
          runcmd += cmd.split()
          runcmd[-1] += ";amovie={}".format(self.audiofile)
          cmd = ""
          #cmd += ",aselect=between(t\,100\,120)"
          cmd += ",atempo={}".format(self.tempo)
          if args.histogram:
            cmd += ",asplit=2[out1][b];"
            #cmd += ",asplit=3[out1][a][b];"
            #cmd += ""
            #cmd += "[a]showspectrum=s={}x{}:".format(200, height)
            #cmd += "orientation=horizontal:color=fire:scale=log:overlap=1[spectrum];"
            cmd += "[b]showcqt=s={}x{}:fps={}[cqt];".format(round(self.width), int(self.height / 3), int(self.framerate))
            cmd += "[vid][cqt]"
            cmd += "vstack"
            #cmd += "[vid0];[vid0]"
            cmd += "[out0]"
            #cmd += "[spectrum][vid]hstack[vidtop];"
            #cmd += "[vidtop][cqt]vstack[out0]"
          else:
            cmd += "[out1]"

          runcmd[-1] += cmd
          cmd = ""
      if out:
        cmd += " -r {0} -framerate {0} ".format(self.framerate)
        cmd += "-pixel_format yuv420p "
        cmd += "-c:v {} ".format(self.codec)
        if self.codec == "libx265":
          cmd += "-x265-params "
          cmd += "b-pyramid=0:"
          cmd += "scenecut=0:"
          cmd += "crf={} ".format(self.crf)
        if self.overwrite:
          cmd += " -y"
        runcmd += cmd.split()
        runcmd.append("{}".format(self.outpath))
      else:
        runcmd += cmd.split()
      cmd = runcmd
    else:
      self.logger.warning("Parsed only")
      cmd = []
    print("Running command\n {}".format(" ".join(cmd)))
    return cmd

