#!/usr/bin/env python3
"""ovl_id_patch.py <game.elf>: OVL_ID_GUARD (RE4DC_OVL_ID=1, tools/link.sh). Writes the main image's identity into
its own `re4dc_image_id` word pair (platform/modules.cpp, initialised data): FNV-1a of the image's .text (whole words)
and the .text byte count, the same two words gen_overlay.py puts in every route overlay header (words 14/15).
routeOverlayLoad compares the two without hashing at run time (the running .text is not the linked .text: hashing
it at run time gave another value). Patching .data does not change .text, so the identity stays the link's.
"""
import struct
import subprocess
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from gen_overlay import binary, fnv  # noqa: E402

MARK = 0x31444952  # "RID1": the word pair's initial value, checked before patching


def main():
    elf = sys.argv[1]
    text = binary(elf, ["-j", ".text"])
    text = text[:len(text) & ~3]
    ident = (fnv(text), len(text))
    sym = None
    for line in subprocess.check_output(["sh-elf-nm", elf], text=True).splitlines():
        p = line.split()
        if len(p) == 3 and p[2] == "_re4dc_image_id":
            sym = int(p[0], 16)
    if sym is None:
        sys.exit("ovl_id_patch: no _re4dc_image_id in %s" % elf)
    # ELF32 little endian: find the section holding sym and its file offset.
    data = bytearray(open(elf, "rb").read())
    shoff, = struct.unpack_from("<I", data, 0x20)
    shentsize, shnum = struct.unpack_from("<HH", data, 0x2E)
    off = None
    for i in range(shnum):
        sh = shoff + i * shentsize
        stype, = struct.unpack_from("<I", data, sh + 4)
        addr, offset, size = struct.unpack_from("<III", data, sh + 12)
        if stype == 1 and addr <= sym < addr + size:  # SHT_PROGBITS
            off = offset + sym - addr
    if off is None:
        sys.exit("ovl_id_patch: _re4dc_image_id is not in a PROGBITS section")
    if struct.unpack_from("<2I", data, off) != (MARK, MARK):
        sys.exit("ovl_id_patch: _re4dc_image_id does not hold the RID1 mark (already patched?)")
    struct.pack_into("<2I", data, off, *ident)
    open(elf, "wb").write(data)
    print("ovl_id_patch: %s image id %08x/%u at %08x" % (elf, ident[0], ident[1], sym))


if __name__ == "__main__":
    main()
