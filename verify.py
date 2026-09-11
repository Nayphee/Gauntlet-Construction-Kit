#!/usr/bin/env python3
"""Check the generated level set from every angle that matters.

Nothing here trusts the generator's intentions: every check reads the
encoded bytes back, or drives the editor's own machine code over them.
"""
import json, statistics, sys
import os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'tools'))
sys.path.insert(0, os.path.join(HERE, 'tools'))
from sim6502 import Sim
import genlevels as GL
import gauntlet_dd as G

S = json.load(open(os.path.join(HERE, 'symbols.json')))
core = open(os.path.join(HERE, 'gcore.prg'), 'rb').read()
ORG, CODE = core[0] | core[1] << 8, core[2:]
# Take the directory as an argument.  It was hardcoded, so generating into
# one directory and verifying another quietly checked the previous set and
# reported a fault that had already been fixed.
_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'levels')
LEV = os.path.join(_dir, 'LEVEL_%03d.prg')
print('verifying %s' % _dir)

problems = []


def note(n, what):
    problems.append('LEVEL %03d: %s' % (n, what))


def editor_run(data, n):
    """decode, count, checksum, re-encode, decode, checksum"""
    s = Sim()
    s.load(ORG, CODE)
    s.mem[0x01FF] = s.mem[0x01FE] = 0xFF
    s.load(S['buf'], data[2:])

    def call(entry):
        s.sp, s.pc = 0xFD, entry
        k = 0
        while s.pc:
            s.step()
            k += 1
            if k > 9_000_000:
                raise RuntimeError('level %d hung the editor' % n)

    call(S['decode'])
    if s.mem[S['ldst']]:
        return None
    call(S['count'])
    call(S['cksum'])
    before = (s.mem[S['cklo']], s.mem[S['ckhi']])
    counts = (s.mem[S['nstart']], s.mem[S['ntrap']], s.mem[S['nwall']])
    call(S['encode'])
    if s.mem[S['ldst']]:
        return 'cannot be saved'
    flags = s.mem[S['buf'] + 1]
    call(S['decode'])
    call(S['cksum'])
    after = (s.mem[S['cklo']], s.mem[S['ckhi']])
    return before, after, counts, flags


sizes, kinds_seen = [], []
for n in range(1, 129):
    data = open(LEV % n, 'rb').read()
    sizes.append(len(data) - 2)
    lv = G.decode(data[2:])

    if not GL.playable(lv, 118 <= n <= 127):
        note(n, 'fails the design rules')

    at = {(c % 32, c // 32): k for c, k in lv.objects}
    starts = [p for p, k in at.items() if k == GL.START]
    if len(starts) != 1:
        note(n, '%d start markers' % len(starts))
        continue
    shut = GL.bfs(lv.grid, starts[0])
    traplist = [p for p, k in at.items() if k == 0x2F]
    # A trap-wall stands until a trap is sprung, and then every one goes.
    # Teleporters count here: stepping on one is a way to reach a trap
    # that does not involve walking through a trap-wall, and leaving them
    # out made this stricter than the generator's own rule, so a level
    # could pass there and fail here.
    before = GL.bfs(lv.grid, starts[0], doors_open=True, shoot=True,
                    teleport=True)
    # a teleporter is a way through, so it counts towards reachability
    opened = GL.bfs(lv.grid, starts[0], doors_open=True, shoot=True,
                    teleport=True, sprung=bool(traplist))
    if traplist and not any(p in before for p in traplist):
        note(n, 'no trap can be reached without passing a trap-wall')

    exits = [p for p, k in at.items() if k in (GL.EXIT, 0x37, 0x38)]
    if not (118 <= n <= 128):
        hostile = sum(1 for k in at.values()
                      if 0x40 <= k < 0x70 or 0x20 <= k <= 0x2E)
        if len(at) < 22 or hostile < 8:
            note(n, 'almost nothing in it: %d objects, %d hostile'
                 % (len(at), hostile))

    keys = sum(1 for k in at.values() if k == 0x1f)
    # Doors that gate part of the map must be openable.  A level can have
    # its exit in plain sight and most of its floor shut away; checking
    # only the exit missed eight such levels in one set.  This has to come
    # after keys is set: placed above it, the name still held the previous
    # level's count and the check reported on the wrong level.
    # a name of its own: "shut" is already the plain doors-shut walk that
    # the monster-proximity check below measures against, and reusing it
    # made that check read teleport-inclusive distances, so a monster a
    # whole map away looked like it started on the player
    keyless = GL.bfs(lv.grid, starts[0], doors_open=False, shoot=True,
                     sprung=bool(traplist), teleport=True)
    if opened and len(keyless) < 0.9 * len(opened) and keys == 0:
        # only a fault if a key would actually help: keys_needed returns
        # 99 when the locked part has no route through door barriers at
        # all, and the generator asks the same question before deciding
        # whether to place one
        far = max((c for c in opened if c not in keyless),
                  key=lambda c: opened[c], default=None)
        if far is not None and GL.keys_needed(lv.grid, starts[0], [far]) < 90:
            note(n, 'doors lock %d%% of the map away and there is no key'
                 % (100 - 100 * len(keyless) // max(1, len(opened))))
    need = GL.keys_needed(lv.grid, starts[0], exits)
    # 99 means there is no route through doors at all - a teleporter-only
    # exit, which the arcade uses on nine of its levels
    if need < 90:
        if need > keys:
            note(n, 'the way out needs %d keys and the level has %d'
                 % (need, keys))
        elif need > 0 and keys < need + (1 if GL.count_barriers(lv.grid) > need
                                            else 0) \
                and GL.THEMED.get(n) not in (GL.theme_alldoors, GL.theme_keyring):
            # a key spent on the wrong door must not strand the player, so
            # a level with more barriers than the exit needs carries a spare
            note(n, 'the way out needs %d keys, other doors exist, and the '
                    'level carries only %d' % (need, keys))
        elif (need > 0 and keys < need
              and GL.THEMED.get(n) not in (GL.theme_alldoors,
                                           GL.theme_keyring)):
            # Spares are intended now: the rule is that a level carries at
            # least what the way out costs, not exactly that.  Demanding
            # exactly kept the set at a third of the arcade's key count.
            note(n, 'the way out needs %d keys but the level carries %d'
                 % (need, keys))
    elif not any(e in opened for e in exits):
        note(n, 'the way out cannot be reached at all')
    walkable = sum(1 for v in lv.grid if v == 0 or v >= 0x13)
    if len(opened) < 0.9 * walkable:
        note(n, 'only %d of %d walkable cells reachable' % (len(opened), walkable))
    # measured with doors shut and breakable walls standing: a caged pack
    # near the start can only reach the player if the player opens it
    for p, k in at.items():
        if 0x40 <= k < 0x70 and p in shut and shut[p] <= 4:
            note(n, 'a monster starts on top of the player')
            break
    # neither shipped set places a stat potion on any level; the game
    # supplies them itself, so one here is a mistake rather than a design
    if any(0x19 <= k <= 0x1E for k in at.values()):
        note(n, 'places a stat potion, which no shipped level does')
    if any(k == 0x32 for k in at.values()):
        note(n, 'contains $32, which the game treats as solid wall')
    tel = [p for p, k in at.items() if k == 0x30]
    for a in tel:
        # the game searches a 16x10 window for a destination and needs two
        # the window comes from the generator rather than a copy of it here,
        # which is how this check went stale when the spacing changed
        if not any(b is not a
                   and abs(a[0] - b[0]) <= GL.TELE_DX + 1
                   and abs(a[1] - b[1]) <= GL.TELE_DY + 1
                   for b in tel):
            note(n, 'a teleporter has no partner on screen')
            break

    got = editor_run(data, n)
    if got is None:
        note(n, 'the editor cannot decode it')
        continue
    if got == 'cannot be saved':
        note(n, 'the editor cannot save it')
        continue
    before, after, (ns, nt, nw), flags = got
    if before != after:
        note(n, 'does not survive an editor load and save')
    if ns != 1:
        note(n, 'the editor counts %d starts' % ns)
    if (nt > 0) != (nw > 0):
        note(n, 'traps %d but trap-walls %d' % (nt, nw))
    if flags != data[3]:
        note(n, 'the flags byte is lost on save')

print('checked 128 levels: %s' % ('\n   '.join([''] + problems) if problems
                                  else 'no problems'))
print()
print('   sizes %d-%d bytes, %d average, ceiling 511' %
      (min(sizes), max(sizes), sum(sizes) // len(sizes)))
sys.exit(1 if problems else 0)
