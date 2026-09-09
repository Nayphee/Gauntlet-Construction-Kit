# Gauntlet: The Deeper Dungeons — an original level set

Welcome to Gauntlet: The Even Deeper and Sloppy Dungeons

`gauntlet_levels.d64` holds the construction kit and 128 original levels.
Nothing from either shipped set is reproduced: the disk carries a tool and a
new set of maps, and needs a Gauntlet game disk to run. Deeper Dungeons is
the better one to boot from, the original release having been buggy.

## Using it

Boot the game disk as normal, choose characters, and when both players are
asked to press fire, swap this disk in. From that point the game only ever
asks the drive for `LEVEL nnn`, so every level comes from here.

To edit, `LOAD"*",8` and `RUN` on this disk — the kit is the first file.

## Shape of the set

**Levels 1–7** play in order and are the only introduction the game gives,
so they ramp across themselves:

| level | monsters | generators |
|-------|----------|------------|
| 1     | 15        | 0          |
| 2     | 7         | 0          |
| 3     | 12        | 3          |
| 4     | 18        | 7          |
| 5     | 23        | 12          |
| 6     | 28        | 18          |
| 7     | 34        | 24          |

Level 1's total is higher than level 2's because eleven of its monsters sit
inside the two shortcut chambers, which are optional; only four are loose on
the way to the ordinary exit.

Level 1 spells CLAUDE WOZ ERE in walls, and carries the three exits the
arcade had. The game picks the next level at `$9A2B` from the map address
the player exits on: `$0CD2` — cell (18,6) — sends them to level 4, `$0FE1`
— cell (1,31) — to level 8, and anything else to level 2. The codes `$37`
and `$38` are only markers and the game blocks them, so the shortcuts are
ordinary `$36` exits placed on those two cells. Each shortcut has a wide
mouth and a trail of gold leading into it, so it reads as somewhere to go
rather than a secret.

| exit | at | costs | guards |
|------|-----|------|--------|
| to level 2 | (30,30) | nothing | none |
| to level 4 | (18,6) | one key | a sealed chamber, 4 monsters |
| to level 8 | (1,31) | two keys | an alcove inside an alcove, 7 monsters between the doors |

The level carries four keys — one for the level-4 chamber, two for the
level-8 cell, one spare — dealt as far apart as the map allows, none of
them inside a chamber they open. Collecting the set is a walk from one
corner to another rather than a detour. Skipping deeper costs more, and the monsters
guarding level 8 stand *between* the two doors, so the second one has to be
fought to rather than merely walked to.

**Levels 8–117** are drawn at random by the game, so there is no curve:
as in the arcade, everything past the introduction is equally dangerous.
The variety is in what kind of danger. Each level rolls its own mix, from a
horde with few spawners to a generator farm with few loose monsters, with
about one in ten deliberately quiet to make the next one land harder.

**Levels 118–128** are the treasure rooms: no monsters, no generators, no
traps, and 40-plus piles of gold.

**Except level 128.** Nothing in the game treats these files specially — the
counter at `$AD13` simply picks one every four to seven levels — so a room
can look exactly like the reward and not be one.

There is no treasure-room timer in this game; the game does not even know it
loaded one. The clock is the same as everywhere else — health running down
while you make no progress — so 128 is built to make that bite:

- the exit is 58 steps away, at the far corner
- 29 monsters, 25 of them across the route between the player and the exit
- 3 generators sitting two cells from the exit, keeping the blockade topped up
- the food lies *behind* you, near the start, so going back for it costs more
  than it gives
- shots stun the other player, so in the scramble you lock each other in place

It is survivable, which is the point. The other ten rooms are honest.

## Themed levels

45 of the 110 pool levels have a theme rather than a procedural layout.

| levels | theme | what it is |
|--------|-------|------------|
| 13, 56, 108 | cages | Deaths everywhere, every one sealed in its own cell with a single door. The magic is in the corridors, free to anyone who leaves the doors shut. |
| 27, 49, 83, 89 | teleport | A teleporter network: short walls, long jumps. Teleporters go down in pairs, because the game only searches the 16x10 window it is drawing for a destination and needs two in the list; one on its own does nothing. |
| 38, 64, 71, 74, 97 | monoculture | One monster family, in numbers, with matching generators. |
| 11, 61, 92, 116 | everything | Every element the format has, on one map. |
| 19, 34, 68, 101 | austere | Walls, treasure, one monster, a way out. Nothing else. |
| 24, 46, 113 | vault | Nine locked rooms, the gold inside, keys in the corridors. |
| 16, 43, 77, 104 | hoard | Gold everywhere and everything guarding it. |
| 31, 52, 80, 95 | trapworks | Most walls are trap-walls; springing a trap rearranges the level. |
| 22, 59, 86 | text | GAUNTLET, DUNGEONS, DEEPER spelled in walls. |
| 21, 36, 47, 69 | names | THOR, THYRA, MERLIN, QUESTOR — the four Gauntlet characters. |
| 14, 29, 41, 54, 73, 88 | pixel art | A skull, a spider, a sword, a crown, a chalice and a key, drawn large in walls. All original art rather than anyone else's characters or marks. |
| 111 | Commodore 64 | The C= mark and a big 64 drawn in walls, with the wall colour pinned to light blue — index 2 in the table at `$8C78`. |

The remaining pool levels use one of ten procedural layouts: maze, chamber
grid, comb, concentric rings, spiral, cavern, diagonal, spine, and two
variants with a central arena.

## Design rules every level obeys

Checked against the encoded bytes, not the generator's intentions:

- exactly one start marker, and an exit reachable **without a key**
- at least 90% of the walkable map reachable
- nothing hostile within five steps of the start
- food in proportion to the monsters the player can actually reach
- treasure reachable once keys are collected
- traps and trap-walls both present or both absent
- no `$32`, `$37` or `$38`, which the game treats as solid wall
- every teleporter has a partner within one screen, or it does nothing
- at most 450 bytes, so the editor can always re-encode and save it

## How the levels look

`flags1` bits 3-5 choose the wall graphics and `flags2` bits 3-5 the wall
colour. The tables behind them are smaller than they appear: at `$8C80`
slots 1 and 3 point at the same graphics and so do 2 and 4, while 5, 6 and 7
point at addresses that are not graphics at all (`$DC04` is a CIA register),
which is why the shipped levels never use them. At `$8C78` colour 7 repeats
colour 0.

So a level has one of **3 x 7 = 21** possible looks:

| graphics | colours |
|----------|---------|
| three distinct sets | light red, light green, light blue, grey, light grey, dark grey, orange |

All 21 are dealt out across the 128 levels, five to seven times each, and no
two consecutive levels share a look. Level 111 is pinned to light blue.

## Doors and keys

The shipped levels build whole stretches of wall out of doors — 2,652 cells
across the set, about 21 a level. Turning a wall run into a door run costs
no extra bytes and cannot cut the map up, since a door is only a wall you
may be able to open.

A wall run that has been punched or split no longer reaches anything at one
end, and dressing that as doors gives a door you can walk round. Rather than
refuse the run - which cut the set to barely one door a level - the missing
wall is built: the run is extended until both ends meet something, and the
extension is kept only if the map still hangs together without the door
being opened.

Doors that gate nothing are turned back into plain wall before the keys are
counted. A door set into a wall the player can already walk round is a tile
wasted and a key wasted looking at it; the arcade's barriers separate two
regions 95% of the time, and converting whole walls blind managed 15%.
Which ones gate has to be judged on the decoded grid.

Keys are counted against **barriers, not cells**: a twenty-cell stretch of
door is one thing to unlock and one key gets you through it. Keys are set to what the way out actually costs, plus a small allowance —
not one per barrier. A key for every door means no decision: you open
everything and the side vaults stop being a gamble. The count is worked out
after encoding, by walking the regions of open floor with the door barriers
as edges, and asking how few barriers lie on any route to an exit.

|                 | keys/level | the exit needs | spare |
|-----------------|------------|----------------|-------|
| arcade Gauntlet | 4.7        | 1.9            | 2.9   |
| this set        | 1.7        | 0.0            | 1.7   |

**34 levels put the way out behind a door**, and those carry *exactly* the
keys required — no spare, so a key cannot be wasted on a side vault and
leave the level unfinishable, and none is left over. The other levels place
their exit in the open and give a small allowance to spend on vaults or
hoard.

The exit is moved into place after encoding, on the decoded grid, because
the wall model cannot predict which cells come out locked: choosing a spot
beforehand and hoping produced a real lock about a quarter of the time.
`verify.py` checks the count both ways — never fewer keys than the exit
needs, and on a locked level never more. About a third of levels are a key or two short of their
barriers, which is what makes the last door a choice rather than a formality.

The count has to be taken on the decoded level rather than the wall runs.
The dispatcher re-orients a wall to the heading it was drawn along, later
edits split runs, and a diagonal run is not even four-connected, so what the
generator thinks is one barrier can decode as several.

Levels 2 to 4 are where the door is taught: the way out is behind one, with
exactly the key for it and nothing spare. Levels 5 to 7 have none, as the
arcade's do.

Keys never outnumber barriers. A level with no door carries no key at all —
61 of 128 used to hand out keys with nothing to open.

## What is behind a door

A door cut into a wall you can already walk round is decoration. These seal
something: 80 regions across the set are reachable only by spending a key or
shooting through a breakable wall, and **none of them is empty** — between
them they hold 382 treasure and 221 monsters. Two thirds hold both, so
opening one is a gamble rather than a formality.

The pockets are found by growing a region out from a dead end until its
boundary is a single cell, then sealing that cell. Dropping a new chamber
into a finished maze nearly always severs a corridor; a cul-de-sac already
has one way in, so closing it cannot cut the map up.

A breakable wall is `$33`, an object rather than a wall pen. It sits above
`$13` and so looks like something lying on the floor, but the game blocks it
at `$92C0` like any other wall until it is shot.

## Food

Deliberately thin. How much a level gives is a roll of its own, so a lean
roll means a lean level and the next one has to be paid for out of what the
last one left you — which is the arcade bargain, and the reason the game
never quite feels winnable.

|                 | per level | range | per hostile | levels with none |
|-----------------|-----------|-------|-------------|------------------|
| arcade Gauntlet | 5.9       | 0-21  | 0.120       | 12               |
| Deeper Dungeons | 9.0       | 0-27  | 0.142       | 17               |
| this set        | 5.5       | 0-15  | 0.112       | 7                |

Deeper Dungeons is markedly more generous than the game it expands, which
is worth knowing if you tune this further: it is the wrong reference. The
figures here are set against the arcade original.

The floor is a rule rather than a coincidence: a level with more than thirty
loose monsters must carry at least two, and more than sixty at least four.
Below that it may give you nothing worth the name. Unfair, but never
actually impossible.

## Trap-walls

A trap opens every trap-wall on the level at once, so a trap-wall is worth
placing only if it is holding something back. They come from sealed cages
now rather than from dressing random wall runs, so what a sprung trap
reveals is always something someone chose to put there:

| a sprung trap reveals | levels |
|-----------------------|--------|
| the way out           | 3      |
| gold and monsters     | 6      |
| a cache of loot       | 5      |
| a pack of monsters    | 5      |

Half the monster cages hold Deaths, which nothing kills, so the wall is the
only thing between you and them. A cache holds gold with food mixed
through. Where the exit is behind one, the trap is somewhere else entirely
and has to be found before the level can be finished.

**The trap takes some finding.** It goes in a dead end where possible, at
least twelve steps from the start and well off the walk to the exit, with a
guard or two standing over it — a trap you stumble onto is a coin flip, one
you go looking for is a choice. Median distance from the start is 36 steps.

## Three silly ones

Not every door has to earn its place. The arcade's level 27 is 273 door
cells against 44 real walls, and its 47 and 71 carry twenty-six and
twenty-seven keys laid out in blocks beside the doors they open. Those are
the jokes that make the rest of the set feel measured.

| level | what it is | door cells | keys |
|-------|-----------|------------|------|
| 26 | a maze built of doors, seven keys for the lot | 274 | 7 |
| 28 | keys threaded down the lanes, door after door | 129 | 23 |
| 75 | the same again | 132 | 23 |

These three skip the pruning. A maze made of doors has a way round every
one of them, so the usual rule would quite correctly wall the lot and take
the joke with it.

## The walk to the exit

The rule is the shortest walk to any exit with every door open and every
trap sprung, and it has to be at least 28 steps. Measuring the *longest*
walk with the doors *shut* flattered a level whose exit sat in the same
room as the start: it only takes one close exit to make a level trivial,
and the player will take that one.

|          | median | quartiles | range  | under 28 steps |
|----------|--------|-----------|--------|----------------|
| arcade   | 68     | 31 / 137  | 5-296  | 15             |
| this set | 53     | 37 / 58   | 20-202 | 1              |

The exit is chosen for the length of the walk against the distance across
the paper, not for being the farthest cell on the map. Taking the farthest
cell gave every level the same shape — the walk to the exit *was* the
straight line to it, a ratio of 1.00 against the arcade's 2.58. Choosing
for the ratio instead lifts it to 1.52, with a quarter of the set above
3.3 and one level at 34.

The arcade varies far more than this set does. Some of its levels are a
five-step hop and some are a three-hundred-step trek; mine mostly land
between forty and sixty, because the exit goes near the farthest cell from
the start and that distance does not vary much on a 32x32 map.

## Magic

Magic ends a fight the way food ends starvation, so too much of it is the
same fault as too much food. The count is sampled from the arcade's own
spread: 39 of its levels carry none, 79 carry one or two, and only ten
carry more. Rolling the two colours independently gave up to four a level
and put three or more on 45 of mine.

|                 | per level | per hostile | 3 or more |
|-----------------|-----------|-------------|-----------|
| arcade Gauntlet | 1.2       | 0.023       | 10        |
| Deeper Dungeons | 3.0       | 0.046       | 66        |
| this set        | 1.0       | 0.017       | 14        |

Deeper Dungeons is nearly three times as generous as the game it expands,
the same way it is with food.

## Friendly fire

`flags1` bit 0 makes shots hurt the other player, bit 1 stuns them. Of the
110 pool levels, 77 are normal, 27 stun and 6 hurt. The introduction and the
treasure rooms are all normal — except level 128, which stuns.

## Rebuilding

```
python3 genlevels.py     # generate the 128 levels
python3 verify.py        # every check, including the editor's own m/l
python3 mklevdisk.py     # write the .d64
```

A different seed in `genlevels.py` gives a completely different set.
