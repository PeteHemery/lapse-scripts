# Lapse Scripts

The collection of scripts provided are for aiding creation of timelapse and hyperlapse videos to be in sync with music.
Three phases are required:

* JSON group config generation
* Audacity label parsing
* FFmpeg running

Running the JSON generator in a directory with images should result in a _config.json_ file
containing groups based on directory name.

For example, _/tmp/example_ has 2 directories containing images:

```bash
$ python lapse-gen.py -i /tmp/example -o config.json
$ cat /tmp/example/config.json
```

```json
{
  "a": {
    "count": 4,
    "path": "/tmp/example/a",
    "files": [
      "IMG_0000.jpg",
      "IMG_0001.jpg",
      "IMG_0002.jpg",
      "IMG_0003.jpg"
    ]
  },
  "b": {
    "count": 3,
    "path": "/tmp/example/b",
    "files": [
      "IMG_0000.jpg",
      "IMG_0001.jpg",
      "IMG_0002.jpg"
    ]
  }
}
```

Phase 2 involves creating labels in the same format used by Audacity.
Each line is tab separated and has the format:

*start time*\\t*end time*\\t*label*

with the time values having 6 decimal places of precision.
NOTE: *start time* and *end time* must be the same value!

Labels have accepted formats by the parser script.
A label starting with '\#' is considered a comment.

Label | Description
----- | -----------
*group name* | Referencing an entire block of files from the JSON config.
*group name*\[*index*\] | Where *index* is the integer offset of a single item in the group (starting from 0).
*group name*\[*slice_start*:*slice_end*\] | Where a subsection of the group files are used. See Python slicing notation.
mark | Marking a subsection within the duration of a group for an effect to be applied.
end | Indicating the end timestamp of the video.
\# *text* | A comment label which is ignored by the parser.

Following *group* and *mark* labels, instructions for effects applied to the files they contain can be specified.

Group Instruction | Description
----------------- | -----------
rep *int* | Repeat the sequence *int* number of times. Must be 2 or higher.
rev | Reverse the order of the files.
boom | Boomerang effect, playing forwards and then backwards.
tempo *float* | Indicate the starting tempo for the group, e.g. "tempo 1.5". Should be modified later by a mark.
hold | Pause on the first item in the group. Released by the next label.

Mark Instruction | Description
---------------- | -----------
tempo *float* | Indicate the tempo from the mark onwards within the group.
hold | Pause on the item in the group where the mark happens to be closest. Released by the next label.

These keywords can be linked together to create descriptions of effects to be applied within the video.
The default delimiter for labels is the pipe symbol, but this can be changed at runtime with a flag
if the user prefers a different delimiter character.

```
0.000000	0.000000	a | rep 4
4.000000	4.000000	mark | hold
5.000000	5.000000	mark | tempo 2.0
6.824233	6.824233	b | boom | rep 2
10.651300	10.651300	# example comment
12.000000	12.000000	end
```

With the JSON config file and Audacity labels file, the parser script can determine how to apply
the effects requested to the file lists and generate an output file that FFmpeg/FFplay can read to concatenate
images together into a video.

Running the above example:

```bash
$ python lapse-parse.py -c config.json -i labels.txt -o list.txt
Written '/tmp/example/list.txt'
$ cat list.txt
# 0.000000	0.000000	a | rep 4
file 'a/IMG_0000.jpg'
duration 0.500000
file 'a/IMG_0001.jpg'
duration 0.500000
file 'a/IMG_0002.jpg'
duration 0.500000
file 'a/IMG_0003.jpg'
duration 0.500000
file 'a/IMG_0000.jpg'
duration 0.500000
file 'a/IMG_0001.jpg'
duration 0.500000
file 'a/IMG_0002.jpg'
duration 0.500000
file 'a/IMG_0003.jpg'
duration 0.500000
# 4.000000	4.000000	mark | hold
file 'a/IMG_0000.jpg'
duration 1.000000
# 5.000000	5.000000	mark | tempo 2.0
file 'a/IMG_0001.jpg'
duration 0.260605
file 'a/IMG_0002.jpg'
duration 0.260605
file 'a/IMG_0003.jpg'
duration 0.260605
file 'a/IMG_0000.jpg'
duration 0.260605
file 'a/IMG_0001.jpg'
duration 0.260605
file 'a/IMG_0002.jpg'
duration 0.260605
file 'a/IMG_0003.jpg'
duration 0.260605
# 6.824233	6.824233	b | boom | rep 2
file 'b/IMG_0000.jpg'
duration 0.575085
file 'b/IMG_0001.jpg'
duration 0.575085
file 'b/IMG_0002.jpg'
duration 0.575085
file 'b/IMG_0001.jpg'
duration 0.575085
file 'b/IMG_0000.jpg'
duration 0.575085
file 'b/IMG_0001.jpg'
duration 0.575085
file 'b/IMG_0002.jpg'
duration 0.575085
file 'b/IMG_0001.jpg'
duration 0.575085
file 'b/IMG_0000.jpg'
duration 0.575085
# 10.651300	10.651300	# example comment
# 12.000000	12.000000	end
file 'b/IMG_0000.jpg'
```

NOTE: The last image is displayed after the end to ensure there is a correct key frame present.

Phase 3 involves running FFmpeg or FFplay using the generated list file.
Running the following will use FFmpeg produce a video file in 16/9 aspect ratio,
width 640 pixels, height 360 pixels, in H265 format.

The height is calculated by the *width / aspect ratio*. Default aspect ratio set as 4/3.

```bash
$ python lapse-run.py -l list.txt -o example.mp4 -w 640 -x 1.777
```

Changing the command slightly, we can preview the output before encoding it, and attach an audio file with it:

```bash
$ python lapse-run.py -l list.txt -o example.mp4 -w 640 -x 1.777 -a audio.m4a -p
```

NOTE: If the video file already exists, previewing will fail without adding the -y flag,
even though the file won't be overwritten.

NOTE: In order for FFplay to preview files, the file paths in the list.txt file need to be relative paths.
If they are absolute paths, or there is an error complaining about *"Unsafe filenames"* then adding the -s flag
will modify the behaviour of the script to allow FFmpeg to write the file.
This can seems to be a gotcha with relative paths that start with '..'

Adding -r to the parser will remove the default relative paths and revert to absolute paths.
