# What the game does with a level

Notes from disassembling `GAUNTPROG $8000` on the Gauntlet and Gauntlet:
The Deeper Dungeons disks. Everything here was worked out from the binary
and from the 256 shipped levels; where a reading is uncertain it says so.

Addresses are for the Deeper Dungeons build unless stated. The two builds
differ by one insertion of fourteen bytes, so most addresses below `$996B`
match in both and everything after is fourteen bytes lower in the arcade
build. See **Two builds** at the end.

## The map in memory

The level occupies a 32x32 grid of bytes at `$0C00`-`$0FFF`, one byte a
cell, laid out row by row. Cell `(x, y)` is at `$0C00 + y * 32 + x`. A file
is decoded into that grid once, at level setup, and the game works from the
grid thereafter.

Flags live at `$0A01` and `$0A02`, the first two bytes of the loaded
record.

## Loading, and why a level disk can be swapped in

There is exactly **one** `LOAD` call site in the program, and it only ever
builds the name `LEVEL nnn`. Nothing else is read from disk once the game
is running.

That is what makes a separate level disk work: load the game, choose
characters, and at the press-fire prompt swap the disk. From that point the
game reads its levels from whatever is in the drive. It never goes back for
sprites, code or anything else.

## Choosing the next level

`$9817` decides which file to load. Below level 8 it plays them in order.
From 8 on it picks at random from the pool, so **levels 8-128 are not a
difficulty curve** - any of them can follow any other, which is why the
shipped sets show no ramp past the introduction.

`$AD13` counts down to the next treasure room, which is picked from files
118-128 every four to seven levels.

### The level 1 shortcuts

`$99CE` runs during level setup and, **only when the level about to be
played is 2**, calls `$9A2B` for each player. `$9A2B` looks at the map
address the player is standing on - not the cell's contents - and
redirects:

| address | cell | goes to |
|---------|------|---------|
| `$0CD2` | (18, 6) | level 4 |
| `$0FE1` | (1, 31) | level 8 |
| anything else | | level 2 |

So the shortcut is a property of *where* the exit is, not what code is on
it. The redirect fires after the player has left level 1, during level 2's
setup, which is why the screen says nothing until the load completes.

`$CA39` rewrites every `$37` and `$38` in the map to `$36`, and it too runs
only when the level is 2 or 5.

**Uncertain.** A static reading of the passability test says `$37` and `$38`
are solid wall - the comparison at `$92C0` blocks everything from `$2F` up,
and neither `$36` nor the other exceptions match. That contradicts the
shipped data: Deeper Dungeons' level 1 puts `$37` on exactly `$0CD2` and
`$38` on exactly `$0FE1`, which is not a coincidence, and the shortcuts are
known to work. The arcade original's level 1 instead has `$36` on `$0FE1`
with `$37` and `$38` at (31,31) and (31,1), which are not magic addresses at
all. Something in that dispatch is not understood; the codes are in the
editor's palette because the evidence says they work.

## The runtime mirror

`$CE00` mirrors the map when the file number is 8 or higher, using two bits
taken from the CIA timer at `$DC04`. Files 1-7 are exempt, which is why the
introduction levels always look the same and the level 1 shortcuts stay
where the redirect expects them.

## Walls, doors and the rest

The vector section draws with a pen whose top three bits select a tile from
a table at `$C816`:

| pen field | tile | what it is |
|-----------|------|-----------|
| 0 | `$00` | empty |
| 1 | `$36` | exit |
| 2 | `$11` | door, vertical |
| 3 | `$00` | empty |
| 4 | `$12` | door, horizontal |
| 5 | `$00` | empty |
| 6 | `$90` | trap-wall |
| 7 | `$10` | wall |

A wall re-orients to the heading it is drawn along, so the pen chooses the
kind of tile and the direction chooses which of the pair. For a run of one
cell there is no direction, so the pen alone decides: `$40` gives an upright
door, `$80` a flat one.

### Trap-walls

A trap-wall (`$90`) stands until a **trap** (`$2F`) is sprung anywhere on
the level, and then every one of them opens at the same moment. A level
with trap-walls and no trap has walls that can never move; a level with a
trap and no trap-walls has a trap that does nothing. Both shipped sets keep
the two together.

### Breakable walls

`$33` is an object, not a wall pen - it sits above `$13` and so looks like
something lying on the floor - but the game blocks it like any other wall
until it is shot. `$B3C6` replaces the cell with whatever `$B43D` holds when
a shot reaches `$1F`, `$33`, `$34`, `$35`, or a code in the range at
`$B43B`-`$B43C`.

### Teleporters

`$AF78` looks for a destination by scanning a **16 by 10 window** around the
source, and `$8D23` needs at least two teleporters in its list. A lone
teleporter does nothing. A partner more than fifteen columns or nine rows
away will not be found.

That gives the design constraint: pairs have to be close enough to be
found and far enough apart to be worth stepping on. The shipped pairs sit
about nineteen cells apart, comfortably inside the window.

A teleporter also makes a region reachable that has no way in on foot. The
arcade uses this: fifteen of its levels have an exit that cannot be walked
to, and nine of those are reached by teleporting.

## Wall graphics and colour

`$8C80` holds eight wall graphic pointers but only **three** are distinct:

```
$6468  $6408  $6508  $6408  $6508  $4FAD  $8D82  $DC04
  0      1      2      3      4      5      6      7
```

Slot 3 repeats 1 and slot 4 repeats 2, and slots 5-7 point at addresses
that are not graphics at all - `$DC04` is a CIA register. The shipped
levels never use those three.

`$8C78` holds eight colours of which **seven** are distinct:

```
10  13  14  12  15  11  8  10
 0   1   2   3   4   5  6   7
```

Slot 7 repeats slot 0.

So a level has 3 x 7 = 21 possible looks. The editor cycles only through
those, which is why its graphics key stops at 2 and its colour key at 6.

## Friendly fire

Bits 0 and 1 of flags A say what one player's shot does to the other: bit 0
hurts, bit 1 stuns, neither is harmless. The shipped Deeper Dungeons set
runs 102 harmless, 26 stun and none that hurt.

## Stat potions

`$19`-`$1E` are the six stat potions - armour, carrying, magic, shot power,
shot speed, fight.

**Neither shipped set places a single one on any of its 256 levels.** That
is about as clear a statement as level data can make: they are not level
furniture, and the game hands them out itself during play. A generator that
places them is the odd one out.

## Two builds

The arcade Gauntlet disk and the Deeper Dungeons disk carry different
`GAUNTPROG` binaries, both 20,477 bytes. Every other file on the two disks -
sprites, character set, font, title data, loader, player code - is
**byte-identical**.

Comparing the two binaries byte by byte suggests 64% differs, which is
misleading: the low bytes of jump targets all move by the same amount. The
shift profile shows the truth.

| from | Deeper Dungeons sits |
|------|---------------------|
| `$8000` | +0 bytes |
| `$996B` | +14 bytes |
| `$CE1C` | +0 bytes |

**One insertion of fourteen bytes**, at the top of the level-setup routine:

```asm
lda #$00
sta $a607
sta $a608
sta $a609
sta $a60a
```

Four bytes of per-monster state, cleared at the start of every level. The
arcade build never clears them there - it only sets them at `$A278` and
`$AD5A` - so whatever they held carried over from the previous level.
`$A4CB` reads the byte and abandons the whole routine if it is non-zero,
so a stale value would silently disable that processing for that slot.
That has the shape of a between-level state leak.

There is no text difference at all: both builds carry the same strings,
including the disk-swap messages.

## What the two shipped sets look like

Worth knowing before using either as a reference, because they are not
alike. Deeper Dungeons is markedly more generous than the game it expands.

| per level | arcade | Deeper Dungeons |
|-----------|--------|-----------------|
| food | 5.9 | 9.0 |
| magic | 1.2 | 3.0 |
| treasure | 23.0 | 22.9 |
| monsters | 33.9 | 38.9 |
| generators | 29.7 | 34.0 |
| door cells | 28.6 | 20.7 |
| keys | 4.7 | 5.4 |

The arcade's food sits in a tight band - 84 of its 110 pool levels carry
between four and eight, and its correlation with the number of monsters on
the level is +0.03, which is to say none at all. Only one dungeon level has
no food; the eleven other foodless levels are the treasure rooms, which
carry none by design.
