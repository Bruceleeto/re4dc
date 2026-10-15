#!/usr/bin/env python3
"""PS2 RE4 (SLUS_211.34 + SNR2 .rel modules) reference disassembler.

Offline analysis aid for comparing the PS2 port's code with the GC decomp (lane ps2code,
2026-10-15). No game data is shipped: point it at your own PS2 files.

Inputs
  - the PS2 main ELF (SLUS_211.34): no symtab, but the SN export table of (hash, name ptr, addr)
    triples in .data/.sndata names ~1400 functions; this tool rebuilds addr -> name from it.
  - SNR2 modules (st1_0.rel ... st5_0.rel, emNN.rel, sscrn.rel, t_*.rel from BIO4DAT.AFS).
    SNR2 layout (little-endian): 'SNR2', relOff, relCount, symOff, symCount, imageEnd(?),
    textEnd(?), ..., strOff, ..., fileSize.  Reloc entry = (offset, type | sym << 8, addend):
    type 4 = R_MIPS_26 (jal), 5 = HI16, 6 = LO16; every reloc names an IMPORTED symbol.
    Symbol entry = (nameOff, addr, hash); addr 0 = import. Addresses ARE file offsets (the image
    starts at file offset 0, code at 0x100); intra-module jal / lui+addiu refs are unrelocated
    file offsets.

Usage
  ps2dis.py elf  <SLUS> name <substr...>           exported names matching
  ps2dis.py elf  <SLUS> dis <addr|name> [end]       disassemble (one function if no end)
  ps2dis.py elf  <SLUS> callers <addr|name>         jal callers
  ps2dis.py rel  <file.rel> syms                    local symbols (name, addr)
  ps2dis.py rel  <file.rel> imports                 imported names
  ps2dis.py rel  <file.rel> dis <addr|name> [end]   disassemble
  ps2dis.py rel  <file.rel> summary [prefix]        per function: calls, float consts, small ints
  ps2dis.py rel  <file.rel> callers <addr|name>     intra-module + import callers
"""
import re
import struct
import sys

R = ['zero', 'at', 'v0', 'v1', 'a0', 'a1', 'a2', 'a3', 't0', 't1', 't2', 't3', 't4', 't5', 't6', 't7',
     's0', 's1', 's2', 's3', 's4', 's5', 's6', 's7', 't8', 't9', 'k0', 'k1', 'gp', 'sp', 'fp', 'ra']
OPS = {0x20: 'lb', 0x21: 'lh', 0x22: 'lwl', 0x23: 'lw', 0x24: 'lbu', 0x25: 'lhu', 0x26: 'lwr', 0x27: 'lwu',
       0x28: 'sb', 0x29: 'sh', 0x2a: 'swl', 0x2b: 'sw', 0x2c: 'sdl', 0x2d: 'sdr', 0x2e: 'swr',
       0x31: 'lwc1', 0x39: 'swc1', 0x37: 'ld', 0x3f: 'sd', 0x1e: 'lq', 0x1f: 'sq', 0x1a: 'ldl', 0x1b: 'ldr',
       0x36: 'lqc2', 0x3e: 'sqc2', 0x33: 'pref',
       0x08: 'addi', 0x09: 'addiu', 0x0a: 'slti', 0x0b: 'sltiu', 0x0c: 'andi', 0x0d: 'ori', 0x0e: 'xori',
       0x0f: 'lui', 0x18: 'daddi', 0x19: 'daddiu',
       0x04: 'beq', 0x05: 'bne', 0x06: 'blez', 0x07: 'bgtz', 0x14: 'beql', 0x15: 'bnel', 0x16: 'blezl',
       0x17: 'bgtzl'}
MEMOPS = {0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2a, 0x2b, 0x2c, 0x2d, 0x2e, 0x31,
          0x39, 0x37, 0x3f, 0x1e, 0x1f, 0x1a, 0x1b, 0x36, 0x3e, 0x33}
FN = {0x00: 'sll', 0x02: 'srl', 0x03: 'sra', 0x04: 'sllv', 0x06: 'srlv', 0x07: 'srav', 0x08: 'jr',
      0x09: 'jalr', 0x0a: 'movz', 0x0b: 'movn', 0x0c: 'syscall', 0x0d: 'break', 0x0f: 'sync',
      0x10: 'mfhi', 0x11: 'mthi', 0x12: 'mflo', 0x13: 'mtlo', 0x14: 'dsllv', 0x16: 'dsrlv', 0x17: 'dsrav',
      0x18: 'mult', 0x19: 'multu', 0x1a: 'div', 0x1b: 'divu', 0x20: 'add', 0x21: 'addu', 0x22: 'sub',
      0x23: 'subu', 0x24: 'and', 0x25: 'or', 0x26: 'xor', 0x27: 'nor', 0x2a: 'slt', 0x2b: 'sltu',
      0x2c: 'dadd', 0x2d: 'daddu', 0x2e: 'dsub', 0x2f: 'dsubu', 0x38: 'dsll', 0x3a: 'dsrl', 0x3b: 'dsra',
      0x3c: 'dsll32', 0x3e: 'dsrl32', 0x3f: 'dsra32'}
SHIFTS = {0x00, 0x02, 0x03, 0x38, 0x3a, 0x3b, 0x3c, 0x3e, 0x3f}
FS = {0x00: 'add.s', 0x01: 'sub.s', 0x02: 'mul.s', 0x03: 'div.s', 0x04: 'sqrt.s', 0x05: 'abs.s',
      0x06: 'mov.s', 0x07: 'neg.s', 0x16: 'rsqrt.s', 0x18: 'adda.s', 0x19: 'suba.s', 0x1a: 'mula.s',
      0x1c: 'madd.s', 0x1d: 'msub.s', 0x1e: 'madda.s', 0x1f: 'msuba.s', 0x24: 'cvt.w.s', 0x28: 'max.s',
      0x29: 'min.s', 0x30: 'c.f.s', 0x32: 'c.eq.s', 0x34: 'c.lt.s', 0x36: 'c.le.s'}


def f32(bits):
    return struct.unpack('<f', struct.pack('<I', bits & 0xffffffff))[0]


class Image:
    """A flat code image: word reader, names, optional reloc names."""

    def __init__(self):
        self.names = {}      # addr -> name
        self.relocs = {}     # addr -> (type, name, addend)
        self.lo = self.hi = 0

    def W(self, va):
        raise NotImplementedError

    def name_of(self, a):
        return self.names.get(a)

    def lookup(self, s):
        try:
            return int(s, 16)
        except ValueError:
            pass
        hits = [a for a, n in self.names.items() if n == s] or [a for a, n in self.names.items() if s in n]
        if not hits:
            imps = getattr(self, 'imports', [])
            imp = [n for n in imps if n == s] or [n for n in imps if s in n]
            if imp:
                return imp[0]   # an imported name: callers() matches it by name
            raise SystemExit('no symbol %s' % s)
        return sorted(hits)[0]

    def dis(self, va, regs=None):
        w = self.W(va)
        op = w >> 26
        rs, rt, rd = (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
        imm = w & 0xffff
        simm = imm - 0x10000 if imm & 0x8000 else imm
        rel = self.relocs.get(va)
        note = ''
        if rel:
            note = '  ; @%s%s' % (rel[1], '+%x' % rel[2] if rel[2] else '')
        if w == 0:
            return 'nop'
        if op in (2, 3):
            if rel:
                return '%s <%s>' % ('j' if op == 2 else 'jal', rel[1])
            t = (va & 0xf0000000) | ((w & 0x3ffffff) << 2)
            return '%s %x <%s>' % ('j' if op == 2 else 'jal', t, self.names.get(t, '?'))
        if op == 0:
            f = w & 63
            n = FN.get(f, 'special%02x' % f)
            if f in SHIFTS:
                return '%s %s,%s,%d' % (n, R[rd], R[rt], (w >> 6) & 31)
            if f == 8:
                return 'jr %s' % R[rs]
            if f == 9:
                return 'jalr %s' % R[rs]
            if f in (0x10, 0x12):
                return '%s %s' % (n, R[rd])
            if f in (0x18, 0x19, 0x1a, 0x1b):
                return '%s %s,%s,%s' % (n, R[rd], R[rs], R[rt])
            if f == 0x2d and rt == 0:
                return 'move %s,%s' % (R[rd], R[rs])
            return '%s %s,%s,%s' % (n, R[rd], R[rs], R[rt])
        if op == 1:
            n = {0: 'bltz', 1: 'bgez', 2: 'bltzl', 3: 'bgezl'}.get(rt, 'regimm%d' % rt)
            return '%s %s,%x' % (n, R[rs], va + 4 + simm * 4)
        if op == 0x11:
            fmt = rs
            ft, fs, fd = rt, rd, (w >> 6) & 31
            if fmt == 0:
                return 'mfc1 %s,f%d' % (R[rt], fs)
            if fmt == 4:
                s = 'mtc1 %s,f%d' % (R[rt], fs)
                if regs is not None and rt in regs:
                    s += '   ; =%g' % f32(regs[rt])
                return s
            if fmt in (2, 6):
                return '%s %s,$%d' % ('cfc1' if fmt == 2 else 'ctc1', R[rt], fs)
            if fmt == 8:
                n = {0: 'bc1f', 1: 'bc1t', 2: 'bc1fl', 3: 'bc1tl'}[rt & 3]
                return '%s %x' % (n, va + 4 + simm * 4)
            if fmt == 0x10:
                f = w & 63
                n = FS.get(f, 's.%02x' % f)
                if f in (0x30, 0x32, 0x34, 0x36):
                    return '%s f%d,f%d' % (n, fs, ft)
                if f in (0x04,):
                    return '%s f%d,f%d' % (n, fd, ft)
                if f in (0x05, 0x06, 0x07, 0x24):
                    return '%s f%d,f%d' % (n, fd, fs)
                if f in (0x18, 0x19, 0x1a):
                    return '%s f%d,f%d' % (n, fs, ft)
                return '%s f%d,f%d,f%d' % (n, fd, fs, ft)
            if fmt == 0x14 and (w & 63) == 0x20:
                return 'cvt.s.w f%d,f%d' % (fd, fs)
            return 'cop1 %08x' % w
        if op == 0x12:
            return 'cop2 %08x' % w
        if op == 0x1c:
            f = w & 63
            sa = (w >> 6) & 31
            if f == 0x29 and sa == 0x12:
                return ('move %s,%s' % (R[rd], R[rs])) if rt == 0 else 'por %s,%s,%s' % (R[rd], R[rs], R[rt])
            n = {0x18: 'mult1', 0x19: 'multu1', 0x1a: 'div1', 0x1b: 'divu1', 0x10: 'mfhi1', 0x12: 'mflo1',
                 0x11: 'mthi1', 0x13: 'mtlo1', 0x00: 'madd', 0x20: 'madd1'}.get(f, 'mmi%02x.%02x' % (f, sa))
            return '%s %s,%s,%s' % (n, R[rd], R[rs], R[rt])
        n = OPS.get(op, 'op%02x' % op)
        if op in (4, 5, 0x14, 0x15):
            if rt == 0 and op == 4 and rs == 0:
                return 'b %x' % (va + 4 + simm * 4)
            return '%s %s,%s,%x' % (n, R[rs], R[rt], va + 4 + simm * 4)
        if op in (6, 7, 0x16, 0x17):
            return '%s %s,%x' % (n, R[rs], va + 4 + simm * 4)
        if op == 0xf:
            return 'lui %s,0x%x%s' % (R[rt], imm, note)
        if op in MEMOPS:
            reg = ('f%d' % rt) if op in (0x31, 0x39) else ('vf%d' % rt if op in (0x36, 0x3e) else R[rt])
            s = '%s %s,%d(%s)%s' % (n, reg, simm, R[rs], note)
            ext = self.mem_note(va, op, rs, simm, regs)
            return s + ext
        if op in (0x0c, 0x0d, 0x0e):
            return '%s %s,%s,0x%x%s' % (n, R[rt], R[rs], imm, note)
        return '%s %s,%s,%d%s' % (n, R[rt], R[rs], simm, note)

    def mem_note(self, va, op, rs, simm, regs):
        return ''

    def track(self, va, regs):
        """Very small constant propagation for lui/ori/addiu (float immediates)."""
        w = self.W(va)
        op = w >> 26
        rs, rt = (w >> 21) & 31, (w >> 16) & 31
        imm = w & 0xffff
        simm = imm - 0x10000 if imm & 0x8000 else imm
        if op == 0xf:
            regs[rt] = imm << 16
        elif op == 0x0d and rs in regs:
            regs[rt] = regs[rs] | imm
        elif op in (0x09, 0x19) and rs in regs:
            regs[rt] = (regs[rs] + simm) & 0xffffffff
        elif op == 0x09 and rs == 0:
            regs[rt] = simm & 0xffffffff
        elif op == 0x0d and rs == 0:
            regs[rt] = imm
        else:
            # any other write kills the destination (approximate)
            if op == 0:
                rd = (w >> 11) & 31
                regs.pop(rd, None)
            elif op not in MEMOPS or op in (0x20, 0x21, 0x23, 0x24, 0x25, 0x27, 0x37, 0x1e):
                if op not in (0x11, 0x12, 1, 2, 3, 4, 5, 6, 7, 0x14, 0x15, 0x16, 0x17):
                    regs.pop(rt, None)
            if op == 0x11 and rs == 0:
                regs.pop(rt, None)

    def func_end(self, fs):
        v = fs + 4
        while v < self.hi:
            if self.W(v) == 0x03e00008:
                return v + 8
            v += 4
        return v

    def func_start(self, va):
        v = va
        while v >= self.lo:
            if v in self.names:
                return v
            w = self.W(v)
            if (w & 0xffff0000) == 0x27bd0000 and (w & 0x8000):
                return v
            v -= 4
        return None

    def listing(self, a, b, out=sys.stdout):
        regs = {}
        for v in range(a, b, 4):
            nm = self.names.get(v)
            if nm:
                out.write('%s:\n' % nm)
            out.write('  %x: %s\n' % (v, self.dis(v, regs)))
            self.track(v, regs)

    def jal_target(self, va):
        w = self.W(va)
        if w >> 26 != 3:
            return None
        rel = self.relocs.get(va)
        if rel:
            return rel[1]
        t = (va & 0xf0000000) | ((w & 0x3ffffff) << 2)
        return self.names.get(t, '%x' % t)

    def summary(self, fs, fe=None):
        """calls, float constants and small integer immediates used by a function."""
        fe = fe or self.func_end(fs)
        calls, floats, ints = [], [], []
        regs = {}
        for v in range(fs, fe, 4):
            w = self.W(v)
            op = w >> 26
            t = self.jal_target(v)
            if t:
                calls.append(t)
            if op == 0x11 and ((w >> 21) & 31) == 4:
                rt = (w >> 16) & 31
                if rt in regs:
                    floats.append(round(f32(regs[rt]), 4))
            fl = self.load_float(v)
            if fl is not None:
                floats.append(round(fl, 4))
            if op in (0x09, 0x0a, 0x0b, 0x0d) and ((w >> 21) & 31) == 0 or op in (0x0a, 0x0b):
                imm = w & 0xffff
                ints.append(imm - 0x10000 if (imm & 0x8000 and op != 0x0d) else imm)
            self.track(v, regs)
        return calls, floats, ints

    def load_float(self, va):
        return None


class Elf(Image):
    TEXT_OFF, TEXT_VA, TEXT_SZ = 0x1000, 0x100000, 0x1ef91c

    def __init__(self, path):
        Image.__init__(self)
        d = self.d = open(path, 'rb').read()
        shoff = struct.unpack_from('<I', d, 0x20)[0]
        shentsize, shnum = struct.unpack_from('<HH', d, 0x2e)
        self.secs = []
        for i in range(shnum):
            _nm, _ty, _fl, addr, off, size = struct.unpack_from('<IIIIII', d, shoff + i * shentsize)
            if addr:
                self.secs.append((addr, off, size, _ty))
        self.lo, self.hi = self.TEXT_VA, self.TEXT_VA + self.TEXT_SZ
        for o in range(0x1f0980, len(d) - 12, 4):
            h, np, ad = struct.unpack_from('<III', d, o)
            if self.lo <= ad < self.hi:
                s = self.cstr(np)
                if s and re.match(r'^[A-Za-z_][\w$.]{2,}$', s):
                    self.names.setdefault(ad, s)
        self.gp = self.find_gp()

    def off(self, va):
        for a, f, s, ty in self.secs:
            if a <= va < a + s and ty != 8:
                return f + va - a
        return None

    def cstr(self, va):
        o = self.off(va)
        if o is None:
            return None
        try:
            e = self.d.index(b'\0', o, o + 256)
        except ValueError:
            return None
        return self.d[o:e].decode('latin1')

    def W(self, va):
        return struct.unpack_from('<I', self.d, self.TEXT_OFF + va - self.TEXT_VA)[0]

    def word(self, va):
        o = self.off(va)
        return None if o is None else struct.unpack_from('<I', self.d, o)[0]

    def find_gp(self):
        entry = struct.unpack_from('<I', self.d, 0x18)[0]
        hi = None
        for v in range(entry, entry + 0x100, 4):
            w = self.W(v)
            if w >> 26 == 0xf and ((w >> 16) & 31) == 28:
                hi = (w & 0xffff) << 16
            elif hi is not None and w >> 26 in (0x09, 0x0d) and ((w >> 16) & 31) == 28:
                lo = w & 0xffff
                return (hi + (lo - 0x10000 if (w >> 26 == 9 and lo & 0x8000) else lo)) & 0xffffffff
        return None

    def mem_note(self, va, op, rs, simm, regs):
        if rs == 28 and self.gp:
            a = (self.gp + simm) & 0xffffffff
            v = self.word(a)
            if v is None:
                return '   ; gp:%x' % a
            if op in (0x31, 0x39):
                return '   ; [%x]=%g' % (a, f32(v))
            return '   ; [%x]=0x%x' % (a, v)
        if regs is not None and rs in regs:
            a = (regs[rs] + simm) & 0xffffffff
            v = self.word(a)
            if v is not None:
                return '   ; [%x]=%s' % (a, ('%g' % f32(v)) if op in (0x31, 0x39) else '0x%x' % v)
        return ''

    def load_float(self, va):
        w = self.W(va)
        if w >> 26 == 0x31 and ((w >> 21) & 31) == 28 and self.gp:
            imm = w & 0xffff
            a = (self.gp + (imm - 0x10000 if imm & 0x8000 else imm)) & 0xffffffff
            v = self.word(a)
            return None if v is None else f32(v)
        return None

    def callers(self, t):
        j = 0x0c000000 | ((t >> 2) & 0x3ffffff)
        return [self.TEXT_VA + i for i in range(0, self.TEXT_SZ, 4)
                if struct.unpack_from('<I', self.d, self.TEXT_OFF + i)[0] == j]


class Rel(Image):
    def __init__(self, path):
        Image.__init__(self)
        d = self.d = open(path, 'rb').read()
        h = struct.unpack_from('<16I', d, 0)
        assert d[:4] == b'SNR2', path
        self.h = h
        ro, rc, so, sc = h[1], h[2], h[3], h[4]
        self.syms = []
        self.imports = []
        for i in range(sc):
            n, a, hs = struct.unpack_from('<III', d, so + 12 * i)
            s = d[n:d.index(b'\0', n)].decode('latin1')
            self.syms.append((s, a))
            if a:
                self.names.setdefault(a, s)
            elif s:
                self.imports.append(s)
        for i in range(rc):
            o, t, a = struct.unpack_from('<III', d, ro + 12 * i)
            self.relocs[o] = (t & 0xff, self.syms[t >> 8][0], a)
        self.lo = 0x100
        self.hi = h[6]   # end of .text (best guess; symbols beyond are data)

    def W(self, va):
        return struct.unpack_from('<I', self.d, va)[0]

    def mem_note(self, va, op, rs, simm, regs):
        if regs is not None and rs in regs:
            a = (regs[rs] + simm) & 0xffffffff
            if 0 < a < len(self.d) - 4:
                v = struct.unpack_from('<I', self.d, a)[0]
                nm = self.names.get(a)
                return '   ; [%x%s]=%s' % (a, ' ' + nm if nm else '',
                                          ('%g' % f32(v)) if op in (0x31, 0x39) else '0x%x' % v)
        return ''

    def load_float(self, va):
        return None

    def track(self, va, regs):
        # module-local lui/addiu address pairs carry file offsets: treat like constants;
        # a relocated lui is an import address (unknown), so drop it.
        Image.track(self, va, regs)
        if va in self.relocs:
            w = self.W(va)
            regs.pop((w >> 16) & 31, None)

    def summary(self, fs, fe=None):
        fe = fe or self.func_end(fs)
        calls, floats, ints = Image.summary(self, fs, fe)
        regs = {}
        for v in range(fs, fe, 4):
            w = self.W(v)
            if w >> 26 == 0x31 and ((w >> 21) & 31) in regs:
                imm = w & 0xffff
                a = (regs[(w >> 21) & 31] + (imm - 0x10000 if imm & 0x8000 else imm)) & 0xffffffff
                if 0 < a < len(self.d) - 4:
                    floats.append(round(f32(struct.unpack_from('<I', self.d, a)[0]), 4))
            self.track(v, regs)
        return calls, floats, ints

    def functions(self):
        """(addr, end, name) for every named text symbol."""
        fs = sorted(a for a in self.names if self.lo <= a < self.hi)
        out = []
        for i, a in enumerate(fs):
            e = fs[i + 1] if i + 1 < len(fs) else self.hi
            out.append((a, e, self.names[a]))
        return out

    def callers(self, t):
        res = []
        tn = (self.names.get(t) or "%x" % t) if isinstance(t, int) else t
        for v in range(self.lo, self.hi, 4):
            if self.W(v) >> 26 == 3 and self.jal_target(v) == tn:
                res.append(v)
        return res


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 1
    kind, path, cmd = argv[1], argv[2], argv[3]
    args = argv[4:]
    img = Elf(path) if kind == 'elf' else Rel(path)
    if cmd == 'name':
        for v, n in sorted(img.names.items()):
            if any(s in n for s in args):
                print('%x %s' % (v, n))
    elif cmd == 'syms':
        for v, n in sorted(img.names.items()):
            print('%x %s' % (v, n))
    elif cmd == 'imports':
        for n in img.imports:
            print(n)
    elif cmd == 'dis':
        a = img.lookup(args[0])
        b = int(args[1], 16) if len(args) > 1 else img.func_end(a)
        img.listing(a, b)
    elif cmd == 'callers':
        t = img.lookup(args[0])
        print('callers of %s' % (t if isinstance(t, str) else '%x <%s>' % (t, img.names.get(t))))
        for c in img.callers(t):
            fs = img.func_start(c)
            print('  %x in %x <%s>' % (c, fs or 0, img.names.get(fs, '?')))
    elif cmd == 'summary':
        pre = args[0] if args else ''
        for a, e, n in img.functions():
            if not n.startswith(pre):
                continue
            calls, floats, ints = img.summary(a, e)
            print('%x %s' % (a, n))
            print('   calls: %s' % ', '.join(c.split('__')[0] + ('' if '__' not in c else '/' + c.split('__')[1][:18]) for c in calls))
            if floats:
                print('   floats: %s' % floats)
            if ints:
                print('   ints: %s' % ints)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
