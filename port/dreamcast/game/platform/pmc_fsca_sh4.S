/* platform/pmc_fsca_sh4.S -- GAME_ROT_FSCA (game30.mk; lane fm 2026-10-05). Last-bit FP policy (user decision
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
        mov.l   @(12,r1),r5
        mov     r1,r2
        mov.l   @(20,r1),r7
        add     #12,r2
        mov.l   @(r0,r1),r9
        mov     r1,r4
        fmov.s  @r2+,fr6
        add     #-88,r4
        fmov.s  @r2+,fr7
        tst     r9,r9
        movt    r8
        mov.l   @(16,r1),r6
        rotl    r5
        fmov.s  @r2+,fr8
        cmp/hi  r10,r5
        neg     r8,r8
        bt      .Lslow
        fmov    fr6,fr9
        fmul    fr12,fr9
        rotl    r7
        cmp/hi  r10,r7
        and     r1,r8
        bt      .Lslow
        fmov    fr8,fr11
        ftrc    fr9,fpul
        rotl    r6
        fmul    fr12,fr11
        cmp/hi  r10,r6
        bt      .Lslow
        fmov    fr7,fr4
        fsca    fpul,dr0
        or      r9,r8
        float   fpul,fr9
        add     #127,r8
        fmul    fr12,fr4
        add     #117,r8
        ftrc    fr11,fpul
        add     #-1,r5
        fmov    fr9,fr10
        fmul    fr13,fr9
        fmul    fr14,fr10
        pref    @r8
        float   fpul,fr11
        add     #-64,r8
        fsub    fr9,fr6
        fmov    fr1,fr9
        fsca    fpul,dr2
        pref    @r8
        ftrc    fr4,fpul
        fmov    fr11,fr15
        fmul    fr14,fr15
        add     #-32,r8
        fmul    fr13,fr11
        pref    @r8
        fsub    fr10,fr6
        add     #-1,r7
        float   fpul,fr10
        mov     r8,r12
        fsub    fr11,fr8
        fmov    fr3,fr11
        fsca    fpul,dr4
        add     #-44,r8
        fmul    fr6,fr9
        pref    @r8
        fsub    fr15,fr8
        fmov    fr10,fr15
        fmul    fr13,fr10
        cmp/hi  r11,r5
        fmul    fr14,fr15
        add     #-1,r6
        fmul    fr8,fr11
        add     #-96,r8
        fsub    fr10,fr7
        fmov    fr5,fr10
        fmul    fr2,fr8
        pref    @r8
        fadd    fr0,fr9
        bf      .Lfixx
.Lrx:
        fsub    fr15,fr7
        cmp/hi  r11,r7
        fmul    fr0,fr6
        mov     r1,r3
        fsub    fr8,fr3
        mov.l   @(8,r1),r7
        fmul    fr7,fr10
        add     #-40,r3
        fadd    fr2,fr11
        bf      .Lfixz
.Lrz:
        fmov    fr3,fr8
        cmp/hi  r11,r6
        fsub    fr6,fr1
        fmov    fr3,fr2
        fadd    fr4,fr10
        bf      .Lfixy
.Lry:
        fmul    fr9,fr8
        fmov    fr11,fr0
        fmul    fr1,fr0
        fmov    fr11,fr6
        fmul    fr4,fr7
        mov     r1,r8
        fmov    fr8,fr15
        fmul    fr1,fr2
        fmul    fr10,fr15
        add     #-105,r8
        fsub    fr7,fr5
        and     r13,r8
        fmul    fr9,fr6
        fmov    fr2,fr4
        fsub    fr0,fr15
        movca.l r0,@r8
        fmul    fr10,fr0
        add     #32,r8
        fmov    fr6,fr7
        fmul    fr5,fr1
        fmul    fr10,fr7
        movca.l r0,@r8
        fmul    fr10,fr4
        fneg    fr10
        fsub    fr8,fr0
        fmov.s  @r2+,fr8
        fadd    fr2,fr7
        fmov.s  @r2+,fr2
        fadd    fr6,fr4
        fmov.s  @r2+,fr6
        fmul    fr5,fr9
        mov.l   r7,@-r3
        fmul    fr6,fr1
        mov.l   r7,@-r4
        mov.l   @(4,r1),r6
        fmul    fr8,fr10
        fmul    fr2,fr9
        mov.l   @(0,r1),r5
        fmul    fr2,fr7
        fmov.s  fr1,@-r4
        fmul    fr5,fr11
        fmov.s  fr1,@-r3
        fmov.s  fr9,@-r4
        fmul    fr5,fr3
        fmov.s  fr9,@-r3
        fmul    fr6,fr4
        fmov.s  fr10,@-r3
        fmul    fr6,fr0
        fmov.s  fr10,@-r4
        fmul    fr8,fr11
        mov.l   r6,@-r3
        fmul    fr8,fr3
        mov.l   r6,@-r4
        fmul    fr2,fr15
        fmov.s  fr0,@-r3
        fmov.s  fr7,@-r3
        fmov.s  fr0,@-r4
        fmov.s  fr11,@-r3
        fmov.s  fr7,@-r4
        fmov.s  fr11,@-r4
        mov.l   r5,@-r3
        mov.l   r5,@-r4
        fmov.s  fr4,@-r4
        fmov.s  fr4,@-r3
        fmov.s  fr15,@-r4
        fmov.s  fr15,@-r3
        fmov.s  fr3,@-r3
        fmov.s  fr3,@-r4
.Ltail:                                 /* the loop is beyond bf's reach: bra, its delay slot also the exit's */
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
