/* platform/sk1_sh4.S -- GAME_SK1_ASM (game30.mk; render only, exact): trans.cpp's off-PowerPC CalcSk1_x /
 * CalcSk1_x2 loops (the source skinning of the infos the native actor path does not take: morphed ones,
 * and the Render() materialisation). The same float operations in the same order as the C loop:
 *   x = float(s[0]) * ls (y, z alike); m = pal + idx * 0x30;
 *   ox = ((x * m0 + y * m3) + z * m6) + m9 (oy: m1 m4 m7 m10, oz: m2 m5 m8 m11), each one fmul / fadd;
 *   d = psQuant(o * ss): hi when o * ss >= hi, lo when <= lo, else truncated.
 * psQuant is done as ftrc then an integer range test (ftrc saturates; a value in [hi, hi + 1) truncates to
 * hi, in (lo - 1, lo] to lo), out of line when out of range; a NaN keeps ftrc's word as the C cast does.
 * The three components interleave (the compiled loop ran them one after another, each compare a branch).
 * ABI: KOS -m4-single -ml, FPSCR.PR=0 SZ=0; saves fr14-fr15.
 *
 * void re4dc_sk1_s16(s16* dst, const s16* src, u32 n, const float* pal, float ls, float ss)
 *   positions / 6-byte normals: src s16 x y z idx (8 bytes, idx signed), dst s16 x y z (6 bytes).
 * void re4dc_sk1_s8(s8* dst, const s8* src, u32 n, const float* pal, float ls, float ss)
 *   small normals: src s8 x y z + u8 idx (4 bytes), dst s8 x y z (3 bytes).
 */
        .macro  SAT fv, back, sz
        fcmp/eq \fv,\fv
        bf      \back                   /* NaN: the C cast's word */
        cmp/pz  r0
        bt      1f
        .ifc    \sz,w
        mov     #-128,r0
        shll8   r0                      /* -32768 */
        .else
        mov     #-128,r0
        .endif
        bra     \back
        nop
1:
        .ifc    \sz,w
        mov     #127,r0
        shll8   r0
        or      #255,r0                 /* 32767 */
        .else
        mov     #127,r0
        .endif
        bra     \back
        nop
        .endm

        .macro  SK1 name, sz, idxext, o1, o2, dstep
        .text
        .align  2
        .global _\name
        .type   _\name, @function
_\name:
        tst     r6,r6
        bt      \name\()_ret0
        fmov.s  fr14,@-r15
        fmov.s  fr15,@-r15
        fmov    fr5,fr14                /* ls (-ml: float args pair-swapped, the first in fr5) */
        fmov    fr4,fr15                /* ss */
\name\()_loop:
        mov.\sz @r5+,r0
        lds     r0,fpul
        mov.\sz @r5+,r0
        float   fpul,fr0
        lds     r0,fpul
        mov.\sz @r5+,r0
        float   fpul,fr1
        lds     r0,fpul
        mov.\sz @r5+,r1                 /* idx */
        float   fpul,fr2
        \idxext
        fmul    fr14,fr0                /* x */
        shll2   r1
        fmul    fr14,fr1                /* y */
        shll2   r1                      /* x16 */
        fmul    fr14,fr2                /* z */
        mov     r1,r2
        add     r1,r1                   /* x32 */
        add     r2,r1                   /* x48 */
        add     r7,r1                   /* m */
        fmov.s  @r1+,fr3                /* m0 */
        fmov.s  @r1+,fr4                /* m1 */
        fmov.s  @r1+,fr5                /* m2 */
        fmul    fr0,fr3                 /* x * m0 */
        fmov.s  @r1+,fr6                /* m3 */
        fmul    fr0,fr4                 /* x * m1 */
        fmov.s  @r1+,fr7                /* m4 */
        fmul    fr0,fr5                 /* x * m2 */
        fmov.s  @r1+,fr8                /* m5 */
        fmul    fr1,fr6                 /* y * m3 */
        fmov.s  @r1+,fr9                /* m6 */
        fmul    fr1,fr7                 /* y * m4 */
        fmov.s  @r1+,fr10               /* m7 */
        fmul    fr1,fr8                 /* y * m5 */
        fmov.s  @r1+,fr11               /* m8 */
        fmul    fr2,fr9                 /* z * m6 */
        fmul    fr2,fr10                /* z * m7 */
        fadd    fr6,fr3                 /* x * m0 + y * m3 */
        fmov.s  @r1+,fr6                /* m9 */
        fmul    fr2,fr11                /* z * m8 */
        fadd    fr7,fr4
        fmov.s  @r1+,fr7                /* m10 */
        fadd    fr8,fr5
        fmov.s  @r1+,fr8                /* m11 */
        fadd    fr9,fr3                 /* + z * m6 */
        fadd    fr10,fr4
        fadd    fr11,fr5
        fadd    fr6,fr3                 /* + m9 */
        fadd    fr7,fr4
        fadd    fr8,fr5
        fmul    fr15,fr3                /* * ss */
        fmul    fr15,fr4
        fmul    fr15,fr5
        ftrc    fr3,fpul
        sts     fpul,r0
        exts.\sz r0,r2
        cmp/eq  r0,r2
        bf      \name\()_sx
\name\()_bx:
        mov.\sz r0,@(0,r4)
        ftrc    fr4,fpul
        sts     fpul,r0
        exts.\sz r0,r2
        cmp/eq  r0,r2
        bf      \name\()_sy
\name\()_by:
        mov.\sz r0,@(\o1,r4)
        ftrc    fr5,fpul
        sts     fpul,r0
        exts.\sz r0,r2
        cmp/eq  r0,r2
        bf      \name\()_sz
\name\()_bz:
        mov.\sz r0,@(\o2,r4)
        dt      r6
        bf/s    \name\()_loop
        add     #\dstep,r4
        fmov.s  @r15+,fr15
        fmov.s  @r15+,fr14
\name\()_ret0:
        rts
        nop
\name\()_sx:
        SAT     fr3, \name\()_bx, \sz
\name\()_sy:
        SAT     fr4, \name\()_by, \sz
\name\()_sz:
        SAT     fr5, \name\()_bz, \sz
        .size   _\name, . - _\name
        .endm

        SK1     re4dc_sk1_s16, w, nop, 2, 4, 6
        SK1     re4dc_sk1_s8, b, "extu.b r1,r1", 1, 2, 3
