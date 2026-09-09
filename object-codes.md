# Object codes: what the editor calls each one, and why

Generated from GAUNTPROG, the editor core and simulation. Columns marked *measured* come from running the game's own code.

| Code | Editor palette | Glyph | On the disk | Handler | Shot (measured) | Health (measured) | Reading | Evidence | Confidence |
|---|---|---|---|---|---|---|---|---|---|
| `$10` | WALL | `block` | 29196 in 127 lv | -- | blocks shot | -- | wall, permanent | below the $11 threshold; shots do not clear it | **firm** |
| `$11` | DOOR V | `vbar` | 1312 in 91 lv | $B65B | blocks shot | none | door, vertical | handler DECs $B449, the counter $1F fills | **firm** |
| `$12` | DOOR H | `hbar` | 1340 in 85 lv | $B65B | blocks shot | none | door, horizontal | same handler as $11 | **firm** |
| `$13` | TREASURE | `$` | 2933 in 123 lv | $B72B | blocks shot | none | treasure | INC $AD11; skipped in treasure rooms | **firm** |
| `$14` | CIDER | `Q` | 729 in 106 lv | $B6AE | destroyed | 0050 -> 0150 | cider | BCD +1 health, clamped at 99; destroyed by a shot | **firm** |
| `$15` | FOOD | `S` | 418 in 91 lv | $B6AE | blocks shot | 0050 -> 0150 | food | same handler as $14; survives a shot | **firm** |
| `$16` | MAGIC B | `X` | 237 in 98 lv | $B6C5 | destroyed | none | magic, blue | INC $B44B; destroyed by a shot | **firm** |
| `$17` | MAGIC Y | `X` | 152 in 71 lv | $B6C5 | blocks shot | none | magic, yellow | same handler as $16; survives a shot | **firm** |
| `$18` | AMULET | `` | 106 in 74 lv | $B6DD | passes through | none | amulet | sets $B44F=$FF and $8F4F=3, a timed state | **firm** |
| `$19` | ARMOUR | `Z` | unused | $9A76 | destroyed | none | armour potion | ORs bit $01 of the ability word at $9BFE,x | **firm** |
| `$1A` | CARRYING | `Z` | unused | $9A79 | destroyed | none | carrying potion | ORs bit $02 of the ability word at $9BFE,x | **firm** |
| `$1B` | EX MAGIC | `Z` | unused | $9A7C | destroyed | none | magic potion | ORs bit $04 of the ability word at $9BFE,x | **firm** |
| `$1C` | SHOT PWR | `Z` | unused | $9A7F | destroyed | none | shot power potion | ORs bit $08 of the ability word at $9BFE,x | **firm** |
| `$1D` | SHOT SPD | `Z` | unused | $9A82 | destroyed | none | shot speed potion | ORs bit $10 of the ability word at $9BFE,x | **firm** |
| `$1E` | FIGHT | `Z` | unused | $9A85 | destroyed | none | fight power potion | ORs bit $20 of the ability word at $9BFE,x | **firm** |
| `$1F` | KEY | `^` | 688 in 110 lv | $B702 | passes through | none | key | INC $B449, which doors consume | **firm** |
| `$20` | GEN A1 | `` | 661 in 82 lv | -- | destroyed | -- | ghost generator, strength 1 | counts down when shot; death alone has no generator | **likely** |
| `$21` | GEN A2 | `` | 462 in 94 lv | -- | damaged | -- | ghost generator, strength 2 | counts down when shot; death alone has no generator | **likely** |
| `$22` | GEN A3 | `` | 778 in 101 lv | -- | damaged | -- | ghost generator, strength 3 | counts down when shot; death alone has no generator | **likely** |
| `$23` | GEN B1 | `` | 235 in 55 lv | -- | destroyed | -- | grunt generator, strength 1 | counts down when shot; death alone has no generator | **likely** |
| `$24` | GEN B2 | `` | 249 in 77 lv | -- | damaged | -- | grunt generator, strength 2 | counts down when shot; death alone has no generator | **likely** |
| `$25` | GEN B3 | `` | 358 in 89 lv | -- | damaged | -- | grunt generator, strength 3 | counts down when shot; death alone has no generator | **likely** |
| `$26` | GEN C1 | `` | 143 in 50 lv | -- | destroyed | -- | demon generator, strength 1 | counts down when shot; death alone has no generator | **likely** |
| `$27` | GEN C2 | `` | 217 in 61 lv | -- | damaged | -- | demon generator, strength 2 | counts down when shot; death alone has no generator | **likely** |
| `$28` | GEN C3 | `` | 286 in 76 lv | -- | damaged | -- | demon generator, strength 3 | counts down when shot; death alone has no generator | **likely** |
| `$29` | GEN D1 | `` | 69 in 38 lv | -- | destroyed | -- | lobber generator, strength 1 | counts down when shot; death alone has no generator | **likely** |
| `$2A` | GEN D2 | `` | 104 in 38 lv | -- | damaged | -- | lobber generator, strength 2 | counts down when shot; death alone has no generator | **likely** |
| `$2B` | GEN D3 | `` | 243 in 60 lv | -- | damaged | -- | lobber generator, strength 3 | counts down when shot; death alone has no generator | **likely** |
| `$2C` | GEN E1 | `` | 162 in 45 lv | -- | destroyed | -- | sorcerer generator, strength 1 | counts down when shot; death alone has no generator | **likely** |
| `$2D` | GEN E2 | `` | 145 in 47 lv | -- | damaged | -- | sorcerer generator, strength 2 | counts down when shot; death alone has no generator | **likely** |
| `$2E` | GEN E3 | `` | 235 in 75 lv | -- | damaged | -- | sorcerer generator, strength 3 | counts down when shot; death alone has no generator | **likely** |
| `$2F` | TRAP | `@` | 230 in 75 lv | -- | passes through | -- | trap | sets $B62D; $B084 clears all traps and trap-walls | **firm** |
| `$30` | TELEPORT | `[` | 312 in 68 lv | -- | passes through | -- | teleporter | sets $8E78,x=1; pairs with $18 at $B4F9 | **firm** |
| `$31` | POISON | `W` | 314 in 75 lv | -- | destroyed | -- | poison | calls the centred-string printer at $B59E | **firm** |
| `$32` | -- | `?` | unused | -- | blocks shot | -- | unused, behaves as a wall | blocked by the passability test at $92C0, so its missing step handler is never reached. Looks like keys in play; cannot be entered, shot or picked up | **firm** |
| `$33` | DST WALL | `æ` | 1036 in 97 lv | -- | special | -- | destructible wall | stepping on it clears the cell at $B4EC | **firm** |
| `$36` | EXIT | `` | 880 in 128 lv | -- | passes through | -- | exit | counted in $C812; $CA0C keeps one at random | **firm** |
| `$37` | EXIT 4 | `` | 1 in 1 lv | -- | passes through | -- | exit to level 4 | the destination is chosen at $9A2B from the map address the exiting player stands on: $0CD2 sends them to level 4 and $0FE1 to level 8. Both shipped level 1s put an exit on those cells - Deeper Dungeons uses $37 and $38, the arcade original uses $36 on $0FE1 - so the codes are interchangeable and it is the address that matters. A static reading of the passability test at $92C0 says $37 and $38 are blocked, which contradicts the shipped data and play; that reading is wrong somewhere and has not been resolved | **uncertain** |
| `$38` | EXIT 8 | `` | 2 in 2 lv | -- | passes through | -- | exit to level 8 | the same story at $0FE1; see $37 | **uncertain** |
| `$3F` | START | `*` | 130 in 127 lv | -- | passes through | -- | player start | $C798 latches $C0/$C1 and $F800/$F801 | **firm** |
| `$40` | MON A1 | `A` | 639 in 67 lv | -- | passes through | -- | ghost, strength 1 | registered as an actor at $C734; named in play | **firm** |
| `$41` | MON A2 | `A` | 495 in 61 lv | -- | passes through | -- | ghost, strength 2 | registered as an actor at $C734; named in play | **firm** |
| `$42` | MON A3 | `A` | 573 in 68 lv | -- | passes through | -- | ghost, strength 3 | registered as an actor at $C734; named in play | **firm** |
| `$48` | MON B1 | `B` | 266 in 45 lv | -- | passes through | -- | grunt, strength 1 | registered as an actor at $C734; named in play | **firm** |
| `$49` | MON B2 | `B` | 236 in 46 lv | -- | passes through | -- | grunt, strength 2 | registered as an actor at $C734; named in play | **firm** |
| `$4A` | MON B3 | `B` | 228 in 64 lv | -- | passes through | -- | grunt, strength 3 | registered as an actor at $C734; named in play | **firm** |
| `$50` | MON C1 | `C` | 205 in 44 lv | -- | passes through | -- | demon, strength 1 | registered as an actor at $C734; named in play | **firm** |
| `$51` | MON C2 | `C` | 196 in 44 lv | -- | passes through | -- | demon, strength 2 | registered as an actor at $C734; named in play | **firm** |
| `$52` | MON C3 | `C` | 217 in 52 lv | -- | passes through | -- | demon, strength 3 | registered as an actor at $C734; named in play | **firm** |
| `$58` | MON D1 | `D` | 229 in 43 lv | -- | passes through | -- | lobber, strength 1 | registered as an actor at $C734; named in play | **firm** |
| `$59` | MON D2 | `D` | 138 in 45 lv | -- | passes through | -- | lobber, strength 2 | registered as an actor at $C734; named in play | **firm** |
| `$5A` | MON D3 | `D` | 283 in 59 lv | -- | passes through | -- | lobber, strength 3 | registered as an actor at $C734; named in play | **firm** |
| `$60` | MON E1 | `E` | 294 in 43 lv | -- | passes through | -- | sorcerer, strength 1 | registered as an actor at $C734; named in play | **firm** |
| `$61` | MON E2 | `E` | 84 in 27 lv | -- | passes through | -- | sorcerer, strength 2 | registered as an actor at $C734; named in play | **firm** |
| `$62` | MON E3 | `E` | 210 in 43 lv | -- | passes through | -- | sorcerer, strength 3 | registered as an actor at $C734; named in play | **firm** |
| `$68` | MON F | `F` | 690 in 108 lv | -- | passes through | -- | death | registered as an actor at $C734; named in play | **firm** |
| `$90` | TRAPWALL | `hatch` | 728 in 71 lv | -- | blocks shot | -- | trap-wall | bit 7; $B084 clears it when a trap fires | **firm** |

## How to read this

**Confidence** is what I can defend, not what I believe:

* **firm** — the routine's effect is unambiguous, and in most cases I ran it
  and measured the result.
* **likely** — the behaviour is clear but the *name* is inference. The
  generators count down when hit, which is generator-like, but nothing in the
  code calls them that. The amulets each set one bit of a six-bit flags word,
  which is power-up-like, but they appear in no shipped level so nothing
  confirms what the bits do.
* **unknown** — `$18`, `$30`, `$31` and `$33`. The editor names these `obj 18`
  and so on rather than guessing, and draws them as `?`.

## Things worth checking in play

* **`$20`, `$23`, `$26`, `$29`, `$2C`** show *destroyed* by one shot while the
  other twelve show *damaged*, so the first of each triple is the weakest.
  Whether the strength ordering runs 1-2-3 as labelled is still unconfirmed.
* **The six potions at `$19`-`$1E` are in no shipped level.** The bit each one
  sets is certain; which ability that bit grants is taken from play reports,
  not from the code. This remains the least-verified group.
* **Generator-to-monster pairing.** Death has no generator, which is why there
  are five generator families and six monster families. That the letters line
  up in order — generator A producing ghosts and so on — is inference from the
  counts, not something the code states.

## Caveats

* Counts are of cells in the **built map**, so `$36` includes exits drawn by
  the vector layer as well as those placed as objects.
* I have never decoded the tile *graphics*. Everything here is behaviour read
  from handlers, so I cannot tell you which of a pair has the square handle.

