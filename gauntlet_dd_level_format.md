# Gauntlet: The Deeper Dungeons (C64) — `LEVEL nnn` file format

> *Gauntlet* (c) 1985 Atari Games Corporation; Commodore 64 conversion
> (c) 1986 U.S. Gold Ltd; *Gauntlet: The Deeper Dungeons* (c) 1987
> U.S. Gold Ltd. This is unofficial documentation of how the file
> format works, written from a disassembly. No original code, level
> data or artwork is reproduced here.


Derived by disassembling the loader at **$C43D** inside `GAUNTPROG $8000`.
All 128 level files on the disk decode and re-encode byte-for-byte, so the
container and both payload sections are fully accounted for.

The map is **32 × 32 cells, one byte each**, built in RAM at **$0C00–$0FFF**.
Levels are small (95–513 bytes) because the map is not stored as a grid — it is
stored as a **drawing program** plus a **sparse object list**.

---

## 1. Container

Every file is a PRG with load address **$0A00**. After the 2-byte load address:

| Offset | C64 addr | Meaning |
|---|---|---|
| 0 | $0A00 | Total record length, low byte (counts from offset 0 inclusive) |
| 1 | $0A01 | Flags A |
| 2 | $0A02 | Flags B — **bit 7 is bit 8 of the total length** |
| 3 | $0A03 | Length of the vector section, in bytes |
| 4… | $0A04 | Vector section |
| 4+veclen… | | Object section |

Object-section length is not stored; the loader computes it at $C665 as
`total − veclen − 4`. Total length is 9 bits, so the ceiling is 511 bytes.

### Flags A ($0A01)

| Bit | Meaning |
|---|---|
| 0 | Gameplay toggle, read at $989C / $AA30. **Never set in any shipped level.** |
| 1 | Gameplay toggle, read at $98A8 / $AA24 |
| 2 | Teleporters live — enables the random-destination picker at $C9ED |
| 3–5 | Wall graphic set, 0–7. Selects a 96-byte tile block copied into the charset at $8C36 |
| 6 | Extends the playfield's right/bottom scroll limit ($87BE) |
| 7 | Extends the left/top limit ($87BC) **and** suppresses the default left border column |

### Flags B ($0A02)

| Bit | Meaning |
|---|---|
| 0–2 | Present in the data (values 0–7) but **never read by the game**. Likely editor metadata |
| 3–5 | Wall colour, 0–7 → `$8C78` = `0A 0D 0E 0C 0F 0B 08 0A`, written to colour RAM |
| 6 | Never set |
| 7 | Bit 8 of total length |

### Implicit borders (drawn before either section)

* Row 0 is filled with `$0A`.
* Unless flags A bit 7 is set, cell (0,0) becomes `$0F` and column 0 of rows 1–31 becomes `$05`.

---

## 2. Vector section — turtle graphics

This is the walls layer. There is **no opcode byte**. Each byte splits as
`TTTVVVVV`: a 3-bit top field and a 5-bit value. The decoder groups consecutive
bytes that share the same top field and reads two command types.

### POINT — 2 bytes, same top field

```
byte 0:  PPP xxxxx      PPP = pen type, xxxxx = column 0–31
byte 1:  PPP yyyyy      yyy = same pen,  yyyyy = row 0–31
```

Moves the cursor to (x, y), sets the pen, and plots one cell there.

| Pen | Tile | Meaning |
|---|---|---|
| $20 | $36 | Teleporter |
| $40 | $11 | Wall, vertical seed |
| $80 | $12 | Wall, horizontal seed |
| $C0 | $90 | Wall with bit 7 set — the solid/indestructible variant |
| $E0 | $10 | Wall, plain |
| $00 / $60 / $A0 | $00 | Floor (erase) |

### DRAW — 1 byte

```
byte:  DDD nnnnn        DDD = heading 0–7, nnnnn = length − 1
```

Steps the cursor `n+1` times along the heading, plotting the current pen at each
step. Headings run clockwise from north:

| DDD | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| | N | NE | E | SE | S | SW | W | NW |
| offset | −32 | −31 | +1 | +33 | +32 | +31 | −1 | −33 |

Movement wraps modulo 1024 — the loader masks the pointer high byte with
`AND #$03 / ORA #$0C`, so running off the right edge continues on the next row
and running off the bottom wraps to the top.

**Wall auto-orientation.** If the pen is `$40` or `$80` when a DRAW executes, it
is replaced from `$C81E` = `40 80 40 80` indexed by `DDD >> 1`. Headings N/NE and
S/SW give the vertical glyph, E/SE and W/NW the horizontal one. So a wall drawn
sideways renders as a sideways wall without the author saying so.

### The disambiguation rule — important for an editor

Because there is no opcode, the decoder resolves POINT vs DRAW by looking at how
many consecutive bytes share the same top field. In a maximal group of length L:

```
L = 1  →  DRAW
L = 2  →  POINT
L = 3  →  DRAW, POINT
L = 4  →  POINT, POINT
L = 5  →  POINT, DRAW, POINT
L = 6  →  POINT, POINT, POINT
L = 7  →  POINT, POINT, DRAW, POINT
```

Even L is all POINTs. Odd L contains exactly one DRAW, always **three bytes from
the end of the group**. A writer must therefore not emit a DRAW whose heading
code collides with a neighbouring pen type in a way that lands it elsewhere in a
group. The practical defence is to decode your own output before writing it —
`encode()` in the accompanying tool does this and raises on ambiguity.

---

## 3. Object section — sparse overlay

Walks the same 32 × 32 map from cell 0, overwriting whatever the vector section
drew. Stops at 1024 cells or when the section is exhausted.

| Byte | Meaning |
|---|---|
| `1nnnnnnn` | Skip `nnnnnnn + 1` cells (1–128) |
| `0ccccccc` | Object code. If the **next** byte is < `$13`, that byte is a repeat count `r` and the object is placed `r + 2` times; otherwise one copy |

The repeat-count rule means an object code below `$13` cannot immediately follow
another object. In practice no shipped level uses a code below `$13`.

### Object codes

| Code | Count in 128 levels | Notes |
|---|---|---|
| $13–$18 | 4575 | Static furniture — walls, doors, food, potions, treasure |
| $1F–$31 | 5462 | More furniture; $13 alone accounts for 2933 |
| $33 | 1036 | |
| $36 | 437 | **Teleporter.** Counted into `$C812` at $C715; $C9ED picks a random one as a destination |
| $37, $38 | 3 | Used once and twice on the whole disk |
| $3F | 130 | **Player start.** $C798 latches the cell into `$C0/$C1` and `$F800/$F801`. Present in 127 of 128 levels |
| ≥ $40 | 4290 | **Actors.** Registered into the monster tables at $0400/$04C0/$0580/$0640 |

Actor codes decompose as `0 0 fff 0 vv`:

* **family** = `(code & $38) >> 3` → six families at $40, $48, $50, $58, $60, $68
* **variant** = `code & 3`, 0–2 — the three monster strengths. $C75F relocates
  these bits to 6–7 of the runtime monster byte
* family `$28` (i.e. code $68) is special-cased at $C76F to the constant `$C0`,
  and is the only family with no variants

Distinguishing the individual sub-$40 codes needs the tile graphics from
`GAUNT CHR $4800`; the loader treats them all identically.

---

## 4. Cell values in the built map

| Value | Meaning |
|---|---|
| $00 | Floor |
| $01–$0F | Wall, low nibble is a **connectivity bitmask** computed by the linker at $CACD/$C586 using `$C809` = `04 01 08 02 01 04 02 08` |
| $10 / $11 / $12 | Wall seeds written by the pen, before linking |
| bit 7 set | Solid/indestructible wall attribute, preserved separately at $C7D6 |
| ≥ $13 | Object codes as above |

Wall linking runs after every plot, so an editor that writes seeds `$10/$11/$12`
gets the same joined-up wall rendering the game produces.

---

## 5. Caveat

`OBJDIS` loads at $C800–$CFFF and overlaps `GAUNTPROG`. The tables this spec
relies on ($C7F9, $C816, $C81E, $CF9C/$CFBC) are the **GAUNTPROG** copies —
`OBJDIS` holds unrelated data at those addresses, so `GAUNTPROG` must be loaded
last. That is consistent with the decoded output being coherent; worth
confirming against the boot loader `GAUNTLET DD $0302` before shipping an editor
that patches the game itself.
