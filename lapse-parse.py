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
Audacity labels to ffmpeg list converter.

Provide an input file path, output file path, a group description file.
Using the labels from Audacity, and the group descriptions, calculate the
order and duration of images to fulfill the instructions in the labels for
"video" effects from the image sequences.
"""
import argparse
import json
import os
import subprocess

from pprint import pformat

DEFAULT_DELIMITER = "|"

VERBOSE_LOG_ENABLED = False


def dprint(*args):
  """
  Print helper that only prints when verbose flag is set
  """
  global VERBOSE_LOG_ENABLED
  if VERBOSE_LOG_ENABLED:
    print(*args)


def split_label_content(labels, config, delimiter):
  """
  Split instructions and gather durations
  """
  for i, x in enumerate(reversed(labels)):
    label = x["label"]
    if "comment_only" in x: # Ignore comment labels
      continue
    if "comment" in x: # Remove the trailing comment
      label = label.split("#")[0]
    instructions = [tmp.strip() for tmp in label.split(delimiter)]
    first_label = instructions[0]
    if len(first_label.split()) != 1:
      raise RuntimeError("First label must be 'mark', 'end' or group name. "
        "Invalid label: '{}'".format(first_label))
    if first_label == "mark":
      x["mark"] = True
    elif first_label == "end":
      x["end"] = True
    else:
      # Parse "group_name[index/slice]"
      indexed = first_label.split("[")
      if len(indexed) == 1:
        if first_label not in config:
          raise RuntimeError("First label must be 'mark', 'end' or group name. "
            "Invalid label: '{}'".format(first_label))
      elif len(indexed) == 2:
        # We have an index or a slice
        if indexed[0] not in config:
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
            f = config[first_label]["files"][x["index"]]
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
          x["sliced_files"] = config[first_label]["files"][start:stop]
          if len(config[first_label]["files"][start:stop]) == 0:
            raise RuntimeError("Cannot parse invalid slice label, "
              "list produced no files: '{}[{}]'".format(first_label, index))
      else:
        raise RuntimeError("Cannot parse invalid index/slice label: '{}'".format(first_label))
      x["group"] = first_label
    x["instructions"] = instructions
    if i != 0:
      x["duration"] = "{:0.6f}".format(float(last) - float(x["timestamp_begin"]))
    last = x["timestamp_begin"]
  return labels


def process_labels(content, config, delimiter):
  """
  Parse the labels for timestamps
  """
  labels = []
  last = 0.0
  for x in content:
    entry = x.split("\t")
    if len(entry) != 3:
      raise RuntimeError("Invalid entry encountered: {}".format(entry))
    timestamp_begin = float(entry[0])
    timestamp_end = float(entry[1])
    if timestamp_begin != timestamp_end:
      raise RuntimeError("Timestamps for beginning and end do not match: {}"
                         .format(x))
    label = entry[2].strip()
    labels.append({"label": label,
                   "timestamp_begin": "{:0.6f}".format(timestamp_begin),
                   "timestamp_end": "{:0.6f}".format(timestamp_end)})
    if label.startswith("#"): # Ignore comment labels
      labels[-1]["comment_only"] = True
    else:
      labels[-1]["diff"] = "{:0.6f}".format(timestamp_begin - last)
      if "#" in label:
        splits = [tmp.lstrip() for tmp in label.split("#")] # Split comments
        labels[-1]["comment"] = " #".join(splits[1:])
      if timestamp_begin > 0.0 and float(labels[-1]["diff"]) == 0.0:
        raise RuntimeError("Difference of 0 calculated. "
          "Duplicated mark for same timestamp?:\n{}\n{}"
          .format(pformat(labels[-1]), pformat(labels[-2])))

      last = timestamp_begin
  labels = split_label_content(labels, config, delimiter)

  return content, config, delimiter, labels


def decode_group_instruction(files, instructions):
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


def decode_mark_instruction(mark_entry, tempo):
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


def build_groups_from_labels(config, labels):
  """
  Construct a list of dicts called groups,
  combining the information from Audacity labels file and the JSON file.
  """
  tempo = 1.0
  groups = []
  for x in labels:
    if any(y in x for y in ["comment_only", "end"]):
      # If label is a pure comment or 'end' just skip without processing
      continue
    if "instructions" not in x:
      raise RuntimeError("No instructions detected: {}".format(x))
    if "group" in x:
      group = config[x["group"]]
      if "index" in x:
        files = [group["files"][x["index"]],] # single file in the list
        #TODO forbid index and hold, tempo, marks?
      elif "slice" in x:
        files = x["sliced_files"]
      else:
        files = group["files"][:] # Make a local copy
      # Apply modifier instructions for the group
      tempo, hold_present, files = decode_group_instruction(files, x["instructions"][1:])

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
    elif "mark" in x:
      tempo, mark = decode_mark_instruction(x, tempo)
      groups[-1]["marks"].append(mark)
    else:
      raise RuntimeError("First label must be 'mark', 'end' or group name. "
        "Invalid label: '{}'".format(x))
  return groups


def build_tempos_from_group(group):
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


def allocate_files_to_groups(groups):
  """
  Distribute the file allocation between the marks in each group
  """
  for g in groups:
    idx = 0
    count = g["count"]
    for x in g["marks"]:
      end_idx = int(idx+x["label_entry"]["num_files"])
      sliced = g["files"][idx:end_idx]
      if len(sliced) != end_idx - idx:
        print("Group: '{}', slice {}:{}\nExpected number of files: {}\nActual files in slice: {}"
              .format(g["name"], idx, end_idx, x["label_entry"]["num_files"], len(sliced)))
        x["label_entry"]["num_files"] = len(sliced)
      x["label_entry"]["files"] = sliced
      x["label_entry"]["files_duration"] = x["duration"] / x["label_entry"]["num_files"]
      x["label_entry"]["path"] = g["group"]["path"]
      idx += x["label_entry"]["num_files"]
    if idx != count:
      raise RuntimeError("Slice index {} does not match file count in group {}"
                         .format(idx, count))


def skip_to_valid_list_of_files(marks):
  j = 0
  while marks[j]["hold"] or \
    marks[j]["label_entry"]["num_files"] < 2 or \
      any(y in marks[j]["label_entry"] for y in ["index", "slice"]):
    j += 1
  if j >= len(marks):
    raise RuntimeError("Cannot find valid mark slot to correct file count in group {}"
                       .format(mark[0]["label_entry"]["group"]))
  return j


def build_scaled_durations(g, tempos, play_duration):
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
    dprint("tempo: {}\nplay duration ratio: {} scaled duration: {}"
           .format(t, tempos[t]["play_duration"], tempos[t]["scaled_duration"]))
  dprint("count: {}  count_without_holds: {}".format(count, count_without_holds))
  scale_ratio = play_duration / scaled_duration
  dprint("scaled_duration pre adjust: {}\nscale_ratio {}".format(scaled_duration, scale_ratio))
  scaled_duration *= scale_ratio
  dprint("scaled_duration: {}".format(scaled_duration))
  calc_files = 0
  files_ratio_total = 0
  for t in tempos:
    tempos[t]["scaled_duration"] *= scale_ratio
    tempos[t]["scaled_duration_ratio"] = tempos[t]["scaled_duration"] / scaled_duration
    tempos[t]["files_ratio"] = int(round(count_without_holds * tempos[t]["scaled_duration_ratio"]))
    files_ratio_total += tempos[t]["files_ratio"]
    if files_ratio_total > count_without_holds:
      tempos[t]["files_ratio"] -= files_ratio_total - count_without_holds
    dprint("tempo: {}\nscaled duration ratio: {} scaled duration: {}"
           .format(t, tempos[t]["scaled_duration_ratio"], tempos[t]["scaled_duration"]))
    dprint("files ratio: {}".format(tempos[t]["files_ratio"]))
    tempo_file_count = 0
    nfilestotal = 0
    nholdstotal = 0
    last_mark = len(tempos[t]["marks"]) - 1
    for i, m in enumerate(tempos[t]["marks"]):
      if m["hold"]:
        m["label_entry"]["num_files"] = 1
        nholdstotal += 1
      else:
        m["label_entry"]["num_files"] = int(
          round(tempos[t]["files_ratio"] * m["duration"] / tempos[t]["play_duration"]))
        tempo_file_count += m["label_entry"]["num_files"]
        if tempo_file_count > tempos[t]["files_ratio"]:
          dprint("tempo_file_count {} > tempos[t]['files_ratio'] {}"
                  .format(tempo_file_count, tempos[t]["files_ratio"]))
          m["label_entry"]["num_files"] -= tempo_file_count - tempos[t]["files_ratio"]
        nfilestotal += m["label_entry"]["num_files"]
      dprint(pformat(m))
      dprint("{}num files: {}, files_ratio {} * (m duration {} / tempo play_duration {})"
            .format("" if not m["hold"] else "hold ", m["label_entry"]["num_files"],
                    tempos[t]["files_ratio"], m["duration"], tempos[t]["play_duration"]))
      if m["label_entry"]["num_files"] == 0:
        raise RuntimeError("Number of files for mark is been calculated as 0.\n"
          "Duplicated mark for same timestamp?\n{}".format(pformat(m)))
      calc_files += m["label_entry"]["num_files"]
      # Check if we've under/over used files available in the group during scaling calculations
      if i == last_mark:
        if nfilestotal < tempos[t]["files_ratio"]:
          diff = tempos[t]["files_ratio"] - nfilestotal
          j = skip_to_valid_list_of_files(tempos[t]["marks"])
          tempos[t]["marks"][j]["label_entry"]["num_files"] += diff
          dprint("\nWarning: Adjusting group {} mark '{}' num_files by +{}\n{}"
                 .format(tempos[t]["marks"][0]["label_entry"]["group"],
                         j, diff, pformat(tempos[t]["marks"][j])))
          nfilestotal += diff
          calc_files += diff
        if calc_files > count:
          print("Warning: Calculated number of files {} ".format(calc_files) +
                "does not match expected count {}. Auto adjusting.".format(count))
          diff = calc_files - count
          j = skip_to_valid_list_of_files(tempos[t]["marks"])
          m["label_entry"]["num_files"] -= diff
          dprint("\nWarning: Adjusting group '{}' mark '{}' num_files by -{}\n{}"
                 .format(tempos[t]["marks"][0]["label_entry"]["group"],
                         j, diff, pformat(tempos[t]["marks"][j])))
          calc_files -= diff
    dprint("num files total: {}\tfiles {}\tholds {}"
           .format(nfilestotal + nholdstotal, nfilestotal, nholdstotal))
  dprint("calc_files: {}".format(calc_files))
  dprint("total scaled_duration: {}\n".format(sum(tempos[t]["scaled_duration"] for t in tempos)))
  if calc_files != count:
    raise RuntimeError("Warning: Calculated number of files {} "
                       "does not match expected count {}.".format(calc_files, count))


def build_timings(content, config, delimiter, labels):
  """
  Build up the timing info by parsing instructions
  """
  groups = build_groups_from_labels(config, labels)
  for g in groups:
    tempos, play_duration = build_tempos_from_group(g)
    build_scaled_durations(g, tempos, play_duration)
  allocate_files_to_groups(groups)

  timings = []
  for x in labels:
    if any(y in x for y in ["comment_only", "end"]):
      # If label is a pure comment or 'end' just append it
      timings.append({"label": "{}\t{}\t{}"
                      .format(x["timestamp_begin"], x["timestamp_end"], x["label"])})
      continue

    timings.append({"label": "{}\t{}\t{}".format(x["timestamp_begin"],
                                                 x["timestamp_end"], x["label"])})
    for f in range(x["num_files"]):
      timings.append({"file": os.path.join(x["path"], x["files"][f]),
                      "duration": "{:0.6f}".format(x["files_duration"])})

  return timings


def aud_to_ff(inpath, outpath, config, delimiter, relative):
  """
  Convert Audacity labels file to ffmpeg image sequence using info from json file.
  """
  with open(inpath) as f:
    content = f.readlines()

  # Sanity checks
  if len(content) < 2:
    raise RuntimeError("Must be more than 2 labels present in file, marking start and end")
  if float(content[0].split("\t")[0]) != 0.0:
    raise RuntimeError("First label must start at 0.0")
  if content[-1].split("\t")[2].strip() != "end":
    raise RuntimeError("Last label must be 'end'")

  timings = build_timings(*process_labels(content, config, delimiter))

  # Make sure the last image duration is set by copying the last image at the end.
  last_file = ""

  # Write the output file
  with open(outpath, "w") as f:
    unsafe = None
    for t in timings:
      if "label" in t:
        f.write("# {}\n".format(t["label"]))
      else:
        if relative:
          dirname = os.path.dirname(outpath)
          image = os.path.relpath(t["file"], start=os.path.dirname(outpath))
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
        last_file = image
    if unsafe:
      print("Warning: relative paths detected that may be 'unsafe' for previewing:\n"
        "{}".format(pformat(unsafe)))
    f.write("file '{}'\n".format(last_file))
  print("Written '{}'".format(outpath))


def main():
  global VERBOSE_LOG_ENABLED
  parser = argparse.ArgumentParser(description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("-i", "--inpath", default="labels.txt", required=True,
                      help="Path to input Audacity labels file (default: %(default)s)")
  parser.add_argument("-o", "--outpath", default="list.txt", required=True,
                      help="Path to output ffmpeg list file (default: %(default)s)")
  parser.add_argument("-c", "--config", default="config.json", required=True,
                      help="json config file describing the picture groups (default: %(default)s)")
  parser.add_argument("-l", "--delimiter", default=DEFAULT_DELIMITER,
                      help="Delimiter used in labels to separate instructions (default: '%(default)s')\n"
                      "NOTE: Cannot be used letters or any of the following: '[]:\\/#.\'")
  parser.add_argument("-r", "--relative", dest="relative", action="store_false",
                      help="Disable relative paths and use absolute paths"
                      "(Will cause problems with ffmpeg run script!) (default: %(default)s)")
  parser.add_argument("-y", "--overwrite", dest="overwrite", action="store_true",
                      help="Over write output file if it already exists (default: %(default)s)")
  parser.add_argument("-v", "--verbose", dest="verbose", action="store_true",
                      help="Enable verbose prints (default: %(default)s)")
  parser.set_defaults(relative=True, overwrite=False, verbose=False)
  args = parser.parse_args()
  VERBOSE_LOG_ENABLED = args.verbose

  if not os.path.exists(args.config):
    raise RuntimeError("Could not find config file '{}'".format(args.config))
  with open(args.config, "r") as f:
    config = json.load(f)
  if not os.path.exists(args.inpath):
    raise RuntimeError("Could not find input file '{}'".format(args.inpath))
  if os.path.exists(args.outpath):
    if not args.overwrite:
      raise RuntimeError("Output file already exists '{}'\nAdd '-y' to enable automatic over writing"
                         .format(args.outpath))
  inpath = args.inpath
  if os.path.isabs(args.outpath):
    outpath = args.outpath
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
      raise RuntimeError("Unhandled system, not posix or nt: {}".format(os.name))
    outpath = os.path.abspath(os.path.join(pwd, args.outpath))

  aud_to_ff(inpath, outpath, config, args.delimiter, args.relative)


if __name__ == "__main__":
  main()
