# Prelapse

The code presented is for aiding creation of timelapse and hyperlapse videos to be in sync with music.
They were made to simply the process and stitching image sequences together and
linking the transitions to events and features of audio.

Three phases are required:

* JSON group config generation
* Audacity label parsing
* Running ffmpeg or ffplay

Running the JSON generator in a directory with images should result in a _config.json_ file
containing groups based on directory name.

For example, _/tmp/example_ has 2 directories containing images:

```bash
$ prelapse gen -i /tmp/example -o config.json
$ cat /tmp/example/config.json
```

```json
{
  "a": {
    "path": "/tmp/example/a",
    "files": [
      "IMG_0000.jpg",
      "IMG_0001.jpg",
      "IMG_0002.jpg",
      "IMG_0003.jpg"
    ]
  },
  "b": {
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

NOTE: All instructions and group names are case sensitive. Using "End" instead of "end" won't work.

Label | Description
----- | -----------
*group name* | Referencing an entire block of files from the JSON config.
*group name*\[*index*\] | Where *index* is the integer offset of a single item in the group (starting from 0).
*group name*\[*slice_start*:*slice_end*\] | Where a subsection of the group files are used. See Python slicing notation.
mark | Marking a subsection within the duration of a group for an effect to be applied.
end | Indicating the end timestamp of the video.
\# *text* | A comment label which is ignored by the parser.

Following *group* and *mark* labels, instructions for effects applied to the files they contain can be specified.
These instruction labels are separated by a delimiter, the pipe character '|' is default.

Group Instruction | Description
----------------- | -----------
rep *int* | Repeat the sequence *int* number of times. Must be 2 or higher.
rev | Reverse the order of the files.
boom | Boomerang effect, playing forwards and then backwards.
tempo *float* | Indicate the starting tempo for the group, e.g. "tempo 1.5". Should be modified later by a mark.
hold | Pause on the first item in the group. Released by the next (mark or group name) label.

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
11.000000	11.000000	a | rev | boom
12.000000	12.000000	end
```

With the JSON config file and Audacity labels file, the parser script can determine how to apply
the effects requested to the file lists and generate an output file that FFmpeg/FFplay can read to concatenate
images together into a video.

Running the above example:

```bash
$ cd /tmp/example
$ prelapse play --dryrun
Written '/tmp/example/prelapse.ffconcat'
Dry run, not executing command:
ffplay -autoexit -hide_banner -loglevel repeat+info -f lavfi -i movie=/tmp/example/prelapse.ffconcat,settb=1/25.000,setpts=1.000000*PTS-STARTPTS,fps=25.000,scale=1280:960:force_original_aspect_ratio=decrease:eval=frame,pad=w=1280:h=960:x=-1:y=-1:color=black:eval=frame,trim=end=11.960[out0]
$ cat /tmp/example/prelapse.ffconcat
ffconcat version 1.0

# 0.000000	0.000000	a | rep 4
file 'a/IMG_0000.jpg'
duration 0.495000
file 'a/IMG_0001.jpg'
duration 0.495000
file 'a/IMG_0002.jpg'
duration 0.495000
file 'a/IMG_0003.jpg'
duration 0.495000
file 'a/IMG_0000.jpg'
duration 0.495000
file 'a/IMG_0001.jpg'
duration 0.495000
file 'a/IMG_0002.jpg'
duration 0.495000
file 'a/IMG_0003.jpg'
duration 0.495000
# 3.960000	3.960000	mark | hold
file 'a/IMG_0000.jpg'
duration 1.000000
# 4.960000	4.960000	mark | tempo 2.0
file 'a/IMG_0001.jpg'
duration 0.262857
file 'a/IMG_0002.jpg'
duration 0.262857
file 'a/IMG_0003.jpg'
duration 0.262857
file 'a/IMG_0000.jpg'
duration 0.262857
file 'a/IMG_0001.jpg'
duration 0.262857
file 'a/IMG_0002.jpg'
duration 0.262857
file 'a/IMG_0003.jpg'
duration 0.262857
# 6.800000	6.800000	b | boom | rep 2
file 'b/IMG_0000.jpg'
duration 0.462222
file 'b/IMG_0001.jpg'
duration 0.462222
file 'b/IMG_0002.jpg'
duration 0.462222
file 'b/IMG_0001.jpg'
duration 0.462222
file 'b/IMG_0000.jpg'
duration 0.462222
file 'b/IMG_0001.jpg'
duration 0.462222
file 'b/IMG_0002.jpg'
duration 0.462222
file 'b/IMG_0001.jpg'
duration 0.462222
file 'b/IMG_0000.jpg'
duration 0.462222
# 10.640000	10.640000	# example comment
# 10.960000	10.960000	a | rev | boom
file 'a/IMG_0003.jpg'
duration 0.142857
file 'a/IMG_0002.jpg'
duration 0.142857
file 'a/IMG_0001.jpg'
duration 0.142857
file 'a/IMG_0000.jpg'
duration 0.142857
file 'a/IMG_0001.jpg'
duration 0.142857
file 'a/IMG_0002.jpg'
duration 0.142857
file 'a/IMG_0003.jpg'
duration 0.142857
# 11.960000	11.960000	end
file 'a/IMG_0003.jpg'
```

NOTE: The last image is displayed after the end to ensure there is a correct key frame present.
NOTE: The timestamps have been adjusted slightly to aligned with the frame rate.
NOTE: Default aspect ratio set as 4/3. Default width is 1280. Default frame rate is 25.

Phase 3 involves running FFmpeg or FFplay using the generated list file.

Running the following will use FFmpeg produce a video file in 16/9 aspect ratio,
width 640 pixels, height 480 pixels, in H265 format.

The height is calculated by the *width / aspect ratio*.

```bash
$ prelapse enc -w 640 -x 16/9 -o test.mp4
```

Changing the command slightly, we can preview the output before encoding it, and attach an audio file with it:

```bash
$ prelapse play -w 640 -x 16/9 -a audio.m4a
```

NOTE: The 'end' label should be at the timestamp of the total duration of the audio,
so that audio and video finish at the same time.

NOTE: If the video file already exists, adding the -y flag will mean the file is overwritten.

NOTE: In order for FFplay to preview files, the file paths in the prelapse.ffconcat file need to be relative paths.
If they are absolute paths, or there is an error complaining about *"Unsafe filenames"* then additional steps are
required to allow FFmpeg to write the file.
There seems to be a gotcha with relative paths that start with '..'.

NOTE: The scripts files don't handle files with brackets or spaces in very well. e.g. IMG_1234 (1).jpg
It's recommended to rename these files before running 'prelapse gen'. e.g. IMG_1234_01.jpg

NOTE: Stuttering can occur when large images are being read quickly during preview.
Reducing the frame rate can help, or resizing the images closer to the intended output size.
