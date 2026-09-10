#!/usr/bin/env python3
"""Master a level set to a .tap that the Gauntlet cassette loader will read.

    python3 mktap.py gauntlet_levels.d64
    python3 mktap.py mylevels/
    python3 mktap.py --d64 gauntlet_levels.d64 --out side2.tap
    python3 mktap.py --levels mylevels --out side2.tap

Give it a .d64 or a directory of LEVEL_nnn.prg files and it works out which
it has; --d64 and --levels say so outright if you would rather be explicit,
or if a directory is named something ending in .d64. Editing a level disk with the kit and then mastering that disk to
tape is the expected route, so a disk is what it takes by default; the
output is named after the input unless --out says otherwise.

The blocks are the cassette's own arrangement - seven levels in the first,
then eight progression levels and two treasure rooms in each of the rest,
every slot a fixed 512 bytes - encoded in the game's turbo format. See
GAME-NOTES.md for how that format was recovered.

This produces the level side only. It is meant to replace side 2 of a
Gauntlet cassette; side 1 carries the program and is not touched.

**Untested on hardware.** The format decodes and round-trips exactly, and
the checksums match the originals, but nothing here has been played from a
real cassette. Treat it as a starting point rather than a finished tool.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import turbotape as T
from mkbatched import build_blocks, LOAD_ADDR

# The first block is named A and the rest A1, as the original tape has it;
# the loader matches on the name, so this is what the game asks for.
NAMES = ['A'] + ['A1'] * 14

# A pilot of zero bits before each block gives the loader time to settle,
# the way the original does.
PILOT = 3000


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source', nargs='?',
                    default=os.path.join(HERE, 'gauntlet_levels.d64'),
                    help='a .d64, or a directory of LEVEL_nnn.prg files; '
                         'which one it is is worked out from the path')
    ap.add_argument('--d64', metavar='FILE',
                    help='say explicitly that the source is a disk image')
    ap.add_argument('--levels', metavar='DIR',
                    help='say explicitly that the source is a directory')
    ap.add_argument('--out', help='the .tap to write '
                                  '(default: the source name with .tap)')
    ap.add_argument('--leader', type=int, default=1200,
                    help='leader bytes before each block')
    args = ap.parse_args()

    if args.d64 and args.levels:
        sys.exit('give --d64 or --levels, not both')
    # the explicit options win over the positional, and say what the source
    # is rather than leaving it to be guessed from the path
    if args.d64:
        src, is_disk = args.d64, True
    elif args.levels:
        src, is_disk = args.levels, False
    else:
        src = args.source
        is_disk = os.path.isfile(src)
    if not os.path.exists(src):
        sys.exit('no such file or directory: %s' % src)
    if is_disk and not os.path.isfile(src):
        sys.exit('%s is not a file' % src)
    if not is_disk and not os.path.isdir(src):
        sys.exit('%s is not a directory' % src)
    if args.out:
        out = args.out
    else:
        out = os.path.splitext(src.rstrip('/'))[0] + '.tap'
    blocks = build_blocks(None if is_disk else src, src if is_disk else None)
    pulses = bytearray()
    for i, payload in enumerate(blocks):
        pulses += bytes([T.ZERO]) * PILOT
        pulses += T.encode_block(NAMES[i] if i < len(NAMES) else 'A1',
                                 LOAD_ADDR, payload, leader=args.leader)
    T.write_tap(out, bytes(pulses))
    print('read %s (%s)' % (src, 'disk' if is_disk else 'directory'))
    print('wrote %s: %d blocks, %d pulses, %d bytes of level data'
          % (out, len(blocks), len(pulses),
             sum(len(b) for b in blocks)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
