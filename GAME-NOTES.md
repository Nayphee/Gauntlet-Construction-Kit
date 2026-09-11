# What the game does with a level

> *Gauntlet* (c) 1985 Atari Games Corporation; Commodore 64 conversion
> (c) 1986 U.S. Gold Ltd; *Gauntlet: The Deeper Dungeons* (c) 1987
> U.S. Gold Ltd. This is unofficial documentation of how the file
> format works, written from a disassembly. No original code, level
> data or artwork is reproduced here.


Notes from disassembling `GAUNTPROG $8000` on the Gauntlet and Gauntlet:
The Deeper Dungeons disks, produced with Claude Opus 5 (Anthropic).
Everything here was worked out from the binary and from the 256 shipped
levels; where a reading is uncertain it says so.

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

## Which releases this applies to

The findings here are from releases that hold their levels as 128 separate
`LEVEL nnn` files, and from two builds of `GAUNTPROG` that differ by
fourteen bytes.

Other releases pack the levels into batches. One examined here holds them
in fifteen files named `A` to `O`, all loading at `$2000`, with `A` holding
seven levels and the rest ten apiece in fixed 512-byte slots - 147 slots
for a 128-level set, so nineteen go spare. The **records inside those slots
are the same format** described in `gauntlet_dd_level_format.md`, and many
are byte-identical to the corresponding file on a separate-files disk, but
the levels appear in a different order and some differ outright.

That release's `GAUNTPROG` is a third build, 20,465 bytes against 20,477,
sharing only about 7% of its code with either of the two described below.
Nothing in the rest of this document should be assumed to hold for it: the
addresses will be different and the loader certainly is.

### The cassette version

The cassette release of Deeper Dungeons uses the **same 512-byte slots**.
**Every level is on side 2.** They sit in fourteen blocks of ten slots,
the first at `$00055` and the rest following at even intervals with about
`$56` bytes of loader framing between them - 140 slots for a 128-level set.
Within a block the slots are exactly `$200` apart and the levels are in
order, with the treasure rooms interleaved: the first block holds levels 1
to 8, then 118, then one more.

A block is therefore 10 x 512 = 5,120 bytes, which is **exactly the data
size of each `A`-`O` file on the batched disk**. The disk files are tape
blocks written to disk.

Both layouts put eight ordinary levels first and the treasure rooms at the
end of the block, but they are not the same block. The tape spends slot 8
on a treasure room and slot 9 on the same filler level in every block; the
batched disk uses slots 8 and 9 for two treasure rooms, and its first file
holds seven slots rather than ten. So it shares the convention, not the
mastering - though the two examined here are different products, one
*Gauntlet* and one *Deeper Dungeons*, so some of that may be the difference
between the games rather than between the media.

### The batched disk carries the cassette's levels

**Settled: the data came from the tape.** The batched disk's levels are the
*Gauntlet* cassette's, block for block. Every one of its fifteen level files is **byte-identical**
to a block on side 2 of the tape:

| tape block | slots | levels | disk file |
|-----------|-------|--------|-----------|
| 1 at `$00055` | 7 | 1-7 | `A`, 3,585 bytes |
| 2 at `$00EAB` | 10 | 8-15, 118, 119 | `B`, 5,120 bytes |
| 3 at `$02301` | 10 | 16-23, 120, 121 | `C` |
| ... | | | |
| 15 at `$11709` | 6 | 112-117 | `O` |

The short first block is the giveaway: seven slots on the tape, seven slots
in file `A`. A disk release designed from scratch would have no reason to
begin with a seven-level file and then switch to ten.

Most of the other files match too - `GAUNT CHR $4800` (12,288 bytes),
`PLYRS.SPR`, `GAUNTFONT $7000`, `DATATREASURE 446`, `PLAYER-$E000` and
others are all byte-identical to stretches of tape side 1. `GAUNTPROG` is
the exception, sharing only about 19% in runs of 32 bytes or more, which is
what you would expect of a program whose tape loading has been replaced
with disk loading.

So the padding and the custom loader are not a disk design at all. They are
the cassette's arrangement, carried over because whoever made the disk
copied the blocks rather than rebuilding the release.

**Not settled: who made it.** The disk examined is a cracked one, but that
does not mean the layout is. Its title screen reads `LEAVE DISK IN DRIVE !`
where the tape reads `LEAVE PLAY PRESSED ON TAPE` - the same fixed-width
slot, both beginning `LEAVE`, so that line was deliberately rewritten for
the medium. Mastering a disk release from the tape blocks and changing the
prompt is exactly what a publisher would do, and also what a careful
cracker would do. The evidence cannot separate them.

So an official disk release in the `A`-`O` layout may well have existed.
None has been seen here, and nothing above establishes one either way.

Side 1 carries the program and asks the player to turn the tape over. Many
of the level records are byte-identical to the file of the same number on
the Deeper Dungeons disk.

The tape is a turbo loader, two pulse lengths only - `$24` and `$42` in the
`.tap`, one bit each, most significant first. Side 1 also holds a table of
the loader's file names, `LEVEL 001` among them.

That settles the shape of the thing. **Fixed-size slots are what tape
needs**, because a tape cannot seek to a named file, and the block is the
loading unit - what the player needs before the next tape stop. The batched
disk releases carry the same 5,120-byte blocks as fifteen files.

What the data cannot say is which release came first, or whether the disk
layout was taken from the tape or both from a common source. The disks
carry no dates and the builds share too little code to order them by their
contents. The rest of the argument is circumstantial:

* every batch loads to the same address, `$2000`, so they are meant to be
  read one at a time into the same buffer
* the slots are a fixed 512 bytes whatever the level actually needs, which
  is what you want when you cannot seek: level *n* of a batch is always at
  `$2000 + 512n`
* a batch is 21 blocks, which holds ten slots with 214 bytes spare, so the
  batch size was chosen to fit the slots rather than the other way round
* the separate-files releases waste none of that: each level is its own
  file, exactly as long as it needs to be

Against it: the levels appear in a different order from the separate-files
disks, and some differ outright, which a straight repackaging would not
explain. The disk examined was also cracked, so some of that may not be
original.

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

### Treasure rooms are timed

`$8251` is set to 1 when a treasure room starts and 0 when it ends. It
gates a routine at `$9E75` that runs every frame only while that flag is
up:

```asm
$9E7B  dec $9def        ; a frame counter
$9E7E  bne $9eb2
$9E80  lda $9de9        ; the treasure-room clock
$9E83  beq $9e8f        ; run out: stop the room
$9E85  dec $9de9
$9E88  lda #$ff
$9E8A  sta $9def        ; reload, so it ticks once every 255 frames
```

The bonus is settled per player at `$AC13` from a count in `$AD11,x`:
nothing collected gives the `NO BONUS` message at `$ACF1`, a haul gives
the `TREASURES` tally at `$ACD3`. `$AEDC` is the flag that makes the room
wind up once, at `$AEAF`, which the main loop calls from `$814D`.

**This was documented the wrong way round at first.** The notes said there
was no treasure-room timer and that the game did not know it had loaded
one - an assertion made from not having found the code rather than from
having looked for it. The routine above is what the play experience
already said was there.

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

### The unused key graphic

`$32` draws as a string of keys and does nothing. It is on none of the 256
shipped levels, and the program never handles it as an object code - the
passability test at `$92C0` blocks it like a wall, so it cannot be stepped
on, shot or collected.

It looks like an abandoned feature: keys dropped where a player died, for
the other player to pick up. That is a reading of the graphic rather than
something the code shows, and the code shows only that it was never wired
up. `object-codes.md` has the detail and the reason the editor leaves it
out of its palette.

### Breakable walls

`$33` is an object, not a wall pen - it sits above `$13` and so looks like
something lying on the floor - but the game blocks it like any other wall
until it is shot. `$B3C6` replaces the cell with whatever `$B43D` holds when
a shot reaches `$1F`, `$33`, `$34`, `$35`, or a code in the range at
`$B43B`-`$B43C`.

### Teleporters

`$AF78` looks for a destination by scanning a **16 by 10 window**, and the
window is the *screen*: it starts from `$87BC` and `$87BE`, the scroll
position, not from the teleporter. So the destination has to be on screen
when the player steps on the source, and since the screen follows the
player that means within roughly seven columns and four rows of the pad.
A pair further apart than that does nothing at all when stood on. 91% of
the arcade's pads have a partner inside that box.

This was first documented as a window around the source, and `$8D23` needs at least two teleporters in its list. A lone
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
hurts, bit 1 stuns, neither is harmless.

**Bit 0 is never set on any shipped level.** Not one of the 256:

| | harmless | stun | hurt |
|---|---------|------|------|
| arcade Gauntlet | 116 | 12 | 0 |
| Deeper Dungeons | 102 | 26 | 0 |

The game implements it properly. `$989C` reads bit 0 at level setup and
prints `SHOTS NOW HURT OTHER PLAYERS`, then checks bit 1 for the stun
message the same way, and `$AA30` reads it again in play to take the health
off. So this is a working feature that no level ever switched on - unlike
`$32`, which has a graphic and no code, this has code and no data.

Why is not something the binary can answer, and it is worth resisting the
obvious guess. Hurting a partner is not an aberration in this game: the
competition between players is half of what Gauntlet is. Food and treasure
go to whoever reaches them first, nobody agreed who should have them, and
in the arcade each player's coins bought their own health, so every item
taken was money off someone else's evening. The arguments were the point.

Friendly fire became a proper feature in *Gauntlet II*, used on some of its
levels. So bit 0 in this build reads less like a mistake and more like an
idea that arrived a game too early - implemented, wired up, and left for
the sequel to switch on.

## Stat potions

`$19`-`$1E` are the six stat potions - armour, carrying, magic, shot power,
shot speed, fight.

**Neither shipped set places a single one on any of its 256 levels**, and
the reason is at `$A20A`: the game places them itself.

```asm
$A20A  lda #$ff
$A20C  sta $a1ed        ; no potion this level
$A20F  lda $9813        ; the level number
$A212  cmp #$08
$A214  bcc $a22c        ; below level 8, never
$A216  jsr $a1f0        ; the random generator at $A1F0
$A219  and #$0f         ; 0-15
$A21B  sta $a1ed
$A21E  cmp #$06
$A220  bcs $a22c        ; 6..15, no potion this time
$A222  ldx #$02         ; 0..5, place one and announce it
$A224  jsr $add1
$A227  jsr $ade6
```

Six chances in sixteen, and only from level 8 onward. The same roll picks
*which* potion: 0 to 5, exactly the range of the six stat potions that
never appear in level data. `$A1ED` holds the choice, `$FF` meaning none.

**Treasure rooms are included.** The level setup at `$985F` splits on the
level number:

```asm
$985F  lda $9813        ; the level number
$9862  cmp #$76         ; $76 = 118, where the treasure rooms start
$9864  bcc $9870        ; below 118: the ordinary level path
$9866  jsr $ae86        ; 118 and up: the treasure-room path
$9869  jsr $a20a        ; and this branch calls the potion routine too
```

Both branches reach `$A20A`, which only refuses below level 8, so a
treasure room rolls for a hidden potion like any other level - and with
around 600 empty cells in the shipped ones there is always somewhere to put
it. A potion in a room with no monsters in it is free.

The placing is at `$A1A3`. It shifts the index left twice, walks the map
through `$C8E2` and `$C94D` looking for a spot, checks the candidate
against `$F800`/`$F801` so it cannot land on the player, and writes the
code into the map with `sta ($8e),y`.

So a level file that carries a stat potion is adding to what the game does
rather than replacing it - the game still rolls for its own. That is a
reason for a generator to leave them alone, not a reason the format cannot
hold them. All six are in the editor's palette, and placing one by hand is
a perfectly good thing to do: it puts a potion exactly where you want it,
on a level of your choosing, which is something the game's own roll can
never be made to do.

### Finding it

Worth recording, because the obvious search fails. `FIND THE HIDDEN POTION`
sits at `$A22F` and **nothing in the program refers to that address** - no
word reference, no split load of `$2F` and `$A2`. Messages carry a two-byte
prefix, the length and a flag, so the record actually begins at `$A22D`,
and the code reads it as `lda $a22d`. The string is 22 characters and the
bytes before it are `16 01`. The other messages have the same shape:
`EXTRA ARMOUR` is 12 characters behind `0c 01`, `YOU HAVE FOUND A` is 16
behind `10 01`.

## The turbo tape format

Recovered by decoding the ROM-loaded bootstrap at the head of the tape,
following its two layers of self-decryption, and disassembling the loader
it copies out of screen memory into `$0830`.

The bootstrap arrives as an ordinary ROM-format file called `GAUNTLET`,
loading at `$0326`-`$0702` - which spans the screen, so part of the turbo
loader travels hidden in screen memory and is copied to `$0830` before use.
It then patches the LOAD vector at `$0330` and calls `$FFD5` as normal.

Pulses, in `.tap` units of 8 cycles:

| pulse | cycles | means |
|-------|--------|-------|
| `$24` | 288 | a 0 bit |
| `$42` | 528 | a 1 bit |

The loader arms CIA timer A with `$0368` (872 cycles) and takes an
interrupt on each tape edge. The timer's high byte is then `$02` for a
short pulse and `$01` for a long one, and `eor #$02 / lsr / lsr / rol $a9`
turns that into a bit. Bits arrive most significant first.

A block is:

    many   $20    leader
    one    $FF    sync
    16 bytes      file name, padded with spaces
    2 bytes       load address, low then high
    2 bytes       end address, low then high
    n bytes       the payload
    1 byte        checksum: every payload byte exclusive-ored together

The loader compares the name against the one the caller asked for and
skips blocks that do not match, so several files sit on one side. On the
level side the blocks are named `A` and then `A1` fourteen times.

**The same format reads every release examined** - two dumps of Gauntlet
side 1, three of side 2, a single-file Gauntlet, and both sides of Deeper
Dungeons. Every block verifies except the first of each level side, which
is the off-by-one below. The loader is unchanged across all of them.

A block can start at any bit position, because the gaps between blocks are
not whole numbers of bytes: the loader shifts bits through `$A9` until it
matches, so a decoder has to search the bit stream rather than a
byte-aligned one. Searching bytes finds only the blocks that happen to line
up - four of fifteen on one side, the rest reading as `$10` leaders, which
is `$20` shifted by one bit.

Re-encoding a block reproduces its pulses exactly. The first
block's header says `$2000-$2E01` for a 3,584-byte payload, one more than
it holds - an off-by-one in the original mastering, harmless because the
loader stops on the pointer comparison.

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
alike. Deeper Dungeons is both harder and more generous than the game it
expands - more of what kills you, and more of what keeps you alive.

| per level | arcade | Deeper Dungeons |
|-----------|--------|-----------------|
| Deaths | 2.0 | 5.4 |
| levels carrying a Death | 58 | 108 |
| traps | 0.8 | 1.8 |
| traps in levels 1-8 | 3 | 15 |
| teleporters | 1.2 | 2.4 |
| monsters | 33.9 | 38.9 |
| generators | 29.7 | 34.0 |
| food | 5.9 | 9.0 |
| magic | 1.2 | 3.0 |
| treasure | 23.0 | 22.9 |
| door cells | 28.6 | 20.7 |
| keys | 4.7 | 5.4 |

The reviews of 1987 said it was much harder, and the table agrees: nearly
three times the Deaths on almost every level, twice the traps, and five
times as many traps in the opening levels. The extra food and magic are
what make that survivable. Treasure alone is unchanged.

The arcade's food sits in a tight band - 84 of its 110 pool levels carry
between four and eight, and its correlation with the number of monsters on
the level is +0.03, which is to say none at all. Only one dungeon level has
no food; the eleven other foodless levels are the treasure rooms, which
carry none by design.
