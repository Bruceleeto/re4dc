! tools/game30/pmc_fsca/pmc_fsca_draft.s (lane fm 2026-10-05): one part of the GAME_ROT_FSCA loop
! (port/dreamcast/game/platform/pmc_fsca_sh4.S) in semantic order with its fixed registers, the input of
! lsched.py (a list scheduler under the hw model's issue rules, minisim.py). mkS.py wraps the schedule into the .S
! (header, prologue, slow path, fixups, loop tail, epilogue, constants):
!   python3 lsched.py pmc_fsca_draft.s --search 300 --out sched.s
!   python3 mkS.py sched.s ../../../game/platform/pmc_fsca_sh4.S
!   python3 minisim.py ../../../game/platform/pmc_fsca_sh4.S .Lpart .Ltail --loop 3    (issue cycles per part)
! Annotations after '!': 'uses' / 'defs' list the registers a branch target reads / writes (the slow path, the
! fixups); o_* are pseudo registers that only order instructions (the angle tests before the FP work on the
! angles, MOVCA before the stores).
mov.l   @(r0,r1),r9
mov.l   @(12,r1),r5
mov.l   @(16,r1),r6
mov.l   @(20,r1),r7
mov     r1,r2
add     #12,r2
fmov.s  @r2+,fr6
fmov.s  @r2+,fr7
fmov.s  @r2+,fr8
tst     r9,r9
movt    r8
neg     r8,r8
and     r1,r8
or      r9,r8
add     #127,r8
add     #117,r8
pref    @r8
add     #-64,r8
pref    @r8
add     #-32,r8
pref    @r8
mov     r8,r12
add     #-44,r8
pref    @r8
add     #-96,r8
pref    @r8
rotl    r5
cmp/hi  r10,r5
bt      .Lslow              ! uses r1 r9 defs o_sx
rotl    r7
cmp/hi  r10,r7
bt      .Lslow              ! uses r1 r9 defs o_sz
rotl    r6
cmp/hi  r10,r6
bt      .Lslow              ! uses r1 r9 defs o_sy
add     #-1,r5
add     #-1,r7
add     #-1,r6
fmov    fr6,fr9             ! uses o_sx
fmul    fr12,fr9
ftrc    fr9,fpul
fsca    fpul,dr0
float   fpul,fr9
fmov    fr9,fr10
fmul    fr13,fr9
fmul    fr14,fr10
fsub    fr9,fr6
fsub    fr10,fr6
fmov    fr1,fr9
fmul    fr6,fr9
fmul    fr0,fr6
fadd    fr0,fr9
fsub    fr6,fr1
cmp/hi  r11,r5
bf      .Lfixx              ! uses r1 defs fr9 r8
fmov    fr8,fr11            ! uses o_sz
fmul    fr12,fr11
ftrc    fr11,fpul
fsca    fpul,dr2
float   fpul,fr11
fmov    fr11,fr15
fmul    fr13,fr11
fmul    fr14,fr15
fsub    fr11,fr8
fsub    fr15,fr8
fmov    fr3,fr11
fmul    fr8,fr11
fmul    fr2,fr8
fadd    fr2,fr11
fsub    fr8,fr3
cmp/hi  r11,r7
bf      .Lfixz              ! uses r1 defs fr11 r8
fmov    fr7,fr4             ! uses o_sy
fmul    fr12,fr4
ftrc    fr4,fpul
fsca    fpul,dr4
float   fpul,fr10
fmov    fr10,fr15
fmul    fr13,fr10
fmul    fr14,fr15
fsub    fr10,fr7
fsub    fr15,fr7
fmov    fr5,fr10
fmul    fr7,fr10
fmul    fr4,fr7
fadd    fr4,fr10
fsub    fr7,fr5
cmp/hi  r11,r6
bf      .Lfixy              ! uses r1 defs fr10 r8
fmov    fr11,fr0
fmul    fr1,fr0
fmov    fr11,fr6
fmul    fr9,fr6
fmov    fr3,fr8
fmul    fr9,fr8
fmov    fr3,fr2
fmul    fr1,fr2
fmov    fr8,fr15
fmul    fr10,fr15
fsub    fr0,fr15
fmul    fr10,fr0
fsub    fr8,fr0
fmov    fr2,fr4
fmul    fr10,fr4
fadd    fr6,fr4
fmov    fr6,fr7
fmul    fr10,fr7
fadd    fr2,fr7
fneg    fr10
fmul    fr5,fr9
fmul    fr5,fr1
fmul    fr5,fr3
fmul    fr5,fr11
fmov.s  @r2+,fr8
fmov.s  @r2+,fr2
fmov.s  @r2+,fr6
fmul    fr8,fr3
fmul    fr2,fr15
fmul    fr6,fr4
fmul    fr8,fr11
fmul    fr2,fr7
fmul    fr6,fr0
fmul    fr8,fr10
fmul    fr2,fr9
fmul    fr6,fr1
mov.l   @(0,r1),r5
mov.l   @(4,r1),r6
mov.l   @(8,r1),r7
mov     r1,r3
add     #-40,r3
mov     r1,r4
add     #-88,r4
mov     r1,r8
add     #-105,r8
and     r13,r8
movca.l r0,@r8              ! uses o_sx o_sy o_sz
add     #32,r8
movca.l r0,@r8              ! defs o_mc
mov.l   r7,@-r3             ! uses o_sx o_sy o_sz o_mc
mov.l   r7,@-r4             ! uses o_sx o_sy o_sz o_mc
fmov.s  fr1,@-r3
fmov.s  fr1,@-r4
fmov.s  fr9,@-r3
fmov.s  fr9,@-r4
fmov.s  fr10,@-r3
fmov.s  fr10,@-r4
mov.l   r6,@-r3
mov.l   r6,@-r4
fmov.s  fr0,@-r3
fmov.s  fr0,@-r4
fmov.s  fr7,@-r3
fmov.s  fr7,@-r4
fmov.s  fr11,@-r3
fmov.s  fr11,@-r4
mov.l   r5,@-r3
mov.l   r5,@-r4
fmov.s  fr4,@-r3
fmov.s  fr4,@-r4
fmov.s  fr15,@-r3
fmov.s  fr15,@-r4
fmov.s  fr3,@-r3
fmov.s  fr3,@-r4
