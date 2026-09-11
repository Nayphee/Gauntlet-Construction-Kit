#!/usr/bin/env python3
"""Generate a complete, original 128-level set for Gauntlet: Deeper Dungeons.

Nothing here is copied from the shipped levels.  Layouts come from recursive
division, which gives a fully connected maze by construction, so every level
is guaranteed walkable from its start to an exit.

The format's limits shape the design:

  * a level is at most 511 bytes, and its vector section at most 255, so a
    wall run costs 3 bytes and about 85 runs is the ceiling
  * the object section must not be empty
  * exactly one start marker, or the game inherits the previous level's
  * levels 1-7 play in order, 8-117 are drawn at random, 118-128 are the
    treasure rooms, which carry no monsters and no traps

Every generated level is encoded, decoded and flood-filled before it is
accepted; anything that fails is regenerated with a different seed.
"""
import argparse
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gauntlet_dd as G

W = H = 32
WALL_PEN, DOORV_PEN, DOORH_PEN = 0xE0, 0x40, 0x80

TREASURE, CIDER, FOOD = 0x13, 0x14, 0x15
MAGIC_B, MAGIC_Y, AMULET = 0x16, 0x17, 0x18
# $19-$1E are the six stat potions.  Neither shipped set places a single
# one on any of its 256 levels, and the game hands them out itself during
# play, so putting them in a level is at best redundant and at worst why a
# potion turns up where the designer never put one.  The editor still
# offers them; the generator does not use them.
POTIONS = list(range(0x19, 0x1F))
KEY, TRAP, TELEPORT, POISON = 0x1F, 0x2F, 0x30, 0x31
EXIT, START = 0x36, 0x3F
GHOST, GRUNT, DEMON, LOBBER, SORCERER, DEATH = 0x40, 0x48, 0x50, 0x58, 0x60, 0x68
# How enclosed each family wants to be, measured off the arcade: the mean
# number of open sides around one of them.  $58 are the lobbers - they
# throw over walls, so the arcade puts them behind one, at 2.16 open sides
# with 59% of them walled in on two sides or more.  $68, the Deaths, are
# caged at 2.38.  The ghosts and grunts stand in the open at 3.1.  This
# generator had every family at 3.1 regardless, so a lobber was just a
# weak monster in a field.
FAMILY_COVER = {0x40: 3.09, 0x48: 3.02, 0x50: 2.74,
                0x58: 2.16, 0x60: 2.65, 0x68: 2.38}

FAMILIES = [GHOST, GRUNT, DEMON, LOBBER, SORCERER]


# ----------------------------------------------------------------------
# Wall runs
# ----------------------------------------------------------------------

# Step per heading.  The model used to know only E and S, so every
# diagonal run collapsed to its starting cell: the map the generator
# reasoned about had no diagonals in it at all, while the encoded level
# did.
STEP = {'N': (0, -1), 'NE': (1, -1), 'E': (1, 0), 'SE': (1, 1),
        'S': (0, 1), 'SW': (-1, 1), 'W': (-1, 0), 'NW': (-1, -1)}


class Walls:
    """Wall segments, kept as runs so they encode three bytes each."""

    def __init__(self):
        self.runs = []                    # (pen, x, y, direction, length)

    def h(self, x, y, n, pen=WALL_PEN):
        if n > 0 and 0 <= x < W and 0 <= y < H:
            self.runs.append((pen, x, y, 'E', min(n, W - x)))

    def v(self, x, y, n, pen=WALL_PEN):
        if n > 0 and 0 <= x < W and 0 <= y < H:
            self.runs.append((pen, x, y, 'S', min(n, H - y)))

    def cmds(self):
        """A POINT plots one cell and a DRAW plots n *more*, so a run of L
        cells is a POINT plus a DRAW of L-1.  Getting this wrong makes every
        run one cell too long, which quietly seals the gaps in the maze.

        The decoder splits the byte stream into groups sharing a top-3-bit
        field, so a POINT whose pen shares that field with the DRAW just
        emitted merges with it and the whole level misparses.  Runs are
        therefore emitted in an order that never puts those two together:
        a door pen of $80 must not follow a southward DRAW, which is also
        field 4."""
        DIRFIELD = {'N': 0, 'NE': 1, 'E': 2, 'SE': 3,
                    'S': 4, 'SW': 5, 'W': 6, 'NW': 7}
        # Doors go first.  A door pen of $80 is field 4 and so is a
        # southward DRAW, and if the doors are left until last there is
        # nothing else to separate them with.  Emitted first, they precede
        # every DRAW and merge only with each other, which is harmless
        # because a run of POINTs decodes as POINTs.
        # Doors go first, but the same greedy rule has to apply among them:
        # a vertical door pen is field 2 and a southward DRAW is field 4, so
        # two door runs in the wrong order merge exactly as a door and a
        # wall would.  Skipping the check inside the door group threw out
        # every level with a lot of doors on it.
        doors = [r for r in self.runs if r[0] in (DOORV_PEN, DOORH_PEN)]
        walls = [r for r in self.runs if r[0] not in (DOORV_PEN, DOORH_PEN)]
        ordered = []
        last = None
        for group in (doors, walls):
            pending = list(group)
            while pending:
                pick = next((i for i, r in enumerate(pending)
                             if (r[0] >> 5) != last), 0)
                r = pending.pop(pick)
                ordered.append(r)
                last = DIRFIELD[r[3]] if r[4] > 1 else (r[0] >> 5)
        # A DRAW is one byte and continues from the cursor, so a wall drawn
        # as a continuous polyline costs 2 + n bytes for n segments where
        # this emitter pays 3 a segment.  That is how the arcade fits 50
        # segments in 105 bytes.  Chaining independent runs after the fact
        # was tried and bought about a byte a level - runs seldom happen to
        # begin where the cursor stands - and risked the decoder's rule of
        # one DRAW per same-field group.  The saving is real but it has to
        # come from generating walls as paths, not from the emitter.
        out = []
        for pen, x, y, d, n in ordered:
            while n > 0:
                take = min(n, 33)              # a POINT plus a DRAW of 32
                out.append(('POINT', pen, x, y))
                if take > 1:
                    out.append(('DRAW', d, take - 1))
                dx, dy = STEP[d]
                x, y = x + dx * take, y + dy * take
                n -= take
        return out

    def cells(self):
        """Which cells the runs cover, for the connectivity check."""
        got = set()
        for pen, x, y, d, n in self.runs:
            dx, dy = STEP[d]
            for i in range(n):
                cx, cy = x + dx * i, y + dy * i
                if 0 <= cx < W and 0 <= cy < H:
                    got.add((cx, cy))
        return got


# ----------------------------------------------------------------------
# Layout
# ----------------------------------------------------------------------

def divide(rng, walls, x0, y0, x1, y1, depth, doors):
    """Recursive division.  Walls go on even coordinates and gaps on odd
    ones: without that a child wall can run alongside its parent's gap and
    seal it, which silently cuts the maze in two."""
    w, h = x1 - x0, y1 - y0
    if depth <= 0 or (w < 5 and h < 5):
        return
    vertical = w > h if w != h else rng.random() < 0.5
    if vertical:
        if w < 5:
            return
        evens = [x for x in range(x0 + 2, x1 - 1) if x % 2 == 0]
        odds = [y for y in range(y0, y1) if y % 2 == 1]
        if not evens or not odds:
            return
        wx = rng.choice(evens)
        gap = rng.choice(odds)
        walls.v(wx, y0, gap - y0)
        walls.v(wx, gap + 1, y1 - gap - 1)
        if doors is not None and rng.random() < 0.30:
            doors.append((wx, gap, DOORV_PEN))
        divide(rng, walls, x0, y0, wx, y1, depth - 1, doors)
        divide(rng, walls, wx + 1, y0, x1, y1, depth - 1, doors)
    else:
        if h < 5:
            return
        evens = [y for y in range(y0 + 2, y1 - 1) if y % 2 == 0]
        odds = [x for x in range(x0, x1) if x % 2 == 1]
        if not evens or not odds:
            return
        wy = rng.choice(evens)
        gap = rng.choice(odds)
        walls.h(x0, wy, gap - x0)
        walls.h(gap + 1, wy, x1 - gap - 1)
        if doors is not None and rng.random() < 0.30:
            doors.append((gap, wy, DOORH_PEN))
        divide(rng, walls, x0, y0, x1, wy, depth - 1, doors)
        divide(rng, walls, x0, wy + 1, x1, y1, depth - 1, doors)


def punch(rng, walls, n):
    """Cut extra doorways through interior walls.

    Recursive division leaves one gap per split, so the rooms form a tree:
    every room is a dead end, and in a game won by running in circles while
    shooting that is fatal.  Extra openings turn the tree into a network, so
    a room being overrun always has another way out.  Runs 0 and 1 are the
    map's own edge and are left alone."""
    for _ in range(n):
        long_runs = [i for i, r in enumerate(walls.runs[2:], start=2) if r[4] >= 6]
        if not long_runs:
            return
        i = rng.choice(long_runs)
        pen, x, y, d, ln = walls.runs[i]
        cut = rng.randrange(2, ln - 1)             # not at either end
        walls.runs[i] = (pen, x, y, d, cut)
        dx, dy = STEP[d]                           # diagonals split too
        walls.runs.append((pen, x + dx * (cut + 1), y + dy * (cut + 1),
                           d, ln - cut - 1))


def remove_cell(walls, cell):
    """Take one cell out of whichever run covers it, splitting the run."""
    for i, (pen, x, y, d, ln) in enumerate(walls.runs):
        dx, dy = STEP[d]
        cells = [(x + dx * k, y + dy * k) for k in range(ln)]
        if cell in cells:
            k = cells.index(cell)
            walls.runs.pop(i)
            if k > 0:
                walls.runs.append((pen, x, y, d, k))
            if k + 1 < ln:
                nx, ny = cells[k + 1]
                walls.runs.append((pen, nx, ny, d, ln - k - 1))
            return True
    return False


def connect(walls, start, doorcells):
    """Open a way into anything the player cannot otherwise reach.

    A layout that walls off a third of the map is not a challenge, it is
    wasted screen: the shipped levels leave 92% of their open space
    reachable, and a chamber grid with random gaps can easily leave far
    less.  Rather than rejecting those layouts, punch through."""
    for _ in range(40):
        open_ = set(open_cells(walls, doorcells))
        if start not in open_:
            return False
        got = reachable(start, walls, doorcells)
        orphans = open_ - got
        if not orphans:
            return True
        wall = walls.cells() - doorcells
        best = None
        for c in wall:
            if c[0] in (0, W - 1) or c[1] in (0, H - 1):
                continue                          # never breach the edge
            nbrs = [(c[0] + dx, c[1] + dy) for dx, dy in
                    ((1, 0), (-1, 0), (0, 1), (0, -1))]
            if any(p in got for p in nbrs) and any(p in orphans for p in nbrs):
                best = c
                break
        if best is None or not remove_cell(walls, best):
            return False
    return True


def arena(rng, walls):
    """A landmark: one open chamber, walled but with several ways in, that
    the level can be remembered by and the richest cache put in."""
    w, h = rng.randint(7, 10), rng.randint(6, 8)
    x0 = rng.randint(6, W - w - 6)
    y0 = rng.randint(6, H - h - 6)
    keep = []
    for r in walls.runs[2:]:
        pen, x, y, d, ln = r
        cells = [(x + i, y) if d == 'E' else (x, y + i) for i in range(ln)]
        if any(x0 - 1 <= c[0] <= x0 + w and y0 - 1 <= c[1] <= y0 + h for c in cells):
            continue                               # clear the site
        keep.append(r)
    walls.runs[2:] = keep
    gaps = {rng.randrange(1, w - 1) for _ in range(2)}
    for i in range(w):                             # walls with several doors
        if i not in gaps:
            walls.h(x0 + i, y0, 1)
            walls.h(x0 + i, y0 + h, 1)
    gaps = {rng.randrange(1, h - 1) for _ in range(2)}
    for i in range(1, h):
        if i not in gaps:
            walls.v(x0, y0 + i, 1)
            walls.v(x0 + w, y0 + i, 1)
    return (x0 + w // 2, y0 + h // 2)


# The game only looks for a destination teleporter inside the 16x10 window
# it is drawing ($AF78 walks that many cells from the camera origin), and it
# needs at least two in the list ($8D23).  A teleporter with no partner on
# screen does nothing at all, so they go down in pairs, close enough that
# standing on one always has the other in view.
# The search at $AF78 starts from $87BC/$87BE - the *screen* scroll
# position, not the teleporter - and scans the visible 16 x 10 cells.  So
# the destination has to be on screen when you step on the source, and
# since the screen follows the player that means within about seven
# columns and four rows of the pad.  A pair further apart than that simply
# does nothing when you stand on it, which is what 40% of this set's pads
# were doing.  91% of the arcade's have a partner inside that box.
TELE_DX, TELE_DY = 7, 4
TELE_MIN = 6           # far enough that stepping on one is worth doing
TELE_SAVE = 20         # steps an open-to-open pair must skip to be worth it


def teleport_pairs(rng, objs, pool, npairs, walk=None, sealed=None):
    """Place teleporters two at a time, each pair within one screen but not
    on top of each other.

    The game finds a destination by scanning a window around the source, so
    a partner has to be near - but near enough to walk to in a few steps is
    a teleporter that saves nobody anything.  The shipped pairs sit about
    nineteen cells apart, comfortably inside the window and far enough to be
    worth stepping on."""
    # A teleporter earns its place by landing somewhere a key would
    # otherwise cost: inside a locked region or a vault.  75% of the
    # arcade's pads sit in a region that cannot be walked to without a
    # key; only 6% of this generator's did, because it paired cells
    # anywhere on the open floor.
    inside = [c for c in (sealed or []) if c not in objs]
    rng.shuffle(inside)
    placed = 0
    for _ in range(npairs):
        while pool or inside:
            # start from a locked cell where there is one, so the pair has
            # somewhere worth arriving at
            # A teleporter does one of two jobs: it lands you inside a
            # locked region, saving a key, or it skips a long walk.  Take
            # the locked cells first; when they run out an open pair is
            # still worth placing, but only if the walk between its ends
            # is long enough to be worth stepping on - the bar below is
            # what stops a pad pair sitting a few steps apart.
            if inside:
                a = inside.pop()
            elif pool:
                a = pool.pop()
            else:
                break
            if objs.get(a) in {START, EXIT, 0x37, 0x38, KEY}:
                continue
            mates = [c for c in pool if c not in objs
                     and abs(c[0] - a[0]) + abs(c[1] - a[1]) >= TELE_MIN
                     and abs(c[0] - a[0]) <= TELE_DX
                     and abs(c[1] - a[1]) <= TELE_DY]
            if walk is not None and a in walk:
                # Prefer pairs with something in the way.  A teleporter whose
                # two ends are a short stroll apart saves nobody anything;
                # what makes one worth stepping on is the wall between.  This
                # is a preference rather than a requirement: demanding it
                # outright leaves the generator hunting for partners that may
                # not exist on this map, and it spins.
                better = [c for c in mates
                          if c in walk
                          and abs(walk[a] - walk[c]) >=
                              3 * (abs(c[0] - a[0]) + abs(c[1] - a[1])) // 2]
                if better:
                    mates = better
                elif a not in (sealed or ()):
                    # An open pair has to earn its place by the walk it
                    # skips.  A locked end is worth a pad on its own -
                    # arriving there saves a key - but two pads on open
                    # floor a few steps apart save nobody anything.
                    continue
            if not mates:
                continue
            b = rng.choice(mates)
            pool.remove(b)
            objs[a] = objs[b] = TELEPORT
            placed += 2
            break
    return placed


BREAKABLE = 0x33


def close_ends(walls, run, start, doorcells, budget=4):
    """Extend a wall run until both ends meet something.

    A run that stops in open floor makes a barrier you can walk round the
    end of.  Refusing to convert those leaves the level with almost no
    doors at all; building the missing wall instead keeps the door and
    makes it mean something.

    The extension is only kept if the map still hangs together without it
    being opened - a wall that seals off a quarter of the level is a worse
    fault than a short door."""
    pen, x, y, d, ln = run
    dx, dy = STEP[d]
    added = []
    for sign, base in ((-1, (x, y)), (1, (x + dx * (ln - 1), y + dy * (ln - 1)))):
        step = (dx * sign, dy * sign)
        grown = []
        for k in range(1, budget + 1):
            p = (base[0] + step[0] * k, base[1] + step[1] * k)
            if not (0 <= p[0] < W and 0 <= p[1] < H):
                grown = []                 # ran off the map: nothing to meet
                break
            if p in walls.cells():
                break                      # met something
            grown.append(p)
        else:
            grown = []                     # never met anything within budget
        first = len(walls.runs)
        wall_runs(walls, grown)
        added.extend(range(first, len(walls.runs)))
    if not added:
        return True
    before = reachable(start, walls, doorcells | {(x + dx * k, y + dy * k)
                                                  for k in range(ln)})
    if len(before) < 340:
        for i in sorted(added, reverse=True):
            del walls.runs[i]
        return False
    return True


def ends_meet(walls, run):
    """Does this wall run finish against something at both ends?

    A run that stops in open floor makes a barrier you can walk round the
    end of, and dressing it as doors makes a door that plainly does not
    reach - the level looks unfinished.  Punching gaps and splitting runs
    leaves plenty of these, so check before converting rather than trying
    to tidy them up afterwards."""
    pen, x, y, d, ln = run
    dx, dy = STEP[d]
    solid = walls.cells()
    for end in ((x - dx, y - dy), (x + dx * ln, y + dy * ln)):
        if not (0 <= end[0] < W and 0 <= end[1] < H):
            continue                       # the map edge counts as solid
        if end not in solid:
            return False
    return True


def ring_of(cells):
    """The cells that enclose a blob, four-connected."""
    inside = set(cells)
    out = set()
    for c in inside:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (c[0] + dx, c[1] + dy)
            if q not in inside and 0 <= q[0] < W and 0 <= q[1] < H:
                out.add(q)
    return sorted(out)


def seal_pockets(rng, walls, start, doorcells, count):
    """Find pockets that already have one way in, and shut that way.

    Dropping a new chamber into a finished maze almost always severs
    something: the map is too fragmented to find a rectangle whose rim can
    be walled without cutting a corridor.  Growing a region out from a dead
    end until its boundary is a single cell finds a pocket that is already
    sealed but for one square, so putting a door there cannot cut the map
    up - it only makes what was a cul-de-sac into a room worth opening."""
    room = reachable(start, walls, doorcells)
    nbr = lambda c: [(c[0] + dx, c[1] + dy) for dx, dy in
                     ((1, 0), (-1, 0), (0, 1), (0, -1))]
    ends = [c for c in room
            if c != start and sum(1 for p in nbr(c) if p in room) == 1]
    rng.shuffle(ends)
    made = []
    taken = set()
    for e in ends:
        if len(made) >= count:
            break
        if e in taken:
            continue
        region = {e}
        while len(region) < 14:
            edge = {p for c in region for p in nbr(c)
                    if p in room and p not in region}
            if not edge:
                break
            if len(edge) == 1 and len(region) >= 3:
                cut = edge.pop()
                if cut != start and cut not in taken:
                    made.append((cut, sorted(region)))
                    taken |= region | {cut}
                break
            region |= edge
    return made


def open_cells(walls, doorcells):
    """Every cell a player can stand on."""
    blocked = walls.cells() - doorcells
    # the game draws the top row and left column itself
    return [(x, y) for y in range(1, H) for x in range(1, W)
            if (x, y) not in blocked]


def walk_dist(start, walls, doorcells, passable_doors=True):
    """Step distances from start, so the exit can be chosen for the length
    of the walk rather than the distance across the paper.

    Placing the exit last, on the cell farthest from the start, gives every
    level the same shape: the walk to it is the straight line to it.  The
    arcade's walk is about two and a half times its straight line, because
    the exit is somewhere the map makes you go round."""
    blocked = walls.cells()
    if passable_doors:
        blocked = blocked - doorcells
    dist = {start: 0}
    edge = [start]
    while edge:
        nxt = []
        for x, y in edge:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + dx, y + dy)
                if (1 <= n[0] < W and 1 <= n[1] < H
                        and n not in dist and n not in blocked):
                    dist[n] = dist[(x, y)] + 1
                    nxt.append(n)
        edge = nxt
    return dist


def reachable(start, walls, doorcells, passable_doors=True):
    blocked = walls.cells()
    if passable_doors:
        blocked = blocked - doorcells
    seen = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if (1 <= n[0] < W and 1 <= n[1] < H
                    and n not in seen and n not in blocked):
                seen.add(n)
                stack.append(n)
    return seen


# ----------------------------------------------------------------------
# Levels
# ----------------------------------------------------------------------

def chambers(rng, walls, doors):
    """A grid of small rooms with doorways: closer to the shipped levels'
    cell and comb structures than an open maze is."""
    step = rng.choice([5, 6, 7])
    for x in range(1 + step, W - 1, step):
        gaps = {rng.randrange(1, H - 1) for _ in range(1 + H // (step * 2))}
        y = 1
        for g in sorted(gaps) + [H - 1]:
            if g > y:
                walls.v(x, y, g - y)
            y = g + 1
            if doors is not None and rng.random() < 0.12:
                doors.append((x, g, DOORV_PEN))
    for y in range(1 + step, H - 1, step):
        gaps = {rng.randrange(1, W - 1) for _ in range(1 + W // (step * 2))}
        x = 1
        for g in sorted(gaps) + [W - 1]:
            if g > x:
                walls.h(x, y, g - x)
            x = g + 1
            if doors is not None and rng.random() < 0.12:
                doors.append((g, y, DOORH_PEN))


def comb(rng, walls):
    """Parallel corridors joined at alternate ends: long sightlines, which
    reward shooting down a lane before anything reaches you."""
    step = rng.choice([3, 4])
    for i, x in enumerate(range(2 + step, W - 2, step)):
        if i % 2:
            walls.v(x, 1, H - 4)
        else:
            walls.v(x, 4, H - 5)


def rings(rng, walls):
    """Concentric rectangles, each with a way through."""
    for i in range(1, 5):
        m = 2 + i * 3
        w, h = W - 2 * m - 1, H - 2 * m - 1
        if w < 4 or h < 4:
            break
        gx, gy = rng.randrange(1, w), rng.randrange(1, h)
        walls.h(m, m, gx)
        walls.h(m + gx + 1, m, w - gx)
        walls.h(m, m + h, w + 1)
        walls.v(m, m + 1, gy)
        walls.v(m, m + gy + 1, h - gy - 1)
        walls.v(m + w, m + 1, h - 1)


def spiral(rng, walls):
    """One long corridor wound in on itself: no choices, just distance."""
    x0, y0, x1, y1 = 2, 2, W - 3, H - 3
    while x1 - x0 > 3 and y1 - y0 > 3:
        walls.h(x0, y0, x1 - x0)
        walls.v(x1, y0, y1 - y0)
        walls.h(x0 + 3, y1, x1 - x0 - 2)
        walls.v(x0 + 3, y0 + 3, y1 - y0 - 3)
        x0, y0, x1, y1 = x0 + 3, y0 + 3, x1 - 3, y1 - 3


def cavern(rng, walls):
    """Scattered lumps rather than rooms: open, awkward, no straight lines
    to hide behind."""
    for _ in range(rng.randint(14, 22)):
        x, y = rng.randrange(2, W - 4), rng.randrange(2, H - 4)
        for k in range(rng.randint(1, 3)):
            if rng.random() < 0.5:
                walls.h(x, min(H - 2, y + k), rng.randint(2, 6))
            else:
                walls.v(min(W - 2, x + k), y, rng.randint(2, 6))


def diag_run(walls, x, y, d, n, pen=WALL_PEN):
    """One diagonal wall, clipped to the map.  The turtle takes SE and NE
    headings as readily as E and S; NW is the one that will not survive the
    encoder's grammar, so it is never used."""
    dx, dy = (1, 1) if d == 'SE' else (1, -1)
    k = 0
    while k < n and 0 <= x + dx * k < W and 0 <= y + dy * k < H:
        k += 1
    if k > 1:
        walls.runs.append((pen, x, y, d, k))


def diagonal(rng, walls):
    """Diagonal passages: walls in pairs, so the space between them is a
    corridor you walk along at forty-five degrees.  A single diagonal is
    just a staircase in the way; two of them make a route."""
    style = rng.choice(['lanes', 'chevrons', 'diamond'])
    if style == 'lanes':
        gap = rng.choice([3, 4])
        d = rng.choice(['SE', 'NE'])
        y0 = 2 if d == 'SE' else H - 3
        for i in range(rng.randint(3, 5)):
            x = 2 + i * (gap * 2)
            diag_run(walls, x, y0, d, 30)
            diag_run(walls, min(W - 2, x + gap), y0, d, 30)
    elif style == 'chevrons':
        for i in range(rng.randint(3, 5)):
            y = 3 + i * 7
            mid = rng.randrange(8, W - 8)
            diag_run(walls, mid, y, 'SE', rng.randint(5, 9))
            diag_run(walls, mid, y, 'NE', rng.randint(5, 9))
    else:                                    # a lozenge in the middle
        cx, cy, r = W // 2, H // 2, rng.randint(6, 9)
        diag_run(walls, cx - r, cy, 'SE', r)
        diag_run(walls, cx - r, cy, 'NE', r)
        diag_run(walls, cx, cy - r, 'SE', r)
        diag_run(walls, cx, cy + r, 'NE', r)


def spine(rng, walls, doors):
    """A central corridor with rooms opening off it."""
    mid = H // 2
    walls.h(1, mid - 2, W - 2)
    walls.h(1, mid + 2, W - 2)
    for x in range(4, W - 3, rng.choice([4, 5])):
        walls.v(x, 1, mid - 3)
        walls.v(x, mid + 3, H - mid - 4)
    for _ in range(rng.randint(4, 7)):
        x = rng.randrange(2, W - 2)
        for i, r in enumerate(walls.runs):
            if r[3] == 'E' and r[1] <= x < r[1] + r[4] and r[4] > 3:
                remove_cell(walls, (x, r[2]))
                break


# ---------------------------------------------------------------------
# Difficulty presets.  Each scales the things that decide how hard a level
# plays.  'arcade' is tuned to the original game's own 128 levels; the
# others move away from it in both directions.
#
# A generator is worth far more than a monster - it keeps making them - so
# the generator scale is the one that really sets the pace.
# Set PLACED to a collections.Counter to tally every object by the site
# that placed it, then read it back after a build.  Three passes were
# spent trimming treasure at sites that turned out not to be where it came
# from; measuring is quicker than guessing.  The tags are labels, not
# current line numbers - they name the site they were attached to when
# the instrumentation went in.
PLACED = None


def _note(tag, n=1):
    if PLACED is not None:
        PLACED[tag] += n


DIFFICULTIES = {
    'gentle':  dict(monsters=0.45, gens=0.30, food=1.60, magic=2.00,
                    treasure=1.20, traps=0.50),
    'easy':    dict(monsters=0.70, gens=0.60, food=1.25, magic=1.40,
                    treasure=1.10, traps=0.75),
    'arcade':  dict(monsters=0.82, gens=1.00, food=1.00, magic=1.15,
                    treasure=0.72, traps=1.00),
    # A level is 450 bytes whatever the difficulty, so the hard end cannot
    # simply add: it has to spend the budget differently.  Treasure is what
    # it gives up, because gold is the one thing on the floor that does not
    # fight back.
    'hard':    dict(monsters=1.30, gens=1.45, food=0.70, magic=0.60,
                    treasure=0.55, traps=1.30),
    'brutal':  dict(monsters=1.70, gens=2.10, food=0.40, magic=0.25,
                    treasure=0.15, traps=1.60),
}
SCALE = dict(DIFFICULTIES['arcade'])


def pen_runs(walls, pen, cells):
    """Add cells with the given pen as the fewest runs.

    Measured with a tally of every length-one run by the code that made
    it: close_ends, the trap-wall rings and the door conversion were
    between them making 21 POINTs a level, which is most of the gap
    between this set's vector section and the arcade's.
    """
    left = set(cells)
    while left:
        c = min(left)
        best = None
        for step, head in (((1, 0), 'E'), ((0, 1), 'S')):
            run, p = [], c
            while p in left:
                run.append(p)
                p = (p[0] + step[0], p[1] + step[1])
            if best is None or len(run) > len(best[0]):
                best = (run, head)
        run, head = best
        walls.runs.append((pen, run[0][0], run[0][1], head, len(run)))
        left -= set(run)


def add_stubs(rng, walls, start, doorcells, n):
    """Short walls sticking off existing ones into open floor.

    The arcade's vector section is 50 DRAWs a level at a median length of
    two cells - a mass of short stubs, not a few long walls.  A stub costs
    one DRAW, three bytes, and makes a dead-end pocket beside it, which is
    the cheapest structure the format sells.  This is a post-pass, so it
    works on every layout style alike.

    Each stub must leave the map connected and must not seal a door.
    """
    solid = walls.cells()
    floor = [(x, y) for x in range(1, W - 1) for y in range(1, H - 1)
             if (x, y) not in solid]
    before = len(reachable(start, walls, doorcells))
    placed = 0
    tries = 0
    while placed < n and tries < n * 12:
        tries += 1
        # a floor cell beside a wall, to grow away from it
        c = rng.choice(floor)
        if c in solid:
            continue
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (c[0] - dx, c[1] - dy) in solid:
                break
        else:
            continue
        length = rng.randint(2, 4)
        run = []
        p = c
        for _ in range(length):
            if p in solid or p in doorcells or not (1 <= p[0] < W - 1
                                                    and 1 <= p[1] < H - 1):
                break
            run.append(p)
            p = (p[0] + dx, p[1] + dy)
        if len(run) < 2:
            continue
        head = 'E' if dx == 1 else 'W' if dx == -1 else 'S' if dy == 1 else 'N'
        mark = len(walls.runs)
        walls.runs.append((WALL_PEN, run[0][0], run[0][1], head, len(run)))
        after = len(reachable(start, walls, doorcells))
        if after < before - len(run):
            del walls.runs[mark:]           # it cut something off
            continue
        before = after                      # or every later stub fails
        solid |= set(run)
        placed += 1
    return placed


def wall_runs(walls, cells):
    """Add cells as the fewest runs, not one run each.

    A length-one run encodes as a POINT: a positioned single cell that
    covers no ground.  Adding a cage rim a cell at a time cost twelve to
    sixteen POINTs apiece, and the set was spending 50 POINTs a level
    against the arcade's 27 - a vector section 30% bigger for the same
    number of wall cells.
    """
    pen_runs(walls, WALL_PEN, cells)


def want_swarm(n):
    """Levels built as a swarm.

    The placer reaches 150 monsters on one attempt in eight, and those
    attempts are the biggest records, so they lose the size race and the
    set ends up with none: 7 levels over 80 monsters against the arcade's
    15.  The same survivorship that hid the warrens and the locked exits.
    """
    return 8 <= n <= 117 and n % 7 == 3


def want_quiet(n):
    """Levels built nearly empty - 37 of the arcade's 110 carry fewer than
    15 monsters, and a quiet level is what makes the next one loud."""
    return 8 <= n <= 117 and n % 7 in (1, 5)


def dungeon(rng, difficulty, want_locked=False, force=None,
            want_sealed=False, shape=None, only_family=None):
    """difficulty runs 0.0 (level 1) to 1.0 (level 117)."""
    walls = Walls()
    # The arcade walls the top on 127 of its levels and the left on 112,
    # but the bottom and right on two apiece: the game bounds movement at
    # the grid edge, so closing the box is 61 wall cells and two runs spent
    # on a fence nobody can walk through anyway.
    if rng.random() < 0.02:
        walls.v(W - 1, 1, H - 1)
        walls.h(1, H - 1, W - 2)
    doors = []
    hub = None
    # A warren fails about four attempts in five, so left to chance it
    # always loses the race to an easier style and the set ends up with
    # none: the first attempt that passes decides the level.  Levels that
    # are meant to be twisty ask for it and keep asking.
    style = force or rng.choice(['maze', 'maze', 'chambers', 'chambers', 'comb',
                        'rings', 'spiral', 'cavern', 'spine',
                        # diagonal is the best value on the machine: 10.6
                        # dead ends for 63 vector bytes, where a warren
                        # needs 148 for 8.  Measured across every style.
                        'diagonal', 'diagonal', 'diagonal', 'diagonal',
                        'diagonal', 'diagonal', 'diagonal', 'diagonal',
                        'labyrinth',
                        'warren', 'warren', 'sparse', 'dense'])
    # What this level is generous with.  Chosen here, before the budget is
    # split, because a character has to be built in: topping one up after
    # the ordinary placement moved the spread of monsters from 0.46 to
    # 0.47 and changed nothing a player would notice.  The ordinary
    # placement goes lean so the chosen thing can dominate.
    character = rng.choice(CHARACTERS)
    # A diagonal layout costs 63 vector bytes where a warren costs 148.
    # Widening its share once before simply handed that saving to the
    # object placer, which spent it on monsters (+26%) and generators
    # (+41%).  The saving has to be kept, not spent.
    lean = 0.70 if force == 'diagonal' else 1.0
    # What each character gives up to pay for what it is generous with.
    # A flat cut for every character made the set *less* varied, not more
    # - monsters went from 0.46 spread to 0.38 - because pulling every
    # level down by the same amount moves them all towards the middle.
    # A character is a trade, so each one trades something different.
    give_up = {'vaults':     dict(mon=0.55, gen=0.70),
               'keyring':    dict(mon=0.65, gen=0.80),
               'trapworks':  dict(mon=0.60, gen=0.55),
               'hoard':      dict(mon=0.50, gen=0.85),
               'nest':       dict(mon=1.25, gen=0.35),
               'deaths':     dict(mon=0.85, gen=0.85),
               'secrets':    dict(mon=0.80, gen=0.90),
               'crossroads': dict(mon=0.75, gen=0.75),
               }.get(character, dict(mon=1.0, gen=1.0))

    if style in ('labyrinth', 'warren'):
        # Its walls cost about 240 of the 450 bytes on their own, so it
        # cannot also carry a full complement of monsters and gold: the
        # record overflows and every attempt is thrown out.
        difficulty *= 0.3 if style == 'labyrinth' else 0.7
    if style == 'chambers':
        chambers(rng, walls, doors)
    elif style == 'comb':
        comb(rng, walls)
        divide(rng, walls, 1, 1, W - 1, H - 1, 2, doors)
    elif style == 'rings':
        rings(rng, walls)
    elif style == 'spiral':
        spiral(rng, walls)
    elif style == 'cavern':
        cavern(rng, walls)
    elif style == 'diagonal':
        diagonal(rng, walls)
        divide(rng, walls, 1, 1, W - 1, H - 1, 3, doors)
    elif style == 'spine':
        spine(rng, walls, doors)
    elif style == 'warren':
        # A maze in patches rather than across the whole map.  Dividing all
        # 32x32 to depth seven costs about 240 of the 450 bytes and leaves
        # nothing for the level's contents; a 16x16 patch is 72 bytes for
        # four dead ends, so two or three of them buy the twist and still
        # leave room for monsters and gold.
        divide(rng, walls, 1, 1, W - 1, H - 1, 3, doors)
        spots = [(2, 2), (W // 2, 2), (2, H // 2), (W // 2, H // 2)]
        rng.shuffle(spots)
        for x0, y0 in spots[:rng.randint(2, 3)]:
            side = rng.randint(12, 15)
            divide(rng, walls, x0, y0,
                   min(W - 2, x0 + side), min(H - 2, y0 + side),
                   5 + (rng.random() < 0.5), doors)
    elif style == 'sparse':
        # Nearly an open field: the arcade has levels with 32 wall cells
        # and they are a relief between the dense ones.
        divide(rng, walls, 1, 1, W - 1, H - 1, rng.randint(1, 2), doors)
    elif style == 'dense':
        divide(rng, walls, 1, 1, W - 1, H - 1, rng.randint(5, 7), doors)
    elif style == 'labyrinth':
        # A genuine maze: divide to depth seven or eight, which gives
        # one-cell corridors and real dead ends for about 250 vector bytes.
        # The other styles come out as open fields, where the walk to the
        # exit is the straight line to it; the arcade's is two and a half
        # times longer than that, because its levels are twisty.
        divide(rng, walls, 1, 1, W - 1, H - 1, 7 + (rng.random() < 0.4),
               doors)
    else:
        divide(rng, walls, 1, 1, W - 1, H - 1, 4 + int(difficulty * 3), doors)

    if style in ('maze', 'chambers', 'cavern') and rng.random() < 0.45:
        hub = arena(rng, walls)                  # a landmark to remember it by
    # A labyrinth barely gets punched: every extra doorway is a short cut,
    # and enough of them turn the maze back into a field.
    punch(rng, walls, rng.randint(0, 1) if style in ('labyrinth', 'warren')
          else 2 + rng.randrange(0, 4))


    for pen in {p for _, _, p in doors}:
        pen_runs(walls, pen, [(x, y) for x, y, p in doors if p == pen])

    def door_cells():
        """Every cell covered by a door-penned run.  Whole wall runs are
        turned into doors above, so a door is rarely a single cell, and
        treating it as one leaves the generator believing the far side is
        solid - which is why nothing was ever placed behind a door."""
        got = set()
        for pen, x, y, d, ln in walls.runs:
            if pen in (DOORV_PEN, DOORH_PEN):
                dx, dy = STEP[d]
                for i in range(ln):
                    got.add((x + dx * i, y + dy * i))
        return got

    doorcells = door_cells()

    cells = open_cells(walls, doorcells)
    if len(cells) < 200:
        return None
    start = rng.choice([c for c in cells if c[0] < 12 and c[1] < 12] or cells)
    if not connect(walls, start, doorcells):
        return None

    # Short stubs off the existing walls, which is what the arcade's maps
    # are made of: 50 segments a level at a median length of two.  Each
    # is one DRAW and makes a dead-end pocket.  Measured on a plain
    # layout, 30 stubs take dead ends from 0.8 to 10.1 and corridor share
    # from 7% to 15% for 90 vector bytes; the count here is what the byte
    # budget will bear.
    if style != 'labyrinth':
        add_stubs(rng, walls, start, doorcells,
                  rng.randint(24, 34) if style == 'sparse'
                  else rng.randint(8, 14) if style == 'diagonal'
                  else rng.randint(20, 30))
    cells = open_cells(walls, doorcells)

    # sealed chambers: a door or a breakable wall is the only way in
    # A maze is nothing but dead ends, so sealing a dozen of them takes a
    # large part of the map behind keys and costs bytes the walls have
    # already spent.
    # Each sealed pocket is a lone wall cell, which encodes as a POINT: a
    # positioned single cell that covers no ground.  Measured against the
    # arcade, this set was spending 50 POINTs a level to its 27, and the
    # vector section came out 30% bigger for the same number of wall cells
    # - about nineteen objects' worth of budget, which is most of the
    # generator shortfall.
    # A sparse level seals nothing: the arcade's most open levels carry 32
    # wall cells and are a relief between the dense ones, and every pocket
    # sealed here was adding walls back.
    pockets = seal_pockets(rng, walls, start, doorcells,
                           0 if style == 'sparse'
                           else rng.randint(0, 1) if difficulty < 0.3
                           else rng.randint(10, 18) if character in
                           ('vaults', 'trapworks')
                           else rng.randint(2, 4) if style in ('labyrinth',
                                                               'warren')
                           else rng.randint(4, 9))
    locked_pockets = []
    trap_pockets = []
    solid = walls.cells()
    for gap, inner in pockets:
        roll = rng.random()
        if roll < (0.7 if character == 'trapworks' else 0.26) \
                and len(inner) >= 3:
            # Walled in with trap-wall rather than a door.  No key opens
            # this and no shot breaks it: it stands until a trap somewhere
            # on the level is sprung, and then every one of them goes at
            # the same moment.  What is behind it should be worth that.
            pen_runs(walls, 0xC0, ring_of(inner))
            trap_pockets.append(inner)
            continue
        if roll < 0.75:
            # A door has to lie the way the wall it sits in lies.  The pen
            # decides: $40 draws a vertical door, $80 a horizontal one.
            # Emitting $40 whatever the surroundings put upright doors in
            # horizontal walls, which reads as a gap rather than a door.
            # It has to span the gap, not sit in the middle of it: a door
            # with open floor at one end is one you walk round.
            across = ((gap[0] - 1, gap[1]) in solid
                      and (gap[0] + 1, gap[1]) in solid)
            down = ((gap[0], gap[1] - 1) in solid
                    and (gap[0], gap[1] + 1) in solid)
            if not across and not down:
                continue                   # nothing to span; leave it open
            pen = DOORH_PEN if across else DOORV_PEN
            walls.runs.append((pen, gap[0], gap[1], 'E', 1))
            doorcells.add(gap)
            locked_pockets.append(inner)   # a key opens this one
        else:
            # only on a secrets level: a lone breakable cell elsewhere is
            # a speck, and the arcade concentrates its breakable walls
            # on 19 levels at 25 cells each rather than sprinkling them
            if character != 'secrets':
                continue
            doors.append(('brk', gap))     # shot open, so no key needed
    # Doors are structure, not decoration.  The shipped levels average
    # twenty-one of them and put some on nearly every level, built by
    # making whole stretches of wall out of doors rather than dotting them
    # about.  Turning a wall run into a door run costs no extra bytes and
    # cannot cut the map up: a door is a wall you may be able to open, so
    # it only ever adds a way through.
    # A labyrinth is already all corridor: dressing its walls as doors puts
    # most of the map behind a key and leaves too little reachable without
    # one, so the level is thrown out before anyone sees it.
    # A warren was cut to 0.15 because dressing a maze in doors put most
    # of the map behind a key and the level was thrown out.  Now that keys
    # are provided for whatever the doors gate, it can carry them: at 0.15
    # the set averaged 16 door cells a level against the arcade's 29.
    if difficulty < 0.3:
        # The arcade's introduction teaches the door with one door and one
        # key - levels 2, 3, 4 and 8 have exactly one barrier each, so a
        # key cannot be wasted.  This set's had three to eleven, which is
        # not a lesson, it is a lottery.  The locked exit still makes its
        # own barrier; almost nothing else becomes a door.
        door_odds = 0.08
    elif character == 'vaults':
        door_odds = 1.0                      # everything that can be a door
    elif character == 'keyring':
        door_odds = 1.0
    elif style == 'sparse':
        door_odds = 0.0
    elif style in ('labyrinth', 'warren'):
        door_odds = 0.75
    else:
        door_odds = 0.95
    if rng.random() < door_odds:
        interior = [i for i, r in enumerate(walls.runs[2:], start=2)
                    # Never a diagonal: its cells only touch at the
                    # corners, so a diagonal door run is not one barrier but
                    # a staircase of separate single-cell doors, each gating
                    # nothing and each drawn upright or flat against a wall
                    # that runs at forty-five degrees to it.
                    if r[0] == WALL_PEN and r[4] >= 3
                    and r[3] in ('E', 'S')]
        rng.shuffle(interior)
        share = rng.choice([0.2, 0.35, 0.5, 0.7, 0.9])
        for i in interior[:int(len(interior) * share)]:
            pen, x, y, d, ln = walls.runs[i]
            if not close_ends(walls, walls.runs[i], start, doorcells):
                continue                   # could not close it without harm
            walls.runs[i] = (DOORH_PEN if d == 'E' else DOORV_PEN, x, y, d, ln)

    doorcells = door_cells() | {g for g, _ in pockets}
    cells = open_cells(walls, doorcells)
    room = reachable(start, walls, doorcells)
    keyless = reachable(start, walls, doorcells, passable_doors=False)
    # An object written onto a door cell replaces the door: the monster or
    # the coin is what ends up in the map, and the barrier it was standing
    # in now has a hole in it.  Nothing is ever placed on a door.
    room = [c for c in room if c not in doorcells]
    keyless = [c for c in keyless if c not in doorcells]
    # The exit has to be reachable without a key, so it comes from the
    # doors-shut set.  Everything else is placed over the doors-open set,
    # or the rooms behind the doors end up empty and there is no reason to
    # spend a key on them.
    outward = sorted(keyless,
                     key=lambda c: -(abs(c[0] - start[0]) + abs(c[1] - start[1])))
    if len(room) < 100 or len(outward) < 60:
        return None
    far = sorted(room,
                 key=lambda c: -(abs(c[0] - start[0]) + abs(c[1] - start[1])))

    # Half the time the way out is behind a door, as it is on 62 of the
    # arcade's 128 levels: a key you must find rather than one you may
    # spend.  The sealed pockets are the reliable place to put it - the
    # wall model cannot predict which cells decode as locked, but a pocket
    # is sealed by a door this code put there itself.
    # only the door-sealed ones: a breakable wall is shot open, not unlocked
    pocket_cells = [c for inner in locked_pockets for c in inner]
    if want_locked and not pocket_cells:
        return None                      # no cage to hide the exit in
    if pocket_cells and (want_locked or rng.random() < 0.25):
        exit_cell = max(pocket_cells,
                        key=lambda c: abs(c[0] - start[0]) + abs(c[1] - start[1]))
    else:
        # Not always the farthest cell on the map.  Putting it there every
        # time gives every level the same length: the arcade's walk to the
        # exit runs from about thirty steps to a hundred and forty, while
        # taking the maximum pinned mine between forty and sixty.
        # Pick the exit for how far the walk is against how far it looks:
        # an exit you can see from the start and cannot reach for eighty
        # steps is a better level than one in the far corner of a field.
        steps = walk_dist(start, walls, doorcells, passable_doors=False)
        # The arcade's walks run 5 to 296 steps - deciles 30, 32, 46, 61,
        # 81, 104, 128, 158, 192 - and this set ran 28 to 138 with every
        # decile between 30 and 72.  A floor of 30 steps and a preference
        # for the twistiest cell gives medium levels every time; the point
        # is that some are a stroll and some are a trek.  Aim at a distance
        # drawn from the arcade's own spread and take the closest cell to
        # it that is still worth walking.
        target = rng.choice([30, 32, 46, 61, 81, 104, 128, 158, 192])
        far_enough = [c for c in outward if steps.get(c, 0) >= 24]
        if far_enough:
            reach = max(steps[c] for c in far_enough)
            aim = min(target, reach)
            best = [c for c in far_enough if steps[c] >= aim * 0.9]
            exit_cell = max(best or far_enough,
                            key=lambda c: steps[c] /
                            max(1, abs(c[0] - start[0]) + abs(c[1] - start[1])))
        else:
            span = max(1, len(outward) // 3)
            exit_cell = outward[rng.randrange(0, span)]

    objs = {start: START, exit_cell: EXIT}

    # Sometimes the way out has no way in: wall the exit up completely and
    # put a teleporter beside it, with its partner out in the level.  The
    # arcade does this on fifteen of its levels and nine of those are
    # teleporter jobs, so it is a device rather than an accident.
    # Wall the exit in and leave one door in the ring.  lock_exit_behind_doors
    # looks for a region that already sits behind a barrier, and pruning the
    # pointless doors left too few of those to find: 35 levels asked for a
    # locked exit and 5 got one.  Building the barrier is surer than hunting
    # for it.
    if (want_locked and 3 < exit_cell[0] < W - 4
            and 3 < exit_cell[1] < H - 4):
        cage = [(exit_cell[0] + dx, exit_cell[1] + dy)
                for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        rim = ring_of(cage)
        if all(c not in objs for c in cage if c != exit_cell) \
                and start not in cage:
            mark = len(walls.runs)
            gate = rim[len(rim) // 2]
            wall_runs(walls, [c for c in rim if c != gate])
            flat = ((gate[0] - 1, gate[1]) in walls.cells()
                    and (gate[0] + 1, gate[1]) in walls.cells())
            walls.runs.append((DOORH_PEN if flat else DOORV_PEN,
                               gate[0], gate[1], 'E', 1))
            left = reachable(start, walls, doorcells | {gate})
            if len(left) > 300:
                doorcells.add(gate)
                room = [c for c in room if c not in rim]
            else:
                del walls.runs[mark:]

    sealed_ok = False
    if (want_sealed and 3 < exit_cell[0] < W - 4
            and 3 < exit_cell[1] < H - 4):
        cage = [(exit_cell[0] + dx, exit_cell[1] + dy)
                for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        rim = ring_of(cage)
        # the exit is in the cage by definition; testing it against objs
        # meant the condition was never once true
        if all(c not in objs for c in cage if c != exit_cell) \
                and start not in cage:
            mark = len(walls.runs)
            wall_runs(walls, rim)
            inside = (exit_cell[0] + 1, exit_cell[1])
            mates = [c for c in room
                     if c not in objs and c not in cage and c not in rim
                     and abs(c[0] - inside[0]) <= 14
                     and abs(c[1] - inside[1]) <= 8
                     and abs(c[0] - inside[0]) + abs(c[1] - inside[1]) >= 8]
            if mates:
                outside = rng.choice(mates)
                left = reachable(start, walls, doorcells)
                if len(left) > 300 and outside in left:
                    objs[inside] = TELEPORT
                    objs[outside] = TELEPORT
                    sealed_ok = True
                    # room was worked out before the cage existed, so its
                    # walls are still in the pool and the object placement
                    # writes gold and monsters straight over them - the
                    # same way objects used to break doors.
                    room = [c for c in room if c not in rim]
                else:
                    del walls.runs[mark:]
            else:
                del walls.runs[mark:]
    if want_sealed and not sealed_ok:
        # Asking for the device and settling for a level without it means
        # the first attempt always wins and the set ends up with none, the
        # same way the warrens and the locked exits did.
        return None
    for tag in doors:
        if isinstance(tag, tuple) and tag[0] == 'brk':
            objs[tag[1]] = BREAKABLE

    # Secrets.  The arcade's breakable walls come in concentrations - 25
    # cells a level on 19 levels, whole hidden rooms and passages you shoot
    # into - where this generator sprinkled single cells over 53 levels.  A
    # secret is a room whose only way in is a stretch of wall that looks
    # like any other until a shot goes through it.  What is inside has to
    # be worth the discovery: gold, food, magic, and now and then a way
    # out that is much shorter than the one you could see.
    if character in ('secrets', 'vaults') or rng.random() < 0.12:
        made = 0
        for gap, inner in list(pockets):
            if made >= (3 if character == 'secrets' else 1):
                break
            if len(inner) < 4 or gap in objs:
                continue
            # The door becomes a breakable stretch, not a single cell.  A
            # one-cell breakable is a speck nobody will shoot at; the
            # arcade's are several cells wide, which is what makes a
            # player try a shot at a wall that looks slightly different.
            objs[gap] = BREAKABLE
            # and the whole ring of the pocket: a room you can shoot into
            # from any side reads as a secret, where a single soft cell in
            # a wall reads as nothing
            for c in ring_of(inner):
                if c not in objs and c != gap:
                    objs[c] = BREAKABLE
            for c in inner:
                if c in objs:
                    continue
                roll = rng.random()
                if roll < 0.5:
                    objs[c] = TREASURE
                elif roll < 0.7:
                    objs[c] = rng.choice([FOOD, CIDER])
                elif roll < 0.8:
                    objs[c] = rng.choice([MAGIC_B, MAGIC_Y])
            made += 1

    # What a trap-walled cage is for.  A trap opens every one of them at
    # once, from wherever the player happens to be standing, so each is a
    # consequence waiting on a decision made elsewhere.
    for k, inner in enumerate(trap_pockets):
        role = rng.random()
        if role < 0.35:
            # a pack that has been waiting.  Deaths cannot be killed, so
            # the cage is the only thing between them and the player
            fam = DEATH if rng.random() < 0.5 else rng.choice(FAMILIES)
            for c in inner:
                objs.setdefault(c, fam + (0 if fam == DEATH
                                          else rng.randint(0, 2)))
        elif role < 0.65:
            # a cache: gold, and something to eat, behind a wall that no
            # key and no shot will open
            for i, c in enumerate(sorted(inner)):
                objs.setdefault(c, rng.choice([FOOD, CIDER])
                                if i % 4 == 3 else TREASURE)
                _note('treasure@968')
        elif role < 0.85:
            # a mixture, so opening one is never a safe bet
            for i, c in enumerate(sorted(inner)):
                objs.setdefault(c, TREASURE if i % 3
                                else rng.choice(FAMILIES) + rng.randint(0, 2))
                _note('treasure@973')
        else:
            # the way out.  The exit is walled in until a trap is sprung,
            # and the trap is somewhere else entirely.
            spot = sorted(inner)[len(inner) // 2]
            for c in list(objs):
                if objs[c] == EXIT and c != spot:
                    del objs[c]
            objs[spot] = EXIT
            for c in inner:
                if c != spot:
                    objs.setdefault(c, TREASURE)
                    _note('treasure@985')

    # What is behind the seal decides whether opening it was clever.  Some
    # hold gold, some hold a pack that has been waiting patiently, and some
    # hold both, which is the interesting case.
    for gap, inner in pockets:
        roll = rng.random()
        fam = (only_family if only_family is not None
               else rng.choice(FAMILIES[:1 + int(difficulty * 4)]))
        tier = min(2, int(difficulty * 3))
        picks = list(inner)
        rng.shuffle(picks)
        picks = picks[:rng.randint(3, 8)]
        if roll < 0.40:                          # a hoard
            for c in picks:
                objs.setdefault(c, TREASURE)
                _note('treasure@999')
        elif roll < 0.70:                        # a cage
            for c in picks:
                objs.setdefault(c, fam + rng.randint(0, tier))
        else:                                    # gold, and company
            for i, c in enumerate(picks):
                objs.setdefault(c, TREASURE if i % 3
                                else fam + rng.randint(0, tier))
                _note('treasure@1005')
    nbr = lambda c: [(c[0] + dx, c[1] + dy) for dx, dy in
                     ((1, 0), (-1, 0), (0, 1), (0, -1))]
    inroom = set(room)

    # how far everything is from the player's starting corner
    depth_from = {start: 0}
    edge = [start]
    while edge:
        nxt = []
        for c in edge:
            for p in nbr(c):
                if p in inroom and p not in depth_from:
                    depth_from[p] = depth_from[c] + 1
                    nxt.append(p)
        edge = nxt

    # The arcade introduces one family at a time and lets the player meet
    # it on its own: level 4 is $48 and nothing else, level 5 is $50 and
    # nothing else.  Mixing them from level 4 on means nobody learns what
    # any of them does.
    fams = ([only_family] if only_family is not None
            else FAMILIES[:1 + int(difficulty * 4)])
    # The arcade uses 174 lobbers across its 128 levels and 1537 ghosts.
    # An even choice among the unlocked families gave this set 603 of
    # them, so the special case was the commonest thing on the floor.
    fams = [f for f in fams for _ in (range(1) if f == 0x58 else range(3))]
    tier = min(2, int(difficulty * 3))
    if difficulty >= 1.0:
        # The shipped levels swing from nothing to 145 monsters and from 5
        # to 116 generators.  That range is most of what makes one level
        # feel unlike the last, so take the whole of it: a horde at one
        # end, a generator farm at the other, and the occasional near-empty
        # room to make the next one land harder.
        mix = rng.random()
        # The arcade's levels swing from 0 to 159 monsters and 32 to 505
        # wall cells; this set ran 0-97 and 141-414, which is a narrower
        # world.  Most of what makes one level feel unlike the last is
        # that range, so take more of it.
        # The arcade's pool is not a hump in the middle: 37 of its 110
        # levels carry fewer than 15 monsters and 15 carry more than 80.
        # A uniform roll gave this set 8 and 6, with every decile between
        # 18 and 72 - the same level over and over at different volumes.
        roll = rng.random() if shape is None else None
        if shape == 'quiet' or (roll is not None and roll < 0.25):
            budget = int(rng.randint(0, 14) * SCALE['monsters'])
        elif shape == 'swarm' or (roll is not None and roll < 0.40):
            budget = int(rng.randint(90, 190) * SCALE['monsters'])
        else:
            budget = int((4 + mix * 90) * SCALE['monsters'])
        budget = int(budget * give_up['mon'] * lean)
        # The target used to average 38 and only 17 survived: a
        # generator-heavy attempt is a bigger record, so it failed the size
        # cap and the retry handed back a sparser level.  Asking for more
        # than the arcade's 29.7 is what it takes to land on it.
        gens_wanted = int((72 - mix * 64) * 2.8 * SCALE['gens']
                          * give_up['gen'] * lean)
        if rng.random() < 0.10:               # a quiet level, now and then
            budget //= 4
            gens_wanted //= 4
    else:
        budget = 6 + int(difficulty * 38)
        gens_wanted = int((difficulty ** 1.4) * 34)

    safe = 6                                  # no ambush on the doormat
    far = [c for c in inroom if depth_from.get(c, 0) > safe and c not in objs]
    deadends = [c for c in far
                if sum(1 for p in nbr(c) if p in inroom) == 1]
    rng.shuffle(deadends)
    rng.shuffle(far)
    spare = [c for c in far if c not in deadends]

    def free_at(c):
        return c in inroom and c not in objs

    relief = set()
    # How much food this level carries, sampled from the arcade set's own
    # distribution over its 110 pool levels.  It is a tight band, not a
    # wild swing: 84 of the 110 sit between four and eight, the median is
    # six, and exactly one dungeon level has none at all.  (The arcade has
    # twelve levels with no food, but eleven of those are treasure rooms.)
    want_food = rng.choices(
        [0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 17, 21],
        weights=[1, 2, 6, 13, 10, 23, 21, 17, 9, 3, 2, 1, 1, 1])[0]
    want_food = max(0, round(want_food * SCALE['food']))
    # The introduction is where a player banks health for the whole run,
    # and this was handing out 46 pieces of food and cider across levels
    # 1-8 against the arcade's 25.  A player who arrives at level 9 with
    # 5000 health has been given the game.
    if difficulty < 0.75:
        want_food = max(0, round(want_food * (0.28 + difficulty * 0.7)))

    def snug(c):
        """How enclosed a cell is: 4 minus its open sides.

        Half the arcade's treasure sits in a dead end or a corridor - a
        cell with two open sides or fewer - against a fifth of this
        generator's, which sprinkled it over open floor.  Gold in the
        middle of a room is scenery; gold down a dead end is a decision.
        """
        return 4 - sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                       if (c[0] + dx, c[1] + dy) in inroom)

    def strip(seed, n):
        """A horizontal run of cells.  Consecutive cells holding the same
        code encode as a two-byte repeat, so a row of generators costs a
        fraction of the same number scattered about - which is how the
        shipped levels afford their density."""
        out = []
        x, y = seed
        while len(out) < n and free_at((x, y)):
            out.append((x, y))
            x += 1
        return out

    def blob(seed, n):
        """A compact clump of cells around seed, for caches and packs."""
        if rng.random() < 0.55:
            run = strip(seed, n)
            if len(run) >= min(3, n):
                return run
        out, edge2 = [], [seed]
        seen = {seed}
        while edge2 and len(out) < n:
            c = edge2.pop(0)
            if free_at(c):
                out.append(c)
            for p in nbr(c):
                if p not in seen and p in inroom:
                    seen.add(p)
                    edge2.append(p)
        return out

    # --- a relief pocket: pacing needs somewhere to stop being chased.
    #     Nothing hostile is placed here, so it is a breather, not a trap.
    ends = [c for c in far if sum(1 for p in nbr(c) if p in inroom) <= 2]
    if ends:
        relief = set()
        seed = rng.choice(ends)
        edge3, seen3 = [seed], {seed}
        while edge3 and len(relief) < 7:
            c = edge3.pop(0)
            if c in inroom:
                relief.add(c)
            for p in nbr(c):
                if p not in seen3 and p in inroom:
                    seen3.add(p)
                    edge3.append(p)
        # the breather counts against the quota like anything else
        for c in list(relief)[:1 if want_food else 0]:
            if free_at(c):
                objs[c] = rng.choice([FOOD, CIDER])

    # --- anything sealed behind a door must be worth opening.  A region
    #     you spend a key on and find bare is a worse outcome than no door
    #     at all, so every one is seeded before the general placement runs.
    behind = set(room) - set(keyless)
    while behind:
        seed = next(iter(behind))
        comp, stack = set(), [seed]
        while stack:
            c = stack.pop()
            if c in comp:
                continue
            comp.add(c)
            for p in nbr(c):
                if p in behind and p not in comp:
                    stack.append(p)
        behind -= comp
        cells2 = sorted(comp)
        rng.shuffle(cells2)
        cells2.sort(key=snug, reverse=True)      # the tucked-away cells first
        roll = rng.random()
        fam = rng.choice(fams)
        # A capped seed, not a share: a region behind a converted door wall
        # can run to hundreds of cells, and filling half of one puts more
        # gold on a single level than the arcade set puts on five.
        # Measured, not guessed: this one site places 40% of the set's
        # treasure, because it runs across eighty-odd sealed regions.  It
        # is the reason three earlier trims at the caches and the loose
        # change moved the total by almost nothing.
        want = min(len(cells2), rng.randint(2, 6))
        for i, c in enumerate(cells2[:want]):
            if roll < 0.35:
                objs.setdefault(c, TREASURE)
                _note('treasure@1143')
            elif roll < 0.9:
                objs.setdefault(c, fam + rng.randint(0, tier))
            else:
                objs.setdefault(c, TREASURE if i % 3
                                else fam + rng.randint(0, tier))
                _note('treasure@1147')

    # --- treasure lives in caches, most of them down dead ends, so that
    #     leaving the direct route is what pays
    caches = max(0, round(rng.randint(0, 2 + int(difficulty * 2))
                          * SCALE['treasure']))
    guarded = []
    if hub and hub in inroom:
        # Most of a level's gold comes from the sealed cages and this pile,
        # not from the caches below, so scaling only the caches moved
        # nothing: treasure stayed a third above the arcade whatever the
        # difficulty said.
        pile = blob(hub, max(1, round(rng.randint(3, 6)
                                      * SCALE['treasure'])))
        for c in pile:
            objs[c] = TREASURE
            _note('treasure@1163')
        if pile and difficulty > 0.1:
            guarded.append(pile[-1])
    for i in range(caches):
        seed = (deadends.pop() if deadends else
                (spare.pop() if spare else None))
        if seed is None:
            break
        cells = blob(seed, rng.randint(1, 3))
        for c in cells:
            objs[c] = TREASURE
            _note('treasure@1173')
        if cells and difficulty > 0.15 and rng.random() < 0.55:
            guarded.append(cells[-1])
    loose = [c for c in spare if free_at(c)]
    loose.sort(key=snug, reverse=True)
    for c in loose[:rng.randint(0, 2)]:
        objs[c] = TREASURE                    # a little loose change as well
        _note('treasure@1177')

    packs = []
    # a guarded cache first: something between the player and the money
    for seed in guarded:
        if budget <= 0:
            break
        cells = blob(seed, rng.randint(2, 4))
        fam = rng.choice(fams)
        for c in cells:
            objs[c] = fam + rng.randint(0, tier)
        if cells:
            packs.append(cells[0])
        budget -= max(1, len(cells))
    ordered = sorted((c for c in far if free_at(c)),
                     key=lambda c: -depth_from.get(c, 0))
    def openness(c):
        return sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                   if (c[0] + dx, c[1] + dy) in inroom)

    while budget > 0 and ordered:
        # Choose the family first, then a seed that suits it.  Sorting the
        # blob afterwards did nothing, because a blob grows into open
        # space wherever it starts: a lobber wants a cell that is already
        # against a wall.
        fam = rng.choice(fams)
        want = FAMILY_COVER.get(fam, 3.0)
        if want < 2.8:
            snug = ([c for c in ordered if openness(c) <= 1]
                    or [c for c in ordered if openness(c) <= 2])
            seed = (rng.choice(snug) if snug
                    else ordered[rng.randrange(0, max(1, len(ordered) // 2))])
        else:
            seed = ordered[rng.randrange(0, max(1, len(ordered) // 2))]
        if seed in relief or not free_at(seed):
            ordered.remove(seed)
            continue
        size = min(budget, rng.randint(5, 11))
        # One code for the whole pack, not one a cell.  Rolling the tier
        # per cell made a pack a mixture, so adjacent monsters rarely
        # matched: 0.36 same-code neighbours against the arcade's 1.67.
        # It also costs bytes, because a run of one code encodes as a
        # two-byte repeat and a mixture does not.
        code = fam + rng.randint(0, tier)
        cells = blob(seed, size)
        if want < 2.8:                      # keep the pack against cover
            cells = [c for c in cells if openness(c) <= 2] or cells[:1]
        for c in cells:
            objs[c] = code
        if cells:
            packs.append(cells[0])
        budget -= max(1, len(cells))
        ordered = [c for c in ordered if free_at(c)]

    # --- Food where it is earned: beside the packs first, then scattered,
    #     until the level's quota is met.  The arcade correlates food with
    #     danger only weakly (+0.34), so this is a quota with a nudge
    #     rather than a formula.
    placed = sum(1 for v in objs.values() if v in (FOOD, CIDER))
    for seed in packs:
        if placed >= want_food:
            break
        for c in blob(seed, 3)[1:2]:
            if free_at(c):
                objs[c] = rng.choice([FOOD, CIDER])
                placed += 1
    loose = [c for c in far if free_at(c)]
    rng.shuffle(loose)
    while placed < want_food and loose:
        c = loose.pop()
        if free_at(c):
            objs[c] = rng.choice([FOOD, CIDER])
            placed += 1

    # --- generators drive the game: the shipped levels run to dozens of
    #     them, so ramp hard rather than treating them as a garnish
    ngen = gens_wanted
    # The arcade's generators sit an average 59 steps from the start; this
    # set had them at 34, so the pressure was all near the door and the far
    # half of the map was quiet.  Draw only from the deeper half.
    gpool = [c for c in far if free_at(c)]
    gpool.sort(key=lambda c: -depth_from.get(c, 0))
    # Not too hard: squeezing thirty generators into the deepest third of
    # the floor packed them into a solid slab.  The arcade's median
    # biggest block is one cell - its generators are singles standing
    # apart - and this had eight levels with blocks of 57 or more, one of
    # them 120 generators in a single wall.
    gpool = gpool[:max(60, len(gpool) * 2 // 3)]
    while ngen > 0 and gpool:
        seed = gpool[rng.randrange(0, max(1, len(gpool) // 2))]
        i = FAMILIES.index(rng.choice(fams))
        code = 0x20 + i * 3 + rng.randint(0, tier)
        # The arcade scatters its generators: mean clump 1.1 cells and
        # 0.20 same-code neighbours.  Clumping them into blobs of one to
        # three was a byte saving - a run of the same code encodes as a
        # two-byte repeat - and it took this set to 1.8 and 0.92, which
        # reads as farms rather than a dungeon.
        put = 0
        for c in blob(seed, rng.choice([1] * 12 + [2, 2, 3])):
            # Keep them apart.  A cell with two generators already beside
            # it is part of a slab, not a threat: the arcade's median
            # biggest block is one cell, and this had eight levels with
            # blocks of 57 or more - one of them 120 generators in a
            # single wall.
            if sum(1 for p in nbr(c)
                   if 0x20 <= objs.get(p, 0) <= 0x2E) >= 1:
                continue
            objs[c] = code
            ngen -= 1
            put += 1
        if not put:
            # nothing went down here, so drop the seed or the loop spins
            gpool.remove(seed)
        gpool = [c for c in gpool if free_at(c)]

    if character == 'deaths' and inroom:
        # The arcade carries 2.0 Deaths a level across 58 of its 128
        # levels; this set had 0.8 across 28.  A Death cannot be killed,
        # only outrun or magicked, so a level that has any is a different
        # level - which makes it a character rather than a sprinkle.
        # Deaths belong in cover too - the arcade's sit at 2.38 open
        # sides, cornered rather than roaming an open floor.
        spots = [c for c in far if free_at(c)]
        spots.sort(key=lambda c: sum(
            1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (c[0] + dx, c[1] + dy) in inroom))
        for c in spots[:rng.randint(3, 9)]:
            objs[c] = 0x68 + rng.randint(0, 1)

    def fill_dead_space():
        """Put something wherever the map has nothing for three cells.

        A quarter of this generator's floor had nothing within three cells
        of it, against 7% of the arcade's - whole wings of a level with no
        reason to walk into them.  The pools the placers draw from cover
        the parts of the map the level was built around, and everything
        else came out bare.
        """
        placed = {c for c in objs}
        for _ in range(1):
            dead = [c for c in inroom
                    if free_at(c)
                    and not any((c[0] + dx, c[1] + dy) in placed
                                for dx in range(-3, 4) for dy in range(-3, 4))]
            if not dead:
                break
            rng.shuffle(dead)
            for c in dead[:max(1, len(dead) // 22)]:
                # A small clump, not a lone object: filling with singles
                # took monster clumping from 0.8 to 0.6 against the
                # arcade's 1.0, and scattered gold everywhere.
                # Mostly generators.  Filling bare ground with packs of
                # monsters took the set to +37% of the arcade's monster
                # count; a generator is one cell, keeps making its own
                # trouble, and is the thing that gives an empty wing a
                # reason to be walked into.
                roll = rng.random()
                if roll < 0.55:
                    i = FAMILIES.index(rng.choice(fams))
                    code, n = 0x20 + i * 3 + rng.randint(0, tier), 1
                elif roll < 0.80:
                    code, n = TREASURE, rng.randint(1, 3)
                elif roll < 0.94:
                    code, n = (rng.choice(fams) + rng.randint(0, tier),
                               rng.randint(2, 4))
                else:
                    code, n = rng.choice([FOOD, CIDER]), 1
                for q in blob(c, n):
                    objs[q] = code
                    placed.add(q)
                placed.add(c)

    # --- the rest of the furniture
    pool = [c for c in far if free_at(c)]
    rng.shuffle(pool)

    def sprinkle(code, n):
        for _ in range(n):
            if pool:
                objs[pool.pop()] = code

    # Keys are dealt out after encoding, in top_up_keys, where the level's
    # real barriers can be counted.  Nothing is placed here.
    # Magic ends a fight the way food ends starvation, so too much of it
    # is the same fault as too much food.  Sampled from the arcade's own
    # spread over its 128 levels, where 39 carry none, 79 carry one or two,
    # and only ten carry more: two colours rolled independently gave up to
    # four on a level and put three or more on 45 of mine.
    want_magic = rng.choices([0, 1, 2, 3, 4, 7],
                             weights=[39, 38, 41, 6, 3, 1])[0]
    want_magic = max(0, round(want_magic * SCALE['magic']))
    for _ in range(want_magic):
        sprinkle(rng.choice([MAGIC_B, MAGIC_Y]), 1)
    if rng.random() < 0.25:
        sprinkle(AMULET, 1)
    # no potions here: see the note by POTIONS
    # The arcade puts teleporters on 22 levels and seven on each - a
    # network, not a pair.  One pair on 34 levels came to the same total
    # spread thin, and a lone pair is a shortcut rather than a way to move
    # about the map.
    if rng.random() < 0.20:
        # The locked areas worth teleporting into are the regions behind
        # the converted doors, not the handful of small pockets: those
        # were 0 to 10 cells and mostly consumed by the time we get here.
        # Anything the player cannot walk to with the doors shut counts.
        keep = {START, EXIT, 0x37, 0x38, KEY}
        openfoot = reachable(start, walls, set())
        behind = [c for c in inroom
                  if c not in openfoot and objs.get(c) not in keep]
        teleport_pairs(rng, objs, pool, rng.randint(2, 4),
                       walk=depth_from, sealed=behind)
    if difficulty > 0.25 and rng.random() < 0.40:
        sprinkle(POISON, rng.randint(1, 3))
    if difficulty > 0.75 and rng.random() < 0.35:
        sprinkle(DEATH, 1)

    # a trap clears every trap-wall at once, so a level needs both or
    # neither: one without the other does nothing at all
    if difficulty > 0.2 and rng.random() < 0.62 * SCALE['traps']:
        # Trap-walls come only from the sealed cages above, which hold
        # something by construction.  Converting random wall runs as well
        # gave 27 levels out of 58 where springing the trap revealed
        # nothing at all: a wall vanished and the map was the same.
        if trap_pockets:
            # The trap should take some finding.  Prefer a dead end, well
            # away from the start and off the walk to the exit, with a
            # guard or two standing over it - a trap you stumble onto by
            # accident is a coin flip, one you go looking for is a choice.
            def deadendish(c):
                return sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                           if (c[0] + dx, c[1] + dy) in inroom) <= 2

            # depth_from is already the step distance from the start; a
            # cell well off the walk to the exit is one whose detour costs
            # more than a few steps.
            to_exit = (abs(exit_cell[0] - start[0])
                       + abs(exit_cell[1] - start[1]))
            cand = [c for c in far if free_at(c)
                    and depth_from.get(c, 0) > 12
                    and (abs(c[0] - exit_cell[0]) + abs(c[1] - exit_cell[1])
                         + depth_from.get(c, 0)) > to_exit + 8]
            # Fall back rather than fail: a cage with no trap to open it
            # breaks the level, and hunting 1500 seeds for a perfect
            # tucked-away corner is slower than accepting a merely distant
            # one.  Best first, then good enough, then anywhere at all.
            wide = [c for c in far if free_at(c)
                    and depth_from.get(c, 0) > 8]
            tucked = ([c for c in cand if deadendish(c)] or cand
                      or [c for c in wide if deadendish(c)] or wide
                      or [c for c in inroom if free_at(c)])
            rng.shuffle(tucked)
            # The arcade puts traps on 24 levels and about four on each;
            # this put one or two, so the level count matched and the
            # count per level was 60% short.
            for c in tucked[:rng.randint(2, 6)]:
                objs[c] = TRAP
                near_it = [q for q in inroom if free_at(q)
                           and abs(q[0] - c[0]) <= 2 and abs(q[1] - c[1]) <= 2]
                rng.shuffle(near_it)
                fam = rng.choice(fams)
                for q in near_it[:rng.randint(1, 3)]:
                    objs[q] = fam + rng.randint(0, tier)
    fill_dead_space()

    return walls, objs


def treasure_room(rng, n):
    """No monsters, no traps: a room full of treasure and a way out."""
    walls = Walls()

    style = n % 4
    if style == 0:                               # concentric boxes
        for i in range(1, 4):
            m = 3 + i * 4
            walls.h(m, m, W - 2 * m - 1)
            walls.v(m, m, H - 2 * m - 1)
            walls.h(m, H - m - 1, W - 2 * m - 1)
            walls.v(W - m - 1, m, H - 2 * m - 1)
    elif style == 1:                             # combs
        for i in range(4, W - 3, 4):
            walls.v(i, 2 if i % 8 else 8, 20)
    elif style == 2:                             # chequered blocks
        for y in range(4, H - 4, 6):
            for x in range(4, W - 4, 8):
                walls.h(x, y, 4)
                walls.h(x, y + 2, 4)
    else:                                        # a spiral
        x0, y0, x1, y1 = 3, 3, W - 4, H - 4
        while x1 - x0 > 4:
            walls.h(x0, y0, x1 - x0)
            walls.v(x1, y0, y1 - y0)
            walls.h(x0 + 2, y1, x1 - x0 - 2)
            walls.v(x0 + 2, y0 + 2, y1 - y0 - 2)
            x0, y0, x1, y1 = x0 + 4, y0 + 4, x1 - 4, y1 - 4

    cells = open_cells(walls, set())
    if len(cells) < 150:
        return None
    start = min(cells, key=lambda c: c[0] + c[1])
    # concentric rings seal whatever they enclose, so open a way in: a
    # treasure room the player cannot walk into is just a picture
    if not connect(walls, start, set()):
        return None
    room = reachable(start, walls, set())
    if len(room) < 120:
        return None
    objs = {start: START}
    far = max(room, key=lambda c: abs(c[0] - start[0]) + abs(c[1] - start[1]))
    objs[far] = EXIT
    pool = [c for c in room if c not in objs]
    rng.shuffle(pool)
    for c in pool[:rng.randint(56, 76)]:
        objs[c] = TREASURE
        _note('treasure@1377')
    # the arcade's treasure rooms carry no food: they are the reward, not
    # a chance to recover
    for c in pool[80:82]:
        objs[c] = rng.choice([MAGIC_B, MAGIC_Y])

    return walls, objs


# ----------------------------------------------------------------------
# A signature level
# ----------------------------------------------------------------------

# 5 rows tall, mostly 3 wide; W needs 5 to read as a W rather than a V
GLYPHS = {
    'C': ['###', '#..', '#..', '#..', '###'],
    'L': ['#..', '#..', '#..', '#..', '###'],
    'A': ['###', '#.#', '###', '#.#', '#.#'],
    'U': ['#.#', '#.#', '#.#', '#.#', '###'],
    'D': ['##.', '#.#', '#.#', '#.#', '##.'],
    'E': ['###', '#..', '###', '#..', '###'],
    'O': ['###', '#.#', '#.#', '#.#', '###'],
    'Z': ['###', '..#', '.#.', '#..', '###'],
    'R': ['##.', '#.#', '##.', '#.#', '#.#'],   # not a copy of A
    'W': ['#...#', '#...#', '#.#.#', '#.#.#', '.#.#.'],
    'G': ['###', '#..', '#.#', '#.#', '###'],
    'H': ['#.#', '#.#', '###', '#.#', '#.#'],
    'Y': ['#.#', '#.#', '###', '.#.', '.#.'],
    'M': ['#.#', '###', '###', '#.#', '#.#'],
    'I': ['###', '.#.', '.#.', '.#.', '###'],
    'Q': ['###', '#.#', '#.#', '###', '..#'],
    'V': ['#.#', '#.#', '#.#', '#.#', '.#.'],
    'B': ['##.', '#.#', '##.', '#.#', '##.'],
    'K': ['#.#', '#.#', '##.', '#.#', '#.#'],
    'F': ['###', '#..', '###', '#..', '#..'],
    'N': ['#.#', '##.', '#.#', '#.#', '#.#'],
    'T': ['###', '.#.', '.#.', '.#.', '.#.'],
    'S': ['###', '#..', '###', '..#', '###'],
    'P': ['###', '#.#', '###', '#..', '#..'],
    '6': ['###', '#..', '###', '#.#', '###'],
    '4': ['#.#', '#.#', '###', '..#', '..#'],
    ' ': ['..', '..', '..', '..', '..'],
}


def runs_from_bitmap(cells):
    """Turn a set of cells into wall runs, taking long vertical strokes
    first so a letter costs a handful of runs rather than one per row."""
    left = set(cells)
    runs = []
    for x, y in sorted(left, key=lambda c: (c[0], c[1])):
        if (x, y) not in left:
            continue
        n = 0
        while (x, y + n) in left:
            n += 1
        if n >= 3:
            for i in range(n):
                left.discard((x, y + i))
            runs.append(('v', x, y, n))
    for x, y in sorted(left, key=lambda c: (c[1], c[0])):
        if (x, y) not in left:
            continue
        n = 0
        while (x + n, y) in left:
            n += 1
        for i in range(n):
            left.discard((x + i, y))
        runs.append(('h', x, y, n))
    return runs


def word_cells(text, x0, y0):
    """Lay a word out left to right, one blank column between letters."""
    cells = set()
    x = x0
    for letter in text:
        g = GLYPHS[letter]
        for dy, row in enumerate(g):
            for dx, c in enumerate(row):
                if c == '#':
                    cells.add((x + dx, y0 + dy))
        x += len(g[0]) + 1
    return cells, x - x0 - 1


# $9A2B reads the player's map address when they leave and sends them to
# level 4 from $0CD2 and level 8 from $0FE1, whatever the exit's code was.
# An ordinary $36 at these two cells is the shortcut; $37 and $38 are only
# markers, and the passability test blocks them.
EXIT_TO_4 = (0x0CD2 - 0x0C00) % W, (0x0CD2 - 0x0C00) // W
EXIT_TO_8 = (0x0FE1 - 0x0C00) % W, (0x0FE1 - 0x0C00) // W


def signature(rng):
    """CLAUDE WOZ ERE, spelled out in walls, with room to play around it.

    Level 1 also carries the two shortcuts the arcade had: an easy way on
    to level 2, and exits to 4 and to 8 that each cost more to reach."""
    walls = Walls()
    walls.v(W - 1, 1, H - 1)
    # the level-8 shortcut sits on the bottom row, so the floor there is
    # left open and the border is drawn around it
    walls.h(3, H - 1, W - 4)
    cells = set()
    for text, y in (('CLAUDE', 8), ('WOZ ERE', 16)):
        got, width = word_cells(text, 0, y)
        x0 = (W - width) // 2
        cells |= {(x + x0, y2) for x, y2 in got}
    for kind, x, y, n in runs_from_bitmap(cells):
        (walls.v if kind == 'v' else walls.h)(x, y, n)

    # A chamber around each shortcut, drawn so that it never covers the
    # magic cell itself.  Both are made obvious rather than hidden: a
    # shortcut nobody finds is not a choice, so each gets a wide mouth and
    # a trail of treasure leading in.  The level-8 exit is in the
    # bottom-left corner, which is why the border along the last row
    # starts at x=3.
    gap = box(walls, EXIT_TO_4[0] - 3, EXIT_TO_4[1] - 3, 6, 4, door='N',
              pen=DOORH_PEN)
    walls.h(gap[0], gap[1], 1, DOORH_PEN)        # seal the gap too: an open
                                                 # side would make the rest
                                                 # of the doors decorative
    # The level-8 shortcut is the deeper one, so it costs two keys rather
    # than one: an outer alcove and an inner cell nested inside it, with
    # the monsters in the space between so the second door has to be fought
    # to rather than merely walked to.
    walls.v(6, H - 6, 6, DOORV_PEN)              # outer alcove
    walls.h(1, H - 6, 5, DOORH_PEN)
    walls.v(3, H - 3, 3, DOORV_PEN)              # inner cell round the exit
    walls.h(1, H - 3, 2, DOORH_PEN)

    start = (2, 2)
    # the two shortcut chambers are built from doors, so they have to be
    # treated as openable here or the level rejects its own design
    doorcells = {(x + STEP[d][0] * i, y + STEP[d][1] * i)
                 for pen, x, y, d, ln in walls.runs
                 if pen in (DOORV_PEN, DOORH_PEN) for i in range(ln)}
    room = reachable(start, walls, doorcells)
    if start not in room or len(room) < 420:
        return None
    if EXIT_TO_4 not in room or EXIT_TO_8 not in room:
        return None
    # $37 and $38 on the two addresses $9A2B redirects from, which is
    # exactly what the shipped level 1 does
    objs = {start: START, (W - 2, H - 2): EXIT,
            EXIT_TO_4: 0x37, EXIT_TO_8: 0x38}
    # An object written onto a door cell replaces the door, which quietly
    # opens the chamber it was sealing.  Nothing goes on a door.
    room = [c for c in room if c not in doorcells]
    # two doors to open, two keys, both out in the open where the player
    # will walk anyway
    # One key for the level-4 chamber, two for the level-8 cell, one spare.
    # They used to be dealt into the top few rows, which put all four within
    # a few steps of each other and of the start: spread them instead, each
    # one as far as possible from the start and from the keys already down,
    # so collecting the set is a walk across the map rather than a detour.
    # not inside either shortcut chamber: a key sealed behind the door it
    # opens is no key at all
    inside = {c for c in room
              if (EXIT_TO_4[0] - 3 <= c[0] <= EXIT_TO_4[0] + 3
                  and EXIT_TO_4[1] - 3 <= c[1] <= EXIT_TO_4[1] + 1)
              or (c[0] <= 6 and c[1] >= H - 6)}
    cand = [c for c in room if c not in objs and c not in inside
            and abs(c[0] - start[0]) + abs(c[1] - start[1]) > 10]
    rng.shuffle(cand)
    chosen = []
    for _ in range(4):
        if not cand:
            break
        best = max(cand, key=lambda c: min(
            [abs(c[0] - start[0]) + abs(c[1] - start[1])]
            + [abs(c[0] - k[0]) + abs(c[1] - k[1]) for k in chosen]))
        chosen.append(best)
        cand.remove(best)
    for c in chosen:
        objs[c] = KEY

    # the guard for level 8 stands in the outer alcove, between the two
    # doors, rather than in the cell with the exit
    ring = [c for c in room if c not in objs
            and 1 <= c[0] <= 5 and H - 5 <= c[1] <= H - 1
            and not (c[0] <= 2 and c[1] >= H - 2)]
    rng.shuffle(ring)
    fam = FAMILIES[0]
    for c in ring[:7]:
        objs[c] = fam + rng.randint(0, 1)

    # the shortcuts are guarded and signposted; the plain exit is neither
    for spot, guards in ((EXIT_TO_4, 4), (EXIT_TO_8, 0)):
        near = [c for c in room if c not in objs
                and abs(c[0] - spot[0]) <= 3 and abs(c[1] - spot[1]) <= 3]
        rng.shuffle(near)
        fam = FAMILIES[0]
        for c in near[:guards]:
            objs[c] = fam + rng.randint(0, 1)
        # a line of gold pointing at the door, so it reads as somewhere to go
        trail = sorted((c for c in room if c not in objs
                        and abs(c[0] - spot[0]) <= 6
                        and abs(c[1] - spot[1]) <= 6),
                       key=lambda c: abs(c[0] - spot[0]) + abs(c[1] - spot[1]))
        for c in trail[:5]:
            objs[c] = TREASURE
            _note('treasure@1579')
    # The arcade's level 1 carries 2 treasure and 75 hostile: an
    # introduction is a fight, not a vault.  This scattered 26 pieces of
    # gold over the open floor on top of the trails and the chambers, so
    # the first thing a player saw was 62 loose coins and almost nothing
    # to shoot.
    pool = [c for c in room if c not in objs and c[1] < 12]
    rng.shuffle(pool)
    # The arcade's level 1 carries $40-$42 and nothing else: one family,
    # the weakest.  It introduces $48 on level 4 and $50 on level 5, one
    # at a time.  This was picking from the first three families, so a
    # player met demons before they had met a ghost.
    fam = FAMILIES[0]
    for c in pool[:18]:
        objs[c] = fam + rng.randint(0, 1)
    # the arcade's level 1 carries three pieces of food and no cider
    for c in pool[18:20]:
        objs[c] = FOOD
    for c in pool[20:21]:
        objs[c] = CIDER
    # and two keys with nothing on level 1 to spend them on: the bank the
    # player carries into the doors of levels 2 to 4, exactly as the
    # arcade's level 1 does it
    for c in pool[21:23]:
        objs[c] = KEY
    lower = [c for c in room if c not in objs and c[1] > 19]
    rng.shuffle(lower)
    for c in lower[:18]:
        objs[c] = TREASURE
        _note('treasure@1591')
    for c in lower[18:22]:
        objs[c] = rng.choice([GHOST, GRUNT])
    for c in lower[22:24]:
        objs[c] = FOOD
    return walls, objs


# ----------------------------------------------------------------------
# Themed levels
#
# The shipped set is not uniform: level 81 is a teleporter network, 24 is
# built almost entirely from doors, 71 fields a single monster type, and
# 114 cages Deaths behind doors with the magic locked in beside them.  A
# themed level every so often is what stops a random set feeling random.
# ----------------------------------------------------------------------

def box(walls, x0, y0, w, h, door=None, pen=WALL_PEN):
    """A sealed cell with one gap.  Drawn as four runs, not w*h single
    cells: a run costs three bytes whatever its length, so a cage built
    cell by cell would eat the whole 255-byte vector section.

    When the cell is made of doors, each side takes the pen matching its
    heading.  A horizontal door pen is $80 and a southward DRAW is also
    top-field 4, so using one pen for all four sides puts those two next
    to each other and the whole level misparses."""
    if pen in (DOORV_PEN, DOORH_PEN):
        hpen, vpen = DOORH_PEN, DOORV_PEN
    else:
        hpen = vpen = pen
    gx, gy = {'N': (x0 + w // 2, y0), 'S': (x0 + w // 2, y0 + h),
              'W': (x0, y0 + h // 2), 'E': (x0 + w, y0 + h // 2)}[door]
    for yy in (y0, y0 + h):                      # top and bottom
        if gy == yy:
            walls.h(x0, yy, gx - x0, hpen)
            walls.h(gx + 1, yy, x0 + w - gx, hpen)
        else:
            walls.h(x0, yy, w + 1, hpen)
    for xx in (x0, x0 + w):                      # sides, corners already done
        if gx == xx:
            walls.v(xx, y0 + 1, gy - y0 - 1, vpen)
            walls.v(xx, gy + 1, y0 + h - gy - 1, vpen)
        else:
            walls.v(xx, y0 + 1, h - 1, vpen)
    return (gx, gy)


def remove_cells(walls, cells):
    """Cut cells out of the wall list, splitting runs where needed."""
    gone = set(cells)
    fresh = []
    for pen, x, y, d, n in walls.runs:
        dx, dy = STEP[d]
        run = []
        for i in range(n):
            c = (x + dx * i, y + dy * i)
            if c in gone:
                if run:
                    fresh.append((pen, run[0][0], run[0][1], d, len(run)))
                    run = []
            else:
                run.append(c)
        if run:
            fresh.append((pen, run[0][0], run[0][1], d, len(run)))
    walls.runs = fresh


def theme_deaths_gauntlet(rng):
    """A run of Deaths down a corridor, with the magic to clear it.

    The other Deaths level is a grid of vaults you choose to open.  This
    one gives you no choice: the way out is down a corridor lined with
    them, and the magic to blow a hole is on the floor before you start.
    Both levels used the same twelve-vault walls, so the set had the same
    showpiece twice.
    """
    walls = Walls()
    objs = {}
    # a spine of chambers, each opening onto the next
    y = 2
    lanes = []
    while y < H - 4:
        walls.h(2, y, W - 5)
        lanes.append(y)
        y += 4
    # a gap in each wall, staggered, so the route snakes down the level
    kept = []
    for i, y in enumerate(lanes):
        gap = 3 + (i * 9) % (W - 9)
        kept.append((y, gap))
    walls.runs = [r for r in walls.runs]
    for y, gap in kept:
        remove_cells(walls, [(x, y) for x in range(gap, gap + 3)])
    start = (2, 1)
    objs[start] = START
    objs[(W - 3, H - 2)] = EXIT
    rows = [y + 1 for y in lanes]
    for i, y in enumerate(rows):
        for x in range(3, W - 4, 2):
            # nothing within five steps of the start: the first corridor
            # has to be walked into, not fallen into
            if abs(x - start[0]) + abs(y - start[1]) <= 6:
                continue
            if rng.random() < 0.55:
                objs[(x, y)] = 0x68 + rng.randint(0, 1)
    # the magic to get through, and food for what it costs
    free = [(x, y) for y in range(1, H - 1) for x in range(1, W - 1)
            if (x, y) not in objs]
    rng.shuffle(free)
    for c in free[:rng.randint(3, 5)]:
        objs[c] = rng.choice([MAGIC_B, MAGIC_Y])
    for c in free[6:6 + rng.randint(5, 9)]:
        objs[c] = rng.choice([FOOD, CIDER])
    for c in free[20:20 + rng.randint(14, 24)]:
        objs[c] = TREASURE
    return walls, objs


def theme_deaths(rng):
    """Deaths everywhere, every one of them caged.

    Death cannot be killed, only outrun or blown away with magic, so a
    level full of them is only fair if the player can walk past.  Each is
    sealed in its own cell with a single door: open one and you have made
    that choice yourself.  The magic sits in the corridors, free to anyone
    who leaves the doors shut."""
    walls = Walls()

    objs = {}
    cells = []
    for gy in range(3):
        for gx in range(4):
            x0, y0 = 2 + gx * 7, 3 + gy * 9
            side = rng.choice('NSEW')
            gap = box(walls, x0, y0, 5, 6, door=side)
            cells.append((x0, y0, gap))
    start = (1, 1)
    objs[start] = START
    objs[(W - 2, H - 2)] = EXIT
    doorcells = {gap for _, _, gap in cells}
    for c in doorcells:
        walls.runs.append((DOORV_PEN, c[0], c[1], 'E', 1))
    # inside each cage: a Death, and treasure to tempt you in
    for x0, y0, _ in cells:
        inner = [(x, y) for x in range(x0 + 1, x0 + 5)
                 for y in range(y0 + 1, y0 + 6)]
        rng.shuffle(inner)
        for c in inner[:rng.randint(2, 3)]:
            objs[c] = DEATH
        for c in inner[3:3 + rng.randint(2, 5)]:
            objs.setdefault(c, TREASURE)
            _note('treasure@1671')
    # and in the corridors, the magic: reachable without opening anything.
    # Doors have to be treated as shut here, or the "corridor" items land
    # inside the cages with the Deaths.
    room = reachable(start, walls, doorcells, passable_doors=False)
    free = [c for c in room if c not in objs]
    rng.shuffle(free)
    # Enough to get past the Deaths that matter, not enough to clear them
    # all: eight put this level among the most magic-rich in the set by a
    # wide margin, against an arcade maximum of seven anywhere.
    for c in free[:5]:
        objs[c] = rng.choice([MAGIC_B, MAGIC_Y])
    for c in free[8:14]:
        objs[c] = rng.choice([FOOD, CIDER])
    for c in free[14:28]:
        objs[c] = TREASURE
        _note('treasure@1686')
    return walls, objs


def theme_teleport(rng):
    """A teleporter network: short walls, long jumps."""
    walls = Walls()

    for _ in range(rng.randint(10, 16)):
        x, y = rng.randrange(2, W - 3), rng.randrange(2, H - 3)
        if rng.random() < 0.5:
            walls.h(x, y, rng.randint(4, 10))
        else:
            walls.v(x, y, rng.randint(4, 10))
    start = (2, 2)
    room = reachable(start, walls, set())
    if len(room) < 500:
        return None
    objs = {start: START}
    far = max(room, key=lambda c: abs(c[0] - start[0]) + abs(c[1] - start[1]))
    objs[far] = EXIT
    free = [c for c in room if c not in objs]
    rng.shuffle(free)
    # walking distances, so a pair is only made where the walk between its
    # two ends is much longer than the hop
    steps = {start: 0}
    edge = [start]
    while edge:
        nxt = []
        for c in edge:
            for p in ((c[0] + 1, c[1]), (c[0] - 1, c[1]),
                      (c[0], c[1] + 1), (c[0], c[1] - 1)):
                if p in room and p not in steps:
                    steps[p] = steps[c] + 1
                    nxt.append(p)
        edge = nxt
    teleport_pairs(rng, objs, free, rng.randint(4, 7), walk=steps)
    free = [c for c in free if c not in objs]
    i = 0
    for c in free[i:i + 30]:
        objs[c] = TREASURE
        _note('treasure@1727')
    for c in free[i + 30:i + 34]:
        objs[c] = rng.choice([FOOD, CIDER])
    fam = rng.choice(FAMILIES)
    for c in free[i + 34:i + 60]:
        objs[c] = fam + rng.randint(0, 2)
    return walls, objs


def theme_mono(rng):
    """One kind of monster, in numbers."""
    walls = Walls()

    doors = []
    divide(rng, walls, 1, 1, W - 1, H - 1, 5, doors)
    punch(rng, walls, 6)
    start = (2, 2)
    if not connect(walls, start, set()):
        return None
    room = reachable(start, walls, set())
    if len(room) < 400:
        return None
    objs = {start: START}
    far = max(room, key=lambda c: abs(c[0] - start[0]) + abs(c[1] - start[1]))
    objs[far] = EXIT
    free = [c for c in room if c not in objs
            and abs(c[0] - start[0]) + abs(c[1] - start[1]) > 6]
    rng.shuffle(free)
    fam = rng.choice(FAMILIES)
    i = FAMILIES.index(fam)
    for c in free[:rng.randint(45, 70)]:
        objs[c] = fam + rng.randint(0, 2)
    for c in free[70:70 + rng.randint(8, 14)]:
        objs[c] = 0x20 + i * 3 + rng.randint(0, 2)
    for c in free[90:120]:
        objs[c] = TREASURE
        _note('treasure@1763')
    for c in free[120:128]:
        objs[c] = rng.choice([FOOD, CIDER])
    return walls, objs


# ----------------------------------------------------------------------
# Assembly and checking
# ----------------------------------------------------------------------

def trap_treasure(rng):
    """A treasure room that isn't.

    Nothing in the game treats files 118-128 specially - the counter at
    $AD13 just picks one every four to seven levels - so a room can look
    exactly like the reward and not be one.  Same patterned walls, same
    carpet of gold, but with monsters bedded down in the piles and shots
    set to stun the other player, so the pair of you lock each other in
    place in the scramble.  There is an exit and there is food; it is
    survivable, which is the point."""
    got = treasure_room(rng, rng.randrange(0, 4))
    if got is None:
        return None
    walls, objs = got
    start = [c for c, k in objs.items() if k == START][0]
    room = reachable(start, walls, set())
    ex = [c for c, k in objs.items() if k == EXIT]
    if not ex:
        return None
    exit_cell = ex[0]

    # There is no treasure-room timer in this game - it does not even know
    # it loaded one - so the clock is the same as everywhere else: health
    # running down while you are not making progress.  The room is built to
    # make that bite.  The monsters mass across the route to the exit, the
    # generators sit behind them to keep it topped up, and what food there
    # is lies back the way you came, so every second spent digging out is
    # health you do not get back.
    def on_route(c):
        here = abs(c[0] - start[0]) + abs(c[1] - start[1])
        there = abs(c[0] - exit_cell[0]) + abs(c[1] - exit_cell[1])
        span = abs(start[0] - exit_cell[0]) + abs(start[1] - exit_cell[1])
        return here + there <= span + 6 and here > 8

    blockade = [c for c in room if c not in objs and on_route(c)]
    rng.shuffle(blockade)
    fam = rng.choice(FAMILIES)
    want = rng.randint(22, 30)
    for c in blockade[:want]:
        objs[c] = fam + rng.randint(0, 2)
    i = FAMILIES.index(fam)
    near_exit = sorted((c for c in room if c not in objs),
                       key=lambda c: abs(c[0] - exit_cell[0])
                       + abs(c[1] - exit_cell[1]))
    for c in near_exit[1:1 + rng.randint(3, 5)]:
        objs[c] = 0x20 + i * 3 + rng.randint(0, 2)
    behind = sorted((c for c in room if c not in objs),
                    key=lambda c: abs(c[0] - start[0]) + abs(c[1] - start[1]))
    for c in behind[1:6]:
        objs[c] = rng.choice([FOOD, CIDER])
    return walls, objs


def build(walls, objs, flags1=0, flags2=0):
    lv = G.Level()
    lv.flags1 = flags1
    lv.flags2 = flags2
    lv.cmds = walls.cmds()
    lv.objects = sorted((y * W + x, code) for (x, y), code in objs.items())
    return lv


def bfs(grid, start, doors_open=False, shoot=False, teleport=False,
        sprung=False):
    """Step distances from start over walkable cells.

    Three views are needed: with doors shut and breakable walls standing,
    to prove the exit can be reached without a key or a fight; with doors
    open; and with breakable walls shot away as well, to prove the player
    can eventually collect everything.

    A breakable wall is $33, which is above $13 and so looks like an object
    lying on the floor.  The game blocks it at $92C0 like any other wall
    until it is shot, so it has to be treated as solid here.

    A trap-wall is $90.  It stands until a trap is sprung anywhere on the
    level and then every one of them goes at once, so `sprung` gives the
    fourth view: what the map looks like afterwards.  A trap-walled cage
    may therefore hold the exit, provided the trap itself can be reached
    without going through one."""
    pads = ([(i % W, i // W) for i, v in enumerate(grid) if v == 0x30]
            if teleport else [])
    dist = {start: 0}
    queue = [start]
    while queue:
        nxt = []
        for x, y in queue:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                p = (x + dx, y + dy)
                if not (0 <= p[0] < W and 0 <= p[1] < H) or p in dist:
                    continue
                v = grid[p[1] * W + p[0]]
                if v == 0x33 and not shoot:
                    continue
                if v == 0x90 and not sprung:
                    continue
                if (v == 0 or v >= 0x13 or v == 0x90
                        or (doors_open and v in (0x11, 0x12))):
                    dist[p] = dist[(x, y)] + 1
                    nxt.append(p)
                    # Standing on a teleporter puts the player on another
                    # one, so a region with no way in on foot is reachable
                    # if a teleporter reaches it.  The parameter existed
                    # and did nothing, so the generator believed a walled
                    # exit was simply unreachable and threw those levels
                    # away - the arcade uses the trick constantly.
                    if teleport and v == 0x30:
                        for q in pads:
                            if (q not in dist
                                    and abs(q[0] - p[0]) <= 15
                                    and abs(q[1] - p[1]) <= 9):
                                dist[q] = dist[p] + 1
                                nxt.append(q)
        queue = nxt
    return dist


def playable(back, treasure_room_level):
    """Design rules, applied to the decoded level rather than the plan.

    Connected is not the same as completable: a level also has to give the
    player somewhere to walk on arrival, food enough to survive what is in
    it, and an exit that is neither trivially close nor walled in."""
    at = {(c % W, c // W): k for c, k in back.objects}
    starts = [p for p, k in at.items() if k == START]
    exits = [p for p, k in at.items() if k in (EXIT, 0x37, 0x38)]
    if len(starts) != 1 or not exits:
        return False
    dist = bfs(back.grid, starts[0])                 # doors shut, walls up
    traplist = [p for p, k in at.items() if k == TRAP]
    # What the player can reach before pulling anything, and what the map
    # becomes once a trap goes off.  A trap-walled cage may hold the exit,
    # or the only way to the far half of the level, so long as a trap can
    # be reached without going through one.
    before = bfs(back.grid, starts[0], doors_open=True, shoot=True,
                 teleport=True)
    everywhere = bfs(back.grid, starts[0], doors_open=True, shoot=True,
                     teleport=True, sprung=bool(traplist))
    if traplist and not any(p in before for p in traplist):
        return False
    reach = [e for e in exits if e in dist]
    keys = sum(1 for k in at.values() if k == KEY)
    need = keys_needed(back.grid, starts[0], exits)
    # 99 means no route through doors at all, which is exactly what a
    # teleporter-only exit looks like: the walk is impossible and the
    # teleporter is the point.  Only charge for keys when a door route
    # exists to be paid for.
    if need < 90 and need > keys:
        return False                      # a way out you cannot afford
    if not reach:
        reach = [e for e in exits if e in everywhere]
    if not reach:
        return False

    # only what the player can actually get at counts: a caged Death is
    # scenery until someone opens the door
    monsters = [p for p, k in at.items() if 0x40 <= k < 0x70 and p in dist]
    gens = [p for p, k in at.items() if 0x20 <= k <= 0x2E and p in dist]
    food = sum(1 for k in at.values() if k in (FOOD, CIDER))
    treasure = sum(1 for k in at.values() if k == TREASURE)

    # How far the way out really is: the shortest walk to any exit, with
    # every door open and every trap sprung.  Measuring the longest, with
    # the doors shut, flattered a level whose exit sat in the same room as
    # the start - it only takes one close exit to make the level trivial,
    # and the player will take that one.
    walk = [everywhere[e] for e in reach if e in everywhere]
    # 28 was too generous a floor.  The arcade's median walk is 81 steps
    # and this set's was 55: on level 8 and after, an exit reached in half
    # a minute reads as a mistake rather than a breather.  The arcade does
    # have short levels - its own minimum is 5 - but they are the
    # exception, and a generator that allows them gets nothing else.
    if not walk or min(walk) < 40:
        return False
    if any(t not in everywhere
           for t in (p for p, k in at.items() if k == TREASURE)):
        return False                              # treasure you cannot get to
    # An exit needs a way in, but not elbow room: when it sits inside a
    # locked pocket, one neighbour is the door you came through, and
    # demanding two threw those levels away.
    for e in reach:
        if any((e[0] + dx, e[1] + dy) in everywhere
               for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            break
    else:
        return False

    # a teleporter with no partner inside the game's 16x10 search window
    # is scenery: standing on it does nothing
    tel = [p for p, k in at.items() if k == TELEPORT]
    for a in tel:
        if not any(b is not a and abs(a[0] - b[0]) <= TELE_DX
                   and abs(a[1] - b[1]) <= TELE_DY for b in tel):
            return False

    # A trap-wall only opens when a trap is sprung, so a level with
    # trap-walls and no trap has walls nothing can ever move, and a level
    # with a trap and no trap-walls has a trap that does nothing.  The
    # verifier rejects both; so must this, or make() never retries.
    trapwalls = sum(1 for v in back.grid if v == 0x90)
    traps = sum(1 for k in at.values() if k == TRAP)
    if (traps > 0) != (trapwalls > 0):
        return False

    # The verifier insists most of the map be reachable; if the generator
    # does not insist on the same thing, make() never retries and a sealed
    # level ships.  Every rule the checker enforces has to be enforced here
    # too, or the retry loop is blind to it.
    walkable = sum(1 for v in back.grid
                   if (v == 0 or v >= 0x13) and v != 0x33)
    # A shade above the verifier's 90%, so a level cannot pass here by a
    # cell and fail there: level 85 came out at 89.97% and slipped through.
    if len(everywhere) < 0.93 * walkable:
        return False
    # A level needs something in it.  Widening the variety produced a
    # 45-byte level with a start, an exit and nothing else - an empty room
    # with a door at the far end.  The arcade's barest carries 31 objects,
    # 17 of them hostile.
    if not treasure_room_level:
        hostile = sum(1 for k in at.values()
                      if 0x40 <= k < 0x70 or 0x20 <= k <= 0x2E)
        if len(at) < 22 or hostile < 8:
            return False

    if treasure_room_level:
        return not monsters and not gens and treasure >= 35

    # Nothing hostile in the player's face on arrival - but measured with
    # the doors shut and the breakable walls standing.  A pack sealed in a
    # cage three steps away is the point of the cage, not a fault: it can
    # only reach the player if the player lets it out.
    for p in monsters + gens:
        if dist.get(p, 99) <= 4:
            return False
    for p, k in at.items():
        if k == POISON and dist.get(p, 99) <= 3:
            return False
    if len(monsters) > 110:                       # survivable density
        return False
    # A level may be mean but not impossible: enough food to matter against
    # what is actually loose, and no more of a guarantee than that.
    # The arcade set leaves twelve of its levels with no food whatever, so
    # a bare level is authentic rather than a fault.  The floor only bites
    # where the level is genuinely crowded.
    if len(monsters) > 60 and food < 2:
        return False
    if len(monsters) > 100 and food < 4:
        return False
    return True


def theme_everything(rng):
    """One of everything.  The shipped set has a handful of levels holding
    all eighteen element kinds at once (104, 91, 74); they feel like a
    showcase after a run of leaner rooms."""
    got = dungeon(rng, 1.0)
    if got is None:
        return None
    walls, objs = got
    start = [c for c, k in objs.items() if k == START][0]
    doorcells = {(x, y) for pen, x, y, d, ln in walls.runs
                 if pen in (DOORV_PEN, DOORH_PEN)}
    room = reachable(start, walls, doorcells)
    free = [c for c in room if c not in objs
            and abs(c[0] - start[0]) + abs(c[1] - start[1]) > 6]
    rng.shuffle(free)
    have = set(objs.values())
    wanted = [AMULET, KEY, TELEPORT, POISON,
              MAGIC_B, MAGIC_Y, FOOD, CIDER, TREASURE]
    wanted += [f + rng.randint(0, 2) for f in FAMILIES] + [DEATH]
    wanted += [0x20 + i * 3 + rng.randint(0, 2) for i in range(5)]
    for code in wanted:
        if code in have or not free:
            continue
        objs[free.pop()] = code
    # traps need trap-walls to act on, so add both or neither
    if not any(r[0] == 0xC0 for r in walls.runs):
        long_runs = [i for i, r in enumerate(walls.runs[2:], start=2)
                     # Never a diagonal: its cells only touch at the
                    # corners, so a diagonal door run is not one barrier but
                    # a staircase of separate single-cell doors, each gating
                    # nothing and each drawn upright or flat against a wall
                    # that runs at forty-five degrees to it.
                    if r[0] == WALL_PEN and r[4] >= 3
                    and r[3] in ('E', 'S')]
        if long_runs and free:
            i = rng.choice(long_runs)
            pen, x, y, d, ln = walls.runs[i]
            walls.runs[i] = (0xC0, x, y, d, ln)
            objs[free.pop()] = TRAP
    return walls, objs


def theme_austere(rng):
    """The opposite: walls, treasure, one kind of monster, a way out.  No
    keys, no doors, no teleporters, nothing to pick up but gold."""
    walls = Walls()

    divide(rng, walls, 1, 1, W - 1, H - 1, 6, None)
    punch(rng, walls, 4)
    start = (2, 2)
    if not connect(walls, start, set()):
        return None
    room = reachable(start, walls, set())
    if len(room) < 420:
        return None
    objs = {start: START}
    objs[max(room, key=lambda c: abs(c[0] - start[0]) + abs(c[1] - start[1]))] = EXIT
    free = [c for c in room if c not in objs
            and abs(c[0] - start[0]) + abs(c[1] - start[1]) > 6]
    rng.shuffle(free)
    fam = rng.choice(FAMILIES)
    for c in free[:rng.randint(24, 34)]:
        objs[c] = fam + rng.randint(0, 1)
    for c in free[40:40 + rng.randint(30, 45)]:
        objs[c] = TREASURE
        _note('treasure@2075')
    for c in free[90:94]:
        objs[c] = FOOD
    return walls, objs


def theme_vault(rng):
    """Locks and keys, and very little else: rooms behind doors, the gold
    inside them, and only enough monsters to make the detour cost."""
    walls = Walls()

    vaults = []
    for gy in range(3):
        for gx in range(3):
            x0, y0 = 3 + gx * 9, 3 + gy * 9
            gap = box(walls, x0, y0, 6, 6, door=rng.choice('NSEW'))
            vaults.append((x0, y0, gap))
    doorcells = {g for _, _, g in vaults}
    for c in doorcells:
        walls.runs.append((DOORH_PEN, c[0], c[1], 'E', 1))
    start = (1, 1)
    objs = {start: START, (W - 2, H - 2): EXIT}
    for x0, y0, _ in vaults:
        inner = [(x, y) for x in range(x0 + 1, x0 + 6)
                 for y in range(y0 + 1, y0 + 6)]
        rng.shuffle(inner)
        for c in inner[:rng.randint(6, 12)]:
            objs[c] = TREASURE
            _note('treasure@2103')
        fam = rng.choice(FAMILIES)
        for c in inner[14:14 + rng.randint(1, 3)]:
            objs[c] = fam + rng.randint(0, 2)
    room = reachable(start, walls, doorcells, passable_doors=False)
    free = [c for c in room if c not in objs]
    rng.shuffle(free)
    for c in free[:max(2, len(vaults) // 2)]:
        objs[c] = KEY
    for c in free[12:18]:
        objs[c] = rng.choice([FOOD, CIDER])
    for c in free[18:26]:
        objs[c] = TREASURE
        _note('treasure@2115')
    return walls, objs


def theme_hoard(rng):
    """A vault of a level: gold everywhere, and everything guarding it."""
    got = dungeon(rng, 1.0)
    if got is None:
        return None
    walls, objs = got
    start = [c for c, k in objs.items() if k == START][0]
    doorcells = {(x, y) for pen, x, y, d, ln in walls.runs
                 if pen in (DOORV_PEN, DOORH_PEN)}
    room = reachable(start, walls, doorcells)
    free = [c for c in room if c not in objs
            and abs(c[0] - start[0]) + abs(c[1] - start[1]) > 6]
    rng.shuffle(free)
    for c in free[:rng.randint(30, 48)]:
        objs[c] = TREASURE
        _note('treasure@2133')
    return walls, objs


def theme_alldoors(rng):
    """A level built out of doors instead of walls.

    The arcade has one of these - level 27, 273 door cells against 44 real
    walls - and it is the joke that makes the rest of the set feel measured.
    Almost nothing here is solid, and with seven keys almost none of it can
    be opened, so the level is about choosing which way to spend them."""
    walls = Walls()

    for i in range(4, W - 3, 4):
        gap = rng.randrange(2, H - 3)
        walls.v(i, 1, gap - 1, DOORV_PEN)
        walls.v(i, gap + 1, H - gap - 2, DOORV_PEN)
    for j in range(5, H - 4, 6):
        gap = rng.randrange(2, W - 3)
        walls.h(1, j, gap - 1, DOORH_PEN)
        walls.h(gap + 1, j, W - gap - 2, DOORH_PEN)
    start = (2, 2)
    doorcells = {c for c in walls.cells()}
    room = reachable(start, walls, doorcells)
    if len(room) < 500:
        return None
    objs = {start: START}
    objs[max(room, key=lambda c: abs(c[0] - start[0]) + abs(c[1] - start[1]))] = EXIT
    free = [c for c in room if c not in objs]
    rng.shuffle(free)
    for c in free[:7]:
        objs[c] = KEY
    fam = rng.choice(FAMILIES)
    for c in free[10:10 + rng.randint(24, 40)]:
        objs[c] = fam + rng.randint(0, 2)
    for c in free[60:100]:
        objs[c] = TREASURE
        _note('treasure@2170')
    for c in free[100:106]:
        objs[c] = rng.choice([FOOD, CIDER])
    return walls, objs


def theme_keyring(rng):
    """Keys threaded through the doors they open.

    Two of the arcade's levels carry twenty-six or twenty-seven keys, laid
    out in blocks beside the doors: the point is not scarcity but the walk,
    door after door, picking up the next key as you pass."""
    walls = Walls()

    lanes = list(range(5, W - 4, 5))
    for i in lanes:
        gap = rng.randrange(3, H - 4)
        walls.v(i, 1, gap - 1, DOORV_PEN)
        walls.v(i, gap + 1, H - gap - 2, DOORV_PEN)
    start = (2, 2)
    doorcells = set(walls.cells())
    room = reachable(start, walls, doorcells)
    if len(room) < 500:
        return None
    objs = {start: START}
    objs[(W - 2, H - 2)] = EXIT
    # a little stack of keys in front of each door, as the arcade lays them
    for i in lanes:
        y = rng.randrange(3, H - 8)
        for k in range(rng.randint(3, 6)):
            c = (i - 1, y + k)
            if c in room and c not in objs:
                objs[c] = KEY
    free = [c for c in room if c not in objs]
    rng.shuffle(free)
    fam = rng.choice(FAMILIES)
    for c in free[:rng.randint(20, 32)]:
        objs[c] = fam + rng.randint(0, 2)
    for c in free[40:76]:
        objs[c] = TREASURE
        _note('treasure@2210')
    for c in free[76:82]:
        objs[c] = rng.choice([FOOD, CIDER])
    return walls, objs


def theme_trapworks(rng):
    """Most of the walls are trap-walls, and there are traps to spring
    them: the level rearranges itself around you."""
    walls = Walls()

    doors = []
    chambers(rng, walls, doors)
    start = (2, 2)
    if not connect(walls, start, set()):
        return None
    for i, r in enumerate(walls.runs[2:], start=2):
        if r[0] == WALL_PEN and r[4] >= 2 and rng.random() < 0.7:
            walls.runs[i] = (0xC0, r[1], r[2], r[3], r[4])
    room = reachable(start, walls, set())
    if len(room) < 380:
        return None
    objs = {start: START}
    objs[max(room, key=lambda c: abs(c[0] - start[0]) + abs(c[1] - start[1]))] = EXIT
    free = [c for c in room if c not in objs
            and abs(c[0] - start[0]) + abs(c[1] - start[1]) > 6]
    rng.shuffle(free)
    for c in free[:rng.randint(3, 6)]:
        objs[c] = TRAP
    fam = rng.choice(FAMILIES)
    for c in free[8:8 + rng.randint(20, 34)]:
        objs[c] = fam + rng.randint(0, 2)
    for c in free[46:76]:
        objs[c] = TREASURE
        _note('treasure@2244')
    for c in free[76:82]:
        objs[c] = rng.choice([FOOD, CIDER])
    return walls, objs


# The C= mark and a big 64, drawn as bitmaps rather than from the letter
# font: the logo is not a letter, and the digits want to be the same height
# as it or the level reads as a word rather than a badge.
C64_LOGO = [
    '....######......',
    '..###....###....',
    '.##.............',
    '##..............',
    '##......########',
    '##......########',
    '##..............',
    '##......########',
    '##......########',
    '.##.............',
    '..###....###....',
    '....######......',
]

# Original pixel art rather than anyone else's characters or trademarks.
PICTURES = {
    'skull': [
        '..#######..',
        '.#########.',
        '##.......##',
        '##.##.##.##',
        '##.##.##.##',
        '##...#...##',
        '##..###..##',
        '.#########.',
        '..#.#.#.#..',
        '..#######..',
    ],
    'crown': [
        '#....#....#',
        '#....#....#',
        '#.#..#..#.#',
        '#.#.###.#.#',
        '##.##.##.##',
        '###########',
        '#.#.#.#.#.#',
        '###########',
    ],
    'spider': [
        '#.........#',
        '.#..###..#.',
        '..#######..',
        '#.#######.#',
        '.#########.',
        '#.#######.#',
        '..#######..',
        '.#.......#.',
        '#.........#',
    ],
    'sword': [
        '...#...',
        '...#...',
        '...#...',
        '...#...',
        '...#...',
        '...#...',
        '...#...',
        '.#####.',
        '...#...',
        '...#...',
        '..###..',
    ],
    'key': [
        '.###...........',
        '#...#..........',
        '#...#..........',
        '#...###########',
        '#...#....#..#..',
        '#...#....#..#..',
        '.###.....#..#..',
    ],
    'chalice': [
        '#########',
        '#.......#',
        '#.......#',
        '.#.....#.',
        '..#####..',
        '....#....',
        '....#....',
        '..#####..',
        '.#######.',
    ],
}


BIG_SIX = [
    '.###.',
    '##..#',
    '##...',
    '##...',
    '####.',
    '##.##',
    '##..#',
    '##..#',
    '.###.',
]

BIG_FOUR = [
    '...##',
    '..###',
    '.#.##',
    '#..##',
    '#####',
    '#####',
    '...##',
    '...##',
    '...##',
]


def theme_c64(rng):
    """The Commodore mark and a 64, in walls."""
    walls = Walls()

    cells = set()

    def stamp(art, x0, y0):
        for dy, row in enumerate(art):
            for dx, c in enumerate(row):
                if c == '#':
                    cells.add((x0 + dx, y0 + dy))

    stamp(C64_LOGO, (W - 16) // 2, 3)
    stamp(BIG_SIX, (W - 11) // 2, 18)
    stamp(BIG_FOUR, (W - 11) // 2 + 6, 18)
    for kind, x, y, n in runs_from_bitmap(cells):
        (walls.v if kind == 'v' else walls.h)(x, y, n)

    start = (2, 2)
    room = reachable(start, walls, set())
    if len(room) < 480:
        return None
    objs = {start: START, (W - 2, H - 2): EXIT}
    free = [c for c in room if c not in objs
            and abs(c[0] - start[0]) + abs(c[1] - start[1]) > 6]
    rng.shuffle(free)
    fam = rng.choice(FAMILIES)
    for c in free[:rng.randint(26, 40)]:
        objs[c] = fam + rng.randint(0, 2)
    i = FAMILIES.index(fam)
    for c in free[44:44 + rng.randint(6, 12)]:
        objs[c] = 0x20 + i * 3 + rng.randint(0, 2)
    for c in free[60:94]:
        objs[c] = TREASURE
        _note('treasure@2398')
    for c in free[94:100]:
        objs[c] = rng.choice([FOOD, CIDER])
    return walls, objs, 2         # wall colour 2 is light blue at $8C78


def theme_picture(rng, name):
    """One large piece of pixel art in walls, with room to fight around it."""
    art = PICTURES[name]
    walls = Walls()

    cells = set()
    x0 = (W - len(art[0])) // 2
    y0 = (H - len(art)) // 2
    for dy, row in enumerate(art):
        for dx, c in enumerate(row):
            if c == '#':
                cells.add((x0 + dx, y0 + dy))
    for kind, x, y, n in runs_from_bitmap(cells):
        (walls.v if kind == 'v' else walls.h)(x, y, n)
    start = (2, 2)
    room = reachable(start, walls, set())
    if len(room) < 500:
        return None
    objs = {start: START, (W - 2, H - 2): EXIT}
    free = [c for c in room if c not in objs
            and abs(c[0] - start[0]) + abs(c[1] - start[1]) > 6]
    rng.shuffle(free)
    fam = rng.choice(FAMILIES)
    for c in free[:rng.randint(26, 42)]:
        objs[c] = fam + rng.randint(0, 2)
    i = FAMILIES.index(fam)
    for c in free[46:46 + rng.randint(6, 14)]:
        objs[c] = 0x20 + i * 3 + rng.randint(0, 2)
    for c in free[64:96]:
        objs[c] = TREASURE
        _note('treasure@2434')
    for c in free[96:102]:
        objs[c] = rng.choice([FOOD, CIDER])
    return walls, objs


def theme_text(rng, word):
    """A word in walls: instantly recognisable, and unlike anything else
    in the set."""
    walls = Walls()

    cells = set()
    rows = [word] if len(word) <= 7 else [word[:len(word) // 2], word[len(word) // 2:]]
    y = 10 if len(rows) == 1 else 7
    for text in rows:
        got, width = word_cells(text, 0, y)
        x0 = max(1, (W - width) // 2)
        cells |= {(x + x0, yy) for x, yy in got}
        y += 8
    for kind, x, yy, n in runs_from_bitmap(cells):
        (walls.v if kind == 'v' else walls.h)(x, yy, n)
    start = (2, 2)
    room = reachable(start, walls, set())
    if len(room) < 500:
        return None
    objs = {start: START, (W - 2, H - 2): EXIT}
    free = [c for c in room if c not in objs
            and abs(c[0] - start[0]) + abs(c[1] - start[1]) > 6]
    rng.shuffle(free)
    fam = rng.choice(FAMILIES)
    for c in free[:rng.randint(24, 40)]:
        objs[c] = fam + rng.randint(0, 2)
    i = FAMILIES.index(fam)
    for c in free[44:44 + rng.randint(6, 12)]:
        objs[c] = 0x20 + i * 3 + rng.randint(0, 2)
    for c in free[60:90]:
        objs[c] = TREASURE
        _note('treasure@2471')
    for c in free[90:96]:
        objs[c] = rng.choice([FOOD, CIDER])
    return walls, objs


# Themed levels are set pieces and they are flat: 48 of them averaged 4.3
# dead ends against the procedural levels' 12.9, and nearly half the pool
# being set pieces is what kept the whole set open.  Duplicates of the
# flattest themes are handed back to the generator, keeping one or two of
# each as a landmark.
_RETURNED_TO_THE_POOL = [47, 54, 59, 68, 69, 71, 73, 74, 77, 80, 83, 86, 88, 89, 92, 95, 97, 101, 104, 108, 113, 116]

THEMED = {
    11: theme_everything,    # one of everything
    13: theme_deaths,        # the cage level
    14: lambda r: theme_picture(r, 'skull'),
    16: theme_hoard,
    19: theme_austere,
    21: lambda r: theme_text(r, 'THOR'),
    22: lambda r: theme_text(r, 'GAUNTLET'),
    24: theme_vault,
    29: lambda r: theme_picture(r, 'spider'),
    26: theme_alldoors,       # a level built of doors, as the arcade's 27
    28: theme_keyring,        # keys threaded through them, as its 47 and 71
    31: theme_trapworks,
    34: theme_austere,
    36: lambda r: theme_text(r, 'THYRA'),
    41: lambda r: theme_picture(r, 'sword'),
    43: theme_hoard,
    46: theme_vault,
    47: lambda r: theme_text(r, 'MERLIN'),
    52: theme_trapworks,
    54: lambda r: theme_picture(r, 'crown'),
    59: lambda r: theme_text(r, 'DUNGEONS'),
    61: theme_everything,
    68: theme_austere,
    74: theme_mono,
    27: theme_teleport,
    38: theme_mono,
    49: theme_teleport,
    56: theme_deaths_gauntlet,
    64: theme_mono,
    71: theme_mono,          # 71 is the shipped set's own single-type level
    83: theme_teleport,
    97: theme_mono,
    69: lambda r: theme_text(r, 'QUESTOR'),
    73: lambda r: theme_picture(r, 'chalice'),
    77: theme_hoard,
    75: theme_keyring,
    80: theme_trapworks,
    86: lambda r: theme_text(r, 'DEEPER'),
    92: theme_everything,
    88: lambda r: theme_picture(r, 'key'),
    89: theme_teleport,
    95: theme_trapworks,
    101: theme_austere,
    104: theme_hoard,
    108: theme_deaths,
    111: theme_c64,
    113: theme_vault,
    116: theme_everything,
}


def count_barriers(grid):
    """Connected groups of door cells: one group is one thing to unlock.

    This has to be counted on the decoded level, not on the wall runs.  The
    dispatcher re-orients a wall to the heading it was drawn along, runs get
    split by later edits, and a diagonal run is not even four-connected, so
    what the generator thinks is one barrier can decode as several."""
    cells = {(i % W, i // W) for i, v in enumerate(grid) if v in (0x11, 0x12)}
    seen, n = set(), 0
    for c in cells:
        if c in seen:
            continue
        n += 1
        stack = [c]
        while stack:
            p = stack.pop()
            if p in seen:
                continue
            seen.add(p)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (p[0] + dx, p[1] + dy)
                if q in cells and q not in seen:
                    stack.append(q)
    return n


def keys_needed(grid, start, targets):
    """How many barriers must be opened to reach any of `targets`.

    Regions of open floor are the nodes and door barriers the edges, so the
    answer is the fewest barriers on any route - not the number of doors on
    the level.  Most levels come out at zero, because the exit is placed
    where no key is required to reach it; those keys are then an allowance
    to spend on side vaults, not a toll."""
    walk = {(i % W, i // W) for i, v in enumerate(grid)
            if (v == 0 or v >= 0x13) and v != 0x33}
    doors = {(i % W, i // W) for i, v in enumerate(grid) if v in (0x11, 0x12)}
    nbr = lambda c: [(c[0] + dx, c[1] + dy) for dx, dy in
                     ((1, 0), (-1, 0), (0, 1), (0, -1))]

    region = {}
    for c in walk:
        if c in region:
            continue
        rid = len(set(region.values()))
        stack = [c]
        while stack:
            p = stack.pop()
            if p in region:
                continue
            region[p] = rid
            for q in nbr(p):
                if q in walk and q not in region:
                    stack.append(q)

    # each barrier is one edge, joining every region it touches
    edges = {}
    seen = set()
    for c in doors:
        if c in seen:
            continue
        group, stack = set(), [c]
        while stack:
            p = stack.pop()
            if p in group:
                continue
            group.add(p)
            for q in nbr(p):
                if q in doors and q not in group:
                    stack.append(q)
        seen |= group
        touch = {region[q] for p in group for q in nbr(p) if q in region}
        for a in touch:
            for b in touch:
                if a != b:
                    edges.setdefault(a, set()).add(b)

    if start not in region:
        return 99
    goal = {region[t] for t in targets if t in region}
    if not goal:
        return 99
    dist = {region[start]: 0}
    queue = [region[start]]
    while queue:
        nxt = []
        for r in queue:
            if r in goal:
                return dist[r]
            for q in edges.get(r, ()):
                if q not in dist:
                    dist[q] = dist[r] + 1
                    nxt.append(q)
        queue = nxt
    return 99


def region_map(grid):
    """Regions of open floor, and which barriers join them."""
    walk = {(i % W, i // W) for i, v in enumerate(grid)
            if (v == 0 or v >= 0x13) and v != 0x33}
    doors = {(i % W, i // W) for i, v in enumerate(grid) if v in (0x11, 0x12)}
    nbr = lambda c: [(c[0] + dx, c[1] + dy) for dx, dy in
                     ((1, 0), (-1, 0), (0, 1), (0, -1))]
    region, rid = {}, 0
    for c in walk:
        if c in region:
            continue
        stack = [c]
        while stack:
            p = stack.pop()
            if p in region:
                continue
            region[p] = rid
            for q in nbr(p):
                if q in walk and q not in region:
                    stack.append(q)
        rid += 1
    edges, seen = {}, set()
    for c in doors:
        if c in seen:
            continue
        group, stack = set(), [c]
        while stack:
            p = stack.pop()
            if p in group:
                continue
            group.add(p)
            for q in nbr(p):
                if q in doors and q not in group:
                    stack.append(q)
        seen |= group
        touch = {region[q] for p in group for q in nbr(p) if q in region}
        for a in touch:
            edges.setdefault(a, set()).update(touch - {a})
    return region, edges


def lock_exit_behind_doors(rng, lv, back, depth):
    """Move the exit into a region `depth` barriers from the start, and give
    the level exactly that many keys.

    Doing this on the decoded grid is the only way it holds: the wall model
    cannot predict which cells come out locked, so choosing a spot before
    encoding and hoping it survives fails about three times in four.  Here
    the regions and barriers are the ones the game will actually see."""
    region, edges = region_map(back.grid)
    at = {(c % W, c // W): k for c, k in lv.objects}
    starts = [p for p, k in at.items() if k == START]
    if not starts or starts[0] not in region:
        return False
    home = region[starts[0]]
    dist = {home: 0}
    queue = [home]
    while queue:
        nxt = []
        for r in queue:
            for q in edges.get(r, ()):
                if q not in dist:
                    dist[q] = dist[r] + 1
                    nxt.append(q)
        queue = nxt
    want = [r for r, d in dist.items() if d == depth]
    if not want:
        return False
    target = rng.choice(want)
    spots = [p for p, r in region.items() if r == target and p not in at]
    if not spots:
        return False
    spot = max(spots, key=lambda c: abs(c[0] - starts[0][0])
               + abs(c[1] - starts[0][1]))

    keep = [(c, k) for c, k in lv.objects if k not in (EXIT, KEY)]
    keep.append((spot[1] * W + spot[0], EXIT))
    # exactly the keys the way out costs: no more, so none is spare, and no
    # fewer, so the level can always be finished
    taken = {c for c, _ in keep}
    free = [i for i, v in enumerate(back.grid)
            if v == 0 and i not in taken and region.get((i % W, i // W)) == home]
    rng.shuffle(free)
    if len(free) < depth:
        return False
    for i in free[:depth]:
        keep.append((i, KEY))
    lv.objects = sorted(keep)
    return True


def gates_something(grid, cells, region=None):
    """Does this barrier have different ground on its two sides?

    Regions are the open floor with every door treated as a wall, so a
    barrier that gates something touches two of them.  The test has to be
    applied to a whole connected barrier, never to one run of it: where two
    runs meet, a run's neighbour is the other run rather than open floor,
    so it appears to touch a single region, looks pointless, and gets walled
    - which is how a sealed alcove lost its doors and the exit inside it
    became unreachable.

    Asking instead whether closing this barrier alone cuts the map is too
    strict: it condemns 46% of the arcade's own doors, because a wall built
    of several barriers has each of them redundant while the others stand
    open."""
    if region is None:
        region, _ = region_map(grid)
    touch = set()
    for c in cells:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (c[0] + dx, c[1] + dy)
            if q in region:
                touch.add(region[q])
    return len(touch) > 1


def face_doors(lv, back):
    """Turn each single-cell door to face the way its wall runs.

    The pen alone decides which way a lone door is drawn - $40 upright, $80
    flat - and a door emitted with the wrong one reads as a gap in the wall
    rather than a door across it.  Runs of more than one cell already follow
    their own heading.  Deciding this on the decoded grid catches every
    source at once, rather than each place that emits a door separately."""
    g = back.grid
    def wall(x, y):
        return 0 <= x < W and 0 <= y < H and (0 < g[y * W + x] < 0x13
                                              or g[y * W + x] == 0x90)
    changed = False
    out = []
    for i, c in enumerate(lv.cmds):
        if (c[0] == 'POINT' and c[1] in (DOORV_PEN, DOORH_PEN)
                and (i + 1 >= len(lv.cmds) or lv.cmds[i + 1][0] != 'DRAW')):
            _, pen, x, y = c
            across = wall(x - 1, y) or wall(x + 1, y)
            down = wall(x, y - 1) or wall(x, y + 1)
            want = None
            if across and not down:
                want = DOORH_PEN
            elif down and not across:
                want = DOORV_PEN
            if want is not None and want != pen:
                out.append(('POINT', want, x, y))
                changed = True
                continue
        out.append(c)
    if changed:
        lv.cmds = out
    return changed


def prune_doors(lv, back):
    """Turn back into plain wall any barrier that does not separate
    anything.

    Test whole barriers, not single runs.  An L-shaped cage drawn as two
    runs has each of them redundant while the other stands open, so run by
    run both look pointless and both get walled - which is how a sealed
    alcove lost its doors and the exit inside it became unreachable."""
    doors = {(i % W, i // W) for i, v in enumerate(back.grid)
             if v in (0x11, 0x12)}
    region, _ = region_map(back.grid)
    doomed, seen = set(), set()
    for c in doors:
        if c in seen:
            continue
        group, stack = set(), [c]
        while stack:
            p = stack.pop()
            if p in group:
                continue
            group.add(p)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (p[0] + dx, p[1] + dy)
                if q in doors and q not in group:
                    stack.append(q)
        seen |= group
        if not gates_something(back.grid, group, region):
            doomed |= group

    changed = False
    out = []
    i = 0
    while i < len(lv.cmds):
        c = lv.cmds[i]
        if c[0] != 'POINT' or c[1] not in (DOORV_PEN, DOORH_PEN):
            out.append(c)
            i += 1
            continue
        _, pen, x, y = c
        n, d = 1, 'E'
        if i + 1 < len(lv.cmds) and lv.cmds[i + 1][0] == 'DRAW':
            d, n = lv.cmds[i + 1][1], lv.cmds[i + 1][2] + 1
        dx, dy = STEP[d]
        cells = [(x + dx * k, y + dy * k) for k in range(n)]
        if all(p in doomed for p in cells):
            out.append(('POINT', WALL_PEN, x, y))
            changed = True
        else:
            out.append(c)
        i += 1
        if n > 1:
            out.append(lv.cmds[i])
            i += 1
    if changed:
        lv.cmds = out
    return changed


# What a level may spend a byte windfall on.  Weighted so the quiet ones
# are as likely as the loud: a level that spends its spare bytes on a
# larder is as much a character as one that spends them on a horde.
# Weighted towards 'plain' after measuring: a windfall on every cheap
# level took monsters to +28% and generators to +30% of the arcade.  A
# character is something a level has now and then, not always.
# 'farm' is left out: generators were already the closest measure to the
# arcade and a windfall of them took the set from -20% to +28%.
WINDFALLS = (['hoard', 'horde', 'larder', 'nest'] + ['plain'] * 6)

# What a level is generous with.  Weighted towards the structural ones,
# because doors and keys are where this set is furthest from the arcade
# and monsters are where it is already over.
CHARACTERS = (['vaults', 'vaults', 'vaults',      # doors and what is behind
               'secrets', 'secrets',              # rooms behind breakable walls
               'keyring', 'keyring',              # keys, and doors to spend
               'trapworks',                       # trap-walls and the trap
               'deaths', 'deaths',                # the thing nothing kills
               'hoard', 'nest', 'crossroads']     # gold, a pack, teleporters
              + ['plain'] * 6)


def spend_windfall(rng, lv, back, kind, room):
    """Spend leftover bytes on one thing, so the level has a character.

    **Not wired in.**  Bolted on after the objects were placed, this
    changed nothing worth having: the spread of monsters across the pool
    went from 0.46 to 0.47 against the arcade's 0.96, because eight to
    sixteen extra objects on top of forty is noise.  It also pushed
    monsters to +21% and generators to +22% of the arcade.

    The idea is right and the placement is the wrong end of it.  Adding a
    character does not create one; the level has to be *built* around it,
    with the ordinary placement leaner so the chosen thing dominates.
    That means choosing the character in dungeon() before the budget is
    split, not topping up afterwards.

    Every structural saving this generator made was handed straight to the
    object placer, which spent it on more of everything: a level that cost
    fewer bytes to draw came back with more monsters rather than more
    interest.  Picking one thing to be generous with is what the shipped
    levels look like - a gold room, a generator farm, a corridor of Deaths
    - and it costs the same bytes.
    """
    at = {(c % W, c // W): k for c, k in lv.objects}
    free = [c for c in room if c not in at]
    if not free or kind == 'plain':
        return False
    rng.shuffle(free)

    def snug(c):
        return 4 - sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                       if (c[0] + dx, c[1] + dy) in room)

    if kind == 'hoard':                    # gold, tucked away together
        free.sort(key=snug, reverse=True)
        code, n = TREASURE, rng.randint(8, 16)
    elif kind == 'horde':                  # one big pack of one kind
        seed = free[0]
        free.sort(key=lambda c: abs(c[0] - seed[0]) + abs(c[1] - seed[1]))
        code, n = 0x40 + rng.randrange(0, 3) * 3, rng.randint(8, 16)
    elif kind == 'farm':                   # generators, scattered
        code, n = 0x20 + rng.randrange(0, 5) * 3, rng.randint(5, 10)
    elif kind == 'larder':                 # food and drink
        code, n = FOOD, rng.randint(4, 9)
    elif kind == 'nest':                   # a knot of the nastier families
        seed = free[0]
        free.sort(key=lambda c: abs(c[0] - seed[0]) + abs(c[1] - seed[1]))
        code, n = 0x40 + rng.randrange(3, 6) * 3, rng.randint(6, 12)
    else:
        return False
    for c in free[:n]:
        lv.objects.append((c[1] * W + c[0], code))
    lv.objects.sort()
    return True


def top_up_keys(rng, lv, back):
    """Set the level's keys to what the way out costs, plus a little.

    A key for every barrier means no decision: the player opens everything
    and the side vaults stop being a gamble.  What matters is the number of
    barriers on the route to the exit - usually one or two - and beyond
    that a small allowance to spend or hoard.  The arcade set needs a key
    to finish on 62 of its 128 levels and carries about three spare."""
    at = {(c % W, c // W): k for c, k in lv.objects}
    starts = [p for p, k in at.items() if k == START]
    exits = [p for p, k in at.items() if k in (EXIT, 0x37, 0x38)]
    if not starts or not exits:
        return False
    need = keys_needed(back.grid, starts[0], exits)
    if 20 < need < 90:
        return False
    if need >= 90:
        # 99 means no route to the exit through doors at all - a
        # teleporter-only exit.  That says nothing about the rest of the
        # map, and bailing here left four such levels with doors, no keys
        # and most of their floor shut away.  Treat the exit as costing
        # nothing and let the allowance below decide.
        need = 0
    nbar = count_barriers(back.grid)
    if nbar == 0:
        want = 0                           # no doors, so no keys
    elif need:
        # A door between the player and the way out used to mean exactly
        # the keys that door costs and no spare, so that a key could not be
        # wasted on a side vault and strand you.  That kept the set at 1.5
        # keys a level against the arcade's 4.7.  The arcade's answer is
        # better: carry enough that spending one on a vault is a choice
        # rather than a trap.
        want = need + rng.choice([0, 1, 2, 3, 3, 4, 5, 5, 6, 7])
        # Exactly enough is not enough when there are other doors to waste
        # a key on.  Level 3 shipped with two keys, two needed, and six
        # barriers: open the wrong vault first and the exit is gone.  Give
        # a spare for every two doors that are not on the way out, at least
        # one whenever any such door exists.
        stray = max(0, nbar - need)
        if stray:
            want = max(want, need + 1 + stray // 2)
        else:
            # nothing to waste a key on: exactly enough, as the arcade's
            # introduction does it - one door, one key, no ambiguity
            want = need
    else:
        # Nothing is compulsory here, so the keys are an allowance to spend
        # on vaults or hoard - but never more of them than there are doors.
        # The arcade carries 4.7 keys a level and locks far more away than
        # this generator did - median 8% of its floor reachable before a
        # key is spent, against 62% here.  It can afford to be mean with
        # doors because it is generous with keys.
        want = min(rng.choice([1, 2, 3, 4, 5, 5, 6, 7, 8, 10]), nbar + 6)
        # ...except that "the exit needs no key" is not the same as "the
        # doors gate nothing".  A level can have the way out in plain sight
        # and most of its map shut away, and this branch was handing those
        # a random allowance that could be zero: eight levels in one set
        # had doors, no keys and up to 92% of the floor unreachable.  The
        # arcade never ships one - it locks more of its map away than this
        # generator does, median 8% reachable before a key is used, and
        # always provides the keys to open it.
        shut = bfs(back.grid, starts[0], doors_open=False, shoot=True,
                   sprung=True, teleport=True)
        opened = bfs(back.grid, starts[0], doors_open=True, shoot=True,
                     sprung=True, teleport=True)
        # a wider margin than the verifier's 0.9, so a level cannot pass
        # here by a few cells and be flagged there
        if opened and len(shut) < 0.97 * len(opened):
            far = max((c for c in opened if c not in shut),
                      key=lambda c: opened[c], default=None)
            if far is not None:
                gated = keys_needed(back.grid, starts[0], [far])
                if gated < 90:
                    want = max(want, gated)
    have = sum(1 for _, k in lv.objects if k == KEY)
    if have == want:
        return False
    if have > want:
        idx = [i for i, (_, k) in enumerate(lv.objects) if k == KEY]
        for i in reversed(idx[want:]):
            lv.objects.pop(i)
        return True
    taken = {c for c, _ in lv.objects}
    free = [i for i, v in enumerate(back.grid) if v == 0 and i not in taken]
    rng.shuffle(free)
    # A key on the way to the exit is not a decision; a key off it is.  The
    # arcade puts 36% of its keys on the route and this set put 50%, so
    # they were being handed over rather than gone for.
    st = [p for p, k in at.items() if k == START]
    ex = [p for p, k in at.items() if k in (EXIT, 0x37, 0x38)]
    if st and ex:
        ds = bfs(back.grid, st[0], doors_open=True, shoot=True,
                 sprung=True, teleport=True)
        goal = min(((ds[e], e) for e in ex if e in ds), default=(None, None))[1]
        if goal is not None:
            de = bfs(back.grid, goal, doors_open=True, shoot=True,
                     sprung=True, teleport=True)
            total = ds[goal]
            def detour(i):
                c = (i % W, i // W)
                if c in ds and c in de:
                    return ds[c] + de[c] - total
                return 0
            free.sort(key=detour, reverse=True)
    for i in free[:want - have]:
        lv.objects.append((i, KEY))
    lv.objects.sort()
    return True


def make(n, seed, shots=0x00, look=(0, 0), want_locked=False,
         want_sealed_exit=False):
    rng = random.Random(seed)
    if n == 1:
        got = signature(rng)
    elif n == 128:
        got = trap_treasure(rng)
    elif n >= 118:
        got = treasure_room(rng, n)
    elif n <= 7:
        # 1-7 are the only levels played in order, so they carry the whole
        # introduction and ramp across themselves
        # The locked exit for levels 2 to 4 is arranged after encoding, in
        # make(); demanding it of the layout as well left level 3 with no
        # layout it could accept at all.
        # one family a level, in the order the arcade introduces them
        got = dungeon(rng, 0.04 + (n - 2) * 0.12,
                      only_family=FAMILIES[min((n - 1) // 2,
                                               len(FAMILIES) - 1)])
    elif n in THEMED:
        got = THEMED[n](rng)
    else:
        # from 8 on the game picks at random from the whole pool, so there
        # is no sense in a curve: as in the arcade, everything past the
        # introduction is equally hard, and the variety is in the layout
        got = dungeon(rng, 1.0,
                      force=('diagonal' if want_diagonal(n)
                             else 'warren' if want_warren(n) else None),
                      want_sealed=want_sealed_exit,
                      shape=('swarm' if want_swarm(n)
                             else 'quiet' if want_quiet(n) else None))
    if got is None:
        return None
    colour = None
    if len(got) == 3:
        walls, objs, colour = got
    else:
        walls, objs = got
    # flags1: wall graphics in bits 3-5, and in bits 0-1 what a shot does
    # to the other player.  Bit 0 hurts, bit 1 stuns, neither is normal -
    # the shipped set runs 102 normal, 26 stun and no hurt, so keep normal
    # the common case but use all three.
    if 118 <= n <= 128:
        # the arcade's treasure rooms carry no food at all: they are the
        # reward, not a chance to recover
        for c in [c for c, k in objs.items() if k in (FOOD, CIDER)]:
            del objs[c]
    gfx, col = look
    lv = build(walls, objs,
               flags1=(gfx << 3) | shots,
               flags2=((col if colour is None else colour) << 3))
    if G.check_vector_grammar(lv.cmds):
        return None
    try:
        data = G.encode(lv)
    except ValueError:
        return None
    # The editor re-encodes from the grid and can produce a slightly larger
    # record than this one.  A level that only just fits at 511 may then be
    # impossible to save, so leave the kit some headroom: a level nobody can
    # edit is no use on an editor's disk.
    if len(data) - 2 > 450:
        return None
    # The vector length is one byte, and the editor appends a no-op to the
    # section whenever it saves.  A level that arrives with 254 vector
    # bytes can never be saved again: leave the editor room to work.
    if data[5] > 246:
        return None

    # Doors that gate nothing become walls again before anything else is
    # decided, so the keys are counted against barriers that matter.
    back = G.decode(data[2:])
    # The two silly levels are silly on purpose: a maze built of doors has
    # a way round every one of them, so the prune would quite correctly
    # wall the lot and take the joke with it.
    silly = THEMED.get(n) in (theme_alldoors, theme_keyring)
    for _ in range(0 if silly else 4):
        # Turning a door changes the pen's top field, which can collide
        # with a neighbouring DRAW.  Keep the facing only if it still
        # encodes, rather than abandoning the whole pass - the pruning in
        # the same pass was being thrown away with it.
        saved = list(lv.cmds)
        turned = face_doors(lv, back)
        if turned and G.check_vector_grammar(lv.cmds):
            lv.cmds = saved
            turned = False
        pruned = prune_doors(lv, back)
        if not pruned and not turned:
            break
        if G.check_vector_grammar(lv.cmds):
            lv.cmds = saved
            break
        try:
            trial = G.encode(lv)
        except ValueError:
            lv.cmds = saved
            break
        data = trial
        back = G.decode(data[2:])

    # Some levels put the way out behind a door.  Which cells decode as
    # locked cannot be known before encoding, so the exit is moved there
    # afterwards, on the grid the game will really see.
    locked = False
    if want_locked:
        # The layout may already have walled the exit in behind a door, in
        # which case there is nothing to relocate: lock_exit_behind_doors
        # would go looking for another region, fail, and the level would be
        # thrown out for want of a lock it already had.
        at0 = {(c % W, c // W): k for c, k in lv.objects}
        st0 = [p for p, k in at0.items() if k == START]
        ex0 = [p for p, k in at0.items() if k in (EXIT, 0x37, 0x38)]
        if st0 and ex0:
            already = keys_needed(back.grid, st0[0], ex0)
            if 0 < already <= 20:
                idx = [i for i, (_, k) in enumerate(lv.objects) if k == KEY]
                for i in reversed(idx[already:]):
                    lv.objects.pop(i)
                if len(idx) < already:
                    taken = {c for c, _ in lv.objects}
                    free = [i for i, v in enumerate(back.grid)
                            if v == 0 and i not in taken]
                    rng.shuffle(free)
                    for i in free[:already - len(idx)]:
                        lv.objects.append((i, KEY))
                    lv.objects.sort()
                try:
                    data = G.encode(lv)
                    locked = True
                except ValueError:
                    pass
    if want_locked and not locked:
        for depth in (rng.choice([1, 1, 2]), 1):
            saved = list(lv.objects)
            if lock_exit_behind_doors(rng, lv, back, depth):
                try:
                    trial = G.encode(lv)
                except ValueError:
                    lv.objects = saved
                    continue
                if len(trial) - 2 <= 450:
                    data = trial
                    locked = True
                    break
            lv.objects = saved
        if not locked:
            # Asking for a locked exit and quietly settling for an open one
            # means the first attempt always wins, because failing to lock
            # costs nothing.  Reject instead and let the next seed try.
            return None

    if locked:
        # The lock was set before the last prune; if that removed a barrier
        # the level can end up carrying a spare key it should not have, so
        # settle the count against the grid as it finally stands.
        back = G.decode(data[2:])
        at2 = {(c % W, c // W): k for c, k in lv.objects}
        st2 = [p for p, k in at2.items() if k == START]
        ex2 = [p for p, k in at2.items() if k in (EXIT, 0x37, 0x38)]
        if st2 and ex2:
            need2 = keys_needed(back.grid, st2[0], ex2)
            have2 = [i for i, (_, k) in enumerate(lv.objects) if k == KEY]
            if len(have2) > need2:
                for i in reversed(have2[need2:]):
                    lv.objects.pop(i)
                try:
                    data = G.encode(lv)
                except ValueError:
                    return None

    # Keys are counted against the barriers the level actually decodes to,
    # which the generator cannot predict, so top them up and re-encode.
    # A locked exit used to be given exactly the keys it needs and skip
    # this, so that no spare could be wasted on a vault.  That was the
    # wrong way round: with other doors on the level a spare is what stops
    # a wrong choice stranding the player, and level 3 shipped with two
    # keys, two needed and six barriers.  Locked levels go through the
    # top-up too now; it only ever adds.
    keeps_own_keys = THEMED.get(n) in (theme_alldoors, theme_keyring)
    for _ in range(0 if (n == 1 or keeps_own_keys) else 3):
        back = G.decode(data[2:])
        if not top_up_keys(rng, lv, back):
            break
        # A door-heavy level can want more keys than the record has room
        # for.  Dropping the level would quietly throw away exactly the
        # levels with the most doors, so shed keys until it fits instead.
        while True:
            try:
                data = G.encode(lv)
            except ValueError:
                data = None
            if data is not None and len(data) - 2 <= 450:
                break
            keys = [i for i, (_, k) in enumerate(lv.objects) if k == KEY]
            if not keys:
                return None
            lv.objects.pop(keys[-1])

    # prove it from the encoded bytes, not from what we meant to write
    back = G.decode(data[2:])
    # playable() decides whether the level works.  There used to be a
    # second, older reachability test here, written before doors were
    # barriers: its flood fill treated $11 and $12 as solid and knew
    # nothing of teleporters or trap-walls, so it threw out every level
    # whose exit was behind a door, walled in with a teleporter, or part
    # of a maze built of doors - the three devices that kept refusing to
    # appear in the set.  One rule, in one place.
    if not playable(back, 118 <= n <= 127):
        return None
    return data


# The wall graphics table at $8C80 has eight slots but only three distinct
# entries: 1 and 3 both point at $6408, 2 and 4 at $6508, and 5-7 point at
# addresses that are not graphics at all ($DC04 is a CIA register), which is
# why the shipped levels never use them.  The colour table at $8C78 has
# seven distinct values, 0 and 7 both being light red.  So there are 3 x 7
# = 21 looks a level can have, and they are dealt out evenly rather than
# rolled, so that no two consecutive levels look the same.
WALL_SETS = [0, 1, 2]                     # one representative of each
WALL_COLOURS = list(range(7))             # 7 duplicates 0


def look_quota(rng):
    looks = [(g, c) for g in WALL_SETS for c in WALL_COLOURS]
    deck = []
    while len(deck) < 128:
        batch = looks[:]
        rng.shuffle(batch)
        if deck and batch[0] == deck[-1]:
            batch.append(batch.pop(0))
        deck += batch
    out = {}
    last = None
    for n in range(1, 129):
        pick = deck.pop(0)
        if pick == last and deck:
            deck.append(pick)
            pick = deck.pop(0)
        out[n] = pick
        last = pick
    return out


def shots_quota(rng):
    """Which levels use friendly fire, as an exact share rather than a coin
    flip per level.

    flags1 bit 0 hurts the other player, bit 1 stuns them, neither is
    normal.  The shipped set is 102 normal to 26 stun and never hurts, so
    normal stays the common case: about a quarter stun, a few hurt, and the
    introduction and the treasure rooms left alone entirely."""
    pool = list(range(8, 118))
    rng.shuffle(pool)
    mode = {n: 0x00 for n in range(1, 129)}
    for n in pool[:27]:                       # a quarter of the pool
        mode[n] = 0x02                        # stun
    for n in pool[27:33]:                     # and a handful that hurt
        mode[n] = 0x01
    mode[128] = 0x02                          # the trap treasure room stuns
    return mode


def want_sealed(n):
    """Levels whose exit is walled in with a teleporter as the only way to
    it.  The arcade does this on fifteen of its 128, nine by teleporter, so
    a dozen here is about the right helping - it is a device, not a
    default."""
    return 8 <= n <= 117 and n % 11 == 4 and n not in THEMED


def _prune_themes():
    for n in _RETURNED_TO_THE_POOL:
        THEMED.pop(n, None)


def want_diagonal(n):
    """Levels built from diagonal walls.

    Measured across every style, diagonal is the best value the format
    offers: 10.6 dead ends for 63 vector bytes, where a warren needs 148
    for 8.  It also passes only one attempt in five, so left to chance it
    loses the race to an easier style and never appears - the same trap
    the warrens and the locked exits fell into.
    """
    # Forced on twenty levels these gave 19.6 dead ends against the
    # arcade's 17.5, while the rest of the set managed 7.1.  Widening the
    # share to two levels in three made the set worse, not better: a
    # diagonal layout costs 63 vector bytes where a warren costs 148, and
    # the change simply handed the saving to the object placer, which
    # spent it on monsters (+26%) and generators (+41%) without the dead
    # ends rising to match.  A third of the pool is what the budget will
    # carry.
    return 8 <= n <= 117 and n % 3 != 0 and n not in THEMED


def want_warren(n):
    """Which levels are built as warrens: a shallow map with two or three
    deep maze patches cut into it.  Every third of the pool, which lands
    the set near the arcade's seventeen dead ends a level."""
    # not also a sealed-exit level: asking one layout for both a maze and a
    # walled-in exit almost never succeeds, and level 15 could not be built
    # at all until they were kept apart
    return (8 <= n <= 117 and n % 4 != 0 and n not in THEMED
            and not want_sealed(n) and not want_diagonal(n))


def want_lock(n):
    """Levels 2 to 4 teach the door: the way out is behind one, with exactly
    the key for it.  Half the pool does the same.  Themed levels have their
    own key-and-exit designs and are left alone."""
    return (2 <= n <= 4) or (8 <= n <= 117 and n % 2 == 0 and n not in THEMED)


_prune_themes()


def main(argv=None):
    """Generate 128 levels.  --seed changes the whole set; --out chooses
    where the files land, so a run cannot quietly overwrite another."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--difficulty', default='arcade',
                    choices=sorted(DIFFICULTIES),
                    help='how hard the set plays: gentle, easy, arcade '
                         '(the original game\'s own numbers), hard, brutal')
    ap.add_argument('--seed', type=int, default=0,
                    help='master seed: a different one gives a different '
                         '128 levels')
    ap.add_argument('--out', default=os.path.join(HERE, 'levels'),
                    help='directory to write LEVEL_nnn.prg into')
    args = ap.parse_args(argv)
    SCALE.clear()
    SCALE.update(DIFFICULTIES[args.difficulty])
    print('difficulty: %s' % args.difficulty)
    return build_set(args.seed, args.out)


def build_set(master=0, outdir=None):
    """Generate the whole 128-level set.  Named apart from build(), which
    makes a single level: the two collided and every level failed to
    encode."""
    if outdir is None:
        outdir = os.path.join(HERE, 'levels')
    # Clear the output before starting.  A run that fails partway used to
    # write nothing and leave the previous run's files in place, so the
    # verifier passed on stale levels and the failure looked like success.
    import os
    import glob
    os.makedirs(outdir, exist_ok=True)
    for f in glob.glob(os.path.join(outdir, 'LEVEL_*.prg')):
        os.remove(f)

    out = {}
    mode = shots_quota(random.Random(20260908 + master))
    looks = look_quota(random.Random(20260909 + master))
    for n in range(1, 129):
        for attempt in range(600):
            # Some level numbers never throw up a layout that can host a
            # locked exit; after a good try, take an open one rather than
            # failing the whole build.
            lock = want_lock(n) and attempt < 400
            seal = want_sealed(n) and attempt < 450
            data = make(n, master * 1000000 + n * 1000 + attempt,
                        shots=mode[n], look=looks[n],
                        want_locked=lock, want_sealed_exit=seal)
            if data:
                out[n] = data
                break
        else:
            sys.exit('level %d would not generate' % n)
    sizes = [len(d) - 2 for d in out.values()]
    print('generated %d levels, %d-%d bytes, %d average'
          % (len(out), min(sizes), max(sizes), sum(sizes) // len(sizes)))
    import os
    for n, d in out.items():
        open(os.path.join(outdir, 'LEVEL_%03d.prg' % n), 'wb').write(d)
    return out


if __name__ == '__main__':
    main()
