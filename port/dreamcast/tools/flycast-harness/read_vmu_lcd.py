"""Save the PACE_VMU speed page (pace.cpp, PACE_VMU=1) out of a running Flycast, as the VMU would show it.

    python read_vmu_lcd.py <evidence-dir> [seconds] [period-seconds]

Every <period> seconds (default 5) for <seconds> (default 600) it reads the game's LCD buffer (pace.cpp v_lcd, a KOS
vmufb_t: 48x32 pixels, 192 bytes) out of the emulated main RAM of the Flycast whose pid is in <dir>/flycast.pid, and
when the page changed saves <dir>/vmu/vmu-<n>-<host s>s.png (x8, VMU-style colours) and appends the page as text rows
to <dir>/vmu/vmu.txt. With PACE_VMU_GPU=1 the page has five lines: FPS / SPD / CPU / GPU <mean>/<max> ms / MODE.
- The address of v_lcd comes from <dir>/re4dc-game.elf (its ELF32 symbol table; the anonymous-namespace symbol ends in
  "5v_lcdE"); the RAM host address from <dir>/flycast.log ("RAM(16 MB) <addr>"); SH-4 0x8C000000 is its first byte.
- KOS layout (util/vmu_fb.c insert_bits): pixel (x, y) is bit (y * 48 + x) of the byte array, most significant first.
Observation only (Windows, ReadProcessMemory); start it with the run, it waits for flycast.pid.
"""
import ctypes
import re
import struct
import sys
import time
from pathlib import Path

from PIL import Image


def lcd_address(elf):
    data = elf.read_bytes()
    shoff, = struct.unpack_from("<I", data, 0x20)
    shentsize, shnum = struct.unpack_from("<HH", data, 0x2E)
    sections = [struct.unpack_from("<10I", data, shoff + i * shentsize) for i in range(shnum)]
    for sh in sections:
        if sh[1] != 2:          # SHT_SYMTAB
            continue
        strtab = sections[sh[6]]
        names = data[strtab[4]:strtab[4] + strtab[5]]
        for off in range(sh[4], sh[4] + sh[5], 16):
            st_name, st_value, st_size = struct.unpack_from("<III", data, off)
            end = names.index(b"\0", st_name)
            if names[st_name:end].endswith(b"5v_lcdE") and st_size == 192:
                return st_value
    raise SystemExit("no v_lcd symbol in %s (a PACE_VMU=1 build is needed)" % elf)


def ram_base(ev):
    found = re.findall(r"RAM\(16 MB\) ([0-9A-Fa-f]+)", (ev / "flycast.log").read_text(errors="replace"))
    return int(found[-1], 16) if found else None


def decode(raw):
    return ["".join("#" if raw[(y * 48 + x) // 8] >> (7 - (y * 48 + x) % 8) & 1 else "." for x in range(48))
            for y in range(32)]


def png(rows, path, scale=8):
    img = Image.new("RGB", (50 * scale, 34 * scale), (152, 176, 128))
    px = img.load()
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c == "#":
                for dy in range(scale - 1):
                    for dx in range(scale - 1):
                        px[scale + x * scale + dx, scale + y * scale + dy] = (24, 40, 32)
    img.save(path)


def main():
    ev = Path(sys.argv[1])
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 600
    period = float(sys.argv[3]) if len(sys.argv) > 3 else 5
    addr = lcd_address(ev / "re4dc-game.elf")
    out = ev / "vmu"
    out.mkdir(exist_ok=True)
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    k.OpenProcess.restype = ctypes.c_void_p
    k.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                    ctypes.POINTER(ctypes.c_size_t)]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    print("v_lcd at %08x" % addr, flush=True)
    start, last, n, handle, base, last_err = time.time(), None, 0, None, None, None
    with (out / "vmu.txt").open("a") as log:
        while time.time() - start < secs:
            try:
                if handle is None:
                    pid = int((ev / "flycast.pid").read_text().strip())
                    base = ram_base(ev)
                    if base is None:
                        raise OSError("no RAM line in flycast.log yet")
                    handle = k.OpenProcess(0x0010 | 0x0400, False, pid)
                    if not handle:
                        raise OSError("OpenProcess failed")
                buf, got = ctypes.create_string_buffer(192), ctypes.c_size_t()
                if not k.ReadProcessMemory(handle, ctypes.c_void_p(base + (addr - 0x8C000000)), buf, 192,
                                           ctypes.byref(got)) or got.value != 192:
                    raise OSError("read failed")
                rows = decode(buf.raw)
                if rows != last and any("#" in r for r in rows):
                    t = time.time() - start
                    png(rows, out / ("vmu-%03d-%04ds.png" % (n, t)))
                    log.write("t=%.1f page %d\n%s\n" % (t, n, "\n".join(rows)))
                    log.flush()
                    n, last = n + 1, rows
            except Exception as ex:  # Flycast not up yet, or gone
                msg = "%s: %s" % (type(ex).__name__, ex)
                if msg != last_err:
                    print("t=%.1f %s" % (time.time() - start, msg), flush=True)
                    last_err = msg
                if handle is not None:
                    k.CloseHandle(handle)
                    handle = None
            time.sleep(period)
    print("read_vmu_lcd: %d pages" % n)


if __name__ == "__main__":
    main()
