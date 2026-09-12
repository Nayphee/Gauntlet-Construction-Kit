#!/usr/bin/env python3
"""The editing model behind gauntkit-pc, with no user interface attached.

Everything here can be exercised without a screen, which is the point: the
GUI on top is a few hundred lines of widget code that cannot be tested in
a sandbox, so all of the behaviour that could go wrong lives down here
instead - loading, painting, the byte ceiling, undo, and saving.

The save path is the same one the C64 editor uses: keep the level's
original vector bytes, append a POINT for every wall cell that changed,
and re-emit the object layer from the grid.  Walls therefore cannot be
corrupted by an edit, and an untouched level saves byte-identical.
"""
import os
import struct

import gauntlet_dd as G

W = H = 32
MAX_RECORD = 511
SAFE_RECORD = 450          # what the game's own sets stay under


# What the palette offers.  Each entry is (code, name, colour); the colour
# is advisory, for whatever draws this, and the glyph is what gets printed
# in the cell - colour alone made a map of 37 shades that nobody could
# read.  $32 is deliberately absent: it has
# a graphic but no step handler, so it behaves as a wall nothing can pass,
# shoot or collect - the C64 kit leaves it out for the same reason.
PALETTE = [
    (0x00, 'floor',         '#202020', ' '),
    (0x10, 'wall',          '#9a9a9a', '#'),
    (0x11, 'door up',       '#6ad2c8', '|'),
    (0x12, 'door across',   '#6ad2c8', '='),
    (0x33, 'breakable',     '#7a6a4a', '%'),
    (0x90, 'trap-wall',     '#b06a30', '!'),
    (0x2F, 'trap',          '#e04020', 'T'),
    (0x13, 'treasure',      '#d08a20', '$'),
    (0x14, 'cider',         '#c04040', 'c'),
    (0x15, 'food',          '#c04040', 'f'),
    (0x16, 'magic blue',    '#5060d0', 'm'),
    (0x17, 'magic yellow',  '#d0c040', 'm'),
    (0x18, 'amulet',        '#b060c0', 'A'),
    (0x31, 'poison',        '#508050', 'p'),
    (0x1F, 'key',           '#d0d0d0', 'k'),
    (0x30, 'teleporter',    '#40c040', 'O'),
    (0x36, 'exit',          '#ffffff', 'X'),
    (0x37, 'exit to 4',     '#ffffff', '4'),
    (0x38, 'exit to 8',     '#ffffff', '8'),
    (0x3F, 'start',         '#ffff40', '@'),
    (0x40, 'ghost',         '#b0b0f0', 'g'),
    (0x48, 'grunt',         '#f0b0b0', 'G'),
    (0x50, 'demon',         '#f08040', 'D'),
    (0x58, 'lobber',        '#a0f0a0', 'L'),
    (0x60, 'sorcerer',      '#d0a0f0', 'S'),
    (0x68, 'Death',         '#f04040', '+'),
    (0x20, 'gen: ghost',    '#7070a0', 'g'),
    (0x23, 'gen: grunt',    '#a07070', 'G'),
    (0x26, 'gen: demon',    '#a06030', 'D'),
    (0x29, 'gen: lobber',   '#60a060', 'L'),
    (0x2C, 'gen: sorcerer', '#9070a0', 'S'),
    (0x19, 'pot: armour',   '#8060a0', 'a'),
    (0x1A, 'pot: carry',    '#8060a0', 'a'),
    (0x1B, 'pot: magic',    '#8060a0', 'a'),
    (0x1C, 'pot: shot pwr', '#8060a0', 'a'),
    (0x1D, 'pot: shot spd', '#8060a0', 'a'),
    (0x1E, 'pot: fight',    '#8060a0', 'a'),
]

# A generator draws its family's letter on a dark square; a live monster
# draws the same letter on a light one, so the two read apart at a glance
# without needing two alphabets.
GEN_CODES = set(range(0x20, 0x2F))

NAME = {c: n for c, n, _, _ in PALETTE}
GLYPH = {c: g for c, _, _, g in PALETTE}


def tile_glyph(code):
    """The character to print in a cell."""
    if code in GLYPH:
        return GLYPH[code]
    if 0x40 <= code < 0x70:                 # a tier within a family
        return GLYPH.get(code & 0xF8, '?')
    if 0x20 <= code <= 0x2E:                # a generator tier
        return GLYPH.get(0x20 + (code - 0x20) // 3 * 3, 'o')
    if 0 < code < 0x13:                     # the other wall tiles
        return '#'
    return '?' 


def tile_name(code):
    if code in NAME:
        return NAME[code]
    if 0x40 <= code < 0x70:
        base = code & 0xF8
        return '%s %d' % (NAME.get(base, 'monster'), (code & 7) + 1)
    if 0x20 <= code <= 0x2E:
        return 'generator'
    if 0 < code < 0x13:
        return 'wall'
    return '$%02X' % code


class Store:
    """A set of levels, from a .d64 or a directory of LEVEL_nnn.prg files."""

    def __init__(self, path):
        self.path = path
        self.from_disk = os.path.isfile(path)
        self.raw = {}
        if self.from_disk:
            self._read_d64(path)
        else:
            self._read_dir(path)
        if not self.raw:
            raise ValueError('no LEVEL files found in %s' % path)

    # -- reading -----------------------------------------------------------
    @staticmethod
    def _spt(t):
        return 21 if t < 18 else 19 if t < 25 else 18 if t < 31 else 17

    @classmethod
    def _off(cls, t, s):
        return sum(cls._spt(x) * 256 for x in range(1, t)) + s * 256

    def _read_d64(self, path):
        img = open(path, 'rb').read()
        self.img = bytearray(img)
        self.slots = {}
        t, s = 18, 1
        while True:
            o = self._off(t, s)
            for i in range(8):
                e = o + 2 + i * 32
                if not img[e]:
                    continue
                nm = bytes(img[e + 3:e + 19]).replace(b'\xa0', b'')
                nm = nm.decode('latin1').strip()
                if not nm.startswith('LEVEL'):
                    continue
                try:
                    n = int(nm[5:])
                except ValueError:
                    continue
                # a file on disk keeps its two-byte load address; the
                # records this editor works with do not
                self.raw[n] = self._chain(img, img[e + 1], img[e + 2])[2:]
                self.slots[n] = e
            if img[o] == 0:
                break
            t, s = img[o], img[o + 1]

    def _chain(self, img, t, s):
        out = bytearray()
        seen = set()
        while t and (t, s) not in seen:
            seen.add((t, s))
            o = self._off(t, s)
            nt, ns = img[o], img[o + 1]
            out += img[o + 2:o + 256] if nt else img[o + 2:o + 1 + ns]
            t, s = nt, ns
        return bytes(out)

    def _read_dir(self, path):
        for f in sorted(os.listdir(path)):
            if not f.startswith('LEVEL_') or not f.endswith('.prg'):
                continue
            try:
                n = int(f[6:9])
            except ValueError:
                continue
            self.raw[n] = open(os.path.join(path, f), 'rb').read()[2:]

    def numbers(self):
        return sorted(self.raw)

    def level(self, n):
        return G.decode(self.raw[n])

    def put(self, n, body):
        """Replace a level's record.  Writing a .d64 in place is refused:
        the record length changes and re-threading the sector chain is a
        different job from editing.  Save to a directory instead."""
        self.raw[n] = body

    def write_dir(self, path):
        os.makedirs(path, exist_ok=True)
        for n, body in sorted(self.raw.items()):
            with open(os.path.join(path, 'LEVEL_%03d.prg' % n), 'wb') as fh:
                fh.write(struct.pack('<H', 0x0A00) + body)
        return len(self.raw)


class Editor:
    """One level, open for editing."""

    def __init__(self, store, n):
        self.store = store
        self.n = n
        self.lv = store.level(n)
        self.original = bytes(self.lv.grid)
        self.undo = []
        self.dirty = False

    # -- editing -----------------------------------------------------------
    def at(self, x, y):
        return self.lv.grid[y * W + x]

    def paint(self, x, y, code):
        """Set one cell.  Returns False if it changed nothing."""
        if not (0 <= x < W and 0 <= y < H):
            return False
        i = y * W + x
        if self.lv.grid[i] == code:
            return False
        self.undo.append((i, self.lv.grid[i]))
        self.lv.grid[i] = code
        self.dirty = True
        return True

    def undo_one(self):
        if not self.undo:
            return False
        i, old = self.undo.pop()
        self.lv.grid[i] = old
        self.dirty = bool(self.undo)
        return True

    def revert(self):
        self.lv.grid[:] = bytearray(self.original)
        self.undo.clear()
        self.dirty = False

    # -- measuring ---------------------------------------------------------
    def size(self):
        """Bytes the level would occupy if saved now, or None if it cannot
        be encoded at all."""
        try:
            return len(G.save_patched(self.lv)) - 2
        except ValueError:
            return None

    def counts(self):
        g = self.lv.grid
        c = {}
        c['walls'] = sum(1 for v in g if 0 < v < 0x13 or v == 0x90)
        c['treasure'] = sum(1 for v in g if v == 0x13)
        c['food'] = sum(1 for v in g if v in (0x14, 0x15))
        c['magic'] = sum(1 for v in g if v in (0x16, 0x17))
        c['keys'] = sum(1 for v in g if v == 0x1F)
        c['doors'] = sum(1 for v in g if v in (0x11, 0x12))
        c['monsters'] = sum(1 for v in g if 0x40 <= v < 0x70)
        c['generators'] = sum(1 for v in g if 0x20 <= v <= 0x2E)
        c['starts'] = sum(1 for v in g if v == 0x3F)
        c['exits'] = sum(1 for v in g if v in (0x36, 0x37, 0x38))
        return c

    def warnings(self):
        """What is wrong with the level as it stands.  Advisory - the C64
        kit warns and saves anyway, and so does this."""
        out = []
        c = self.counts()
        if not c['starts']:
            out.append('no start')
        elif c['starts'] > 1:
            out.append('%d starts' % c['starts'])
        if not c['exits']:
            out.append('no exit')
        sz = self.size()
        if sz is None:
            out.append('cannot be encoded')
        elif sz > MAX_RECORD:
            out.append('%d bytes: over the 511 ceiling' % sz)
        elif sz > SAFE_RECORD:
            out.append('%d bytes: past what the game ships' % sz)
        if c['doors'] and not c['keys']:
            out.append('doors but no key')
        if sum(1 for v in self.lv.grid if v == 0x90) and \
                not sum(1 for v in self.lv.grid if v == 0x2F):
            out.append('trap-walls but no trap')
        return out

    # -- saving ------------------------------------------------------------
    def save(self):
        """Encode and hand back to the store.  Raises ValueError if the
        level will not fit."""
        body = G.save_patched(self.lv)[2:]
        if len(body) > MAX_RECORD:
            raise ValueError('%d bytes, over the %d ceiling'
                             % (len(body), MAX_RECORD))
        self.store.put(self.n, body)
        self.original = bytes(self.lv.grid)
        self.undo.clear()
        self.dirty = False
        return len(body)
