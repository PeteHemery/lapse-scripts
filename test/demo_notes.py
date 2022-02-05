#! /usr/bin/env python3

import sys
from aubio import source, notes

if len(sys.argv) < 2:
    print("Usage: %s <filename> [samplerate]" % sys.argv[0])
    sys.exit(1)

filename = sys.argv[1]

downsample = 1
samplerate = 44100 // downsample
if len( sys.argv ) > 2: samplerate = int(sys.argv[2])

win_s = 2048 // downsample # fft size
hop_s = 512 // downsample # hop size

s = source(filename, samplerate, hop_s)
samplerate = s.samplerate

tolerance = 0.8

notes_o = notes("default", win_s, hop_s, samplerate)

print("%8s" % "time","[ start","vel","last ]")

# total number of frames read
total_frames = 0
with open("test-labels.txt", "w") as f:
  while True:
    samples, read = s()
    new_note = notes_o(samples)
    if (new_note[0] != 0):
        note_str = ' '.join(["%.2f" % i for i in new_note])
        f.write("{0}\t{0}\t{1}\n".format("{:0.6f}".format((total_frames/float(samplerate))), new_note))
    total_frames += read
    if read < hop_s: break
