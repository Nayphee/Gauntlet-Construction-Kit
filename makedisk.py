#!/usr/bin/env python3
"""Build a complete Gauntlet level disk: the construction kit plus 128
procedurally generated levels.

    python3 makedisk.py                     # gauntlet_levels.d64, seed 0
    python3 makedisk.py --seed 12           # a different 128 levels
    python3 makedisk.py --out mydisk.d64

Needs only Python 3 and these files beside it:

    genlevels.py     the level generator
    gauntlet_dd.py   the level format codec
    mklevdisk.py     the .d64 writer
    gauntkit.prg     the editor, already assembled

Swap the finished disk in at the game's press-fire prompt.  The game only
reads LEVEL nnn once it is running, so it will take its levels from here.

Verification needs two more files (gcore.prg and symbols.json) and is run
separately with verify.py; this script checks only that every level encodes
and that the disk is well formed.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--seed', type=int, default=0,
                    help='master seed: a different one gives a different '
                         'set of 128 levels')
    ap.add_argument('--out', default=os.path.join(HERE, 'gauntlet_levels.d64'),
                    help='the .d64 to write')
    ap.add_argument('--kit', default=os.path.join(HERE, 'gauntkit.prg'),
                    help='the construction kit .prg to put first on the disk')
    ap.add_argument('--keep', metavar='DIR',
                    help='also keep the individual LEVEL_nnn.prg files here')
    args = ap.parse_args()

    missing = [f for f in ('genlevels.py', 'gauntlet_dd.py', 'mklevdisk.py')
               if not os.path.exists(os.path.join(HERE, f))]
    if not os.path.exists(args.kit):
        missing.append(os.path.basename(args.kit))
    if missing:
        sys.exit('missing beside this script: %s' % ', '.join(missing))

    levels = args.keep or os.path.join(HERE, 'levels')
    for step in (
            [sys.executable, os.path.join(HERE, 'genlevels.py'),
             '--seed', str(args.seed), '--out', levels],
            [sys.executable, os.path.join(HERE, 'mklevdisk.py'),
             '--levels', levels, '--kit', args.kit, '--out', args.out]):
        r = subprocess.run(step, cwd=HERE)
        if r.returncode:
            sys.exit('failed: %s' % ' '.join(os.path.basename(a)
                                             for a in step[1:2]))
    print('wrote %s' % args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
