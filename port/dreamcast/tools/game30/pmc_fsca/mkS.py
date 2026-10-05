#!/usr/bin/env python3
"""mkS.py <sched body> <out .S>: lane fm, wraps the scheduled fast path (lsched.py --out) into
platform/pmc_fsca_sh4.S: header, prologue, the body with a return label after each fixup branch, the loop tail,
epilogue, the slow path, the fixups and the constants. Body comments ('! uses ...') are scheduler annotations and
are dropped."""
import re, sys

body = []
for l in open(sys.argv[1]):
    code = l.split('!')[0].rstrip()
    if not code.strip():
        continue
    body.append('        ' + code.strip())
    m = re.match(r'\s*bf\s+\.Lfix([xyz])', code)
    if m:
        body.append('.Lr%s:' % m.group(1))

HEAD = r'''/* platform/pmc_fsca_sh4.S -- GAME_ROT_FSCA (game30.mk; lane fm 2026-10-05). Last-bit FP policy (user decision
 * 2026-09-23 (3)), NOT exact against the original game: cModel::partsMatCalc's loop over every part (RotMatrix,
 * TransMatrix, ScaleMatrix, PSMTXCopy) with the three angles' sin and cos from FSCA plus the residual correction of
 * include/re4dc_fsca.h. Hand-scheduled for the SH-4's dual issue (lane fm's list scheduler under the hw model's
 * pairing rules and latencies): the same IEEE single operations on the same operands as platform/pmc_fsca.c's C
 * twin (pmc_words), so the words are bit-identical to it; GAME_ROT_FSCA=2 compares the two on every part.
 *
 * Per part (rb = part + 0x94, the pos field):
 *   - next = pList; the next part's lines fetched with PREF: pList, ang / scale, pos, and the two lines at the
 *     ends of the 96 bytes mat + l_mat (0x0C .. 0x6B: the words at 0x08 and 0x68; the current part's lines again
 *     at the last part: no PREF of NULL + offset);
 *   - each angle word w: rotl(w) > (XMAX << 1) | 1 is |x| > 2 pi or NaN: the whole part goes to the C twin
 *     (re4dc_pmc_part_slow) before any FP operation on its angles; otherwise
 *     k = ftrc(x K), (s0, c0) = FSCA(k), d = (x - k S1) - k S2, s = c0 d + s0, c = c0 - d s0
 *     (the C twin's operations; + and * commute bit-exactly). For |x| < 2^-27 the C twin returns fdlibm's exact
 *     (x, 1); FSCA(0) is (+0, 1) in the hardware table, so this path gives the same words for every normal tiny x
 *     and +0, and only -0 and denormals (rotl(w) - 1 <= 0x00FFFFFE) need s = x (the fixups below; c is 1 already);
 *   - RotMatrix's products and sums in its order, the 3x3 words times scale_c (ScaleMatrix), the translation
 *     column = pos (moved as integer words, bits unchanged), stored downwards into l_mat and mat (PSMTXCopy).
 *     Before the stores, the two whole cache lines inside mat + l_mat (from (part + 0x0C + 31) & -32; the 96
 *     bytes always hold two) are allocated with MOVCA.L instead of being read from memory: the 24 stores then
 *     write every word of both lines, and nothing reads them in between (the loop is bus-bound: a part's
 *     line fills and write-backs take longer than its arithmetic).
 * Returns NULL (partsMatCalc's miss path never runs). The local matrices (and so the skeleton the renderer reads)
 * differ from the exact game in the last bits; RotMatrix's memo no longer sees the parts.
 *
 * cParts offsets (static_asserts in model.cpp): mat 0x0C, l_mat 0x3C, pos 0x94, ang 0xA0, scale 0xAC, pList 0xF4.
 * ABI: KOS -m4-single -ml, FPSCR.PR=0 SZ=0; saves r8-r13, fr12-fr15, pr (the slow path calls C).
 * Registers: r0 0x60 (pList - pos), r1 rb, r2 ang / scale loads, r3 / r4 l_mat / mat stores, r5-r7 angle words
 * then pos, r8 PREF chain / fixup temp / MOVCA line, r9 next, r10 / r11 test limits, r12 the next rb, r13 -32;
 * fr12-fr14 K, S1, S2.
 */
#if defined(RE4DC_ROT_FSCA) && RE4DC_ROT_FSCA == 2
#define PMC_ENTRY _re4dc_pmc_run_asm
#else
#define PMC_ENTRY _re4dc_pmc_run
#endif
        .text
        .align  5
        .global PMC_ENTRY
        .type   PMC_ENTRY, @function
PMC_ENTRY:                              /* r4 = first part (not NULL) */
        mov.l   r8,@-r15
        mov.l   r9,@-r15
        mov.l   r10,@-r15
        mov.l   r11,@-r15
        mov.l   r12,@-r15
        mov.l   r13,@-r15
        fmov.s  fr12,@-r15
        fmov.s  fr13,@-r15
        fmov.s  fr14,@-r15
        fmov.s  fr15,@-r15
        sts.l   pr,@-r15
        mova    .Lconst,r0
        fmov.s  @r0+,fr12               /* K */
        fmov.s  @r0+,fr13               /* S1 */
        fmov.s  @r0+,fr14               /* S2 */
        mov.l   @r0+,r10                /* (XMAX << 1) | 1 */
        mov.l   @r0+,r11                /* 0x00FFFFFE */
        mov     #-32,r13                /* line mask */
        mov     r4,r1
        add     #127,r1
        add     #21,r1                  /* rb = part + 0x94 */
        bra     .Lpart
        mov     #96,r0                  /* pList - pos */
.Lslow:                                 /* an angle beyond 2 pi or NaN: the whole part in the C twin (before .Lpart:
                                           the bt's reach it) */
        mov     r1,r4
        add     #-128,r4
        add     #-20,r4                 /* part = rb - 0x94 */
        mov.l   .Lslowfn,r3
        jsr     @r3
        nop
        mov     r9,r12
        add     #127,r12
        add     #21,r12                 /* the next rb (unused when next is NULL) */
        bra     .Ltail
        mov     #96,r0
.Lpart:
'''

TAIL = r'''.Ltail:                                 /* the loop is beyond bf's reach: bra, its delay slot also the exit's */
        tst     r9,r9
        bt      .Ldone
        bra     .Lpart
.Ldone:
        mov     r12,r1                  /* rb = next + 0x94 */
        lds.l   @r15+,pr
        fmov.s  @r15+,fr15
        fmov.s  @r15+,fr14
        fmov.s  @r15+,fr13
        fmov.s  @r15+,fr12
        mov.l   @r15+,r13
        mov.l   @r15+,r12
        mov.l   @r15+,r11
        mov.l   @r15+,r10
        mov.l   @r15+,r9
        mov     #0,r0
        rts
        mov.l   @r15+,r8
.Lfixx:                                 /* x is -0 or denormal: sin = x (fdlibm's exact tiny result) */
        mov     r1,r8
        add     #12,r8
        bra     .Lrx
        fmov.s  @r8,fr9
.Lfixz:
        mov     r1,r8
        add     #20,r8
        bra     .Lrz
        fmov.s  @r8,fr11
.Lfixy:
        mov     r1,r8
        add     #16,r8
        bra     .Lry
        fmov.s  @r8,fr10
        .align  2
.Lconst:
        .long   0x4622f983              /* RE4DC_FSCA_K = 65536 / (2 pi) */
        .long   0x38c90000              /* RE4DC_FSCA_S1 */
        .long   0x32fdaa22              /* RE4DC_FSCA_S2 */
        .long   0x81921fb7              /* (RE4DC_FSCA_XMAX_BITS << 1) | 1 */
        .long   0x00fffffe              /* rotl(w) - 1 at or below: -0 or denormal */
.Lslowfn:
        .long   _re4dc_pmc_part_slow
        .size   PMC_ENTRY, .-PMC_ENTRY
'''

open(sys.argv[2], 'w', newline='\n').write(HEAD + '\n'.join(body) + '\n' + TAIL)
print('wrote', sys.argv[2], len(body), 'body lines')
