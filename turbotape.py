#!/usr/bin/env python3
"""Read and write the turbo tape format Gauntlet uses.

Worked out by decoding the ROM-loaded bootstrap at the head of the tape,
following its two layers of self-decryption, and disassembling the loader
it copies out of screen memory into $0830.

Pulses, in .tap units of 8 cycles:

    $24 (288 cycles)  a 0 bit
    $42 (528 cycles)  a 1 bit

The loader arms CIA timer A with $0368 (872 cycles) and takes an interrupt
on each tape edge; the timer's high byte is then $02 for a short pulse and
$01 for a long one, and `eor #$02 / lsr / lsr / rol $a9` turns that into a
bit. Bits arrive most significant first.

A block is:

    many   $20    leader
    one    $FF    sync
    16 bytes      file name, padded with spaces
    2 bytes       load address, low then high
    2 bytes       end address, low then high
    n bytes       the payload
    1 byte        checksum: every payload byte exclusive-ored together

The loader compares the name against the one the caller asked for and
skips blocks that do not match, so several files can sit on one side.
"""
import sys

ZERO, ONE = 0x24, 0x42
LEADER, SYNC = 0x20, 0xFF


def bits_of(pulses):
    for p in pulses:
        if p == ZERO:
            yield 0
        elif p == ONE:
            yield 1


def bytes_of(pulses):
    """Decode a whole pulse stream, most significant bit first."""
    out = bytearray()
    v = n = 0
    for b in bits_of(pulses):
        v = (v << 1) | b
        n += 1
        if n == 8:
            out.append(v)
            v = n = 0
    return bytes(out)


def find_blocks(pulses):
    """Yield (name, start, end, payload, checksum_ok) from a pulse stream.

    The search runs over bits, not bytes. The loader shifts bits through
    $A9 until it sees $20 bytes and then $FF, so a block can begin at any
    bit position - and on a real tape it usually does, because the gaps
    between blocks are not whole numbers of bytes. Searching a byte-aligned
    stream finds only the blocks that happen to line up: on one Deeper
    Dungeons side that was four of fourteen, the rest reading as $10
    leaders, which is $20 shifted by one bit.
    """
    bits = list(bits_of(pulses))
    n = len(bits)
    want = []
    for b in (LEADER, LEADER, SYNC):
        for k in range(7, -1, -1):
            want.append((b >> k) & 1)
    w = len(want)

    def byte_at(p):
        v = 0
        for k in range(8):
            v = (v << 1) | bits[p + k]
        return v

    i = 0
    while i <= n - w:
        if bits[i:i + w] != want:
            i += 1
            continue
        p = i + w
        if p + 20 * 8 > n:
            return
        name = bytes(byte_at(p + k * 8) for k in range(16))
        p += 16 * 8
        lo, hi, elo, ehi = (byte_at(p + k * 8) for k in range(4))
        p += 4 * 8
        start, end = lo | hi << 8, elo | ehi << 8
        size = end - start
        if not (0 < size <= 0xC000) or p + (size + 1) * 8 > n:
            i += 1
            continue
        payload = bytes(byte_at(p + k * 8) for k in range(size))
        got = byte_at(p + size * 8)
        chk = 0
        for x in payload:
            chk ^= x
        yield (name.decode('latin1').rstrip(), start, end, payload, got == chk)
        i = p + (size + 1) * 8


def encode_block(name, start, payload, leader=2000):
    """Build the pulse stream for one block."""
    body = bytearray()
    body += name.encode('latin1').ljust(16)[:16]
    end = start + len(payload)
    body += bytes([start & 0xFF, start >> 8, end & 0xFF, end >> 8])
    body += payload
    chk = 0
    for b in payload:
        chk ^= b
    body.append(chk)
    pulses = bytearray()
    for _ in range(leader):
        for k in range(7, -1, -1):
            pulses.append(ONE if (LEADER >> k) & 1 else ZERO)
    for k in range(7, -1, -1):
        pulses.append(ONE if (SYNC >> k) & 1 else ZERO)
    for b in body:
        for k in range(7, -1, -1):
            pulses.append(ONE if (b >> k) & 1 else ZERO)
    return bytes(pulses)


def write_tap(path, pulse_bytes):
    hdr = b'C64-TAPE-RAW' + bytes([1, 0, 0, 0])
    hdr += len(pulse_bytes).to_bytes(4, 'little')
    open(path, 'wb').write(hdr + pulse_bytes)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    d = open(sys.argv[1], 'rb').read()[20:]
    n = 0
    for name, start, end, payload, ok in find_blocks(d):
        n += 1
        print('   %-16s $%04X-$%04X  %5d bytes  checksum %s'
              % (repr(name), start, end, len(payload), 'ok' if ok else 'BAD'))
    print('%d blocks' % n)


if __name__ == '__main__':
    main()
