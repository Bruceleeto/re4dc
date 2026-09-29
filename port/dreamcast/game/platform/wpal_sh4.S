/* platform/wpal_sh4.S -- GAME_WPAL_FAST=3 (game30.mk; render only, exact): trans.cpp MakeWeightPalette's
 * entry loop as one SH-4 loop. Per entry, the same float operations in the same order as the C loop:
 *   m = 0 (all 12); for each weight j: rate = float(wht[j]) * 0.01f, or 1.0f - total for the last;
 *   total += rate; m[r][c] += s[r][c] * rate (s = the parts matrix id[j], one fmul then one fadd);
 * then the entry stored transposed (PSMTXReorder: d[c][r] = m[r][c]). The twelve sums stay in fr0-fr11
 * and two temps (fr14 / fr15) alternate, so a load, a multiply and an add of neighbouring elements
 * overlap (the compiled loop ran each element's load -> fmul -> fadd chain through one temp).
 * ABI: KOS -m4-single -ml, FPSCR.PR=0 SZ=0; saves r8-r9 and fr12-fr15.
 *
 * int re4dc_wpal_sh4(const Weight* w, int n, const float* mtx, float* dst): the weight count (sum of num).
 * Weight (trans.cpp): id[3] 0x00, num 0x03, wht[4] 0x04, 8 bytes; mtx = gx->mtx (48-byte 3x4 matrices);
 * dst = the palette (48 bytes an entry). n > 0.
 */
        .text
        .align  2
        .global _re4dc_wpal_sh4
        .type   _re4dc_wpal_sh4, @function
_re4dc_wpal_sh4:
        mov.l   r8,@-r15
        mov.l   r9,@-r15
        fmov.s  fr12,@-r15
        fmov.s  fr13,@-r15
        fmov.s  fr14,@-r15
        fmov.s  fr15,@-r15
        mov.l   .Lcent,r9               /* 0.01f */
        mov     #0,r2                   /* cnt */
.Lentry:
        mov.b   @(3,r4),r0
        fldi0   fr0
        extu.b  r0,r1                   /* weights left */
        fldi0   fr1
        add     r1,r2
        fldi0   fr2
        mov     r4,r3                   /* &id[j]; wht[j] at +4 */
        fldi0   fr3
        fldi0   fr4
        fldi0   fr5
        fldi0   fr6
        fldi0   fr7
        fldi0   fr8
        fldi0   fr9
        fldi0   fr10
        fldi0   fr11
        tst     r1,r1
        bt/s    .Lstore
        fldi0   fr13                    /* total */
.Lweight:
        mov.b   @r3,r0                  /* id[j] */
        extu.b  r0,r0
        shll2   r0
        shll2   r0                      /* x16 */
        mov     r0,r8
        add     r0,r0                   /* x32 */
        add     r0,r8                   /* x48 */
        dt      r1                      /* T: the last weight */
        bf/s    .Lrate
        add     r6,r8                   /* s */
        fldi1   fr12
        bra     .Lmac
        fsub    fr13,fr12               /* rate = 1 - total */
.Lrate:
        mov.b   @(4,r3),r0              /* wht[j] */
        extu.b  r0,r0
        lds     r0,fpul
        float   fpul,fr12
        lds     r9,fpul
        fsts    fpul,fr14
        fmul    fr14,fr12               /* rate = float(wht) * 0.01f */
        fadd    fr12,fr13               /* total += rate */
.Lmac:
        fmov.s  @r8+,fr14
        fmov.s  @r8+,fr15
        fmul    fr12,fr14
        fmul    fr12,fr15
        fadd    fr14,fr0
        fmov.s  @r8+,fr14
        fadd    fr15,fr1
        fmov.s  @r8+,fr15
        fmul    fr12,fr14
        fmul    fr12,fr15
        fadd    fr14,fr2
        fmov.s  @r8+,fr14
        fadd    fr15,fr3
        fmov.s  @r8+,fr15
        fmul    fr12,fr14
        fmul    fr12,fr15
        fadd    fr14,fr4
        fmov.s  @r8+,fr14
        fadd    fr15,fr5
        fmov.s  @r8+,fr15
        fmul    fr12,fr14
        fmul    fr12,fr15
        fadd    fr14,fr6
        fmov.s  @r8+,fr14
        fadd    fr15,fr7
        fmov.s  @r8+,fr15
        fmul    fr12,fr14
        fmul    fr12,fr15
        fadd    fr14,fr8
        fmov.s  @r8+,fr14
        fadd    fr15,fr9
        fmov.s  @r8+,fr15
        fmul    fr12,fr14
        fmul    fr12,fr15
        add     #1,r3
        fadd    fr14,fr10
        bf/s    .Lweight                /* T still dt's */
        fadd    fr15,fr11
.Lstore:
        add     #48,r7
        fmov.s  fr11,@-r7               /* d32 = m23 */
        fmov.s  fr7,@-r7                /* d31 = m13 */
        fmov.s  fr3,@-r7                /* d30 = m03 */
        fmov.s  fr10,@-r7               /* d22 = m22 */
        fmov.s  fr6,@-r7                /* d21 = m12 */
        fmov.s  fr2,@-r7                /* d20 = m02 */
        fmov.s  fr9,@-r7                /* d12 = m21 */
        fmov.s  fr5,@-r7                /* d11 = m11 */
        fmov.s  fr1,@-r7                /* d10 = m01 */
        fmov.s  fr8,@-r7                /* d02 = m20 */
        fmov.s  fr4,@-r7                /* d01 = m10 */
        fmov.s  fr0,@-r7                /* d00 = m00 */
        add     #48,r7
        dt      r5
        bf/s    .Lentry
        add     #8,r4
        fmov.s  @r15+,fr15
        fmov.s  @r15+,fr14
        fmov.s  @r15+,fr13
        fmov.s  @r15+,fr12
        mov.l   @r15+,r9
        mov     r2,r0
        rts
        mov.l   @r15+,r8
        .align  2
.Lcent: .long   0x3C23D70A
        .size   _re4dc_wpal_sh4, . - _re4dc_wpal_sh4
