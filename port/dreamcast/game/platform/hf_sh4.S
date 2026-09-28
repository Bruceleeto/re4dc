/* Exact common-layout Hermite loop, GAME_HF_ASM. ABI: -m4-single, PR=SZ=0.
 * r4=HermitePrm, r5=Vec out, r6=u16 history[3]. Return 0 on success or -1
 * after restoring output/history for the unmodified C fallback. No calls.
 * Caller admits only even key addresses and layouts 0/5/6. Invalid history
 * and exhausted searches use the original C path, including its error log
 * and persistent cross-axis stale-pair behavior. Never replace that behavior.
 * Preserve r8-r14, fr12-fr15. Local bytes 0..31 hold original pointers/data;
 * 32 is decode mode (0 exact key, 1 blend, 2 clamp). 36 local +44 saved=80 B.
 */
        .text
        .align 2
        .global _re4dc_hf_run
        .type _re4dc_hf_run,@function
_re4dc_hf_run:
        mov.l r8,@-r15
        mov.l r9,@-r15
        mov.l r10,@-r15
        mov.l r11,@-r15
        mov.l r12,@-r15
        mov.l r13,@-r15
        mov.l r14,@-r15
        fmov.s fr12,@-r15
        fmov.s fr13,@-r15
        fmov.s fr14,@-r15
        fmov.s fr15,@-r15
        add #-36,r15
        mov.l r5,@(0,r15)
        mov.l r6,@(4,r15)
        mov.l @r5,r0
        mov.l r0,@(8,r15)
        mov.l @(4,r5),r0
        mov.l r0,@(12,r15)
        mov.l @(8,r5),r0
        mov.l r0,@(16,r15)
        mov.w @r6,r0
        mov.l r0,@(20,r15)
        mov.w @(2,r6),r0
        mov.l r0,@(24,r15)
        mov.w @(4,r6),r0
        mov.l r0,@(28,r15)
        mov r5,r14
        mov r6,r13
        fmov.s @r4+,fr1                 /* mutable frame */
        fmov.s @r4+,fr2                 /* maxFrame */
        mov.l @r4+,r11                  /* flags */
        mov.b @r4,r10                   /* type */
        add #4,r4
        mov.l @r4,r12                   /* key header */
        mov #12,r9
        tst r10,r10
        bt .Lh_stride
        mov r10,r0
        cmp/eq #5,r0
        bf .Lh_stride6
        bra .Lh_stride
        mov #6,r9
.Lh_stride6:
        mov #4,r9
.Lh_stride:
        mov #3,r8
        fldi0 fr0
        fldi0 fr3
        fldi0 fr4
.Lh_axis:
        mov.w @r12+,r7
        extu.w r7,r7                    /* n / search count */
        mov r12,r3                      /* frames */
        mov r7,r0
        shll r0
        add r0,r12
        mov r12,r4                      /* data */
        mul.l r9,r7
        sts macl,r0
        add r0,r12                      /* next axis */
#if RE4DC_HF_PF
        mov #1,r0
        cmp/gt r0,r8
        bf .Lh_no_pref
        pref @r12
.Lh_no_pref:
#endif
        mov r7,r5
        add #-1,r5                      /* last */
        mov #0,r0
        mov.l r0,@(32,r15)
        fcmp/gt fr2,fr1                 /* maxFrame <= frame, NaN false */
        bt .Lh_max
        fcmp/eq fr2,fr1
        bf .Lh_index
.Lh_max:
        mov r11,r0
        and #6,r0
        cmp/eq #4,r0
        bt .Lh_wrap
        mov #2,r0
        bra .Lh_index
        mov.l r0,@(32,r15)
.Lh_wrap:
        fsub fr2,fr1
        mov r11,r0
        tst #8,r0
        bf .Lh_index
        mov #0,r0
        mov.w r0,@r13
.Lh_index:
        mov #0,r6
        mov r11,r0
        tst #8,r0
        bf .Lh_validate
        mov.w @r13,r6
        extu.w r6,r6
.Lh_validate:
        cmp/gt r5,r6
        bf .Lh_valid
        bra .Lh_cold
        nop
.Lh_valid:
        mov.l @(32,r15),r0
        cmp/eq #2,r0
        bf .Lh_search_init
        mov r5,r6
        mov #0,r1
        bra .Lh_decode
        nop
.Lh_search_init:
        mov r6,r0
        shll r0
        mov r3,r2
        add r0,r2
.Lh_search:
        mov.w @r2,r0
        extu.w r0,r0
        lds r0,fpul
        float fpul,fr3
        fcmp/eq fr1,fr3
        bf .Lh_between
        mov #0,r1
        mov #0,r0
        bra .Lh_decode
        mov.l r0,@(32,r15)
.Lh_between:
        fcmp/gt fr3,fr1
        bf .Lh_step
        mov r6,r1
        add #1,r1
        cmp/gt r5,r1
        bf .Lh_next_in_range
        mov #0,r1
.Lh_next_in_range:
        mov r1,r0
        shll r0
        mov.w @(r0,r3),r0
        extu.w r0,r0
        lds r0,fpul
        float fpul,fr4
        fcmp/gt fr1,fr4
        bf .Lh_step
        mov #1,r0
        bra .Lh_decode
        mov.l r0,@(32,r15)
.Lh_step:
        mov r11,r0
        tst #1,r0
        bf .Lh_back
        fcmp/gt fr1,fr3
        bt .Lh_back
        add #1,r6
        add #2,r2
        cmp/gt r5,r6
        bf .Lh_search_more
        mov #0,r6
        bra .Lh_search_more
        mov r3,r2
.Lh_back:
        add #-1,r6
        add #-2,r2
        cmp/pz r6
        bt .Lh_search_more
        mov r5,r6
        mov r5,r0
        shll r0
        mov r3,r2
        add r0,r2
.Lh_search_more:
        dt r7
        bf .Lh_search
        bra .Lh_cold                     /* stale pair: original C handles */
        nop
.Lh_decode:
        mul.l r9,r6
        sts macl,r0
        add r4,r0                       /* key i0 */
        mul.l r9,r1
        sts macl,r1
        add r4,r1                       /* key i1 */
        tst r10,r10
        bf .Lh_decode_int
        /* type0 is only 2-aligned: compose words, never issue unaligned long. */
        .macro HF_F32 base, offset, dst
        mov \base,r2
        add #\offset,r2
        mov.w @r2+,r3
        extu.w r3,r3
        mov.w @r2,r2
        shll16 r2
        or r3,r2
        lds r2,fpul
        fsts fpul,\dst
        .endm
        HF_F32 r0,0,fr5
        HF_F32 r1,0,fr6
        HF_F32 r0,8,fr7
        HF_F32 r1,4,fr8
        bra .Lh_decoded
        nop
.Lh_decode_int:
        mov.w @r0,r2
        lds r2,fpul
        float fpul,fr5
        mov.w @r1,r2
        lds r2,fpul
        float fpul,fr6
        mov r10,r2
        mov #5,r3
        cmp/eq r3,r2
        bf .Lh_type6
        add #4,r0
        mov.w @r0,r2
        lds r2,fpul
        float fpul,fr7
        add #2,r1
        mov.w @r1,r2
        bra .Lh_int_scale
        nop
.Lh_type6:
        add #3,r0
        mov.b @r0,r2
        lds r2,fpul
        float fpul,fr7
        add #2,r1
        mov.b @r1,r2
.Lh_int_scale:
        lds r2,fpul
        float fpul,fr8
        mov.l .Lh_scale,r2
        lds r2,fpul
        fsts fpul,fr9
        fmul fr9,fr5
        fmul fr9,fr6
        fmul fr9,fr7
        fmul fr9,fr8
.Lh_decoded:
        mov.l @(32,r15),r2
        mov #2,r0
        cmp/eq r0,r2
        bt .Lh_value
        mov r11,r0
        tst #8,r0
        bf .Lh_no_hist
        mov.w r6,@r13
.Lh_no_hist:
        tst r2,r2
        bt .Lh_value
        /* hfHermite: each rounded operation and summation order preserved. */
        fmov fr1,fr10
        fsub fr3,fr10
        fmov fr4,fr9
        fsub fr3,fr9
        fdiv fr9,fr10                    /* t */
        fmov fr10,fr11
        fmul fr10,fr11                   /* t2=t*t */
        fmov fr11,fr12
        fmul fr10,fr12                   /* t3=t*t2 */
        fmov fr12,fr13
        fadd fr12,fr13
        fneg fr13
        mov.l .Lh_three,r0
        lds r0,fpul
        fsts fpul,fr0
        fmul fr11,fr0
        fadd fr0,fr13                    /* h01=-(t3+t3)+3*t2 */
        fmov fr12,fr14
        fsub fr11,fr14                   /* h11=t3-t2 */
        fmov fr14,fr9
        fsub fr11,fr9
        fadd fr10,fr9                    /* h10=h11-t2+t */
        fmov fr13,fr15
        fneg fr15
        fldi1 fr0
        fadd fr0,fr15                    /* h00=-h01+1 */
        fmov fr5,fr0
        fmul fr15,fr0
        fmov fr6,fr15
        fmul fr13,fr15
        fadd fr15,fr0
        fmov fr7,fr13
        fmul fr9,fr13
        fadd fr13,fr0
        fmul fr8,fr14
        bra .Lh_store
        fadd fr14,fr0
.Lh_value:
        fmov fr5,fr0
.Lh_store:
        fmov.s fr0,@r14
        add #4,r14
        add #2,r13
        dt r8
        bt .Lh_done
        bra .Lh_axis
        nop
.Lh_done:
        bra .Lh_return
        mov #0,r0
.Lh_cold:
        mov.l @(0,r15),r1
        mov.l @(8,r15),r0
        mov.l r0,@r1
        mov.l @(12,r15),r0
        mov.l r0,@(4,r1)
        mov.l @(16,r15),r0
        mov.l r0,@(8,r1)
        mov.l @(4,r15),r1
        mov.l @(20,r15),r0
        mov.w r0,@r1
        mov.l @(24,r15),r0
        mov.w r0,@(2,r1)
        mov.l @(28,r15),r0
        mov.w r0,@(4,r1)
        mov #-1,r0
.Lh_return:
        add #36,r15
        fmov.s @r15+,fr15
        fmov.s @r15+,fr14
        fmov.s @r15+,fr13
        fmov.s @r15+,fr12
        mov.l @r15+,r14
        mov.l @r15+,r13
        mov.l @r15+,r12
        mov.l @r15+,r11
        mov.l @r15+,r10
        mov.l @r15+,r9
        mov.l @r15+,r8
        rts
        nop
        .align 2
.Lh_scale: .long 0x38d1b717              /* 0.0001f */
.Lh_three: .long 0x40400000
        .size _re4dc_hf_run,.-_re4dc_hf_run
