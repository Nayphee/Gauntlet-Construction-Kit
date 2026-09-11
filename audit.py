#!/usr/bin/env python3
"""Measure a level set against the arcade original across every feature
this generator tries to produce, in one pass.

    python3 audit.py levels
    python3 audit.py levels --ref /path/to/arcade/levels

Tuning one number at a time is how a set ends up right in the place you
last looked and wrong everywhere else. This prints the lot, so a change
that fixes doors and quietly halves the generators shows up the same day.

Every figure is per level unless it says otherwise. The arcade column is
the reference; 'off' is how far this set sits from it, and anything past
25% is flagged.

The reference levels are not included in this repository - they are the
original game's, extracted from its disk - so with nothing at --ref the
arcade column prints as '-' and only this set's figures are shown. To
compare, point --ref at a directory of LEVEL_nnn.prg files pulled from an
arcade Gauntlet disk with gauntlet_dd.py.
"""
import argparse
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import genlevels as GL
import gauntlet_dd as G

MON = lambda k: 0x40 <= k < 0x70
GEN = lambda k: 0x20 <= k <= 0x2E


def load(path):
    out = []
    for n in range(1, 129):
        f = os.path.join(path, 'LEVEL_%03d.prg' % n)
        if os.path.exists(f):
            out.append(G.decode(open(f, 'rb').read()[2:]))
    return out


def neighbours(cells):
    """Mean count of same-code orthogonal neighbours - how clumped it is."""
    acc = []
    for c, k in cells.items():
        acc.append(sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                       if cells.get((c[0] + dx, c[1] + dy)) == k))
    return statistics.mean(acc) if acc else 0.0


def measure(levels):
    m = {}
    per = lambda f: statistics.mean(f([k for _, k in l.objects]) for l in levels)
    m['food'] = per(lambda x: sum(1 for k in x if k in (0x14, 0x15)))
    m['magic'] = per(lambda x: sum(1 for k in x if k in (0x16, 0x17)))
    m['treasure'] = per(lambda x: sum(1 for k in x if k == 0x13))
    m['monsters'] = per(lambda x: sum(1 for k in x if MON(k)))
    m['generators'] = per(lambda x: sum(1 for k in x if GEN(k)))
    m['keys'] = per(lambda x: sum(1 for k in x if k == 0x1F))
    m['traps'] = per(lambda x: sum(1 for k in x if k == 0x2F))
    m['teleporters'] = per(lambda x: sum(1 for k in x if k == 0x30))
    m['door cells'] = statistics.mean(
        sum(1 for v in l.grid if v in (0x11, 0x12)) for l in levels)
    m['wall cells'] = statistics.mean(
        sum(1 for v in l.grid if 0 < v < 0x13 or v == 0x90) for l in levels)

    mon_n, gen_n, walks, twist, dead, corr, frac = [], [], [], [], [], [], []
    locked = sealed = noexit = 0
    for l in levels:
        at = {(c % 32, c // 32): k for c, k in l.objects}
        mon_n.append(neighbours({c: k for c, k in at.items() if MON(k)}))
        gen_n.append(neighbours({c: k for c, k in at.items() if GEN(k)}))
        st = [q for q, k in at.items() if k == 0x3F]
        ex = [q for q, k in at.items() if k in (0x36, 0x37, 0x38)]
        if not st or not ex:
            noexit += 1
            continue
        walk = GL.bfs(l.grid, st[0], doors_open=True, shoot=True,
                      sprung=True, teleport=True)
        got = [walk[e] for e in ex if e in walk]
        if got:
            steps = min(got)
            walks.append(steps)
            e = min(((walk[e], e) for e in ex if e in walk))[1]
            straight = abs(e[0] - st[0][0]) + abs(e[1] - st[0][1])
            if straight:
                twist.append(steps / straight)
        need = GL.keys_needed(l.grid, st[0], ex)
        if 0 < need < 90:
            locked += 1
        foot = GL.bfs(l.grid, st[0], doors_open=True, shoot=True, sprung=True)
        if not any(e in foot for e in ex):
            sealed += 1
        # only levels that actually have doors: including the rest puts a
        # pile of 1.0s in the sample and the median stops meaning anything
        if any(v in (0x11, 0x12) for v in l.grid):
            shut = GL.bfs(l.grid, st[0], doors_open=False, shoot=True,
                          sprung=True, teleport=True)
            if walk:
                frac.append(len(shut) / len(walk))
        floor = {(i % 32, i // 32) for i, v in enumerate(l.grid)
                 if (v == 0 or v >= 0x13 or v == 0x90) and v != 0x33}
        nb = lambda c: sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                           if (c[0] + dx, c[1] + dy) in floor)
        counts = [nb(c) for c in floor]
        if counts:
            dead.append(sum(1 for x in counts if x == 1))
            corr.append(100 * sum(1 for x in counts if x == 2) / len(counts))

    m['monster clumping'] = statistics.mean(mon_n)
    m['generator clumping'] = statistics.mean(gen_n)
    m['walk to exit'] = statistics.median(walks) if walks else 0
    m['path over straight'] = statistics.median(twist) if twist else 0
    m['dead ends'] = statistics.mean(dead) if dead else 0
    m['corridor %'] = statistics.mean(corr) if corr else 0
    m['reachable before key %'] = 100 * statistics.median(frac) if frac else 0
    m['levels: locked exit'] = locked
    m['levels: sealed exit'] = sealed
    m['levels: no exit'] = noexit
    return m


ORDER = ['food', 'magic', 'treasure', 'monsters', 'generators', 'keys',
         'traps', 'teleporters', 'door cells', 'wall cells',
         'monster clumping', 'generator clumping',
         'walk to exit', 'path over straight', 'dead ends', 'corridor %',
         'reachable before key %',
         'levels: locked exit', 'levels: sealed exit', 'levels: no exit']


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('levels', nargs='?', default=os.path.join(HERE, 'levels'))
    ap.add_argument('--ref', default=os.path.join(HERE, 'origlevels'),
                    help='the reference set to measure against')
    ap.add_argument('--tolerance', type=float, default=25.0,
                    help='flag anything this many percent off the reference')
    args = ap.parse_args()

    mine = measure(load(args.levels))
    if os.path.isdir(args.ref):
        ref = measure(load(args.ref))
    else:
        ref = None

    print('%-24s %9s %9s %8s' % ('', 'arcade', 'this set', 'off'))
    flagged = 0
    for k in ORDER:
        a = ref[k] if ref else float('nan')
        b = mine[k]
        if ref and a:
            off = 100 * (b - a) / a
            mark = '  <--' if abs(off) > args.tolerance else ''
            if mark:
                flagged += 1
            print('%-24s %9.1f %9.1f %7.0f%%%s' % (k, a, b, off, mark))
        else:
            print('%-24s %9s %9.1f' % (k, '-', b))
    if ref:
        print('\n%d of %d measures are more than %.0f%% from the arcade'
              % (flagged, len(ORDER), args.tolerance))
    return 0


if __name__ == '__main__':
    sys.exit(main())
