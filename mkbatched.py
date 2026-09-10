#!/usr/bin/env python3
"""Write a level set in the batched layout that the cassette releases use,
and that at least one disk release carries as files `A` to `O`.

    python3 mkbatched.py gauntlet_levels.d64 --out blocks/

writes the fifteen blocks as files `A` to `O`, each with a $2000 load
address, ready to be put on a disk with c1541 or any other tool:

    c1541 -format "gauntlet,gk" d64 batched.d64 -write blocks/A A ...

The layout was recovered from a Gauntlet cassette and matches the disk
files byte for byte:

    A   levels 1-7                        7 slots
    B   levels 8-15,   plus 118 and 119   10 slots
    C   levels 16-23,  plus 120 and 121
    D   levels 24-31,  plus 122 and 123
    E   levels 32-39,  plus 124 and 125
    F   levels 40-47,  plus 126 and 127
    G   levels 48-55,  plus 128
    H-N levels 56-111, eight to a block
    O   levels 112-117                    6 slots

Every slot is a fixed 512 bytes whatever the level needs, which is what a
cassette requires: it cannot seek to a named file, so level *n* of a block
is always at `$2000 + 512n`. Unused slots are left as zeros.

This is offered for completeness. The editor cannot read these - it loads
and saves one named `LEVEL nnn` file at a time - so a disk written here is
for feeding a batched release, not for editing.
"""
import argparse
import itertools
import os
import sys

SLOT = 512
HERE = os.path.dirname(os.path.abspath(__file__))
LOAD_ADDR = 0x2000


def layout():
    """Which level goes in which slot of which block, as the tape has it."""
    blocks = []
    prog = list(range(1, 118))          # the levels played in order
    # The treasure rooms cycle rather than run out: block G holds 128 and
    # then wraps back to 118, so every block after the first gets two.
    treas = itertools.cycle(range(118, 129))
    first, rest = 7, 8
    take = first
    while prog:
        block = [prog.pop(0) for _ in range(min(take, len(prog)))]
        if take != first:               # every block after the first gets
            for _ in range(2):          # two treasure rooms, always
                block.append(next(treas))
        blocks.append(block)
        take = rest
    return blocks


def read_d64(path):
    """Pull LEVEL 001 .. LEVEL 128 out of a .d64, as {number: record}."""
    img = open(path, 'rb').read()
    def spt(t):
        return 21 if t < 18 else 19 if t < 25 else 18 if t < 31 else 17
    def off(t, s):
        return sum(spt(x) * 256 for x in range(1, t)) + s * 256
    def chain(t, s):
        out = bytearray()
        seen = set()
        while t and (t, s) not in seen:
            seen.add((t, s))
            o = off(t, s)
            nt, ns = img[o], img[o + 1]
            out += img[o + 2:o + 256] if nt else img[o + 2:o + 1 + ns]
            t, s = nt, ns
        return bytes(out)
    levels = {}
    t, s = 18, 1
    seen = set()
    while (t, s) not in seen:
        seen.add((t, s))
        o = off(t, s)
        for i in range(8):
            e = o + 2 + i * 32
            if not img[e]:
                continue
            name = bytes(img[e + 3:e + 19]).replace(b'\xa0', b'').decode('latin1')
            if name.startswith('LEVEL'):
                try:
                    n = int(name.split()[1])
                except (IndexError, ValueError):
                    continue
                levels[n] = chain(img[e + 1], img[e + 2])[2:]
        if img[o] == 0:
            break
        t, s = img[o], img[o + 1]
    return levels


def build_blocks(leveldir, d64=None):
    from_disk = read_d64(d64) if d64 else None
    out = []
    for block in layout():
        buf = bytearray()
        for n in block:
            if from_disk is not None:
                if n not in from_disk:
                    sys.exit('the disk has no LEVEL %03d' % n)
                raw = from_disk[n]
            else:
                path = os.path.join(leveldir, 'LEVEL_%03d.prg' % n)
                raw = open(path, 'rb').read()[2:]
            # use the length the record declares, not the length of the
            # file: an extracted .prg can carry trailing bytes, and those
            # would push every later slot out of alignment
            n_bytes = raw[0] | ((raw[2] >> 7) << 8)
            rec = raw[:n_bytes]
            if len(rec) > SLOT:
                sys.exit('LEVEL_%03d is %d bytes, too big for a %d-byte slot'
                         % (n, len(rec), SLOT))
            buf += rec + bytes(SLOT - len(rec))
        # the tape pads a short block out to ten slots
        while len(buf) < 10 * SLOT and len(block) > 7:
            buf += bytes(SLOT)
        out.append(bytes(buf))
    return out


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
    ap.add_argument('--out', metavar='DIR', default='blocks',
                    help='directory to write the blocks A .. O into')
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
    blocks = build_blocks(None if is_disk else src, src if is_disk else None)
    names = 'ABCDEFGHIJKLMNO'[:len(blocks)]
    os.makedirs(args.out, exist_ok=True)
    for nm, b in zip(names, blocks):
        open(os.path.join(args.out, nm), 'wb').write(
            bytes([LOAD_ADDR & 0xFF, LOAD_ADDR >> 8]) + b)
    print('wrote %d blocks to %s, %d bytes of level data'
          % (len(blocks), args.out, sum(len(b) for b in blocks)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
