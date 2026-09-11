# Gauntlet: The Deeper Dungeons — an original level set

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

A treasure room **is** timed. `$8251` is set to 1 when one starts and 0 when
it ends, and it gates a routine at `$9E75` that runs every frame only while
that flag is up:

```asm
$9E7B  dec $9def        ; a frame counter
$9E7E  bne $9eb2
$9E80  lda $9de9        ; the treasure-room clock
$9E83  beq $9e8f        ; run out: stop the room
$9E85  dec $9de9
$9E88  lda #$ff
$9E8A  sta $9def        ; reload, so it ticks once every 255 frames
```

The bonus is settled at `$AC13`, per player, from a count in `$AD11,x`: a
player with nothing gets the `NO BONUS` message at `$ACF1`, one with a
haul gets the `TREASURES` tally at `$ACD3`.

So the pressure in a treasure room is the clock, not attrition. Level 128
plays against that: the room looks like the reward and the exit is a long
way through a blockade, so the timer runs out while you are still fighting
for the gold.

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
trap sprung, and it has to be at least 40 steps. Measuring the *longest*
walk with the doors *shut* flattered a level whose exit sat in the same
room as the start: it only takes one close exit to make a level trivial,
and the player will take that one.

|          | median | quartiles | range  | under 40 steps |
|----------|--------|-----------|--------|----------------|
| arcade   | 68     | 32 / 134  | 5-296  | 40             |
| this set | 56     | 50 / 65   | 20-119 | 1              |

The one under 40 is level 1, whose free exit to level 2 sits 20 steps off
by design: it is the introduction, and its two other exits are the long
way round.

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

## Stat potions

None are placed by the generator. The game rolls for its own at `$A20A` -
six chances in sixteen, from level 8 onward - and picks which of the six it
will be from the same roll, so a generated set that scattered them would
just be adding to that. Neither shipped set puts one in level data either.

Placing them **by hand** is another matter, and the editor has all six in
its palette. A potion you put somewhere deliberately is worth more than one
the game drops at random: you choose the level and the spot, which the roll
at `$A20A` can never be made to do. `GAME-NOTES.md` has the routine.

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

The six that hurt are a **departure from both shipped sets**, neither of
which sets that bit on a single one of their 256 levels. The game
implements it fully — it prints its own message and takes the health off in
play — so the levels work.

It is not a departure from the series, though: friendly fire became a
proper feature in *Gauntlet II* and was used on some of its levels. And it
suits the game. Gauntlet is as much about competing with the other player
as cooperating — food and treasure go to whoever gets there first, and in
the arcade each player's coins bought their own health, so everything taken
was money off someone else. Six levels in 128 where you can also shoot each
other is a rarity rather than a policy, and a one-line change to the quota
if you disagree.

## What the rules cannot do

Every placement rule here is a generalisation drawn from measuring the
arcade: lobbers behind walls, generators deep, keys off the route,
teleporters into locked ground. They are worth having and they are not
design. A rule fires the same way on a level where it makes sense and one
where it does not, and it cannot see that a lobber behind a wall the
player will never approach from that side is a lobber in a field.

Almost every fault found in this generator was found by looking at a
level, not at a number: a wall of 120 generators, a lobber room in the
open, food banked up across the introduction, teleporters that could not
reach each other. The audit had all four of those inside its tolerances at
the time. Numbers catch a set that is wrong on average; they cannot catch
a set that is wrong in the particular.

## A monster belongs where its trick works

Measured off the arcade, each family sits at a different amount of cover —
the mean open sides around one of them:

| family | arcade | this set before | now |
|--------|--------|-----------------|-----|
| `$40` ghosts | 3.09 | 3.10 | 3.29 |
| `$48` | 3.02 | 2.99 | 3.14 |
| `$50` | 2.74 | 3.08 | 2.47 |
| `$58` lobbers | **2.16** | 3.12 | 2.88 |
| `$60` | 2.65 | 3.22 | 2.75 |
| `$68` Deaths | 2.38 | 3.22 | 2.83 |

**A lobber throws over walls**, so the arcade puts one behind a wall: 59%
of them are walled in on two sides or more. This generator had every
family at about 3.1 open sides regardless, so a lobber was a weak monster
standing in a field, and the one thing it can do that nothing else can was
never used.

They are also rare in the original — 174 across its 128 levels against
1537 ghosts — and an even choice among the unlocked families gave this set
603, so the special case was the commonest thing on the floor. It is 263
now.

The family is chosen before the seed, because sorting a pack afterwards
does nothing: a blob grows into open space wherever it starts, so the
*seed* has to be against a wall.

## The two Deaths levels

Death cannot be killed, only outrun or blown away with magic, so a level
built around them is a different game and worth two set pieces.

**Level 13, the vaults.** Twelve cells in a grid, each holding a Death and
the gold it guards, each with one door. Opening a cell is a choice the
player makes; the magic sits in the corridors, free to anyone who leaves
the doors shut. 27 Deaths.

**Level 56, the gauntlet.** No choice at all: the way out is down a
corridor lined with them, staggered so the route snakes, and the magic to
blow a hole in it is on the floor before you start. 52 Deaths.

They shared identical walls until now — the same twelve-vault grid twice,
which is one set piece pretending to be two.

## A teleporter you cannot use is not a shortcut

The game scans the **screen** for a destination, not a box around the
teleporter: `$AF78` starts from the scroll position at `$87BC`/`$87BE`.
The destination has to be visible when you stand on the source, which
means within about seven columns and four rows of it. Pairs further apart
than that do nothing when stepped on.

This generator paired within 14 columns and 8 rows, so **40% of its pads
had no partner they could reach** — a teleporter in the middle of a
scrolling map that never goes anywhere. 91% of the arcade's pads have a
usable partner; this set now has 100%.

## No wing of the map is left bare

**29% of this generator's floor had nothing within three cells of it,
against 7% of the arcade's** — whole quarters of a level with no reason to
walk into them. The placers draw from pools built around the parts of the
map the level was designed on, and everything outside came out empty.

A pass now finds floor that has nothing near it and puts something there —
**mostly generators**. Three things it got wrong first: filling every bare
cell took dead space to 2% and the records to 342 bytes; filling with
single objects took monster clumping from 0.8 to 0.6 against the arcade's
1.0; and filling with packs of monsters took the monster count to +37%.

A generator is the right thing for bare ground. It is one cell, so it does
not inflate a count the way a pack of six does; it keeps making its own
trouble; and it gives an empty wing a reason to be walked into. Dead space
is 10% against the arcade's 7%, monsters +2%, and generators still stand
apart — biggest block a median of 1, worst 2.

## The way out is never a few steps away

The shortest walk to an exit is 40 steps. On level 8 and after, an exit
reached in half a minute reads as a mistake.

That is a rule about the exit, and it does not reach the real limit. The
arcade's walks run 5 to 296 steps with a median of 81; this set runs 40 to
138 with a median of 57, and no choice of exit will change that, because
**the maps cannot reach**. The furthest cell from the start is a median 69 steps here
against the arcade's 87, and its longest is 297 against this set's 138. An
open map's walk is its straight line; only a twisty one can be long.

Two things measured on the way that turned out not to be the fault: the
exits are not visually close (32 cells from the start against the arcade's
27), and the arcade's short levels carry **fewer** hostiles than its long
ones, not more, so a short walk there is a breather rather than a fight.

## The introduction is where the health bank is filled

The arcade gives 25 pieces of food and cider across levels 1 to 8; this set
was giving 46, and a player arrived at level 9 with 5000 health. That is
the run decided before the pool starts.

Food is now scaled by how far into the game a level sits, steeply at the
start: levels 1-8 carry 27 against the arcade's 25, and the whole-set
average is unchanged at 5.6 a level. The generosity was all in the wrong
place rather than in the total.

## Generators stand apart

The arcade's **median biggest block of generators is one cell**. They are
singles, spaced out, each its own threat. One level in its 128 has a real
slab, at 61 cells.

This generator built walls of them. Eight levels had blocks of 57 or more
and one had **120 generators in a single block** — a screen filled corner
to corner with spawners, which is not a dungeon, it is a wall.

Depth and spacing pull against each other. Drawing thirty generators from
the deepest third of the floor leaves them nowhere to go but into each
other, so the pool is the deeper two thirds, and a cell that already has a
generator beside it is refused. Median block is 1, worst 3.

## Exactly enough keys is only enough when nothing else has a door

Level 3 shipped with two keys, two needed to reach the exit, and **six
door barriers**. Open the wrong vault first and the exit is gone. Every
check passed it, because the checks asked whether the keys *could* reach
the exit, not whether a reasonable player would still have them.

Two rules now. Where a level has doors that are not on the way out, it
carries a spare for every two of them and at least one — a wrong choice
costs a key, not the level. And where nothing can be wasted, it carries
exactly enough, which is how the arcade's introduction does it: levels 2,
3, 4 and 8 have one barrier and one key each, so the door is taught with
no ambiguity at all. This generator's introduction had three to eleven
barriers, which is a lottery rather than a lesson; it now converts almost
nothing to a door on those levels except the locked exit itself.

| | arcade | before | now |
|---|--------|--------|-----|
| level 2 keys / barriers | 1 / 1 | 6 / 3 | 1 / 1 |
| level 3 | 2 / 2 | 2 / 6 | 1 / 1 |
| pool levels a wrong door strands | 0 | 40 | 0 |
| keys a level | 4.7 | 2.9 | 4.1 |

## The introduction teaches one monster at a time

The arcade's first levels carry one family each, in order:

| level | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|-------|---|---|---|---|---|---|---|---|
| arcade | `$40` | `$40` | — | `$48` | `$50` | — | `$68` | `$50 $58 $68` |

Level 1 is `$40`-`$42` and nothing else. `$48` does not appear until level
4, `$50` until level 5, and each arrives on its own so the player can learn
what it does before meeting it in company.

This generator picked from the first three families on level 1, so a
player met demons before they had met a ghost, and from level 4 on it
mixed everything it had unlocked. The introduction now takes one family a
level and uses nothing else.

## The pool is not a hump in the middle

The arcade's levels are not variations on an average one. **37 of its 110
pool levels carry fewer than 15 monsters and 15 carry more than 80**; the
deciles run 0, 2, 9, 22, 31, 41, 51, 67, 97. A quiet level is what makes
the next one loud.

A uniform roll gave this set 8 levels under 15 and 6 over 80, with every
decile between 18 and 72 — the same level over and over at different
volumes. The budget is now deliberately bimodal, and the swarms are named
by level number because they are the biggest records and lose the size race
otherwise: one attempt in eight reaches 150 monsters and none of them was
surviving.

Spread went from 0.50 to 0.66 against the arcade's 0.96, and it brought
every resource into line at the same time — monsters -1%, generators +1%,
treasure -3%, magic +1%, food -2%.

## Set pieces are flat, and there were too many

The themed levels — the text, the pictures, the vault, the teleport maze —
average **4.3 dead ends against the procedural levels' 12.9**, because a
level built to spell a word or hold one idea has few passages in it. There
were 48 of them in a pool of 110, so nearly half the set was a set piece,
and that was most of what kept the whole thing open.

Measured by theme, the flattest were the duplicates: four `theme_teleport`
at 0.8 dead ends, four `theme_trapworks` at 0.0, three `theme_vault` at
0.0. Keeping one or two of each as a landmark and handing the other 22
levels back to the generator took the set from 8.4 dead ends to 9.9,
treasure to exactly the arcade's 23.0, and monster clumping to within 2%.

A set piece is worth having. Thirteen of them are worth having; forty-eight
are a set that does not vary because half of it never varies.

## Where a thing sits decides what it is worth

Counts are half of it. The same objects placed differently make a
different level. Two placements carry most of the weight:

**Depth.** Generators sit an average 40 steps from the start, 79% of the
way to the exit, matching the arcade's 59 steps and 77%. Drawn from the
whole floor instead they land at 34 steps, which puts the pressure by the
door and leaves the far half of the map quiet.

**Keys were handed over rather than gone for.** A key on the route to the
exit is not a decision. The arcade puts 36% of its keys on the route; this
set put 50%. Placement now sorts by how far off the route a cell is, which
takes it to 30% — slightly meaner than the original.

Hostiles standing on the route were already right: 51% against the
arcade's 45%.

## Secrets

A secret is a room whose only way in is a stretch of wall that looks like
any other until a shot goes through it. The arcade builds them at scale:
breakable walls on 19 levels, **25 cells each** where they appear, with
138 pieces of loot that can only be reached by shooting. This generator
sprinkled 78 single breakable cells over 53 levels, which is a speck on a
wall nobody will try a shot at.

They are now a character. A `secrets` level takes up to three sealed
pockets, makes the whole ring of each breakable, and fills the inside
with gold, food and magic. Any level may carry one at a lower rate. The
lone breakable cells elsewhere are gone: 17 levels now carry them at
about 11 cells each.

What makes a secret work is that it is *findable* — a wall that looks
slightly different, a room shape on the map with no door — and worth the
shot. A single soft cell is neither.

## Every level trades something

A level picks a character before its budget is split, and pays for it by
giving up something else:

| character | generous with | gives up |
|-----------|---------------|----------|
| `vaults` | doors, and what is behind them | monsters, generators |
| `keyring` | keys and doors to spend them on | monsters |
| `trapworks` | trap-walls and the trap that clears them | generators |
| `hoard` | gold, tucked away | monsters |
| `nest` | monsters | generators |
| `crossroads` | teleporters | both |
| `plain` | — | — |

Half the pool is `plain`. The trade is what makes it work: a flat cut for
every character made the set **less** varied, not more — the spread of
monsters fell from 0.46 to 0.38 — because pulling every level down by the
same amount moves them all towards the middle.

It closed real gaps. Generators went from -20% of the arcade to -4%, doors
from -16% to -11%, food to +2%. What it did **not** do is make the set
more varied: monster spread is 0.45 against the arcade's 0.96, where it was
0.46 before. The characters change what a level is made of without
changing how far levels sit from each other, and that gap is still open.

## A windfall of bytes should buy character — but not like this

Every structural saving this generator makes is handed to the object
placer, which spends it on more of everything. The obvious answer is to
pick one thing to be generous with — a gold room, a horde, a larder — so a
cheap level comes back interesting rather than crowded.

Bolted on after the objects are placed it does nothing worth having: the
spread of monsters across the pool moves from 0.46 to 0.47 against the
arcade's 0.96, because eight to sixteen extra objects on top of forty is
noise, and it pushes monsters to +21% and generators to +22%.

`spend_windfall` is left in the source, unused, with that written on it.
The idea is right and the placement is the wrong end of it: adding a
character does not create one. The level has to be built around the chosen
thing, with the ordinary placement leaner so it dominates — chosen in
`dungeon()` before the budget is split, not topped up afterwards.

## Stubs: what the arcade's walls are actually made of

The arcade's vector section is **50 DRAWs a level at a median length of
two cells** — a mass of short stubs, not a few long walls. This generator
was drawing 28 longer segments and 41 single cells, which is rooms.

A stub is a two-to-four-cell wall growing off an existing one into open
floor. It costs one DRAW, makes a dead-end pocket beside it, and is the
cheapest structure the format sells. Applied as a pass over the finished
layout, so it works on every style alike, with a connectivity check so no
stub cuts the map:

| | dead ends | corridor % | vector bytes |
|---|-----------|-----------|-------------|
| a plain layout | 0.8 | 7 | 64 |
| + 30 stubs | 10.1 | 15 | 154 |
| + 45 stubs | 15.6 | 19 | 199 |
| the arcade | 17.5 | 20 | 105 |

The shape is right at 45 stubs; the bytes are double. The arcade pays half
because a DRAW is **one byte** and continues from the cursor, so a wall
drawn as a continuous polyline costs 2 + n bytes for n segments where this
emitter pays 3 each. Chaining independent runs after the fact was tried
and bought a byte a level — runs seldom happen to start where the cursor
stands. The saving has to come from generating walls as paths, which is
the next algorithm rather than this one.

At what the budget bears — twenty to thirty stubs on an ordinary level —
dead ends reach 15.4 against the arcade's 17.5, inside tolerance for the
first time.

## Which layout style buys the most structure

Measured across every style — vector bytes spent against dead ends and
corridor share produced:

| style | vector bytes | dead ends | corridor % | passes |
|-------|--------------|-----------|-----------|--------|
| diagonal | 63 | 10.6 | 8.9 | 20% |
| comb | 56 | 1.7 | 7.5 | 29% |
| warren | 148 | 8.0 | 11.4 | 16% |
| dense | 154 | 5.0 | 12.8 | 8% |
| chambers | 127 | 1.0 | 10.7 | 8% |
| the arcade | 103 | 17.5 | 19.9 | — |

**Diagonal is the best value the format offers**: more dead ends than a
warren for less than half the bytes. Forced on a third of the pool those
levels give 19.6 dead ends, above the arcade's 17.5, while the rest of the
set manages 7.1.

Widening it further made the set *worse*. A diagonal layout is cheap, so
handing more levels to it simply gives the object placer a bigger budget,
and it spent that on monsters (+26%) and generators (+41%) without the
structure rising to match. A third of the pool is what this budget carries.

## Teleporters go somewhere worth going

A teleporter earns its place by landing where a key would otherwise be
spent: inside a locked region or a vault. **75% of the arcade's pads sit in
a region that cannot be walked to with the doors shut.** This generator
managed 6%, because it paired cells anywhere on the open floor — a pair of
pads on the same side of every door, which saves the player nothing.

One end of each pair now starts in a locked region, and if there is nowhere
locked left to land the pair is not placed at all: better none than a
shortcut that is not short. That takes it to 32%.

A teleporter that lands on open floor is still worth placing if it skips a
long walk, so those are allowed on their own terms: an open-to-open pair
has to save at least 20 steps or it is not placed. This set's open pairs
now skip a median 17 steps against the arcade's 14.

The remaining gap is that the arcade links locked regions to **each other**,
so both ends of a pair can be behind doors; a scheme that locks one end
tops out at 50%.

### Gold belongs where the map closes in

Half the arcade's treasure sits in a dead end or a corridor — a cell with
two open sides or fewer — against a fifth of this generator's, which
sprinkled it over open floor. Gold in the middle of a room is scenery;
gold down a dead end is a decision. Placement now prefers enclosed cells,
which takes it to 29%.

Level 1 was the worst of it: 62 pieces of treasure and 15 hostiles, where
the arcade's carries **2 treasure and 75 hostile**. An introduction is a
fight, not a vault. It is now 28 and 33 — still gentler than the original,
but the right shape.

### A floor on what a level may contain

Widening the variety produced a 45-byte level with a start, an exit and
nothing else — an empty room with a door at the far end, and every
correctness check passed it. A level now needs 22 objects and 8 hostile
ones; the arcade's barest carries 31 and 17.

## The border is decoration

The arcade walls the **top** on 127 of its 128 levels and the **left** on
112, but the bottom and right on two apiece. The game bounds movement at
the grid edge, so a drawn border is 61 wall cells and two vector runs spent
on a fence nobody can walk through.

This generator fenced all four sides on every level. Stopping cost nothing
and bought a good deal: the vector section fell from 132 bytes to 123, wall
cells from a floor of 141 to 80, and the levels the bytes paid for came
back as generators and doors.

It is also most of what kept the set uniform. A level cannot be sparse if
it starts with a box drawn round it.

## Measure before you tune

Three separate trims to the treasure moved it by almost nothing, because
none of them was where the treasure came from. Tagging all 28 placement
sites and counting found one — the sealed-region filler, running across
eighty-odd regions — placing 40% of it on its own.

The same again for the byte budget. Splitting the record showed the vector
section at 134 bytes against the arcade's 103 for a similar number of wall
cells, about nineteen objects' worth. The cause was **POINTs**: single
positioned cells that cover no ground, 50 a level against the arcade's 27.
Tallying every length-one run by the code that made it found three sources
between them responsible for 21 a level.

Totals hide shape. Traps appear on 23 levels here against the arcade's 24,
but the arcade puts about four on each rather than one. Teleporters are the
reverse: a network of seven on 22 levels rather than pairs spread thinly
over 34. Both per-level averages can be right while neither design is.

## Auditing a set

`audit.py` prints all twenty measures against the arcade in one pass and
flags anything more than 25% off. Run it after any change to the
generator, not just the measure you were aiming at — several of the
faults found late in this project were features that had quietly stopped
working while something else was being tuned.

## Where this set still differs from the arcade

| per level | arcade | this set |
|-----------|--------|----------|
| food | 5.9 | 5.7 |
| magic | 1.2 | 1.0 |
| door cells | 28.6 | 26.2 |
| generators | 29.7 | 24.2 |
| treasure | 23.0 | 31.0 |
| monsters | 33.9 | 41.8 |
| keys | 4.7 | 2.6 |
| walk to the exit | 68 steps | 53 |

Food, magic and doors are close now. Treasure and monsters run generous,
generators and keys light.

**How things are grouped matters as much as how many there are.** The
arcade scatters its generators and clumps its monsters.

| same-code neighbours | arcade | before | now |
|----------------------|--------|--------|-----|
| generators | 0.20 | 0.92 | 0.56 |
| monsters | 1.67 | 0.36 | 0.99 |

The generator clumping was a byte saving — a run of one code encodes as a
two-byte repeat — and it read as farms rather than a dungeon. The monster
scattering was a bug: the tier was rolled per cell, so a pack came out a
mixture and adjacent monsters rarely matched. One code for the whole pack
both looks right and costs less, which paid for scattering the generators.

**The one that has not closed is where the doors go.** The arcade leaves a
median of 8% of its floor reachable before a key is spent; this set leaves
55%. That is not a matter of how many doors there are — they are within
10% of each other — but of which walls become doors. The arcade puts them
on the chokepoints, so a door shuts off a wing of the map; this generator
converts wall runs more or less at random, so most doors gate a cupboard.
Closing it means choosing runs whose removal separates large regions,
which is a different algorithm rather than a bigger number.

## Difficulty

`--difficulty` scales what makes a level hard. `arcade` is the default and
is tuned against the original game's own 128 levels.

    python3 genlevels.py --difficulty brutal --seed 7 --out set7

| per level | gentle | arcade | brutal | the real arcade |
|-----------|--------|--------|--------|-----------------|
| monsters | 34.1 | 39.7 | 39.8 | 33.9 |
| generators | 15.7 | 25.5 | 21.4 | 29.7 |
| food | 7.9 | 5.5 | 3.4 | 5.9 |
| magic | 1.8 | 1.0 | 0.3 | 1.2 |
| treasure | 30.9 | 29.2 | 27.1 | 23.0 |

**Food and magic are what actually move**, and they are also what the
player feels: a brutal level gives you 3.4 food and almost no magic against
gentle's 7.9 and 1.8. Traps scale too.

**Monsters and generators barely move, and brutal has fewer generators than
arcade.** That is not a bug in the scaling, it is the format. A level is
450 bytes whatever the difficulty, and asking for more of everything makes
a bigger record: 13 brutal attempts in 60 fail the size cap against
arcade's 4, and the ones that survive are the sparse ones. The retry loop
then hands back exactly what you did not ask for.

So difficulty at the hard end has to spend the budget differently rather
than spend more of it — `hard` and `brutal` give up treasure, since gold is
the one thing on the floor that does not fight back — and even then the
monster count is close to fixed. The honest summary is that this is a
hunger and firepower dial, not a monster dial.

## Rebuilding

```
python3 genlevels.py     # generate the 128 levels
python3 verify.py        # every check, including the editor's own m/l
python3 mklevdisk.py     # write the .d64
```

A different seed in `genlevels.py` gives a completely different set.
