#!/usr/bin/env python3
"""
gauntlet_dd.py — codec for "LEVEL nnn" files from
Gauntlet: The Deeper Dungeons (C64).

Reimplements the game's own level loader ($C43D in GAUNTPROG $8000).
Verified: all 128 level files on the disk decode and re-encode
byte-for-byte identically.

  python3 gauntlet_dd.py show   LEVEL_001.prg
  python3 gauntlet_dd.py dump   LEVEL_001.prg      # command listing
  python3 gauntlet_dd.py verify <dir-of-prg-files>
"""

W = H = 32
MAP_SIZE = W * H                      # 1024 bytes, lives at $0C00 in the C64

# --- $C816: pen type (top 3 bits of a POINT byte) -> tile written ---
PEN_TILE = [0x00, 0x36, 0x11, 0x00, 0x12, 0x00, 0x90, 0x10]

# --- $C7F9: the 8 heading vectors, as offsets into the 1K map ---
DIR_DELTA = [-32, -31, 1, 33, 32, 31, 4095, -33]   # 4095 == -1 (mod 1024)
DIR_NAME = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
DIR_INDEX = {n: i for i, n in enumerate(DIR_NAME)}

# --- $C81E: walls re-orient to the heading they are drawn along ---
WALL_REORIENT = [0x40, 0x80, 0x40, 0x80]           # indexed by dir >> 1

OBJ_TREASURE   = 0x13
OBJ_EXIT       = 0x36
OBJ_EXIT_COND  = (0x37, 0x38)
OBJ_START      = 0x3F
ACTOR_MIN      = 0x40


# ----------------------------------------------------------------------
# Model
# ----------------------------------------------------------------------

class Level:
    def __init__(self):
        self.flags1 = 0          # $0A01
        self.flags2 = 0          # $0A02
        self.cmds = []           # ('POINT', pen, x, y) | ('DRAW', dirname, length)
        self.objects = []        # (cell_index, code), ascending cell order
        self.grid = bytearray(MAP_SIZE)
        self.vec = b''          # the record's vector bytes, kept verbatim
        self.obj_top = None     # top 3 bits of the original first object byte
        self.vec_final = b''    # vector bytes actually written by the last save
        self.obj_head = b'\x80\x80'   # first object bytes, for lookahead fidelity

    # --- header field accessors ---
    @property
    def wall_set(self):     return (self.flags1 >> 3) & 7
    @property
    def wall_colour(self):  return (self.flags2 >> 3) & 7
    def random_exit(self):  return bool(self.flags1 & 0x04)
    @property
    def wrap_h(self):       return bool(self.flags1 & 0x80)
    @property
    def wrap_v(self):       return bool(self.flags1 & 0x40)

    def exits(self):
        return [(c % W, c // W) for c, code in self.objects if code == OBJ_EXIT]

    def actors(self):
        return [(c, code) for c, code in self.objects if code >= ACTOR_MIN]

    def start(self):
        for c, code in self.objects:
            if code == OBJ_START:
                return (c % W, c // W)
        return None


# ----------------------------------------------------------------------
# Decoding
# ----------------------------------------------------------------------

def decode(data):
    """data = level file contents with the 2-byte PRG load address stripped."""
    lv = Level()
    lv.flags1 = data[1]
    lv.flags2 = data[2]
    total = data[0] | ((data[2] >> 7) << 8)
    veclen = data[3]
    lv.total, lv.veclen = total, veclen
    lv.objlen = total - veclen - 4

    g = lv.grid
    for x in range(W):                      # $C4AD
        g[x] = 0x0A
    if not (lv.flags1 & 0x80):              # $C4B8
        g[0] = 0x0F
        for r in range(1, H):
            g[r * W] = 0x05

    lv.vec = bytes(data[4:4 + veclen])
    if lv.objlen > 0:
        lv.obj_top = data[4 + veclen] & 0xE0
        lv.obj_head = bytes(data[4 + veclen:4 + veclen + 2]).ljust(2, b'\x80')

    # ---- vector section ($C454 dispatcher) ----
    v = data[4:]            # lookahead may run past veclen, exactly as the game does
    def top(k):
        return (v[k] if k < len(v) else 0) & 0xE0

    ptr, pen, i, left = 0, 0x00, 0, veclen
    while left > 0:
        if left == 1 or top(i) != top(i + 1):
            is_point = False
        elif left == 3:
            is_point = top(i + 1) != top(i + 2)
        elif top(i + 1) != top(i + 2):
            is_point = True
        else:
            is_point = top(i + 2) == top(i + 3)

        if is_point:                                        # $C4F1
            b0, b1 = v[i], v[i + 1]
            pen = b0 & 0xE0
            x, y = b0 & 0x1F, b1 & 0x1F
            ptr = y * W + x
            g[ptr] = PEN_TILE[pen >> 5]
            lv.cmds.append(('POINT', pen, x, y))
            i += 2; left -= 2
        else:                                               # $C522
            b = v[i]
            d, n = b >> 5, b & 0x1F
            if pen in (0x40, 0x80):
                pen = WALL_REORIENT[d >> 1]
            for _ in range(n + 1):
                ptr = (ptr + DIR_DELTA[d]) & 0x3FF
                g[ptr] = PEN_TILE[pen >> 5]
            lv.cmds.append(('DRAW', DIR_NAME[d], n + 1))
            i += 1; left -= 1

    # ---- object section ($C68D) ----
    o = data[4 + veclen: 4 + veclen + lv.objlen]
    ptr, j = 0, 0
    while j < len(o) and ptr < MAP_SIZE:
        b = o[j]
        if b & 0x80:                       # skip (b & $7F) + 1 cells
            ptr += (b & 0x7F) + 1
            j += 1
            continue
        code, count = b, 1
        if j + 1 < len(o) and o[j + 1] < 0x13:
            count = o[j + 1] + 2           # repeat byte: n -> n + 2 copies
            j += 1
        j += 1
        for _ in range(count):
            if ptr >= MAP_SIZE:
                break
            g[ptr] = code
            lv.objects.append((ptr, code))
            ptr += 1
    lv.trailing = len(o) - j
    return lv


# ----------------------------------------------------------------------
# Encoding
# ----------------------------------------------------------------------

def encode_vectors(cmds):
    out = bytearray()
    for c in cmds:
        if c[0] == 'POINT':
            _, pen, x, y = c
            if pen & 0x1F or not (0 <= x < W and 0 <= y < H):
                raise ValueError('bad POINT %r' % (c,))
            out += bytes([pen | x, pen | y])
        else:
            _, dname, n = c
            if not 1 <= n <= 32:
                raise ValueError('DRAW length must be 1-32: %r' % (c,))
            out.append((DIR_INDEX[dname] << 5) | (n - 1))
    return bytes(out)


def encode_objects(objs, first_top=None):
    """Encode the sparse object layer.

    first_top pins the top 3 bits of the very first byte. The vector
    dispatcher can look ahead into the object section, so changing that byte
    can change how the walls decode; passing the original byte's top field
    keeps the wall layout stable. A skip byte is $80|(n-1), whose top field
    is $80/$A0/$C0/$E0 for n-1 in 0-31/32-63/64-95/96-127, so the leading
    skip is split to land in the required band.
    """
    out = bytearray()
    pos, i = 0, 0
    if first_top is not None and objs and objs[0][0] > 0 and first_top >= 0x80:
        gap = objs[0][0]
        band = ((first_top - 0x80) >> 5) * 32         # 0, 32, 64 or 96
        if gap > band:                                # band reachable?
            n = min(gap, band + 32)
            out.append(0x80 | (n - 1))
            pos = n
    while i < len(objs):
        cell, code = objs[i]
        gap = cell - pos
        while gap > 0:                        # skips cover 1..128 cells each
            n = min(gap, 128)
            out.append(0x80 | (n - 1))
            gap -= n
        run = 1
        while (i + run < len(objs) and objs[i + run][1] == code
               and objs[i + run][0] == cell + run):
            run += 1
        consumed = run
        while run > 0:
            if run == 1:
                out.append(code); take = 1
            else:
                take = min(run, 0x14)         # max 20 copies per repeat pair
                out += bytes([code, take - 2])
            run -= take
        pos = cell + consumed
        i += consumed
    return bytes(out)


# tile -> a pen that plots it.  $00 and $60 both plot floor; $60 is the
# spare used when $00 would merge with a neighbouring group.
TILE_PEN = {0x10: 0xE0, 0x90: 0xC0, 0x11: 0x40, 0x12: 0x80,
            0x36: 0x20, 0x92: 0x20, 0x00: 0x00}


def vector_only_grid(lv, vec=None):
    """The wall layout the vector section alone produces."""
    """The dispatcher can look ahead into the object section, so the real
    first object bytes are supplied to keep the wall parse faithful."""
    v = lv.vec if vec is None else vec
    total = 4 + len(v)                       # object length 0 ...
    hdr = bytes([total & 0xFF, lv.flags1,
                 0x80 if total > 255 else 0x00, len(v)])
    return decode(hdr + v + lv.obj_head).grid   # ... but the bytes are there
                                                # for the lookahead to read


def wall_edits(lv):
    """POINT commands that turn the original wall layout into the current one.

    Appended after the original vector bytes, so they override it. Cells
    that an object covers are skipped - the object layer runs last and hides
    whatever is underneath."""
    base = vector_only_grid(lv)
    out = []
    for i in range(MAP_SIZE):
        t = lv.grid[i]
        if 0x13 <= t <= 0x7F:          # an object sits here; wall is hidden
            continue
        if base[i] == t or t not in TILE_PEN:
            continue
        out.append((TILE_PEN[t], i % W, i // W))
    return out


def edit_runs(edits):
    """The same edits, as straight runs: (pen, x, y, direction, length).

    A player paints a wall a cell at a time, and saving every cell as its
    own POINT costs two bytes each - a 46-cell wall came to 92 bytes where
    a POINT and a DRAW cover it in three, and a level that should have fit
    reported TOO BIG.  Adjacent same-pen cells in a straight line become
    one run.  Only horizontal and vertical runs, and never in a direction
    whose top field equals the pen's, because the decoder would read the
    DRAW byte as part of the POINT group.
    """
    cells = {}
    for pen, x, y in edits:
        cells.setdefault(pen, set()).add((x, y))
    runs = []
    for pen, left in cells.items():
        pf = pen >> 5
        # a direction to draw in, whose field is not the pen's
        horiz = 'E' if DIR_INDEX['E'] != pf else 'W'
        vert = 'S' if DIR_INDEX['S'] != pf else 'N'
        left = set(left)
        while left:
            c = min(left)
            best, bd = [c], horiz
            for d in (horiz, vert):
                dx, dy = {'E': (1, 0), 'W': (-1, 0), 'S': (0, 1), 'N': (0, -1)}[d]
                run, p = [], c
                while p in left:
                    run.append(p)
                    p = (p[0] + dx, p[1] + dy)
                if len(run) > len(best):
                    best, bd = run, d
            runs.append((pen, best[0][0], best[0][1], bd, len(best)))
            left -= set(best)
    return runs


DIR8 = [('N', 0, -1), ('NE', 1, -1), ('E', 1, 0), ('SE', 1, 1),
        ('S', 0, 1), ('SW', -1, 1), ('W', -1, 0), ('NW', -1, -1)]


def edit_polylines(edits, wild=(), policy=None):
    """The edits as polylines: one POINT, then a DRAW per straight leg.

    A snake wall - right, down, right, up - is one shape to the person
    who painted it, and the format can say so: the turtle keeps its
    position after a DRAW, so the next DRAW carries on from the corner.
    Emitting a fresh POINT at every corner cost a 31-cell snake 17 bytes
    where a polyline is 6.

    Two rules keep the decoder honest.  A DRAW's direction field must
    differ from the pen's field, or the byte is folded into the POINT's
    group; and consecutive DRAWs must differ in field, or they group as
    POINT bytes.  A leg that would repeat the previous direction - only
    possible past 32 cells - starts a new POINT instead.
    """
    # Doors are one pen class: at $C81E a DRAW re-orients a door pen to
    # its heading, so a leg going N or S draws vertical doors and one
    # going E or W horizontal ones, whichever pen the POINT had.  Atari
    # draws a staircase of alternating doors as one polyline of N and W
    # legs.  Keying doors by pen made every horizontal door in such a
    # staircase its own POINT: 158 on level 27 where Atari uses 28.
    # policy: how legs and starts are chosen.  The greedy walk below is
    # a heuristic, and different heuristics win on different maps: a
    # level of doors is best drawn as long spines with fix-ups after,
    # a lattice as the longest new run each time.  The save tries each
    # and keeps the smallest.
    policy = policy or {}
    by_length = policy.get('by_length', False)   # score legs by total length
    start_hi = policy.get('start_hi', False)     # start where most neighbours
    ortho = policy.get('ortho', False)           # no diagonal legs
    seed = policy.get('seed')                    # randomise tie-breaks
    rnd = __import__('random').Random(seed) if seed is not None else None
    DOOR = 'door'
    cells = {}
    door_pen = {}
    for pen, x, y in edits:
        key = DOOR if pen in (0x40, 0x80) else pen
        cells.setdefault(key, set()).add((x, y))
        if key == DOOR:
            door_pen[(x, y)] = pen
    wild = set(wild)
    cmds = []
    for key, allc in cells.items():
        left = set(allc)                    # still to be covered
        through = allc | wild
        while left:
            def degree(c):
                return sum(1 for _, dx, dy in DIR8 if (c[0] + dx, c[1] + dy) in allc)
            start = min(left, key=lambda c: ((-degree(c) if start_hi else degree(c)),
                                             rnd.random() if rnd else 0, c))
            pen = door_pen[start] if key == DOOR else key
            pf = pen >> 5
            cmds.append(('POINT', pen, start[0], start[1]))
            left.discard(start)
            here = start
            last_field = pf
            while True:
                best, bd, bf, bnew = [], None, None, 0
                for f, (name, dx, dy) in enumerate(DIR8):
                    if f == last_field:
                        continue
                    if ortho and f & 1:
                        continue
                    # A door leg draws the kind of door its heading
                    # makes.  It may still cross a door of the other
                    # kind - drawing it wrong - as long as that cell is
                    # not yet covered: a later leg will draw it right,
                    # and the last command wins.  Atari runs the whole
                    # left edge of level 27 as vertical doors and fixes
                    # the horizontal ones afterwards.  A cell already
                    # covered correctly must not be crossed wrongly.
                    need = WALL_REORIENT[f >> 1] if key == DOOR else None
                    leg, p = [], (here[0] + dx, here[1] + dy)
                    while p in through and len(leg) < 32:
                        if need is not None and p in allc and door_pen[p] != need \
                                and p not in left:
                            break
                        leg.append(p)
                        p = (p[0] + dx, p[1] + dy)
                    # bind need now: a closure over the loop variable
                    # would see whichever direction was tried last
                    good = (lambda c, n=need: door_pen.get(c) == n) if need is not None \
                        else (lambda c: True)
                    while leg and not (leg[-1] in left and good(leg[-1])):
                        leg.pop()
                    new = sum(1 for c in leg if c in left and good(c))
                    score = (len(leg) if by_length else new, new) if new else (0, 0)
                    bscore = (len(best) if by_length else bnew, bnew) if bnew else (0, 0)
                    if score > bscore or (score == bscore and new and len(leg) < len(best)):
                        best, bd, bf, bnew = leg, name, f, new
                        bgood = good
                if not best:
                    break
                cmds.append(('DRAW', bd, len(best)))
                left -= {c for c in best if bgood(c)}
                here = best[-1]
                last_field = bf
    return cmds


POLICIES = [{}, {'by_length': True}, {'start_hi': True},
            {'by_length': True, 'start_hi': True}, {'ortho': True},
            {'by_length': True, 'ortho': True}]


def best_polylines(edits, wild, floor):
    """The smallest encoding any policy produces."""
    best = None
    for pol in POLICIES:
        cmds = separate_groups(edit_polylines(edits, wild, pol), floor)
        if check_vector_grammar(cmds):
            continue
        n = len(encode_vectors(cmds))
        if best is None or n < best[0]:
            best = (n, cmds)
    return best[1] if best else separate_groups(edit_polylines(edits, wild), floor)


def separate_groups(cmds, floor):
    """Insert no-op POINTs where the decoder would misgroup.

    Consecutive bytes with the same top field form a group, and in a group
    of odd length the decoder takes the byte three from the end as a
    DRAW.  So a DRAW of field F followed by a POINT whose pen is F forms
    a three-byte group that reads correctly - but only if the group ends
    there.  Another POINT of pen F makes it five bytes, and the DRAW is
    now read as POINT data.  The guard is the C64 kit's putnop: before a
    POINT whose pen field matches the DRAW before it, plot a floor cell
    with a pen of a different field.  Floor pens $00, $60 and $A0 have
    fields 0, 3 and 5, so one always differs.  `floor` is a cell that is
    floor in the final map, so the no-op changes nothing.
    """
    out = []
    last_draw_field = None
    for i, c in enumerate(cmds):
        if c[0] == 'POINT':
            pf = c[1] >> 5
            if last_draw_field is not None and pf == last_draw_field:
                # [DRAW, POINT] is a valid three-byte group on its own;
                # it breaks only if the group continues with another
                # same-field POINT
                nxt = cmds[i + 1] if i + 1 < len(cmds) else None
                if nxt and nxt[0] == 'POINT' and (nxt[1] >> 5) == pf:
                    nop_pen = next(p for p in (0x00, 0x60, 0xA0) if (p >> 5) != pf)
                    out.append(('POINT', nop_pen, floor[0], floor[1]))
            out.append(c)
            last_draw_field = None
        else:
            out.append(c)
            last_draw_field = DIR_INDEX[c[1]]
    return out


def runs_to_bytes(runs):
    """Encode runs as POINT + DRAW pairs.  A run of one is a bare POINT.

    Goes through encode_vectors so the DRAW byte is built the one way the
    decoder reads it: the POINT plots the first cell and DRAW n plots n
    more.  Hand-rolling the byte here plotted one cell too many."""
    cmds = []
    for pen, x, y, d, n in runs:
        cmds.append(('POINT', pen, x, y))
        if n > 1:
            cmds.append(('DRAW', d, n - 1))
    return encode_vectors(cmds)


def objects_from_grid(lv):
    """Which cells the object layer must write, given the grid and the
    level's vector bytes.

    Not simply every cell in $13-$7F: pen $20 plots $36 from the *vector*
    layer, so those cells are already there and must not be emitted twice.
    Replay the vector section alone and emit only the differences."""
    base = vector_only_grid(lv, lv.vec_final)
    return [(i, lv.grid[i]) for i in range(MAP_SIZE)
            if 0x13 <= lv.grid[i] <= 0x7F and base[i] != lv.grid[i]]


def save_patched(lv, load_addr=0x0A00):
    """Rebuild the record keeping the original vector bytes untouched and
    re-emitting only the object layer from the current grid.

    This is what the editor uses. Walls are whatever the level shipped with,
    so they cannot be corrupted or grow; every object edit is exact. Levels
    whose walls have been changed need the full encoder instead."""
    # walls first: any cell the editor changed becomes an appended POINT
    edits = wall_edits(lv)
    wild = [(i % W, i // W) for i in range(MAP_SIZE) if 0x13 <= lv.grid[i] <= 0x7F]
    floor = next(((i % W, i // W) for i in range(MAP_SIZE) if lv.grid[i] == 0), (1, 1))
    poly = encode_vectors(best_polylines(edits, wild, floor))
    chained = runs_to_bytes(edit_runs(edits))
    bare = b''.join(bytes([p | x, p | y]) for p, x, y in edits)
    base_vec = lv.vec + poly
    sep = lv.vec + bytes([0x60, 0x60]) + poly
    base_bare = lv.vec + bare
    sep_bare = lv.vec + bytes([0x60, 0x60]) + bare

    # Candidate vector sections. The original is tried first so an unedited
    # save is byte-identical. If the dispatcher's lookahead makes the wall
    # parse depend on object bytes, append a no-op POINT: pens $00 and $60
    # both plot floor, and their top fields are below $80, so they can never
    # match a leading skip byte. The final group then resolves without the
    # decoder ever needing to look at the object section.
    vecs = [base_vec, sep, lv.vec + chained, lv.vec + bytes([0x60, 0x60]) + chained,
            base_bare, sep_bare]
    floor = next((i for i in range(MAP_SIZE) if lv.grid[i] == 0x00), None)
    if floor is not None:
        for v0 in list(vecs):
            for pen in (0x00, 0x60):
                if v0 and (v0[-1] & 0xE0) == pen:
                    continue
                vecs.append(v0 + bytes([pen | (floor % W), pen | (floor // W)]))

    obj = None
    lv_vec = lv.vec
    for vec in vecs:
        lv.vec_final = vec
        objs = objects_from_grid(lv)
        for pin in (lv.obj_top, 0x80, 0xA0, 0xC0, 0xE0, None):
            cand = encode_objects(objs, first_top=pin)
            total = 4 + len(vec) + len(cand)
            if total > 511 or len(vec) > 255:
                continue
            f2 = (lv.flags2 & 0x7F) | (0x80 if total > 255 else 0)
            trial = bytes([total & 0xFF, lv.flags1, f2, len(vec)]) + vec + cand
            if _lookahead_extent(trial) < total and decode(trial).grid == lv.grid:
                obj, lv_vec = cand, vec
                break
        if obj is not None:
            break
    if obj is None:
        raise ValueError('cannot encode: too big, or no leading skip reaches '
                         'the band the wall parse needs')
    if not obj:
        raise ValueError('level needs at least one object')
    total = 4 + len(lv_vec) + len(obj)
    f2 = (lv.flags2 & 0x7F) | (0x80 if total > 255 else 0)
    body = bytes([total & 0xFF, lv.flags1, f2, len(lv_vec)]) + lv_vec + obj
    if _lookahead_extent(body) >= total:
        raise ValueError('vector lookahead runs off the record')
    back = decode(body)
    if back.grid != lv.grid:
        raise ValueError('grid not reproduced')
    return bytes([load_addr & 0xFF, load_addr >> 8]) + body


def encode(lv, load_addr=0x0A00):
    """Build a complete .prg. Raises if the result would not decode back."""
    return encode_sections(lv.flags1, lv.flags2, encode_vectors(lv.cmds),
                           encode_objects(lv.objects), lv.cmds, lv.objects,
                           load_addr)


def encode_sections(flags1, flags2, vec, obj, cmds, objects, load_addr=0x0A00):
    """Assemble prebuilt sections into a record and prove it decodes back to
    exactly `cmds` and `objects`."""
    if len(vec) > 255:
        raise ValueError('vector section exceeds 255 bytes')
    if len(obj) == 0:
        # The game enters its object loop unconditionally, then underflows
        # the byte counter and floods the map. Every level needs an object.
        raise ValueError('object section must not be empty')
    for code in (c for _, c in objects):
        if not 0x13 <= code <= 0x7F:
            raise ValueError('object code $%02X outside $13-$7F' % code)
    total = 4 + len(vec) + len(obj)
    if total > 511:
        raise ValueError('level exceeds 511 bytes')
    f2 = (flags2 & 0x7F) | (0x80 if total > 255 else 0x00)
    body = bytes([total & 0xFF, flags1, f2, len(vec)]) + vec + obj
    if _lookahead_extent(body) >= total:
        # The dispatcher would read past the record into whatever RAM held
        # the previous level: nondeterministic on real hardware.
        raise ValueError('vector lookahead reads past end of record')
    back = decode(body)
    if back.cmds != cmds:
        raise ValueError('encoding is ambiguous — see check_vector_grammar()')
    if back.objects != objects:
        raise ValueError('object section does not round-trip')
    return bytes([load_addr & 0xFF, load_addr >> 8]) + body


def _lookahead_extent(body):
    """Highest record offset the game's vector dispatcher will read."""
    veclen = body[3]
    v = body[4:]
    def top(k):
        return (v[k] if k < len(v) else 0) & 0xE0
    i, left, hi = 0, veclen, -1
    while left > 0:
        if left == 1:
            pt = False; hi = max(hi, i)
        elif top(i) != top(i + 1):
            pt = False; hi = max(hi, i + 1)
        elif left == 3:
            pt = top(i + 1) != top(i + 2); hi = max(hi, i + 2)
        elif top(i + 1) != top(i + 2):
            pt = True; hi = max(hi, i + 2)
        else:
            pt = top(i + 2) == top(i + 3); hi = max(hi, i + 3)
        if pt:
            i += 2; left -= 2
        else:
            i += 1; left -= 1
    return hi + 4


def check_vector_grammar(cmds):
    """Return a list of complaints about DRAW placement, or [] if the
    command list will survive a decode/encode round trip.

    The decoder carries no opcode byte: it splits the stream into maximal
    groups of bytes sharing the same top-3-bit field, and within a group of
    L bytes it reads POINTs except for a single DRAW three bytes from the
    end (or the whole group, when L == 1)."""
    b = encode_vectors(cmds)
    if len(b) > 255:
        return ['vector section exceeds 255 bytes']
    total = len(b) + 5                           # + one dummy object byte
    hdr = bytes([total & 0xFF, 0, 0x80 if total > 255 else 0, len(b)])
    if decode(hdr + b + b'\x3f').cmds != cmds:
        return ['command list does not survive a round trip']
    return []


# ----------------------------------------------------------------------
# Runtime map transforms ($CE00)
# ----------------------------------------------------------------------

# $CDF0 / $CDE0: wall connectivity nibble remaps. A mirror has to swap the
# east/west (bits 1,3) or north/south (bits 0,2) connection bits.
REMAP_H = [0x00, 0x01, 0x08, 0x09, 0x04, 0x05, 0x0C, 0x0D,
           0x02, 0x03, 0x0A, 0x0B, 0x06, 0x07, 0x0E, 0x0F]
REMAP_V = [0x00, 0x04, 0x02, 0x06, 0x01, 0x05, 0x03, 0x07,
           0x08, 0x0C, 0x0A, 0x0E, 0x09, 0x0D, 0x0B, 0x0F]


def _remap(v, table):
    if (v & 0x7F) < 0x10:
        return table[v & 0x7F] | (v & 0x80)
    return v


def flip_h(grid):
    # $CD4F: mirror columns, x <-> (32 - x) mod 32. Columns 0 and 16 are fixed.
    out = bytearray(MAP_SIZE)
    for y in range(H):
        for x in range(W):
            out[y * W + ((W - x) % W)] = _remap(grid[y * W + x], REMAP_H)
    return out


def flip_v(grid):
    # $CCC8: mirror rows, y <-> (32 - y) mod 32. Rows 0 and 16 are fixed.
    out = bytearray(MAP_SIZE)
    for y in range(H):
        for x in range(W):
            out[((H - y) % H) * W + x] = _remap(grid[y * W + x], REMAP_V)
    return out


def orient(grid, bits):
    # Apply the game's random orientation; bits 0-3 as held in $CE1C.
    # Levels 1-7 are exempt and never transformed.
    g = grid
    if bits & 1:
        g = flip_h(g)
    if bits & 2:
        g = flip_v(g)
    return g


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------

LEGEND = {0x00: '.', 0x05: '|', 0x0A: '-', 0x0F: '+',
          0x10: '#', 0x11: '#', 0x12: '#', 0x90: '%',
          OBJ_EXIT: 'X', OBJ_TREASURE: '$', OBJ_START: '@'}


def render(lv):
    rows = []
    for y in range(H):
        r = ''
        for x in range(W):
            c = lv.grid[y * W + x]
            if c in LEGEND:
                r += LEGEND[c]
            elif c >= ACTOR_MIN:
                r += 'abcdefgh'[(c & 0x38) >> 3]
            else:
                r += 'o'
            r += ''
        rows.append(r)
    return '\n'.join(rows)


# ----------------------------------------------------------------------

def main():
    import sys, glob, os
    mode, path = sys.argv[1], sys.argv[2]
    if mode == 'verify':
        files = sorted(glob.glob(os.path.join(path, '*.prg')))
        ok = 0
        for p in files:
            raw = open(p, 'rb').read()
            lv = decode(raw[2:])
            if encode(lv) == raw and lv.trailing == 0:
                ok += 1
            else:
                print('MISMATCH', p)
        print('%d/%d files round-trip byte-for-byte' % (ok, len(files)))
        return
    lv = decode(open(path, 'rb').read()[2:])
    print('bytes=%d  vector=%d  objects=%d  flags=$%02X/$%02X  '
          'wall-set=%d colour=%d random-exit=%s  start=%s  actors=%d'
          % (lv.total, lv.veclen, lv.objlen, lv.flags1, lv.flags2,
             lv.wall_set, lv.wall_colour, lv.random_exit(), lv.start(),
             len(lv.actors())))
    if mode == 'show':
        print(render(lv))
    elif mode == 'dump':
        for c in lv.cmds:
            print('  POINT pen=$%02X at (%2d,%2d)' % c[1:] if c[0] == 'POINT'
                  else '  DRAW  %-2s x%d' % (c[1], c[2]))
        print('  --- objects ---')
        for cell, code in lv.objects:
            print('  $%02X at (%2d,%2d)' % (code, cell % W, cell // W))


if __name__ == '__main__':
    main()
