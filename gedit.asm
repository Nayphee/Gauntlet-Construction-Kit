; ----------------------------------------------------------------------
; gedit.asm - the Gauntlet Construction Kit: a level editor for the
;             Commodore 64 game Gauntlet and Gauntlet: The Deeper
;             Dungeons.  Edits any disk that holds its levels as 128
;             separate LEVEL nnn files.
;
; Pure machine code behind a one-line BASIC stub, "0 sys2100".  The stub
; and the code are one file: the m/l is loaded straight to where it runs,
; so there is no copier and no relocation.  build.py settles the sys
; address by iteration, because it depends on where main lands, which
; depends on the origin, which depends on the stub's length.
;
; Memory map:
;   $080d-$271e  the BASIC stub, then code and tables
;   $9800-$9bff  the 32x32 map, 1K-aligned for the DRAW wrap
;   $9c00-$9cf9  wall-edit list, 125 entries of two bytes
;   $9d00-$9eff  512-byte level record buffer
;
; The whole editor runs in edloop; it returns to BASIC only on quit.
; Everything the panel shows - the cursor position, the tile under it,
; the trap and trap-wall counts, the wall graphics and colour, the shot
; mode, and the byte cost of the level as it stands - is maintained in
; machine code, because the same work in BASIC was visibly slow.
;
; Zero page used: $22-$27, $fb-$fe.  All are free while BASIC is idle;
; nothing here returns to BASIC mid-use.
;
; CBM prg Studio syntax: open this in prg Studio and build it, with the
; origin at $080D and a one-line BASIC stub of "0 SYS2100" in front.  The
; python route, which settles the sys address by iteration and writes the
; symbol table the automated checks need, is
;   python3 build.py
; and check with checkregs.py, checklegend.py and the three test suites.
; ----------------------------------------------------------------------

; ---- equates ---------------------------------------------------------
grid    = $9800                 ; 1024-byte map, one byte per cell.  Must stay
                                ; 1K-aligned: the DRAW wrap masks the pointer
                                ; high byte with AND #3
gridend = $9c                   ; high byte of grid + $400
buf     = $9d00
bufcap  = $9f                   ; high byte of buf + 512, the write guard
pancol  = 11                    ; side panel colour; it is drawn reverse video
weblk   = $9c00                 ; wall-edit list: POINT pairs appended to the
                                ; vector section, 250 bytes = 125 edits max
screen  = $0400
colram  = $d800

mlo     = $fb                   ; map / destination pointer
mhi     = $fc
srclo   = $fd
srchi   = $fe
dstlo   = $22
dsthi   = $23
collo   = $24
colhi   = $25
objlo   = $26
objhi   = $27
enclo   = $28                   ; record write cursor (encode only)
enchi   = $29

; build.py rewrites this line as it settles the sys address
*=$080d

; ---- entry points ----------------------------------------------------
; A jump table at a fixed address, so the checkers and the test suites can
; call any routine by name without caring where the assembler put it.
; genaddr.py writes these addresses out to symbols.json.
        jmp decode
        jmp redraw
        jmp loadlev
        jmp savelev
        jmp encode
        jmp clrwe
        jmp cksum
        jmp newlvl
        jmp count
        jmp edloop
        jmp panel
        jmp preview
        jmp doload
        jmp main

; ---- variables ------------------------------------------------------
scrtop  byte 0                  ; top map row on screen, 0-7
vlen    byte 0
pen     byte 0
tmp     byte 0
tmp2    byte 0
remlo   byte 0
remhi   byte 0
objcod  byte 0
objcnt  byte 0
rowno   byte 0
fnlen   byte 0
fnbuf   byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
ldst    byte 0                  ; 0 = ok, 1 = error (load or save)
szlo    byte 0                  ; encoded length of the map as it stands
szhi    byte 0
veclen  byte 0                  ; vector bytes of the loaded record, kept
runcnt  byte 0
fobj    byte 0
objtop  byte 0
cklo    byte 0
ckhi    byte 0
dev     byte 8                  ; device to load and save levels on; the
                                ; editor sets this from $ba, the device the
                                ; program itself was loaded from
ntrap   byte 0
nwall   byte 0
nstart  byte 0
nexit   byte 0
curx    byte 0
cury    byte 0
tidx    byte 1
mode    byte 0
lastky  byte 0
lvlno   byte 1
prevky  byte 0                  ; last key, for the repeat guard only
rptrat  byte 255                ; held-key speed out of 256: 255 is the
rptacc  byte 0                  ; fastest, 128 half, 64 a quarter                  ; level number, poked by BASIC
svk1    byte 0
svk2    byte 0
errno   byte 0
numval  byte 0
numlen  byte 0
numovf  byte 0
numbuf  byte 0,0,0
endlo   byte 0
endhi   byte 0                  ; 1 when the level is not from disk
pbuf    byte 0,0,0,0,0,0,0,0    ; one panel row under construction
dirty   byte 0                  ; 1 once the map has been painted; cleared
                                ; by BASIC on load, new and a good save
welen   byte 0                  ; bytes used in weblk (2 per wall edit)
noopc   byte 0,0                ; column,row the no-op POINT targets
gap     byte 0                  ; pending skip count while encoding
gaphi   byte 0


; ======================================================================
; decode - rebuild the map from the record in buf
; ======================================================================
decode
        lda #0
        tax
@clr    sta grid,x
        sta grid+$100,x
        sta grid+$200,x
        sta grid+$300,x
        inx
        bne @clr

        ldx #31                 ; top row = $0a
        lda #$0a
@top    sta grid,x
        dex
        bpl @top

        lda buf+1               ; left column unless flags1 bit 7
        bmi novert
        lda #$0f
        sta grid
        lda #<grid
        clc
        adc #32
        sta mlo
        lda #>grid
        adc #0
        sta mhi
        ldx #31
@lcol   ldy #0
        lda #$05
        sta (mlo),y
        lda mlo
        clc
        adc #32
        sta mlo
        bcc @lc1
        inc mhi
@lc1    dex
        bne @lcol
novert

; ---- vector section --------------------------------------------------
        lda buf+3
        sta vlen
        sta veclen
        lda #0
        sta pen
        ldy #0

vloop   lda vlen
        bne vgo
        jmp objsec
vgo     cmp #1
        beq isdraw
        jsr cmptop              ; tops of b0,b1 equal?
        bne isdraw
        lda vlen
        cmp #3
        bne vgt3
        iny                     ; exactly 3 left
        jsr cmptop
        php
        dey
        plp
        bne ispnt
        beq isdraw
vgt3    iny
        jsr cmptop
        php
        dey
        plp
        bne ispnt
        iny
        iny
        jsr cmptop
        php
        dey
        dey
        plp
        bne isdraw
ispnt   jsr dopoint
        jmp vloop
isdraw  jsr dodraw
        jmp vloop

; compare the top 3 bits of buf+4,y and buf+5,y; returns Z set if equal
cmptop  lda buf+4,y
        and #$e0
        sta tmp
        lda buf+5,y
        and #$e0
        cmp tmp
        rts

; POINT: two bytes, sets pen and moves the cursor to an absolute cell
dopoint lda buf+4,y
        pha
        and #$e0
        sta pen
        pla
        and #$1f
        sta tmp
        lda buf+5,y
        and #$1f
        tax
        lda rowlo,x
        clc
        adc tmp
        sta mlo
        lda rowhi,x
        adc #0
        sta mhi
        jsr plot
        iny
        iny
        dec vlen
        dec vlen
        rts

; DRAW: one byte, walks n+1 cells along a heading
dodraw  tya
        pha
        lda buf+4,y
        pha
        and #$e0
        lsr
        lsr
        lsr
        lsr
        tax                     ; heading * 2
        lsr
        lsr
        tay                     ; heading >> 1
        lda pen
        cmp #$80
        beq dreor
        cmp #$40
        bne dnoreo
dreor   lda wallre,y
        sta pen
dnoreo  pla
        and #$1f
        tay                     ; length - 1
dstep   lda mlo
        clc
        adc dirvec,x
        sta mlo
        lda mhi
        adc dirvec+1,x
        and #3
        ora #>grid
        sta mhi
        jsr plot
        dey
        bpl dstep
        pla
        tay
        iny
        dec vlen
        rts

; write the pen's tile at (mlo)
plot    pha
        tya
        pha
        lda pen
        asl
        rol
        rol
        rol
        and #7
        tay
        lda pentil,y
        ldy #0
        sta (mlo),y
        pla
        tay
        pla
        rts

; ---- object section --------------------------------------------------
objsec  lda buf+3               ; objptr = buf + 4 + veclen
        clc
        adc #<buf
        adc #4
        sta objlo
        lda #>buf
        adc #0
        sta objhi

        lda buf+2               ; remaining = total - veclen - 4
        asl
        rol
        and #1
        sta remhi
        lda buf
        sec
        sbc buf+3
        sta remlo
        lda remhi
        sbc #0
        sta remhi
        lda remlo
        sec
        sbc #4
        sta remlo
        lda remhi
        sbc #0
        sta remhi

        lda #<grid
        sta mlo
        lda #>grid
        sta mhi
        ldy #0

oloop   lda (objlo),y
        bpl isobj
        and #$7f                ; skip (n+1) cells
        sec
        adc mlo
        sta mlo
        lda mhi
        adc #0
        sta mhi
        jmp onext

isobj   sta objcod
        lda #0
        sta objcnt
        lda remlo               ; only one byte left? place a single copy
        cmp #1
        bne opeek
        lda remhi
        beq oplace
opeek   iny                     ; look at the next byte
        bne op1
        inc objhi
op1     lda (objlo),y
        dey
        cpy #$ff
        bne op2
        dec objhi
op2     cmp #$13
        bcs oplace
        sta objcnt              ; it is a repeat count: n + 2 copies
        inc objcnt
        iny
        bne op3
        inc objhi
op3     jsr decrem
oplace  jsr putobj
        dec objcnt
        bpl oplace

onext   jsr decrem
        iny
        bne on1
        inc objhi
on1     lda mhi
        cmp #gridend
        bcs odone
        lda remlo
        ora remhi
        bne oloop
odone   rts

putobj  ldx #0
        lda objcod
        sta (mlo,x)
        inc mlo
        bne pu1
        inc mhi
pu1     rts

decrem  lda remlo
        bne de1
        dec remhi
de1     dec remlo
        rts

; ======================================================================
; encode - rebuild the record in buf from the grid, keeping the original
;          vector bytes untouched and re-emitting only the object layer.
;
; A cell is an object iff it holds $13-$7f.  Exits drawn by the VECTOR
; layer are stored as $92 by the editor's pen table, so they fall outside
; that range and cannot be emitted twice.
; ======================================================================
encode  jsr apvec               ; append wall edits + the decoupling no-op
        bcc encok               ; carry set: the vector section is full, and
        jmp encbig              ; encbig is too far for a branch to reach
encok   lda #<buf               ; write cursor = buf + 4 + new veclen
        clc
        adc #4
        adc buf+3
        sta enclo
        lda #>buf
        adc #0
        sta enchi

        lda #0
        sta gap
        sta gaphi
        lda #<grid
        sta mlo
        lda #>grid
        sta mhi
        ldx #0
enloop  lda (mlo,x)
        cmp #$13                ; below $13 is floor or wall
        bcc engap
        cmp #$80                ; $80 and up is wall, or the $92 exit marker
        bcs engap
        sta objcod              ; an object - save it before putgap eats A
        jsr putgap              ; flush the pending skip first
        lda #0
        sta runcnt
        lda mhi                 ; no run scanning in the last page, where a
        cmp #gridend-1          ; peek could read past the grid into buf
        beq enemit
enrun   ldy runcnt
        iny
        cpy #20                 ; at most 20 copies per repeat pair
        beq enemit
        lda (mlo),y
        cmp objcod
        bne enemit
        sty runcnt
        jmp enrun
enemit  lda objcod
        jsr putbyt
        lda runcnt
        beq ennext
        sec
        sbc #1                  ; repeat byte = copies - 2
        jsr putbyt
        lda runcnt              ; skip the cells the run covered
        clc
        adc mlo
        sta mlo
        lda mhi
        adc #0
        sta mhi
        jmp ennext
engap   inc gap                 ; count another skipped cell, 16-bit
        bne ennext
        inc gaphi
ennext  inc mlo
        bne enn1
        inc mhi
enn1    lda mhi
        cmp #gridend
        bne enloop
        lda enclo               ; ---- header: total length ----
        sec
        sbc #<buf
        sta buf
        lda enchi
        sbc #>buf
        cmp #2                  ; 512 bytes or more cannot be expressed
        bcs encbig
        lsr
        lda buf+2
        and #$7f
        bcc ence1
        ora #$80
ence1   sta buf+2
        lda buf                 ; 511 is the hard ceiling
        cmp #$ff
        bne ence2
        lda buf+2
        bmi encbig
ence2   lda #0
        sta ldst
        rts
encbig  lda #1                  ; too big: tell the caller, write nothing
        sta ldst
        rts

; ----------------------------------------------------------------------
; apvec - extend the vector section in place.
;
; Appends the wall-edit POINT pairs the editor recorded, then a final
; no-op POINT.  The no-op uses pen $00 or $60: both plot floor, and both
; top fields are below $80, so neither can match a leading skip byte.
; That makes the last group resolve without the dispatcher reading any
; object byte, so re-encoding objects can never disturb the walls.
;
; The first appended byte must not share a top field with the last
; original byte, or it would join that group and flip its parity.  When
; it would, a separator no-op goes in first.
; ----------------------------------------------------------------------
; The vector length is one byte.  A level loaded with 254 vector bytes and
; a trailing no-op to add would carry it to 256, which wraps to zero and
; throws the whole wall layout away: the record still saved, 254 bytes
; shorter, with every wall gone.  Refuse instead.
apvec   lda veclen
        clc
        adc welen
        bcs apbig               ; past 255 before the no-op even goes on
        adc #2
        bcs apbig
        lda veclen
        sta buf+3
        jsr fndcel              ; pick a cell the object layer will cover
        lda welen
        beq apnoop              ; no wall edits: just the trailing no-op
        jsr lastop              ; would the first edit join the last group?
        sta tmp2
        lda weblk
        and #$e0
        cmp tmp2
        bne apcopy
        jsr putnop              ; yes - separate them first
apcopy  ldx #0
apc1    lda weblk,x
        jsr apbyt
        inx
        cpx welen
        bne apc1
apnoop  jsr putnop
        clc                     ; carry clear: the caller may go on
        rts
apbig   sec                     ; carry set: no room for the wall edits
        rts

; append A to the vector section, bumping veclen
apbyt   pha
        lda #<buf
        clc
        adc #4
        adc buf+3
        sta dstlo
        lda #>buf
        adc #0
        sta dsthi
        pla
        ldy #0
        sta (dstlo),y
        inc buf+3
        rts

; Emit a no-op POINT at noopc.  Pens $00, $60 and $a0 all plot floor, so
; any of them is harmless; pick one whose top field matches neither the
; preceding byte nor the first byte of the object section.  Matching either
; would merge the pair into that group and flip its parity, which would
; turn this POINT into a DRAW and paint a wall.
putnop  jsr lastop
        sta tmp2
        ldx #0
pnp0    lda flrpen,x
        cmp tmp2
        beq pnp1
        cmp objtop
        bne pnp2
pnp1    inx
        cpx #3
        bne pnp0
        lda #$00                ; all three collide: cannot happen with two
pnp2    sta tmp                 ; constraints and three candidates
        lda noopc               ; column
        and #$1f
        ora tmp
        jsr apbyt
        lda noopc+1             ; row
        and #$1f
        ora tmp
        jsr apbyt
        rts

; A = top 3 bits of the last byte of the vector section, or $ff if empty.
; Returns the value only - the caller does its own comparison, because a
; cmp here would be undone by the load that follows it.
lastop  lda buf+3
        beq lstemp
        lda #<buf
        clc
        adc #3
        adc buf+3
        sta dstlo
        lda #>buf
        adc #0
        sta dsthi
        ldy #0
        lda (dstlo),y
        and #$e0
        rts
lstemp  lda #$ff
        rts

flrpen  byte $00,$60,$a0

; Find the first cell holding an object.  The no-op POINT targets it, so the
; object layer overwrites it and the no-op can never be seen.  Also work out
; the top field the first object byte will have: the object code itself when
; that cell is cell 0, otherwise a skip byte $80|(n-1).
fndcel  lda #0
        sta noopc
        sta noopc+1
        lda #<grid
        sta srclo
        lda #>grid
        sta srchi
        ldy #0
        ldx #0
fnd1    lda (srclo,x)
        cmp #$13
        bcc fnd2
        cmp #$80
        bcc fnd3                ; found one
fnd2    inc srclo
        bne fnd2a
        inc srchi
fnd2a   inc noopc               ; column counter 0-31
        lda noopc
        cmp #32
        bne fnd2b
        lda #0
        sta noopc
        inc noopc+1
fnd2b   lda srchi
        cmp #gridend
        bne fnd1
        lda #0                  ; none found - fall back to (0,0)
        sta noopc
        sta noopc+1
fnd3    sta fobj                ; A still holds the object code
        lda noopc+1             ; row >= 4 means a skip of 128 -> byte $ff
        cmp #4
        bcs fndbig
        ora noopc               ; row 0 and column 0 -> object is at cell 0
        bne fndskp
        lda fobj                ; first byte is the object code itself
        and #$e0
        sta objtop
        rts
fndskp  lda noopc+1             ; n = row*32 + col
        asl
        asl
        asl
        asl
        asl
        clc
        adc noopc
        sec
        sbc #1                  ; skip byte is $80|(n-1)
        ora #$80
        and #$e0
        sta objtop
        rts
fndbig  lda #$e0                ; $80|127 = $ff
        sta objtop
        rts

; write the pending skip, if any, as one $80|(n-1) byte
putgap  lda gap
        ora gaphi
        beq putg9
putg1   lda gaphi               ; more than 128 cells still pending?
        bne putg2
        lda gap
        cmp #129
        bcc putg3
putg2   lda #$ff                ; a full 128-cell skip
        jsr putbyt
        lda gap
        sec
        sbc #128
        sta gap
        lda gaphi
        sbc #0
        sta gaphi
        lda gap
        ora gaphi
        bne putg1
        beq putg9
putg3   lda gap                 ; the remainder, 1 to 128 cells
        sec
        sbc #1
        ora #$80
        jsr putbyt
putg9   lda #0
        sta gap
        sta gaphi
        rts

; append A to the record
putbyt  pha
        ldy #0
        sta (enclo),y
        inc enclo
        bne putb1
        inc enchi
putb1   pla
        rts

; 16-bit checksum of the grid, left in cklo/ckhi.  The editor takes one
; before encoding and one after re-decoding its own output; if they differ
; the edit cannot be represented and the save is abandoned rather than
; written.  This is the backstop that makes a corrupt file impossible.
cksum   lda #0
        sta cklo
        sta ckhi
        lda #<grid
        sta srclo
        lda #>grid
        sta srchi
        ldy #0
        ldx #0
cks1    lda (srclo,x)
        clc
        adc cklo
        sta cklo
        lda ckhi
        adc #0
        sta ckhi
        inc cklo                ; position-sensitive: a bare sum would miss
        bne cks1a               ; a value moving from one cell to another
        inc ckhi
cks1a   inc srclo
        bne cks2
        inc srchi
cks2    lda srchi
        cmp #gridend
        bne cks1
        rts

; count - traps ($2f) and trap-linked walls (bit 7 set, but not the $92
;         exit marker) across the whole map
count   lda #0
        sta ntrap
        sta nwall
        sta nstart
        sta nexit
        lda #<grid
        sta srclo
        lda #>grid
        sta srchi
        ldx #0
cnt1    lda (srclo,x)
        cmp #$2f                ; a trap
        bne cnt1a
        inc ntrap
        jmp cnt3
cnt1a   cmp #$3f                ; a player start marker
        bne cnt1b
        inc nstart
        jmp cnt3
cnt1b   cmp #$36                ; an exit, of any of the three kinds: $37
        beq cnt1c               ; and $38 are the level 4 and level 8
        cmp #$37                ; shortcuts, and count just the same
        beq cnt1c
        cmp #$38
        bne cnt2
cnt1c   inc nexit
        jmp cnt3
cnt2    cmp #$92
        beq cnt3
        and #$80                ; test bit 7 of the cell, not the sign of the
        beq cnt3                ; comparison - bpl here would read cmp's N flag
        inc nwall
cnt3    inc srclo
        bne cnt4
        inc srchi
cnt4    lda srchi
        cmp #gridend
        bne cnt1
        rts


; ======================================================================
; edloop - the interactive editor.
;
; BASIC used to run this, spending 200-400 ms rebuilding the side panel
; after every paint.  Here the whole hot path - key, cursor, paint,
; scroll, panel - is machine code; BASIC sees control again only for the
; rare commands (load, save, help, quit), whose key is left in lastky.
; ======================================================================
edloop  lda #$00                ; the KERNAL default: only the cursor keys,
        sta $028a               ; space and delete auto-repeat when held.
                                ; Asking it to repeat everything ($80) is
                                ; what made a held key and a deliberate
                                ; second press indistinguishable.
        jsr curon
edwait  jsr $ffe4
        beq edwait
        sta tmp
        cmp prevky
        bne edwnew              ; a different key always acts at once
        jsr rptfast             ; the same key again.  If the KERNAL repeats
        bcc edwgo               ; it, throttle; if not, the player pressed it
                                ; twice on purpose, so act at once.
        lda rptrat              ; throttle by fractions, not whole steps:
        cmp #255                ; add the rate and act only on a carry, so
        beq edwgo               ; 128 is half speed and 192 three quarters.
        clc                     ; 255 means no throttling at all
        adc rptacc
        sta rptacc
        bcc edwait
        jmp edwgo
edwnew  lda #0                  ; a new key always acts at once
        sta rptacc
edwgo   lda tmp
        sta lastky
        sta prevky
        jsr curoff
        jsr msgoff              ; whatever the last action reported has now
                                ; been read: clear it on the next keypress
        lda lastky
        cmp #$91                ; cursor up (shift crsr down)
        bne edk1
        lda cury
        beq edw9
        dec cury
edw9    jmp eddone
edk1    cmp #$11                ; cursor down
        bne edk2
        lda cury
        cmp #31
        beq eds9
        inc cury
eds9    jmp eddone
edk2    cmp #$9d                ; cursor left (shift crsr right)
        bne edk3
        lda curx
        beq eda9
        dec curx
eda9    jmp eddone
edk3    cmp #$1d                ; cursor right
        bne edk4
        lda curx
        cmp #31
        beq edd9
        inc curx
edd9    jmp eddone
edk4    cmp #$20                ; space - paint
        bne edk5
        jsr paint
        jmp eddone
edk5    cmp #$2e                ; . - next tile
        bne edk6
        inc tidx
        lda tidx
        cmp #57                 ; palette entries
        bcc edp9
        lda #0                  ; wrap to the first
        sta tidx
edp9    jmp eddone
edk6    cmp #$2c                ; , - previous tile
        bne edk7
        dec tidx
        bpl edm9
        lda #56                 ; wrap to the last
        sta tidx
edm9    jmp eddone
edk7    cmp #$2b                ; + - next level number
        bne edk7a
        lda lvlno
        cmp #128
        beq edn9
        inc lvlno
edn9    jmp eddone
edk7a   cmp #$2d                ; - - previous level number
        bne edk7b
        lda lvlno
        cmp #1
        beq edn8
        dec lvlno
edn8    jmp eddone
edk7b   cmp #$db                ; shift-+ - ten levels on
        bne edk7c
        lda lvlno
        clc
        adc #10
        cmp #129
        bcc edk7d
        lda #128
edk7d   sta lvlno
        jmp eddone
edk7c   cmp #$dd                ; shift-- - ten levels back
        bne edk7e
        lda lvlno
        sec
        sbc #10
        bcs edk7f
        lda #1
edk7f   cmp #1
        bcs edk7g
        lda #1
edk7g   sta lvlno
        jmp eddone
edk7e   cmp #$14                ; del - erase this cell
        bne edk8x
        jsr erase
        jmp eddone
edk8x   cmp #$4d                ; m - paint as you move
        bne edk8
        lda mode
        eor #$01
        sta mode
        jmp eddone
edk8    cmp #$4c                ; l - load the level LVL shows
        bne edk9
        lda dirty
        beq edld
        lda #5
        jsr confirm
        bcc eddone
edld    jsr doload
        jmp edloop
edk9    cmp #$53                ; s - save
        beq edsav
        cmp #$56                ; v - save as well, out of habit
        bne edka
edsav   jsr dosave
        jmp edloop
edka    cmp #$54                ; t - trap preview
        bne edkb
        jsr dotrap
        jmp edloop
edkb    cmp #$43                ; c - new level
        bne edkc
        jsr donew
        jmp edloop
edkc    cmp #$46                ; f - shots
        bne edkd
        jsr docyc
        jmp edloop
edkd    cmp #$47                ; g - wall graphic set
        bne edke
        jsr dogfx
        jmp edloop
edke    cmp #$4b                ; k - wall colour
        bne edkf
        jsr docol
        jmp edloop
edkf    cmp #$51                ; q - quit, confirmed here
        bne edexit
        lda #6
        jsr confirm
        bcc eddone
edexit  jsr curon               ; ? or a confirmed q: hand back to BASIC
        rts
eddone  lda mode
        beq edd1
        lda lastky              ; only paint on a movement key
        cmp #$20
        beq edd1
        cmp #$2c
        beq edd1
        cmp #$2e
        beq edd1
        cmp #$4d
        beq edd1
        jsr paint
edd1    jsr edscrl
        jsr edpanl
        lda dirty               ; the size and the warnings only move when
        beq edd2                ; the map does
        jsr pnwarn
        jsr pnbyte
edd2
        jmp edloop

; ---- write the current tile, and log a wall edit if it is a vector tile
paint   ldx tidx
        lda tilev,x
        sta tmp
        jsr cellpt
        ldx #0
        lda (mlo,x)             ; already what the cursor holds?  Painting a
        cmp tmp                 ; wall over the same wall used to log a fresh
        beq pnt9                ; edit every time, so brushing back and forth
        lda #1                  ; grew the record by two bytes a step until
        sta dirty               ; the level would no longer fit
        lda tmp
        sta (mlo,x)
        ldx tidx
        lda tilep,x
        cmp #$ff
        beq pnt9                ; an object: the object layer handles it
        sta tmp
        jmp welog               ; tmp holds the pen

; ---- log a wall edit for the cell under the cursor, with the pen in tmp.
;      Both paint and erase come here: editing one cell three times used to
;      append three entries, so the record grew whether or not the map had
;      changed, and erase kept its own copy of the code that did it.
welog   ldx #0
wel1    cpx welen
        beq welnew
        lda weblk,x
        and #$1f
        cmp curx
        bne wel2
        lda weblk+1,x
        and #$1f
        cmp cury
        beq welup               ; this cell is already listed: replace it
wel2    inx
        inx
        jmp wel1
welup   lda tmp
        ora curx
        sta weblk,x
        lda tmp
        ora cury
        sta weblk+1,x
        rts
welnew  lda welen
        cmp #249
        bcs pnt9                ; list full
        tax
        lda tmp
        ora curx
        sta weblk,x
        inx
        lda tmp
        ora cury
        sta weblk,x
        inx
        stx welen
pnt9    rts

; ---- erase: write floor, and log it so a wall underneath goes too
erase   jsr cellpt
        ldx #0
        lda (mlo,x)
        beq era9                ; already floor: nothing to record
        cmp #$13
        bcs eraobj              ; an object: it lives in the object section,
        pha                     ; so clearing it needs no wall edit at all -
        lda #$00                ; logging one cost two bytes of vector for
        sta (mlo,x)             ; nothing, and a run of erases could push a
        lda #1                  ; level over the ceiling
        sta dirty
        lda #$00                ; pen $00 is floor, so the byte is just x
        sta tmp
        pla
        jmp welog
eraobj  lda #$00
        sta (mlo,x)
        lda #1
        sta dirty
era9    rts

; ---- mlo/mhi = grid cell under the cursor
cellpt  ldx cury
        lda rowlo,x
        clc
        adc curx
        sta mlo
        lda rowhi,x
        adc #0
        sta mhi
        rts

; ---- dstlo/collo = screen and colour position; carry set if off-screen
scrpos  lda cury
        sec
        sbc scrtop
        bcc scp9
        cmp #25
        bcs scp9
        tax
        lda scrlo,x
        clc
        adc curx
        sta dstlo
        sta collo
        lda scrhi,x
        adc #0
        sta dsthi
        clc
        adc #$d4
        sta colhi
        clc
        rts
scp9    sec
        rts

curon   jsr cellpt              ; highlight the cell without hiding it:
        ldx #0                  ; keep the glyph, force reverse video, white
        lda (mlo,x)
        tax
        lda chtab,x
        ora #$80                ; ora, not eor: an already-reversed glyph
        sta tmp                 ; must stay reversed, not flip back
        jsr scrpos
        bcs cur9
        ldy #0
        lda tmp
        sta (dstlo),y
        lda #1                  ; white
        sta (collo),y
cur9    rts

curoff  jsr cellpt
        ldx #0
        lda (mlo,x)
        tax
        lda chtab,x
        sta tmp
        lda coltab,x
        sta tmp2
        jsr scrpos
        bcs cur9
        ldy #0
        lda tmp
        sta (dstlo),y
        lda tmp2
        sta (collo),y
        rts

; ---- carry set if this key is one that may repeat when held
; ---- carry set if this is a key the KERNAL auto-repeats, which is the
;      only case that needs throttling.  Everything else reaching here is a
;      second deliberate press and acts immediately: the old list worked the
;      other way round, so any key not on it silently stopped working on its
;      second press, which caught ?, the cycling toggles and shift-+ in turn.
rptfast ldx #5
rpk1    cmp rptfst,x
        beq rpk9
        dex
        bpl rpk1
        clc
        rts
rpk9    sec
        rts

rptfst  byte $91,$11,$9d,$1d     ; the four cursor keys
        byte $20,$14             ; space and delete - the KERNAL repeats
                                 ; these two as well, and holding space to
                                 ; draw a run of wall is worth having

; ---- keep the cursor inside the 25-row window
edscrl  lda scrtop
        sta tmp2
        lda cury
        cmp scrtop
        bcs eds1
        sta scrtop
eds1    lda cury
        sec
        sbc #24
        bcc eds2
        cmp scrtop
        bcc eds2
        sta scrtop
eds2    lda scrtop
        cmp #8
        bcc eds3
        lda #7
        sta scrtop
eds3    lda scrtop
        cmp tmp2
        beq eds4
        jsr redraw
eds4    rts

; ---- the live panel fields: cursor position, tile name, mode
edpanl  jsr drawlv
        lda curx
        ldx #114                ; row 2, columns 34-35
        jsr pdig
        lda cury
        ldx #154                ; row 3
        jsr pdig
        jsr pclr                ; row 5: the item label
        ldx #4
edpt    lda lbtile,x
        sta pbuf,x
        dex
        bpl edpt
        lda #4
        jsr pblit
        lda tidx                ; the selected tile, row 7
        jsr namptr              ; 57 names x 8 bytes is 456, past an index
        ldy #0                  ; register, so address them with a pointer
edp1    lda (srclo),y
        sta pbuf,y
        iny
        cpy #8
        bne edp1
        lda #5
        jsr pblit
        jsr undnam              ; what the cursor is standing on
        jsr pclr                ; row 10: is paint-as-you-move on?
        ldy #7
edp2    lda mode
        beq edp3
        lda lbdron,y
        jmp edp4
edp3    lda lbdraw,y
edp4    sta pbuf,y
        dey
        bpl edp2
        lda #13
        jmp pblit

; ---- srclo/srchi = tilen + A*8, as a 16-bit address
namptr  asl
        sta tmp
        lda #0
        rol
        sta tmp2
        asl tmp
        rol tmp2
        asl tmp
        rol tmp2
        lda #<tilen
        clc
        adc tmp
        sta srclo
        lda #>tilen
        adc tmp2
        sta srchi
        rts

; ---- name the cell under the cursor, on panel row 23
undnam  jsr cellpt
        ldx #0
        lda (mlo,x)
        sta tmp2
        beq undlk               ; floor is in the palette
        cmp #$10
        bcs undhi
        lda #$10                ; a linked wall mask: show it as a wall
        sta tmp2
        jmp undlk
undhi   lda tmp2
        bpl undlk               ; bit 7 clear: use the value as it is
        cmp #$92
        beq undlk
        lda #$90                ; any trap-linked wall
        sta tmp2
undlk   ldx #0
undsc   lda tilev,x
        cmp tmp2
        beq undfnd
        inx
        cpx #57
        bne undsc
        jsr pclr                ; not in the palette
        lda #$3f
        sta pbuf
        jmp undout
undfnd  txa
        jsr namptr
        jsr pclr
        ldy #0
undcp   lda (srclo),y
        sta pbuf,y
        iny
        cpy #8
        bne undcp
undout  lda #7
        jmp pblit

; ---- two decimal digits of A at screen offset X
pdig    stx tmp
        ldy #$ff
        sec
pdg1    iny
        sbc #10
        bcs pdg1
        adc #10
        sta tmp2
        tya
        clc
        adc #48
        ldx tmp
        ora #$80                ; the panel is reverse video
        sta $0400,x
        lda #pancol
        sta $d800,x
        inx
        lda tmp2
        clc
        adc #48
        ora #$80
        sta $0400,x
        lda #pancol
        sta $d800,x
        rts


tilev   byte $00,$10,$90,$33,$11,$12,$13,$14
        byte $15,$16,$17,$18,$19,$1a,$1b,$1c
        byte $1d,$1e,$1f,$20,$21,$22,$23,$24
        byte $25,$26,$27,$28,$29,$2a,$2b,$2c
        byte $2d,$2e,$2f,$30,$31,$36,$37,$38
        byte $3f,$40,$41,$42,$48,$49,$4a,$50
        byte $51,$52,$58,$59,$5a,$60,$61,$62
        byte $68
tilep   byte $00,$e0,$c0,$ff,$40,$80,$ff,$ff
        byte $ff,$ff,$ff,$ff,$ff,$ff,$ff,$ff
        byte $ff,$ff,$ff,$ff,$ff,$ff,$ff,$ff
        byte $ff,$ff,$ff,$ff,$ff,$ff,$ff,$ff
        byte $ff,$ff,$ff,$ff,$ff,$ff,$ff,$ff
        byte $ff,$ff,$ff,$ff,$ff,$ff,$ff,$ff
        byte $ff,$ff,$ff,$ff,$ff,$ff,$ff,$ff
        byte $ff
tilen   byte $05,$0d,$10,$14,$19,$20,$20,$20
        byte $17,$01,$0c,$0c,$20,$20,$20,$20
        byte $14,$12,$01,$10,$17,$01,$0c,$0c
        byte $04,$13,$14,$20,$17,$01,$0c,$0c
        byte $04,$0f,$0f,$12,$20,$16,$20,$20
        byte $04,$0f,$0f,$12,$20,$08,$20,$20
        byte $14,$12,$05,$01,$13,$15,$12,$05
        byte $03,$09,$04,$05,$12,$20,$20,$20
        byte $06,$0f,$0f,$04,$20,$20,$20,$20
        byte $0d,$01,$07,$09,$03,$20,$02,$20
        byte $0d,$01,$07,$09,$03,$20,$19,$20
        byte $01,$0d,$15,$0c,$05,$14,$20,$20
        byte $01,$12,$0d,$0f,$15,$12,$20,$20
        byte $03,$01,$12,$12,$19,$09,$0e,$07
        byte $05,$18,$20,$0d,$01,$07,$09,$03
        byte $13,$08,$0f,$14,$20,$10,$17,$12
        byte $13,$08,$0f,$14,$20,$13,$10,$04
        byte $06,$09,$07,$08,$14,$20,$20,$20
        byte $0b,$05,$19,$20,$20,$20,$20,$20
        byte $07,$05,$0e,$20,$01,$31,$20,$20
        byte $07,$05,$0e,$20,$01,$32,$20,$20
        byte $07,$05,$0e,$20,$01,$33,$20,$20
        byte $07,$05,$0e,$20,$02,$31,$20,$20
        byte $07,$05,$0e,$20,$02,$32,$20,$20
        byte $07,$05,$0e,$20,$02,$33,$20,$20
        byte $07,$05,$0e,$20,$03,$31,$20,$20
        byte $07,$05,$0e,$20,$03,$32,$20,$20
        byte $07,$05,$0e,$20,$03,$33,$20,$20
        byte $07,$05,$0e,$20,$04,$31,$20,$20
        byte $07,$05,$0e,$20,$04,$32,$20,$20
        byte $07,$05,$0e,$20,$04,$33,$20,$20
        byte $07,$05,$0e,$20,$05,$31,$20,$20
        byte $07,$05,$0e,$20,$05,$32,$20,$20
        byte $07,$05,$0e,$20,$05,$33,$20,$20
        byte $14,$12,$01,$10,$20,$20,$20,$20
        byte $14,$05,$0c,$05,$10,$0f,$12,$14
        byte $10,$0f,$09,$13,$0f,$0e,$20,$20
        byte $05,$18,$09,$14,$20,$20,$20,$20
        byte $05,$18,$09,$14,$20,$34,$20,$20
        byte $05,$18,$09,$14,$20,$38,$20,$20
        byte $13,$14,$01,$12,$14,$20,$20,$20
        byte $0d,$0f,$0e,$20,$01,$31,$20,$20
        byte $0d,$0f,$0e,$20,$01,$32,$20,$20
        byte $0d,$0f,$0e,$20,$01,$33,$20,$20
        byte $0d,$0f,$0e,$20,$02,$31,$20,$20
        byte $0d,$0f,$0e,$20,$02,$32,$20,$20
        byte $0d,$0f,$0e,$20,$02,$33,$20,$20
        byte $0d,$0f,$0e,$20,$03,$31,$20,$20
        byte $0d,$0f,$0e,$20,$03,$32,$20,$20
        byte $0d,$0f,$0e,$20,$03,$33,$20,$20
        byte $0d,$0f,$0e,$20,$04,$31,$20,$20
        byte $0d,$0f,$0e,$20,$04,$32,$20,$20
        byte $0d,$0f,$0e,$20,$04,$33,$20,$20
        byte $0d,$0f,$0e,$20,$05,$31,$20,$20
        byte $0d,$0f,$0e,$20,$05,$32,$20,$20
        byte $0d,$0f,$0e,$20,$05,$33,$20,$20
        byte $0d,$0f,$0e,$20,$06,$20,$20,$20


; ======================================================================
; panel - redraw the side panel, columns 32-39.
;
; Rows 2, 3, 6 and 8 carry live values the editor loop pokes directly
; (cursor digits, tile name, mode); this fills in everything else.
; ======================================================================
panel   jsr pclr                ; lay an orange bar down the whole strip
        lda #24
pnbar   pha
        jsr pblit
        pla
        sec
        sbc #1
        bpl pnbar
        jsr drawlv

        jsr pclr                ; row 2: the x label
        lda #24
        sta pbuf
        lda #2
        jsr pblit

        jsr pclr                ; row 3: the y label
        lda #25
        sta pbuf
        lda #3
        jsr pblit

        jsr pclr                ; row 12: trap count
        ldx #2
pnl12   lda lbtr,x
        sta pbuf,x
        dex
        bpl pnl12
        lda ntrap
        ldx #4                  ; right-align with the gfx and col digits
        jsr pnum2
        lda #15
        jsr pblit

        jsr pclr                ; row 13: trap-wall count
        ldx #2
pnl13   lda lbtw,x
        sta pbuf,x
        dex
        bpl pnl13
        lda nwall
        ldx #4
        jsr pnum2
        lda #16
        jsr pblit

        jsr pclr                ; row 21: the mismatch warning
        lda ntrap
        bne pnlw1
        lda nwall
        beq pnlw3               ; neither present: nothing to say
        ldx #7
pnlw0   lda lbnotr,x
        sta pbuf,x
        dex
        bpl pnlw0
        jmp pnlw3
pnlw1   lda nwall
        bne pnlw3               ; both present: fine
        ldx #7
pnlw2   lda lbnowa,x
        sta pbuf,x
        dex
        bpl pnlw2
pnlw3   lda #21
        jsr pblit

        jsr pclr                ; row 14: which wall graphic set
        ldx #3
pnlg    lda lbgfx,x
        sta pbuf,x
        dex
        bpl pnlg
        lda buf+1
        and #$38
        lsr
        lsr
        lsr
        clc
        adc #48
        sta pbuf+5
        lda #17
        jsr pblit

        jsr pclr                ; row 15: which wall colour
        ldx #3
pnlc    lda lbcol,x
        sta pbuf,x
        dex
        bpl pnlc
        lda buf+2
        and #$38
        lsr
        lsr
        lsr
        clc
        adc #48
        sta pbuf+5
        lda #18
        jsr pblit

        jsr pclr                ; row 16: the shots label
        ldx #5
pnl17   lda lbsh,x
        sta pbuf,x
        dex
        bpl pnl17
        lda #8
        jsr pblit

        jsr pclr                ; row 17: normal / stun / hurt
        lda buf+1
        and #$01
        bne pnlh
        lda buf+1
        and #$02
        bne pnls
        ldx #5
pnln1   lda lbnorm,x
        sta pbuf,x
        dex
        bpl pnln1
        jmp pnl18
pnls    ldx #3
pnls1   lda lbstun,x
        sta pbuf,x
        dex
        bpl pnls1
        jmp pnl18
pnlh    ldx #3
pnlh1   lda lbhurt,x
        sta pbuf,x
        dex
        bpl pnlh1
pnl18   lda #9
        jsr pblit

        jsr pclr                ; row 8: label for the cursor cell
        ldx #6
pnlu    lda lbund,x
        sta pbuf,x
        dex
        bpl pnlu
        lda #6
        jsr pblit

        jsr pnwarn
        jsr pnbyte
        jmp edpanl              ; the live fields too, so a fresh screen is
                                ; complete before the first key is pressed

; ---- rows 19 and 20: the two design warnings.  These read nstart and
;      nexit, which only count sets, so they have to be recounted after an
;      edit or the message stays up after the fault is fixed: placing an
;      exit left NO EXIT! on the screen until the next load or save.
pnwarn  jsr count
        jsr pclr                ; row 20: start-marker warning
        lda nstart
        cmp #1
        beq pnls9
        ldx #7
pnls8   lda lbnost,x
        sta pbuf,x
        dex
        bpl pnls8
pnls9   lda #20
        jsr pblit

        jsr pclr                ; row 19: no way out of the level
        lda nexit
        bne pnle9
        ldx #7
pnle8   lda lbnoex,x
        sta pbuf,x
        dex
        bpl pnle8
pnle9   lda #19
        jsr pblit
        rts

drawlv  jsr pclr                ; row 0: the level number
        ldx #3
pnl0    lda lblvl,x
        sta pbuf,x
        dex
        bpl pnl0
        lda lvlno
        ldx #4
        jsr pnum3
        lda #0
        jmp pblit

pclr    lda #32                 ; blank the row buffer
        ldx #7
pcl1    sta pbuf,x
        dex
        bpl pcl1
        rts

pblit   tax                     ; A = panel row; write pbuf to it
        lda scrlo,x
        clc
        adc #32
        sta dstlo
        sta collo
        lda scrhi,x
        adc #0
        sta dsthi
        clc
        adc #$d4
        sta colhi
        ldy #7
pbl1    lda pbuf,y
        ora #$80                ; the panel is reverse video throughout
        sta (dstlo),y
        lda #pancol
        sta (collo),y
        dey
        bpl pbl1
        rts

pnum2   stx tmp                 ; A as two digits at pbuf+X
        ldy #$ff
        sec
pn21    iny
        sbc #10
        bcs pn21
        adc #10
        sta tmp2
        ldx tmp
        tya
        clc
        adc #48
        sta pbuf,x
        inx
        lda tmp2
        clc
        adc #48
        sta pbuf,x
        rts

; ---- szlo/szhi as three digits at pbuf+0.  The record length is nine
;      bits, so pnum3 cannot print it: it subtracts hundreds from A alone
;      and stops at 255.
pnsz    ldy #0
pnz1    lda szlo
        sec
        sbc #100
        tax
        lda szhi
        sbc #0
        bcc pnz2
        stx szlo
        sta szhi
        iny
        jmp pnz1
pnz2    tya
        clc
        adc #48
        sta pbuf
        lda szlo
        ldx #1
        jsr pnum2
        rts

; ---- row 18: what the map would take to save.  Only an edit can change
;      it, so paint calls this rather than the whole panel: encoding costs
;      about 35,000 cycles, and doing that on every cursor step would drag.
pnbyte  jsr pclr                ; row 10: the label
        ldx #7
pnbl1   lda lbbyte,x
        sta pbuf,x
        dex
        bpl pnbl1
        lda #10
        jsr pblit
        jsr pclr
        jsr encode              ; safe to repeat: apvec rebuilds the vector
        lda ldst                ; section from veclen every time
        bne pnbx
        lda buf                 ; length is nine bits: low byte in buf,
        sta szlo                ; top bit in bit 7 of buf+2
        lda buf+2
        asl
        lda #0
        rol
        sta szhi
        jsr pnsz
        lda #47                 ; "/511"
        sta pbuf+3
        lda #53
        sta pbuf+4
        lda #49
        sta pbuf+5
        sta pbuf+6
        jmp pnb9
pnbx    ldx #7                  ; will not fit at all
pnb8    lda lbtoob,x
        sta pbuf,x
        dex
        bpl pnb8
pnb9    lda #11
        jsr pblit
        rts

pnum3   stx tmp                 ; A as three digits at pbuf+X
        ldy #$ff
        sec
pn31    iny
        sbc #100
        bcs pn31
        adc #100
        sta tmp2
        ldx tmp
        tya
        clc
        adc #48
        sta pbuf,x
        inc tmp
        lda tmp2
        ldx tmp
        jsr pnum2
        rts

; ======================================================================
; preview - show the map as a trap leaves it
; ======================================================================
preview lda #<grid
        sta srclo
        lda #>grid
        sta srchi
        ldx #0
pvw1    lda (srclo,x)
        cmp #$2f
        beq pvwc
        cmp #$92
        beq pvwn
        and #$80
        beq pvwn
pvwc    lda #0
        sta (srclo,x)
pvwn    inc srclo
        bne pvw2
        inc srchi
pvw2    lda srchi
        cmp #gridend
        bne pvw1
        jmp redraw


lblvl   byte $0c,$16,$0c,$20
lbtr    byte $14,$12,$20
lbtw    byte $14,$17,$20
lbnotr  byte $0e,$0f,$20,$14,$12,$01,$10,$21
lbnowa  byte $0e,$0f,$20,$17,$01,$0c,$0c,$13
lbsh    byte $13,$08,$0f,$14,$13,$3a
lbnorm  byte $0e,$0f,$12,$0d,$01,$0c
lbstun  byte $13,$14,$15,$0e
lbhurt  byte $08,$15,$12,$14
lbnum   byte $0c,$05,$16,$05,$0c,$3f
lbtile  byte $09,$14,$05,$0d,$3a
lbdraw  byte $04,$12,$01,$17,$20,$0f,$06,$06
lbdron  byte $04,$12,$01,$17,$20,$0f,$0e,$20
lbgfx   byte $07,$06,$18,$20
lbcol   byte $03,$0f,$0c,$20
lbund   byte $03,$15,$12,$13,$0f,$12,$3a
lbnost  byte $13,$14,$01,$12,$14,$13,$21,$20
lbbyte  byte $02,$19,$14,$05,$13,$3a,$20,$20
lbtoob  byte $14,$0f,$0f,$20,$02,$09,$07,$21
lbnoex  byte $0e,$0f,$20,$05,$18,$09,$14,$21


; ======================================================================
; Command handling.  Everything the editor does now lives here; BASIC
; sees control again only for the two text pages and to quit.
; ======================================================================

; ---- show an 8-character message on panel row 10, then pause
showmsg asl                     ; A = message index
        asl
        asl
        clc
        adc #<msgtab
        sta srclo
        lda #0
        adc #>msgtab
        sta srchi
        jsr pclr
        ldy #7
shm1    lda (srclo),y
        sta pbuf,y
        dey
        bpl shm1
        lda #22
        jmp pblit

msgoff  jsr pclr                ; wipe the message row
        lda #22
        jmp pblit

delay   ldx #$40
dly1    ldy #0
dly2    dey
        bne dly2
        dex
        bne dly1
        rts

; ---- confirm: A = prompt message index.  Carry set if the answer was y
confirm pha
        jsr pclr
        pla
        pha
        asl
        asl
        asl
        clc
        adc #<msgtab
        sta srclo
        lda #0
        adc #>msgtab
        sta srchi
        ldy #7
cnf1    lda (srclo),y
        sta pbuf,y
        dey
        bpl cnf1
        lda #22
        jsr pblit
        jsr pclr
        lda dirty
        beq cnf2
        ldx #7
cnf1a   lda lbunsv,x
        sta pbuf,x
        dex
        bpl cnf1a
cnf2    lda #23
        jsr pblit
        jsr pclr
        ldx #5
cnf3    lda lbyes,x
        sta pbuf,x
        dex
        bpl cnf3
        lda #24
        jsr pblit
cnf5    jsr $ffe4
        beq cnf5
        pha
        lda #0                  ; likewise for the y/n answer
        sta prevky
        pla
        cmp #$59                ; y
        beq cnfyes
        pla                     ; drop the saved prompt index
        jsr panel               ; redraw over the prompt
        clc                     ; no.  panel clobbers tmp and tmp2, so the
        rts                     ; answer must not be parked in either
cnfyes  pla
        jsr panel
        sec                     ; yes
        rts

; ---- read the drive error channel; clears the error light
errch   lda #0
        jsr $ffbd
        lda #15
        ldx dev
        ldy #15
        jsr $ffba
        jsr $ffc0
        bcs erc9
        ldx #15
        jsr $ffc6
        bcs erc8
        jsr $ffcf
        sec
        sbc #48
        sta errno
        jsr $ffcf
        sec
        sbc #48
        sta tmp
        lda errno
        asl
        sta tmp2
        asl
        asl
        clc
        adc tmp2
        clc
        adc tmp
        sta errno
erc1    jsr $ffb7
        bne erc2
        jsr $ffcf
        cmp #$0d
        bne erc1
erc2    jsr $ffcc
erc8    lda #15
        jmp $ffc3
erc9    lda #99
        sta errno
        rts

; ---- build "level nnn" in fnbuf from lvlno
mkfn    ldx #0
mkf1    lda lblev,x
        sta fnbuf,x
        inx
        cpx #6
        bne mkf1
        lda lvlno
        ldy #$ff
        sec
mkf2    iny
        sbc #100
        bcs mkf2
        adc #100
        sta tmp
        tya
        clc
        adc #48
        sta fnbuf+6
        lda tmp
        ldy #$ff
        sec
mkf3    iny
        sbc #10
        bcs mkf3
        adc #10
        clc
        adc #48
        sta fnbuf+8
        tya
        clc
        adc #48
        sta fnbuf+7
        lda #9
        sta fnlen
        rts

; ---- load the level named by lvlno; a blank one if it is not there
doload  jsr mkfn
        jsr loadlev
        lda ldst
        beq dld1
        jsr errch               ; no such file: clear the drive and start blank
        jsr newlvl
        jmp dld2
dld1    jsr decode
dld2    lda #0
        sta dirty
        sta scrtop
        lda #0
        sta curx
        sta cury
        jsr clrwe
        jsr count
        jsr redraw
        jmp panel

; ---- encode, verify by re-decoding, and only then write
dosave  jsr cksum
        lda cklo
        sta svk1
        lda ckhi
        sta svk2
        jsr encode
        lda ldst
        beq dsv1
        lda #2                  ; too big
        jmp dsvend
dsv1    jsr decode
        jsr cksum
        lda cklo
        cmp svk1
        bne dsvbad
        lda ckhi
        cmp svk2
        beq dsv2
dsvbad  jsr doload              ; cannot represent it: reload and say so
        lda #3
        jmp dsvend
dsv2    jsr mkfn
        jsr savelev
        lda ldst
        bne dsvwr
        jsr errch
        lda errno
        bne dsvwr
        lda #0
        sta dirty
        lda #0                  ; saved
        jmp dsvend
dsvwr   lda #1                  ; write error
        sta dirty
dsvend  pha                     ; panel first, or it would wipe the message -
        jsr panel               ; but it clobbers A, which is the message
        pla                     ; index, so hold on to it across the call
        jmp showmsg             ; the message stays up until the next key

; ---- preview, without losing anything
dotrap  jsr encode
        lda ldst
        beq dtr1
        lda #2
        jsr showmsg
        jsr delay
        jmp msgoff
dtr1    jsr clrwe
        jsr decode
        jsr preview
        lda #7                  ; fired
        jsr showmsg
dtr2    jsr $ffe4
        beq dtr2
        lda #0                  ; the dismiss key was eaten here, so the
        sta prevky              ; guard must not see it as the last key
        jsr decode
        jsr redraw
        jsr msgoff
        jmp panel

; ---- cycle the three flag fields
docyc   lda buf+1               ; shots: normal, stun, hurt
        and #$01
        bne dcy0
        lda buf+1
        and #$02
        bne dcy1
        lda buf+1
        and #$fc
        ora #$02
        jmp dcy9
dcy1    lda buf+1
        and #$fc
        ora #$01
        jmp dcy9
dcy0    lda buf+1
        and #$fc
dcy9    sta buf+1
        jmp panel

; The table at $8C80 has eight slots but only three distinct entries: 1 and
; 3 point at the same graphics, 2 and 4 at another, and 5, 6 and 7 point at
; addresses that are not graphics at all - $DC04 is a CIA register.  Only
; 0-2 are offered, so every press of g actually changes something and none
; of them draws rubbish.
dogfx   lda buf+1               ; wall graphic set: 0, 1, 2
        and #$38
        clc
        adc #8
        cmp #$18
        bcc dgf1
        lda #0
dgf1    sta tmp
        lda buf+1
        and #$c7
        ora tmp
        sta buf+1
        lda #1
        sta dirty
        jmp panel

; Colour 7 in the table at $8C78 repeats colour 0, so it is skipped and the
; cycle runs 0-6.
docol   lda buf+2               ; wall colour: 0 to 6
        and #$38
        clc
        adc #8
        cmp #$38
        bcc dcl1
        lda #0
dcl1    sta tmp
        lda buf+2
        and #$c7
        ora tmp
        sta buf+2
        lda #1
        sta dirty
        jmp panel

donew   lda #5                  ; new lvl?
        jsr confirm
        bcc dnw9
        jsr clrwe
        jsr newlvl
        lda #0
        sta dirty
        jsr count
        jsr redraw
        jmp panel
dnw9    rts


msgtab  byte $13,$01,$16,$05,$04,$20,$20,$20
        byte $17,$12,$20,$05,$12,$12,$20,$20
        byte $14,$0f,$0f,$20,$02,$09,$07,$20
        byte $03,$01,$0e,$14,$20,$13,$01,$16
        byte $0c,$0f,$01,$04,$20,$05,$12,$12
        byte $0e,$05,$17,$20,$0c,$16,$0c,$3f
        byte $11,$15,$09,$14,$3f,$20,$20,$20
        byte $06,$09,$12,$05,$04,$20,$20,$20
        byte $20,$20,$20,$20,$20,$20,$20,$20
lbunsv  byte $15,$0e,$13,$01,$16,$05,$04,$21
lbyes   byte $19,$20,$0f,$12,$20,$0e
; PETSCII, not screen codes: this goes to the drive, not the screen
lblev   byte $4c,$45,$56,$45,$4c,$20


; ======================================================================
; main - the whole program, so BASIC is only a SYS
;
; Shows the two help pages, loads a level, then runs the editor.  The
; only keys that reach here are ? for the pages again and q to leave.
; ======================================================================
CHROUT  = $ffd2
GETIN   = $ffe4

main    lda $ba                 ; last device used, or 8
        cmp #8
        bcs mn1
        lda #8
mn1     cmp #31
        bcc mn2
        lda #8
mn2     sta dev

        lda #255                ; held-key speed, out of 256.  A cursor step
        sta rptrat              ; costs about 3 ms and the KERNAL leaves 80
                                ; between repeats, so throttling below the
                                ; full rate only made the cursor sluggish

        lda #15                 ; light grey screen and border, black ink
        sta $d020
        sta $d021
        lda #0
        sta $0286
        lda #$80                ; let the KERNAL repeat every key
        sta $028a
        lda #142                ; uppercase and graphics: the map glyphs
        jsr CHROUT              ; are all in that set
        lda #128                ; and lock it, so shift+commodore cannot
        sta $0291               ; swap the charset under us

        jsr pages               ; both help screens
        jsr doload              ; level 1, drawn, panel filled

mloop   jsr edloop              ; the m/l handles everything but ? and q
        lda lastky
        cmp #$3f                ; ?
        bne mq
        jsr helpsc
        lda #147                ; the pages scribbled over the map
        jsr CHROUT
        jsr redraw
        jsr panel
        jmp mloop

mq      cmp #$51                ; q
        bne mloop
        lda #0                  ; hand the keyboard back as we found it
        sta $028a
        lda #147
        jsr CHROUT
        lda #6
        sta $d021
        lda #14
        sta $d020
        sta $0286
        rts                     ; back to the SYS, or to the boot menu

; ---- both help pages, a keypress between them
helpsc  lda #<helptab           ; ? starts at the instructions: the title
        sta srclo               ; page is only worth seeing on the way in
        lda #>helptab
        sta srchi
        jsr pgskip
        jmp pgloop

pages   lda #<helptab
        sta srclo
        lda #>helptab
        sta srchi
pgloop  ldy #0                  ; a zero-length page ends the table, so
        lda (srclo),y           ; adding a screen needs no code change
        beq pg9
        jsr onepg
        jsr waitky
        jmp pgloop
pg9     rts

; ---- print rows until a zero length; leaves srclo/srchi past the page
onepg   lda #147
        jsr CHROUT
opg1    ldy #0
        lda (srclo),y
        beq opg9
        sta tmp
        jsr bump
        ldy #0
opg2    lda (srclo),y
        jsr CHROUT
        iny
        cpy tmp
        bne opg2
        tya
        clc
        adc srclo
        sta srclo
        bcc opg1
        inc srchi
        jmp opg1
opg9    jmp bump

; ---- step srclo past one whole page without printing it
pgskip  ldy #0
psk1    lda (srclo),y
        beq psk9
        sta tmp
        inc tmp                 ; the length byte as well as the row
        lda srclo
        clc
        adc tmp
        sta srclo
        bcc psk1
        inc srchi
        jmp psk1
psk9    jmp bump                ; and past the page terminator

bump    inc srclo
        bne bmp9
        inc srchi
bmp9    rts

waitky  jsr GETIN
        beq waitky
        lda #0                  ; this key was eaten here, so the repeat
        sta prevky              ; guard must not still be holding it
        rts

helptab byte $28,$20,$20,$12,$2a,$2a,$2a,$2a
        byte $20,$47,$41,$55,$4e,$54,$4c,$45
        byte $54,$20,$43,$4f,$4e,$53,$54,$52
        byte $55,$43,$54,$49,$4f,$4e,$20,$4b
        byte $49,$54,$20,$2a,$2a,$2a,$2a,$92
        byte $0d,$01,$0d,$20,$20,$59,$4f,$55
        byte $20,$4e,$45,$45,$44,$20,$41,$20
        byte $47,$41,$55,$4e,$54,$4c,$45,$54
        byte $20,$4f,$52,$20,$27,$44,$45,$45
        byte $50,$45,$52,$0d,$27,$20,$44,$55
        byte $4e,$47,$45,$4f,$4e,$53,$27,$20
        byte $47,$41,$4d,$45,$20,$44,$49,$53
        byte $4b,$20,$54,$48,$41,$54,$20,$53
        byte $55,$50,$50,$4f,$52,$54,$53,$20
        byte $31,$32,$38,$0d,$25,$20,$53,$45
        byte $50,$41,$52,$41,$54,$45,$20,$4c
        byte $45,$56,$45,$4c,$20,$46,$49,$4c
        byte $45,$53,$2e,$20,$20,$54,$48,$49
        byte $53,$20,$50,$52,$4f,$47,$52,$41
        byte $4d,$0d,$24,$20,$4c,$45,$54,$53
        byte $20,$59,$4f,$55,$20,$45,$44,$49
        byte $54,$20,$41,$4c,$4c,$20,$31,$32
        byte $38,$20,$4c,$45,$56,$45,$4c,$20
        byte $46,$49,$4c,$45,$53,$2e,$0d,$01
        byte $0d,$26,$20,$59,$4f,$55,$20,$43
        byte $41,$4e,$20,$4b,$45,$45,$50,$20
        byte $41,$20,$53,$45,$50,$41,$52,$41
        byte $54,$45,$20,$44,$49,$53,$4b,$20
        byte $4f,$46,$20,$59,$4f,$55,$52,$0d
        byte $27,$20,$4c,$45,$56,$45,$4c,$20
        byte $46,$49,$4c,$45,$53,$2e,$20,$20
        byte $4c,$4f,$41,$44,$20,$54,$48,$45
        byte $20,$47,$41,$4d,$45,$20,$46,$52
        byte $4f,$4d,$20,$59,$4f,$55,$52,$0d
        byte $25,$20,$47,$41,$4d,$45,$20,$44
        byte $49,$53,$4b,$2c,$20,$53,$45,$4c
        byte $45,$43,$54,$20,$50,$4c,$41,$59
        byte $45,$52,$20,$43,$48,$41,$52,$41
        byte $43,$54,$45,$52,$53,$0d,$22,$20
        byte $41,$4e,$44,$20,$4c,$45,$54,$20
        byte $54,$48,$45,$20,$47,$41,$4d,$45
        byte $20,$46,$49,$4e,$49,$53,$48,$20
        byte $4c,$4f,$41,$44,$49,$4e,$47,$2e
        byte $0d,$23,$20,$57,$48,$45,$4e,$20
        byte $45,$49,$54,$48,$45,$52,$20,$50
        byte $4c,$41,$59,$45,$52,$20,$49,$53
        byte $20,$50,$52,$4f,$4d,$50,$54,$45
        byte $44,$20,$54,$4f,$0d,$24,$20,$50
        byte $52,$45,$53,$53,$20,$46,$49,$52
        byte $45,$20,$54,$4f,$20,$53,$54,$41
        byte $52,$54,$20,$54,$48,$45,$20,$47
        byte $41,$4d,$45,$2c,$20,$53,$57,$41
        byte $50,$0d,$23,$20,$4f,$55,$54,$20
        byte $54,$48,$45,$20,$47,$41,$4d,$45
        byte $20,$44,$49,$53,$4b,$20,$41,$4e
        byte $44,$20,$49,$4e,$53,$45,$52,$54
        byte $20,$59,$4f,$55,$52,$0d,$27,$20
        byte $4c,$45,$56,$45,$4c,$20,$44,$49
        byte $53,$4b,$2e,$20,$20,$54,$48,$45
        byte $4e,$20,$50,$52,$45,$53,$53,$20
        byte $46,$49,$52,$45,$20,$54,$4f,$20
        byte $50,$4c,$41,$59,$2e,$0d,$01,$0d
        byte $23,$20,$54,$48,$45,$20,$47,$41
        byte $4d,$45,$20,$52,$45,$41,$44,$53
        byte $20,$41,$20,$4c,$45,$56,$45,$4c
        byte $20,$46,$49,$4c,$45,$20,$45,$56
        byte $45,$52,$59,$0d,$23,$20,$54,$49
        byte $4d,$45,$20,$49,$54,$20,$43,$48
        byte $41,$4e,$47,$45,$53,$20,$4c,$45
        byte $56,$45,$4c,$2c,$20,$53,$4f,$20
        byte $41,$4e,$20,$45,$44,$49,$54,$0d
        byte $27,$20,$54,$41,$4b,$45,$53,$20
        byte $45,$46,$46,$45,$43,$54,$20,$54
        byte $48,$45,$20,$4e,$45,$58,$54,$20
        byte $54,$49,$4d,$45,$20,$54,$48,$41
        byte $54,$20,$4c,$45,$56,$45,$4c,$0d
        byte $0b,$20,$43,$4f,$4d,$45,$53,$20
        byte $55,$50,$2e,$0d,$01,$0d,$26,$20
        byte $20,$20,$12,$20,$50,$52,$45,$53
        byte $53,$20,$41,$4e,$59,$20,$4b,$45
        byte $59,$20,$46,$4f,$52,$20,$54,$48
        byte $45,$20,$4e,$45,$58,$54,$20,$50
        byte $41,$47,$45,$20,$92,$00,$20,$20
        byte $20,$20,$20,$20,$20,$20,$20,$20
        byte $20,$20,$12,$20,$2a,$20,$49,$4e
        byte $53,$54,$52,$55,$43,$54,$49,$4f
        byte $4e,$53,$20,$2a,$20,$92,$0d,$07
        byte $12,$4b,$45,$59,$53,$92,$0d,$27
        byte $43,$52,$53,$52,$20,$4d,$4f,$56
        byte $45,$20,$43,$55,$52,$53,$4f,$52
        byte $20,$20,$20,$20,$20,$44,$45,$4c
        byte $20,$20,$20,$20,$45,$52,$41,$53
        byte $45,$20,$54,$49,$4c,$45,$0d,$28
        byte $53,$50,$43,$20,$20,$50,$4c,$41
        byte $43,$45,$20,$49,$54,$45,$4d,$20
        byte $20,$20,$20,$20,$20,$43,$20,$20
        byte $20,$20,$20,$20,$43,$4c,$45,$41
        byte $52,$20,$4c,$45,$56,$45,$4c,$0d
        byte $27,$2c,$2e,$20,$20,$20,$50,$52
        byte $45,$56,$2f,$4e,$45,$58,$54,$20
        byte $49,$54,$45,$4d,$20,$20,$4c,$20
        byte $20,$20,$20,$20,$20,$4c,$4f,$41
        byte $44,$20,$4c,$45,$56,$45,$4c,$0d
        byte $27,$4d,$20,$20,$20,$20,$44,$52
        byte $41,$57,$20,$4d,$4f,$44,$45,$20
        byte $20,$20,$20,$20,$20,$20,$53,$20
        byte $20,$20,$20,$20,$20,$53,$41,$56
        byte $45,$20,$4c,$45,$56,$45,$4c,$0d
        byte $28,$47,$20,$20,$20,$20,$57,$41
        byte $4c,$4c,$20,$47,$46,$58,$20,$53
        byte $45,$54,$20,$20,$20,$20,$4b,$20
        byte $20,$20,$20,$20,$20,$57,$41,$4c
        byte $4c,$20,$43,$4f,$4c,$4f,$55,$52
        byte $0d,$21,$54,$20,$20,$20,$20,$54
        byte $52,$41,$50,$20,$50,$52,$45,$56
        byte $49,$45,$57,$20,$20,$20,$20,$51
        byte $20,$20,$20,$20,$20,$20,$51,$55
        byte $49,$54,$0d,$28,$46,$20,$20,$20
        byte $20,$53,$48,$4f,$54,$53,$20,$4d
        byte $4f,$44,$45,$20,$20,$20,$20,$20
        byte $20,$3f,$20,$20,$20,$20,$20,$20
        byte $54,$48,$49,$53,$20,$53,$43,$52
        byte $45,$45,$4e,$0d,$27,$2b,$2d,$20
        byte $20,$20,$4c,$45,$56,$45,$4c,$20
        byte $2b,$2d,$31,$20,$20,$20,$20,$20
        byte $20,$20,$53,$48,$46,$54,$2b,$2d
        byte $20,$4c,$45,$56,$45,$4c,$20,$2b
        byte $2d,$31,$30,$0d,$01,$0d,$24,$12
        byte $50,$41,$4e,$45,$4c,$92,$20,$20
        byte $20,$20,$58,$20,$26,$20,$59,$20
        byte $3d,$20,$54,$48,$45,$20,$4d,$41
        byte $50,$20,$49,$53,$20,$33,$32,$58
        byte $33,$32,$0d,$1f,$20,$20,$20,$20
        byte $20,$20,$20,$20,$20,$20,$49,$54
        byte $45,$4d,$20,$3d,$20,$53,$45,$4c
        byte $45,$43,$54,$45,$44,$20,$49,$54
        byte $45,$4d,$0d,$23,$20,$20,$20,$20
        byte $20,$20,$20,$20,$43,$55,$52,$53
        byte $4f,$52,$20,$3d,$20,$49,$54,$45
        byte $4d,$20,$55,$4e,$44,$45,$52,$20
        byte $43,$55,$52,$53,$4f,$52,$0d,$22
        byte $20,$20,$20,$20,$20,$20,$20,$20
        byte $20,$53,$48,$4f,$54,$53,$20,$3d
        byte $20,$4e,$4f,$52,$4d,$41,$4c,$2f
        byte $53,$54,$55,$4e,$2f,$48,$55,$52
        byte $54,$0d,$20,$20,$20,$20,$20,$20
        byte $20,$20,$20,$20,$42,$59,$54,$45
        byte $53,$20,$3d,$20,$35,$31,$31,$20
        byte $42,$59,$54,$45,$53,$20,$46,$52
        byte $45,$45,$0d,$24,$20,$20,$20,$20
        byte $20,$20,$20,$20,$20,$20,$44,$52
        byte $41,$57,$20,$3d,$20,$44,$52,$41
        byte $57,$20,$4d,$4f,$44,$45,$20,$28
        byte $4f,$4e,$2f,$4f,$46,$46,$29,$0d
        byte $24,$20,$20,$20,$20,$20,$20,$20
        byte $54,$52,$20,$26,$20,$54,$57,$20
        byte $3d,$20,$54,$52,$41,$50,$53,$20
        byte $26,$20,$54,$52,$41,$50,$20,$57
        byte $41,$4c,$4c,$53,$0d,$27,$20,$20
        byte $20,$20,$20,$47,$46,$58,$20,$26
        byte $20,$43,$4f,$4c,$20,$3d,$20,$57
        byte $41,$4c,$4c,$20,$47,$46,$58,$20
        byte $30,$2d,$32,$2c,$20,$43,$4f,$4c
        byte $20,$30,$2d,$36,$0d,$01,$0d,$26
        byte $20,$20,$54,$52,$41,$50,$53,$20
        byte $43,$4c,$45,$41,$52,$20,$45,$56
        byte $45,$52,$59,$20,$54,$52,$41,$50
        byte $57,$41,$4c,$4c,$20,$41,$54,$20
        byte $4f,$4e,$43,$45,$2e,$0d,$28,$20
        byte $4c,$45,$56,$45,$4c,$53,$20,$31
        byte $31,$38,$2d,$31,$32,$38,$20,$41
        byte $52,$45,$20,$54,$48,$45,$20,$54
        byte $52,$45,$41,$53,$55,$52,$45,$20
        byte $52,$4f,$4f,$4d,$53,$2e,$0d,$01
        byte $0d,$26,$20,$20,$20,$12,$20,$50
        byte $52,$45,$53,$53,$20,$41,$4e,$59
        byte $20,$4b,$45,$59,$20,$46,$4f,$52
        byte $20,$54,$48,$45,$20,$4e,$45,$58
        byte $54,$20,$50,$41,$47,$45,$20,$92
        byte $00,$1f,$20,$20,$20,$20,$20,$20
        byte $20,$20,$20,$20,$20,$20,$12,$20
        byte $2a,$20,$4d,$41,$50,$20,$4c,$45
        byte $47,$45,$4e,$44,$20,$2a,$20,$92
        byte $0d,$01,$0d,$0a,$12,$54,$45,$52
        byte $52,$41,$49,$4e,$92,$0d,$23,$20
        byte $20,$98,$2e,$90,$20,$20,$45,$4d
        byte $50,$54,$59,$20,$20,$20,$20,$20
        byte $20,$20,$20,$20,$20,$20,$98,$12
        byte $20,$92,$90,$20,$20,$57,$41,$4c
        byte $4c,$0d,$28,$20,$20,$1f,$e6,$90
        byte $20,$20,$54,$52,$41,$50,$57,$41
        byte $4c,$4c,$20,$20,$20,$20,$20,$20
        byte $20,$20,$98,$12,$e6,$92,$90,$20
        byte $20,$42,$52,$45,$41,$4b,$41,$42
        byte $4c,$45,$0d,$27,$20,$20,$9f,$dd
        byte $c0,$90,$20,$44,$4f,$4f,$52,$53
        byte $20,$56,$2f,$48,$20,$20,$20,$20
        byte $20,$20,$20,$1c,$db,$90,$20,$20
        byte $54,$45,$4c,$45,$50,$4f,$52,$54
        byte $45,$52,$0d,$23,$20,$20,$1e,$2a
        byte $90,$20,$20,$53,$54,$41,$52,$54
        byte $20,$20,$20,$20,$20,$20,$20,$20
        byte $20,$20,$20,$90,$12,$58,$92,$90
        byte $20,$20,$45,$58,$49,$54,$0d,$01
        byte $0d,$0a,$12,$50,$49,$43,$4b,$55
        byte $50,$53,$92,$0d,$20,$20,$20,$81
        byte $24,$90,$20,$20,$54,$52,$45,$41
        byte $53,$55,$52,$45,$20,$20,$20,$20
        byte $20,$20,$20,$20,$95,$de,$90,$20
        byte $20,$4b,$45,$59,$0d,$23,$20,$20
        byte $9e,$d1,$90,$20,$20,$43,$49,$44
        byte $45,$52,$20,$20,$20,$20,$20,$20
        byte $20,$20,$20,$20,$20,$9e,$d7,$90
        byte $20,$20,$50,$4f,$49,$53,$4f,$4e
        byte $0d,$21,$20,$20,$1c,$d3,$90,$20
        byte $20,$46,$4f,$4f,$44,$20,$20,$20
        byte $20,$20,$20,$20,$20,$20,$20,$20
        byte $20,$1f,$40,$90,$20,$20,$54,$52
        byte $41,$50,$0d,$28,$20,$20,$1f,$d8
        byte $90,$20,$20,$4d,$41,$47,$49,$43
        byte $20,$28,$42,$4c,$55,$45,$29,$20
        byte $20,$20,$20,$9e,$d8,$90,$20,$20
        byte $4d,$41,$47,$49,$43,$20,$28,$59
        byte $45,$4c,$29,$0d,$23,$20,$20,$9a
        byte $c1,$90,$20,$20,$50,$4f,$54,$49
        byte $4f,$4e,$20,$20,$20,$20,$20,$20
        byte $20,$20,$20,$20,$96,$5c,$90,$20
        byte $20,$41,$4d,$55,$4c,$45,$54,$0d
        byte $1e,$20,$20,$20,$20,$20,$41,$52
        byte $4d,$4f,$55,$52,$2c,$20,$43,$41
        byte $52,$52,$59,$49,$4e,$47,$2c,$20
        byte $4d,$41,$47,$49,$43,$2c,$0d,$23
        byte $20,$20,$20,$20,$20,$53,$48,$4f
        byte $54,$20,$50,$4f,$57,$45,$52,$2c
        byte $20,$53,$48,$4f,$54,$20,$53,$50
        byte $45,$45,$44,$2c,$20,$46,$49,$47
        byte $48,$54,$0d,$01,$0d,$0b,$12,$4d
        byte $4f,$4e,$53,$54,$45,$52,$53,$92
        byte $0d,$26,$20,$20,$9c,$41,$90,$20
        byte $47,$48,$4f,$53,$54,$20,$20,$20
        byte $20,$9c,$42,$90,$20,$47,$52,$55
        byte $4e,$54,$20,$20,$20,$20,$9c,$43
        byte $90,$20,$44,$45,$4d,$4f,$4e,$0d
        byte $26,$20,$20,$9c,$44,$90,$20,$4c
        byte $4f,$42,$42,$45,$52,$20,$20,$20
        byte $9c,$45,$90,$20,$53,$4f,$52,$43
        byte $45,$52,$45,$52,$20,$9c,$46,$90
        byte $20,$44,$45,$41,$54,$48,$0d,$26
        byte $20,$20,$20,$20,$49,$4e,$56,$45
        byte $52,$53,$45,$44,$20,$9c,$12,$41
        byte $2d,$45,$92,$90,$20,$49,$53,$20
        byte $49,$54,$53,$20,$47,$45,$4e,$45
        byte $52,$41,$54,$4f,$52,$0d,$01,$0d
        byte $23,$20,$20,$20,$20,$20,$20,$20
        byte $20,$20,$12,$20,$50,$52,$45,$53
        byte $53,$20,$41,$4e,$59,$20,$4b,$45
        byte $59,$20,$54,$4f,$20,$53,$54,$41
        byte $52,$54,$20,$92,$00,$00

; ----------------------------------------------------------------------
; newlvl - build the smallest valid level and decode it.
;
; Rather than construct the grid by hand, write a minimal record and run
; the normal decoder over it, so a blank level is built by exactly the
; same path as a loaded one.  The record is:
;
;   06 00 00 00 | a0 3f
;   |  |  |  |    |  +-- object $3f: the player start
;   |  |  |  |    +----- skip 33 cells, so the start lands at (1,1)
;   |  |  |  +---------- vector section is empty
;   |  |  +------------- flags2
;   |  +---------------- flags1: borders on, no wrap
;   +------------------- total length
;
; The object section is deliberately not empty: the game's loader would
; underflow its byte counter and flood the map.
; ----------------------------------------------------------------------
newlvl  lda #6
        sta buf
        lda #0
        sta buf+1
        sta buf+2
        sta buf+3
        lda #$a0
        sta buf+4
        lda #$3f
        sta buf+5
        jmp decode

; clear the wall-edit list (called when a level is loaded)
clrwe   lda #0
        sta welen
        rts

; ======================================================================
; savelev - scratch then save buf to disk under the name in fnbuf
; ======================================================================
savelev jsr mkname              ; build "s0:name" and "name,p,w"
        lda fnlen
        clc
        adc #3
        ldx #<scrbuf
        ldy #>scrbuf
        jsr $ffbd
        lda #$0f
        ldx dev
        ldy #$0f
        jsr $ffba
        jsr $ffc0               ; open 15,8,15,"s0:name"  - scratch old copy
        lda #$0f
        jsr $ffc3

        lda fnlen
        clc
        adc #4                  ; ",p,w" is four characters, not five
        ldx #<wnam
        ldy #>wnam
        jsr $ffbd
        lda #2
        ldx dev
        ldy #2
        jsr $ffba
        jsr $ffc0               ; open 2,8,2,"name,p,w"
        bcs saverr
        ldx #2
        jsr $ffc9               ; chkout 2
        bcs saverr
        lda #$00                ; PRG load address $0a00, low then high
        jsr $ffd2
        lda #$0a
        jsr $ffd2
        lda buf+2               ; end = buf + total, and total is 9 bits:
        asl                     ; bit 8 lives in bit 7 of flags2, so a record
        lda #0                  ; over 255 bytes must not be cut short
        rol
        sta tmp
        lda #<buf
        clc
        adc buf
        sta endlo
        lda #>buf
        adc tmp
        sta endhi
        lda #<buf
        sta mlo
        lda #>buf
        sta mhi
savlp   lda mlo
        cmp endlo
        bne savgo
        lda mhi
        cmp endhi
        beq savdon
savgo   ldx #0
        lda (mlo,x)
        jsr $ffd2
        inc mlo
        bne savlp
        inc mhi
        lda mhi                 ; guard against a corrupt length
        cmp #bufcap
        bne savlp
savdon  jsr $ffcc               ; clrchn
        lda #2
        jsr $ffc3               ; close 2
        lda #0
        sta ldst
        rts
saverr  jsr $ffcc
        lda #2
        jsr $ffc3
        lda #1
        sta ldst
        rts

; copy fnbuf into the scratch and write filenames
mkname  ldx #0
mkn1    lda fnbuf,x
        sta scrnam,x
        sta wnam,x
        inx
        cpx fnlen
        bne mkn1
        ldy #0
mkn2    lda wsuf,y              ; append ",p,w"
        sta wnam,x
        inx
        iny
        cpy #5
        bne mkn2
        rts

scrbuf  text "s0:"
scrnam  byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
wnam    byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
wsuf    text ",p,w"

; ======================================================================
; redraw - paint the 32 x 25 viewport
; ======================================================================
redraw  lda scrtop
        asl
        asl
        asl
        asl
        asl
        sta srclo
        lda #>grid
        sta srchi
        lda #0
        sta rowno
rrow    ldx rowno
        lda scrlo,x
        sta dstlo
        sta collo
        lda scrhi,x
        sta dsthi
        clc
        adc #$d4
        sta colhi
        ldy #31
rcol    lda (srclo),y
        tax
        lda chtab,x
        sta (dstlo),y
        lda coltab,x
        sta (collo),y
        dey
        bpl rcol
        lda srclo
        clc
        adc #32
        sta srclo
        bcc rnc
        inc srchi
rnc     inc rowno
        lda rowno
        cmp #25
        bne rrow
        rts

; ======================================================================
; loadlev - kernal load of fnbuf into buf
; ======================================================================
loadlev lda fnlen
        ldx #<fnbuf
        ldy #>fnbuf
        jsr $ffbd               ; setnam
        lda #2
        ldx dev
        ldy #0                  ; secondary 0: load to our address
        jsr $ffba               ; setlfs
        lda #0
        ldx #<buf
        ldy #>buf
        jsr $ffd5               ; load
        lda #0
        rol                     ; carry -> bit 0
        sta ldst
        rts

; ======================================================================
; tables
; ======================================================================
; $92 marks an exit the VECTOR layer drew: outside the object range,
; so the encoder will not emit it twice.  The game itself sees $36.
pentil  byte $00,$92,$11,$00,$12,$00,$90,$10
wallre  byte $40,$80,$40,$80
; interleaved lo,hi pairs - indexed by heading*2, exactly as the game's $c7f9
dirvec  byte $e0,$ff,$e1,$ff,$01,$00,$21,$00
        byte $20,$00,$1f,$00,$ff,$0f,$df,$ff

rowlo   byte $00,$20,$40,$60,$80,$a0,$c0,$e0
        byte $00,$20,$40,$60,$80,$a0,$c0,$e0
        byte $00,$20,$40,$60,$80,$a0,$c0,$e0
        byte $00,$20,$40,$60,$80,$a0,$c0,$e0
rowhi   byte $98,$98,$98,$98,$98,$98,$98,$98
        byte $99,$99,$99,$99,$99,$99,$99,$99
        byte $9a,$9a,$9a,$9a,$9a,$9a,$9a,$9a
        byte $9b,$9b,$9b,$9b,$9b,$9b,$9b,$9b

scrlo   byte $00,$28,$50,$78,$a0,$c8,$f0,$18
        byte $40,$68,$90,$b8,$e0,$08,$30,$58
        byte $80,$a8,$d0,$f8,$20,$48,$70,$98
        byte $c0
scrhi   byte $04,$04,$04,$04,$04,$04,$04,$05
        byte $05,$05,$05,$05,$05,$06,$06,$06
        byte $06,$06,$06,$06,$07,$07,$07,$07
        byte $07

chtab   byte $2e,$a0,$a0,$a0,$a0,$a0,$a0,$a0
        byte $a0,$a0,$a0,$a0,$a0,$a0,$a0,$a0
        byte $a0,$5d,$40,$24,$51,$53,$58,$58
        byte $1c,$41,$41,$41,$41,$41,$41,$5e
        byte $81,$81,$81,$82,$82,$82,$83,$83
        byte $83,$84,$84,$84,$85,$85,$85,$00
        byte $5b,$57,$3f,$e6,$3f,$3f,$98,$98
        byte $98,$3f,$3f,$3f,$3f,$3f,$3f,$2a
        byte $01,$01,$01,$01,$01,$01,$01,$01
        byte $02,$02,$02,$02,$02,$02,$02,$02
        byte $03,$03,$03,$03,$03,$03,$03,$03
        byte $04,$04,$04,$04,$04,$04,$04,$04
        byte $05,$05,$05,$05,$05,$05,$05,$05
        byte $06,$06,$06,$06,$06,$06,$06,$06
        byte $07,$07,$07,$07,$07,$07,$07,$07
        byte $08,$08,$08,$08,$08,$08,$08,$08
        byte $66,$66,$66,$66,$66,$66,$66,$66
        byte $66,$66,$66,$66,$66,$66,$66,$66
        byte $66,$66,$98,$66,$66,$66,$66,$66
        byte $66,$66,$66,$66,$66,$66,$66,$66
        byte $66,$66,$66,$66,$66,$66,$66,$66
        byte $66,$66,$66,$66,$66,$66,$66,$66
        byte $66,$66,$66,$66,$66,$66,$66,$66
        byte $66,$66,$66,$66,$66,$66,$66,$66
        byte $66,$66,$66,$66,$66,$66,$66,$66
        byte $66,$66,$66,$66,$66,$66,$66,$66
        byte $66,$66,$66,$66,$66,$66,$66,$66
        byte $66,$66,$66,$66,$66,$66,$66,$66
        byte $66,$66,$66,$66,$66,$66,$66,$66
        byte $66,$66,$66,$66,$66,$66,$66,$66
        byte $66,$66,$66,$66,$66,$66,$66,$66
        byte $66,$66,$66,$66,$66,$66,$66,$66

coltab  byte $0c,$0c,$0c,$0c,$0c,$0c,$0c,$0c
        byte $0c,$0c,$0c,$0c,$0c,$0c,$0c,$0c
        byte $0c,$03,$03,$08,$07,$02,$06,$07
        byte $0a,$0e,$0e,$0e,$0e,$0e,$0e,$09
        byte $04,$04,$04,$04,$04,$04,$04,$04
        byte $04,$04,$04,$04,$04,$04,$04,$06
        byte $02,$07,$09,$0c,$09,$09,$00,$00
        byte $00,$09,$09,$09,$09,$09,$09,$05
        byte $04,$04,$04,$04,$04,$04,$04,$04
        byte $04,$04,$04,$04,$04,$04,$04,$04
        byte $04,$04,$04,$04,$04,$04,$04,$04
        byte $04,$04,$04,$04,$04,$04,$04,$04
        byte $04,$04,$04,$04,$04,$04,$04,$04
        byte $04,$04,$04,$04,$04,$04,$04,$04
        byte $04,$04,$04,$04,$04,$04,$04,$04
        byte $04,$04,$04,$04,$04,$04,$04,$04
        byte $06,$06,$06,$06,$06,$06,$06,$06
        byte $06,$06,$06,$06,$06,$06,$06,$06
        byte $06,$06,$00,$06,$06,$06,$06,$06
        byte $06,$06,$06,$06,$06,$06,$06,$06
        byte $06,$06,$06,$06,$06,$06,$06,$06
        byte $06,$06,$06,$06,$06,$06,$06,$06
        byte $06,$06,$06,$06,$06,$06,$06,$06
        byte $06,$06,$06,$06,$06,$06,$06,$06
        byte $06,$06,$06,$06,$06,$06,$06,$06
        byte $06,$06,$06,$06,$06,$06,$06,$06
        byte $06,$06,$06,$06,$06,$06,$06,$06
        byte $06,$06,$06,$06,$06,$06,$06,$06
        byte $06,$06,$06,$06,$06,$06,$06,$06
        byte $06,$06,$06,$06,$06,$06,$06,$06
        byte $06,$06,$06,$06,$06,$06,$06,$06
        byte $06,$06,$06,$06,$06,$06,$06,$06
