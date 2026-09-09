# Gauntlet Construction Kit and level generator

A level editor for the Commodore 64 game *Gauntlet*, and a generator that
makes complete 128-level disks for it.

Swap the finished `.d64` in at the game's press-fire prompt: the game only
reads `LEVEL nnn` once it is running, so it takes its levels from there.

A **Deeper Dungeons** disk is strongly recommended - it carries bug fixes
the original release lacks. An original *Gauntlet* disk works too, provided
it is not one of the versions that pack the levels into batched files. See
*Which game disk to use* below.

## Build a disk

    python3 makedisk.py                 # gauntlet_levels.d64, seed 0
    python3 makedisk.py --seed 12       # a different 128 levels
    python3 makedisk.py --out mine.d64 --keep mylevels

Python 3 and nothing else. Five files have to sit together:

| file | what it is |
|------|-----------|
| `makedisk.py` | runs the two steps below |
| `genlevels.py` | the level generator |
| `gauntlet_dd.py` | the level format codec |
| `mklevdisk.py` | the `.d64` writer |
| `gauntkit.prg` | the editor, already assembled |

The steps also run separately, so a set can be inspected or hand-edited in
between:

    python3 genlevels.py --seed 7 --out set7
    python3 mklevdisk.py --levels set7 --kit gauntkit.prg --out disk.d64

## Which game disk to use

**A Deeper Dungeons disk is strongly recommended.** Not for its levels -
this replaces those - but because its `GAUNTPROG` carries bug fixes the
original release does not, and the original is prone to crashing.

**An original Gauntlet disk will also work**, so long as it holds its levels
as separate `LEVEL nnn` files. You get the same editing and the same
generated set; you also get the crashes.

The fix is small and specific: Deeper Dungeons clears four bytes of
per-monster state at the start of every level that the earlier build leaves
holding whatever the previous level put there. The routine that reads them
abandons its work when it finds a non-zero value, so the leak silently
disables that processing until something else resets it. Every other file
on the two disks is byte-identical, so that one change is the whole
difference between the builds. `GAME-NOTES.md` has the addresses.

**Some Gauntlet releases will not work with this at all.** There are disk
versions that store the levels in batches rather than as 128 separate
`LEVEL nnn` files. The editor loads and saves one named level file at a
time, so it cannot read those, and a disk built here will not feed them.

The test is quick: `LOAD"$",8` on your game disk. If it shows a long list
of `LEVEL 001` .. `LEVEL 128` entries, you are fine. If instead it shows a
short list with single-letter files of about 21 blocks each - `A`, `B`, `C`
and so on - it is a batched release and none of this applies.

One such disk examined here holds its levels in fifteen files named `A` to
`O`, all loading at `$2000`: `A` carries seven levels and the rest ten
apiece, each in a fixed 512-byte slot, 147 slots for a 128-level set. The
records inside those slots are the same format this project documents -
many match a separate-files disk byte for byte - so the levels are
readable, but the packing, the ordering and the loader are all different.

Those levels came from the **cassette**: all fifteen files are
byte-identical to blocks on side 2 of the Gauntlet tape, down to the odd
seven-level first file matching the tape's short first block. Whether the
disk was an official release mastered from the tape or a conversion by
someone else is not settled - the disk examined was cracked, but its title
screen had been properly rewritten for disk, which either would do.
`GAME-NOTES.md` has the evidence.

Fixed-size slots are what tape needs, since a tape cannot seek to a named
file. Every level sits on side 2 in blocks of ten slots, and those blocks
are what the batched disk stores as files.

## The editor

`gauntkit.prg` loads with `LOAD"*",8` and runs with `RUN`. It is pure
machine code behind a one-line BASIC stub, and edits any level file on a
Gauntlet or Deeper Dungeons disk that stores them as separate `LEVEL nnn`
files. Press `?` for the key list.

The panel shows the byte cost of the level as you work: the format allows
511 bytes and a level that will not fit cannot be saved, so the count
matters. It warns about a missing start or exit, but never refuses a level
- you are free to build something unplayable if you want to.

## Check a set

`verify.py` puts every level through the editor's own 6502 code and applies
the design rules. It needs `gcore.prg`, `symbols.json`, and a 6502
simulator on the path:

    python3 verify.py set7

## Rebuild the editor

Only needed if you change `gedit.asm`:

    python3 build.py                    # gedit.asm -> gauntkit.prg
    python3 checkregs.py gedit.asm      # registers live across a call
    python3 checklegend.py              # legend agrees with the map
    python3 test_loop.py                # encode/decode round trips
    python3 test_edloop.py              # the edit loop
    python3 test_panel.py               # the status panel

## What the generator aims at

Figures are measured against the arcade original's own 128 levels, not
against Deeper Dungeons, which is markedly more generous than the game it
expands - roughly twice the food and three times the magic.

| | arcade | this set |
|---|--------|----------|
| food per level | 5.9 | 5.5 |
| magic per level | 1.2 | 1.0 |
| treasure per level | 23.0 | 28.1 |
| monsters per level | 33.9 | 40.6 |
| doors per level | 28.6 cells | 23.0 |
| walk to the exit | 68 steps | 56 |

## The documents

| file | what is in it |
|------|--------------|
| `GAME-NOTES.md` | what the game does with a level: the exit redirect, the runtime mirror, trap-walls, teleporter range, the wall tables, and how the two shipped builds differ |
| `gauntlet_dd_level_format.md` | the `LEVEL nnn` file format: container, vector section, object section, and the disambiguation rule an editor has to obey |
| `object-codes.md` | every object code, what it does, and how confident the reading is |
| `LEVELS.md` | the design rules this generator follows, and where the set still differs from the arcade |

All of it was worked out from the binaries and the 256 shipped levels.
Where a reading is uncertain the documents say so rather than guessing.

## How this was made

The disassembly, the editor, the level generator and the documentation were
all produced with Claude Opus 5 (Anthropic), working from a disk image of
the game and a 6502 simulator.

The work was empirical rather than clever: read the game's code to find out
what a byte in a level file means, then check the reading against all 256
shipped levels, and keep the checkers honest by breaking something on
purpose to confirm they complain. Several confident conclusions turned out
to be wrong and were corrected by measurement - the documents say where a
reading is still uncertain rather than smoothing it over.

## Copyright and trademarks

*Gauntlet* is copyright (c) 1985 Atari Games Corporation. The Commodore 64
conversion is copyright (c) 1986 U.S. Gold Ltd, published under licence.
*Gauntlet: The Deeper Dungeons* is copyright (c) 1987 U.S. Gold Ltd.
*Gauntlet* is a trademark of its respective owners. Rights in the series
have changed hands since; Atari Games' games later passed through Midway
and Warner, and the U.S. Gold catalogue through Eidos.

**This project is not affiliated with, endorsed by, or connected to any of
them.** It is an unofficial fan-made tool.

Nothing here is derived from the original disks. The editor and the level
generator were written from scratch; the levels on `gauntlet_levels.d64`
are generated. The file format was worked out by disassembling the game,
and the documentation describes how it works without reproducing any of the
original code, level data or artwork.

You need your own copy of *Gauntlet* or *Gauntlet: The Deeper Dungeons* to
use any of this. No part of either game is included or distributed here.

If you own the rights and would like something changed, please get in touch.
