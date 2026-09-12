#!/usr/bin/env python3
"""gauntkit-pc - edit Gauntlet levels on a PC.

    python3 gauntkit-pc.py gauntlet_levels.d64
    python3 gauntkit-pc.py levels/

The whole map is on screen at once, which is the one thing the C64 kit
cannot do - it scrolls a 16 by 10 window over a 32 by 32 map.  Otherwise
this is the same editor: paint tiles, watch the byte count, save.

Needs nothing but Python 3 and tkinter, which ships with it on Windows and
macOS.  On Debian or Ubuntu: apt install python3-tk.

All of the editing logic lives in editcore.py, which is tested; this file
is the widgets.

Keys:
    1-9, 0      pick from the first ten palette entries
    click/drag  paint
    right-click pick up the tile under the cursor
    u           undo one cell
    s           save        r  revert this level
    [ / ]       previous / next level
    w           write every level out to a directory
"""
import os
import sys

import editcore as E

try:
    import tkinter as tk
    from tkinter import messagebox, simpledialog
except ImportError:
    sys.exit('tkinter is missing.  On Debian/Ubuntu: apt install python3-tk')

CELL = 20
PAD = 8


class App:
    def __init__(self, root, store):
        self.root = root
        self.store = store
        self.nums = store.numbers()
        self.idx = 0
        self.code = 0x10
        self.painting = False
        root.title('gauntkit-pc')

        wrap = tk.Frame(root, bg='#101010')
        wrap.pack(fill='both', expand=True)

        self.canvas = tk.Canvas(wrap, width=E.W * CELL, height=E.H * CELL,
                                bg='#101010', highlightthickness=0)
        self.canvas.grid(row=0, column=0, padx=PAD, pady=PAD)

        side = tk.Frame(wrap, bg='#101010')
        side.grid(row=0, column=1, sticky='n', padx=(0, PAD), pady=PAD)

        self.title = tk.Label(side, font=('TkFixedFont', 13, 'bold'),
                              bg='#101010', fg='#e0e0e0', anchor='w')
        self.title.pack(fill='x')
        self.info = tk.Label(side, font=('TkFixedFont', 10), justify='left',
                             bg='#101010', fg='#a0a0a0', anchor='w')
        self.info.pack(fill='x', pady=(6, 8))
        self.warn = tk.Label(side, font=('TkFixedFont', 10, 'bold'),
                             justify='left', bg='#101010', fg='#e08040',
                             anchor='w', wraplength=230)
        self.warn.pack(fill='x', pady=(0, 8))

        # The header flags - the C64 kit's GFX, COL and SHOTS lines.  Not
        # everything about a level is in the grid.
        tk.Label(side, text='level settings', font=('TkFixedFont', 10),
                 bg='#101010', fg='#707070', anchor='w').pack(fill='x')
        self.flagbox = tk.Frame(side, bg='#101010')
        self.flagbox.pack(fill='x', pady=(0, 8))
        self.flaglab = {}
        for i, (field, label) in enumerate(
                (('gfx', 'wall graphic'), ('colour', 'wall colour'),
                 ('shots', 'shots'), ('randexit', 'one exit only'),
                 ('scroll', 'scroll limits'))):
            tk.Label(self.flagbox, text=label, font=('TkFixedFont', 9),
                     bg='#101010', fg='#909090', anchor='w'
                     ).grid(row=i, column=0, sticky='w')
            b = tk.Label(self.flagbox, text='', font=('TkFixedFont', 9),
                         bg='#282828', fg='#e0e0e0', anchor='w', padx=6,
                         width=12)
            b.grid(row=i, column=1, sticky='ew', padx=(6, 0), pady=1)
            b.bind('<Button-1>', lambda e, f=field: self.bump(f))
            self.flaglab[field] = b

        tk.Label(side, text='palette', font=('TkFixedFont', 10),
                 bg='#101010', fg='#707070', anchor='w').pack(fill='x')
        self.pal = tk.Frame(side, bg='#101010')
        self.pal.pack(fill='x')
        self.swatch = {}
        for i, (code, name, colour, glyph) in enumerate(E.PALETTE):
            b = tk.Label(self.pal, text='%s %-13s' % (glyph, name), bg=colour,
                         fg=self._ink(colour), font=('TkFixedFont', 9),
                         anchor='w', padx=4)
            b.grid(row=i % 15, column=i // 15, sticky='ew', pady=1, padx=1)
            b.bind('<Button-1>', lambda e, c=code: self.pick(c))
            self.swatch[code] = b

        tk.Label(side, text=('click paint  right-click pick\n'
                             'u undo   s save   r revert\n'
                             '[ ] level   w write all\n'
                             'click a setting to change it'),
                 font=('TkFixedFont', 9), justify='left',
                 bg='#101010', fg='#606060', anchor='w').pack(fill='x',
                                                              pady=(8, 0))

        self.canvas.bind('<Button-1>', self.down)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.up)
        self.canvas.bind('<Button-3>', self.pickup)
        self.canvas.bind('<Motion>', self.hover)
        root.bind('<Key>', self.key)

        # Two items a cell: the square, and a character on top of it.
        # Colour alone gave 37 shades that nobody could tell apart.
        self.cells = [[None] * E.W for _ in range(E.H)]
        self.marks = [[None] * E.W for _ in range(E.H)]
        for y in range(E.H):
            for x in range(E.W):
                self.cells[y][x] = self.canvas.create_rectangle(
                    x * CELL, y * CELL, x * CELL + CELL, y * CELL + CELL,
                    outline='#181818', fill='#202020')
                self.marks[y][x] = self.canvas.create_text(
                    x * CELL + CELL // 2, y * CELL + CELL // 2,
                    text='', font=('TkFixedFont', max(8, CELL - 8), 'bold'),
                    fill='#000000')
        self.load(0)

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _ink(bg):
        r, g, b = (int(bg[i:i + 2], 16) for i in (1, 3, 5))
        return '#000000' if r + g + b > 380 else '#ffffff'

    @staticmethod
    def colour(code):
        for c, _, col, _ in E.PALETTE:
            if c == code:
                return col
        if 0x40 <= code < 0x70:
            return App.colour(code & 0xF8)
        if 0x20 <= code <= 0x2E:
            return App.colour(0x20 + (code - 0x20) // 3 * 3)
        if code in E.GEN_CODES:
            return '#404040'
        if 0 < code < 0x13:
            return '#9a9a9a'
        return '#303030'

    # -- level handling ----------------------------------------------------
    def load(self, idx):
        self.idx = idx % len(self.nums)
        self.ed = E.Editor(self.store, self.nums[self.idx])
        self.redraw()

    def draw_cell(self, x, y):
        code = self.ed.at(x, y)
        bg = self.colour(code)
        self.canvas.itemconfig(self.cells[y][x], fill=bg)
        self.canvas.itemconfig(self.marks[y][x],
                               text=E.tile_glyph(code), fill=self._ink(bg))

    def redraw(self):
        for y in range(E.H):
            for x in range(E.W):
                self.draw_cell(x, y)
        self.status()

    def status(self):
        n = self.nums[self.idx]
        sz = self.ed.size()
        c = self.ed.counts()
        self.title.config(text='LEVEL %03d%s' % (n, ' *' if self.ed.dirty
                                                 else ''))
        self.info.config(text=(
            'bytes   %s / %d\n'
            'walls   %-4d doors  %d\n'
            'monst   %-4d gens   %d\n'
            'gold    %-4d food   %d\n'
            'keys    %-4d magic  %d\n'
            'pen     %s %s'
            % ('%d' % sz if sz is not None else '--', E.MAX_RECORD,
               c['walls'], c['doors'], c['monsters'], c['generators'],
               c['treasure'], c['food'], c['keys'], c['magic'],
               E.tile_glyph(self.code), E.tile_name(self.code))))
        self.warn.config(text='\n'.join(self.ed.warnings()))
        for field, b in self.flaglab.items():
            v = self.ed.get(field)
            if field == 'shots':
                txt = E.Editor.SHOTS[v]
            elif field == 'scroll':
                txt = E.Editor.SCROLL[v]
            elif field == 'randexit':
                txt = 'on' if v else 'off'
            else:
                txt = str(v)
            b.config(text=txt)
        for code, b in self.swatch.items():
            b.config(relief='solid' if code == self.code else 'flat',
                     bd=2 if code == self.code else 0)

    # -- input -------------------------------------------------------------
    def bump(self, field):
        """Click a setting to step it; the C64 kit does the same with keys."""
        self.ed.cycle(field)
        self.status()

    def pick(self, code):
        self.code = code
        self.status()

    def xy(self, ev):
        return ev.x // CELL, ev.y // CELL

    def down(self, ev):
        self.painting = True
        self.put(*self.xy(ev))

    def drag(self, ev):
        if self.painting:
            self.put(*self.xy(ev))

    def up(self, _):
        self.painting = False

    def put(self, x, y):
        if self.ed.paint(x, y, self.code):
            self.draw_cell(x, y)
            self.status()

    def pickup(self, ev):
        x, y = self.xy(ev)
        if 0 <= x < E.W and 0 <= y < E.H:
            self.pick(self.ed.at(x, y))

    def hover(self, ev):
        x, y = self.xy(ev)
        if 0 <= x < E.W and 0 <= y < E.H:
            self.root.title('gauntkit-pc   %2d,%-2d  %s'
                            % (x, y, E.tile_name(self.ed.at(x, y))))

    def key(self, ev):
        k = ev.keysym
        if k in '1234567890':
            i = 9 if k == '0' else int(k) - 1
            if i < len(E.PALETTE):
                self.pick(E.PALETTE[i][0])
        elif k == 'u':
            if self.ed.undo_one():
                self.redraw()
        elif k == 'r':
            self.ed.revert()
            self.redraw()
        elif k == 's':
            self.save()
        elif k == 'bracketleft':
            self.step(-1)
        elif k == 'bracketright':
            self.step(1)
        elif k == 'w':
            self.write_all()

    def step(self, d):
        if self.ed.dirty and not messagebox.askokcancel(
                'unsaved', 'Level %03d has unsaved edits.  Leave it?'
                % self.nums[self.idx]):
            return
        self.load(self.idx + d)

    def save(self):
        try:
            n = self.ed.save()
        except ValueError as e:
            messagebox.showerror('will not fit', str(e))
            return
        self.status()
        messagebox.showinfo('saved', 'Level %03d held in memory at %d bytes.'
                            '\n\nPress w to write every level to a '
                            'directory.' % (self.nums[self.idx], n))

    def write_all(self):
        where = simpledialog.askstring('write all',
                                       'Directory to write LEVEL files into:',
                                       initialvalue='edited')
        if not where:
            return
        try:
            n = self.store.write_dir(where)
        except OSError as e:
            messagebox.showerror('could not write', str(e))
            return
        messagebox.showinfo('written',
                            '%d levels written to %s\n\nBuild a disk with:\n'
                            '  python3 mklevdisk.py --levels %s --out my.d64'
                            % (n, where, where))


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip().split('\n\n')[1].strip())
    path = sys.argv[1]
    if not os.path.exists(path):
        sys.exit('no such file or directory: %s' % path)
    try:
        store = E.Store(path)
    except ValueError as e:
        sys.exit(str(e))
    root = tk.Tk()
    App(root, store)
    root.mainloop()


if __name__ == '__main__':
    main()
