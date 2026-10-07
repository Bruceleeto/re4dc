# Lane ln: a simpler native rendering pipeline for Leon (2026-10-05)

Experiment lane (LANE-BRIEF 2026-10-05). Branch exp/ln-20261005, worktree /root/probe/lanes-20261005/ln/tree, base
3f4b599d (r22 source). Proof of concept with the pass/fail threshold fixed before coding. Render only: the logic trace
stays STRICT; the renderer reads the matrices the game already computes (no reduced render skeleton).

Threshold (fixed by the brief, before coding): PASS if the prototype cuts Leon's attributable drawn-tick cost by >= 40 %
AND >= 1.5 hw ms on r100-h-fight, the look is equal on frame-locked frozen frames (same mesh: identical or within the
known 1 RGB565 noise, otherwise an off/on sheet), logic STRICT on H2, 0 MISALIGN. Stop rules: Leon < 2.5 hw ms per drawn
fight tick, or the design cannot reach the threshold on paper.

**Verdict: FAIL** (the 40 % criterion). Both knobs (LEON_NATIVE_PIPE=1 LEON_FACE_LAZY=1) cut Leon's attributable cost on
r100-h-fight from 7.711 to 5.525 hw ms per drawn tick: -2.19 ms = 28.3 % (needs 40 % = -3.08); r100-h-quiet -2.17
(27.6 %), perf-r101sq -2.30 (28.9 %). The >= 1.5 ms criterion is met. Exact: TA streams equal to knobs-off on every
compared frame, look equal, 0 MISALIGN, knob-off image byte-identical. H2: each knob alone STRICT; both together close
the radio call one tick later (the known wall-time sensitivity of that fixture), and STRICT once timing-matched (see
"Gates"). Details under "Result".

## Step 1: Leon's current drawn-tick cost in r22

Source: hwmodel runs of the r22 cost arm (route-build DBG_WARP=1 PACE_MODE=fast PC_SAMPLER=0 PACE_FORCE=2
ENC_CENSUS=1), arm ln-a = the int-cC2 build (its traced frames are identical to int-20261005/hwmodel-int-cC2-*: same
per-call cycles), rerun with a wider call-record watch list (kit/modesplit-ln.sh: owner_leon_palettes / bind,
actor_semantics, preflight, skin / texture leases, one_chunk, pass_positions, Part::whole / strips, avk kernels,
commonScreenMat, calcWeightMat, CalcSk1_x / x2, shape, lightSetEm, LightSetModel, ...). Evidence
D:\Flycast-Evidence\re4-dreamcast\ln-20261005\hwmodel-ln-a-{hf,hq,sq}. Attribution by call records and their call tree
(scratchpad leon3.py), not bucket.py's actor table. Records are deterministic per traced frame; frames whose records lost
or split a pass around a thread switch are dropped (hf: 4 of 6 kept, hq 6, sq 5). Totals of the arm match the r22
baseline once PACE/WAIT is excluded (hf 95.54 - 36.44 = 59.10, hq 49.84 - 6.23 = 43.61, sq 72.40 drawn).

hw ms per drawn tick (nominal model):

| component | r100-h-fight | r100-h-quiet | perf-r101sq |
|---|---:|---:|---:|
| P1 pass 1 (OT 0x11) re4dc_actor_transaction_draw | 3.813 | 3.768 | 4.005 |
| . plan (re4dc_actor_plan_leon = owner_leon_bind 0.24 + plan) | 0.275 | 0.275 | 0.312 |
| . palettes: second owner_leon_bind | 0.233 | 0.234 | 0.234 |
| . palettes: skin_bones + skin_groups (71 bones, 665 entries) | 0.309 | 0.312 | 0.317 |
| . palettes: finite scan of 7,980 palette floats (self) | 0.356 | 0.358 | 0.376 |
| . actor_semantics (29 chunk proofs + material certificate) | 0.150 | 0.151 | 0.235 |
| . preflight of all 21 runs (both passes) | 0.376 | 0.346 | 0.404 |
| . skin + texture leases | 0.056 | 0.049 | 0.067 |
| . submission: one_chunk x7 (kernels, emit, 1 window) | 1.715 | 1.714 | 1.700 |
| . submission: second preflight + run bookkeeping | 0.147 | 0.137 | 0.157 |
| . rest (identity, ledger, plan copies, record, modelviews) | 0.195 | 0.192 | 0.204 |
| P2 pass 2 (OT 0xB, hair: 14 runs, 2 materials) own | 2.330 | 2.580 | 2.368 |
| . actor_semantics again | 0.153 | 0.151 | 0.152 |
| . preflight again (14 runs) | 0.295 | 0.307 | 0.268 |
| . one_chunk x14 (incl. 14 window opens 0.21) | 1.674 | 1.887 | 1.731 |
| . rest (14 window closes, run bookkeeping, mv re-proof, release) | 0.208 | 0.235 | 0.217 |
| (PS2 world PT/TR flush triggered by the first hair run: world cost, excluded) | (3.382) | (2.089) | (3.440) |
| MR ModelRender + commonModelTrans overhead, both passes | 0.092 | 0.091 | 0.118 |
| TR Leon's emTrans (ModelTrans + commonScreenMat + lightSetEm) | 0.699 | 0.689 | 0.732 |
| . face (be_flag 2) CPU morph + skin: calcWeightMat, CalcSk1_x / x2, shape | 0.561 | 0.566 | 0.584 |
| WEP weapon in hand (4 skinned lit parts, FRONT_NATIVE), pass 1 + pass 2 | 0.776 | 0.742 | 0.724 |
| **Leon attributable total** | **7.711** | **7.870** | **7.947** |
| of which the owner passes P1 + P2 + MR | 6.235 | 6.439 | 6.492 |

Not counted: SKIN_PALETTE_LAZY / MODEL_PREP_KEEP already removed Leon's source palettes and model preparation; no Leon
shadow is drawn in these presets (DrawFootShadow 0.000, no shadow.cpp / mirror.cpp model draw); the skeleton, motion and
cloth are logic. The weapon is the second ModelRender of the 0x11 OT group (cObjWep copies pPL->ot_type = 7; 4 skinned
lit parts) and an empty ModelRender (LightSetModel only, 0.04) beside Leon in the 0xB group; its Trans (< 0.06,
SKIN_PALETTE_LAZY defers its palette to the draw) is not separable without a diagnostic and is left out.
perf-20261004 measured 3.7 + 2.0 on r21x; r22's two passes are 3.81 + 2.33. Stop rule (< 2.5 ms): not met.

## Step 2: the current path, per drawn tick

Trans: emTrans(Leon) -> ModelTrans: two OT entries (0x11 world, 0xB translucent), commonScreenMat: SKIN_PALETTE_LAZY
registers lazy palettes for the 7 unmorphed infos; the face info (be_flag 2) keeps the full CPU path (calcWeightMat,
MakeWeightPalette, ResetShape / CalculateShape_new, CalcSk1_x positions, CalcSk1_x2 normals) whose arrays only a
source draw of Leon reads: the owner path draws the face from its own bone palettes.

Render, OT group 0x11: ModelRender -> commonModelTrans -> re4dc_actor_transaction_draw (pass 1): identity + ledger
choice, re4dc_actor_plan_leon (owner_leon_bind: role bindings, revision, 2,856 finite tests on all 119 parts' mat and
lt_inv_mat), actor_plan_layout, actor_semantics (chunk proofs, live material certificate), actor_acquire (texture,
workspace and palette-arena leases, owner_leon_palettes = owner_leon_bind again + skin_bones + skin_groups + a finite
scan of every palette float, per-info modelviews, skin registry lease, preflight of all 21 runs), ledger choice 2,
ACTOR_PROOF_LEAN skip, then re4dc_actor_submit_owned_runs for the 7 pass-1 runs: preflight again, texture commit, one
TA_DIRECT window, one_chunk per run (one_qualifies, Frame (avk_build_all: screen x palette per entry), COARSE_GATE_ONCE
fog proof, constant lights, re4dc_avk_pos_skin_u16 per meshlet, constant colour fill, Part::whole / strips to the store
queue).

OT group 0xB: the same entry with choice 2 (pass 2): actor_semantics again, modelviews re-proved, the 14 hair runs
through re4dc_actor_submit_owned_runs: preflight again, re4dc_ps2_world_before_owned_tr (flushes the PS2 world PT / TR
pass before the first owned TR run: world cost), and a window open + close per run (the runs alternate the two hair
materials), then actor_release.

The irreducible work of the image: 71 bone matrices, 665 palette entries, 665 screen matrices, 3,660 skinned records
(2,313 + 1,347) through the vertex kernel, 8,211 emitted strip vertices (3,894 + 4,317), 15 TA headers. That is about
2.4 ms of the 6.2 ms the two passes cost; the rest is proofs, leases, repeated preflights, a second bind, the palette
scan and per-run windows. The data is already the pipeline the brief describes: offline pre-converted meshlets
(<= 128 records sorted by palette entry, u8 strips), one FTRV kernel per meshlet fed by the gameplay skeleton
(palette = skeleton x bind inverse x weights), constant light, store-queue submission.

## Design: LEON_NATIVE_PIPE (render only, exact)

Knob LEON_NATIVE_PIPE (game/native_model_registry.mk beside ACTOR_PROOF_LEAN, default 0; needs ACTOR_TRANSACTION=1,
COARSE_ONE_SUBMIT=1, ACTOR_VTX_KERNEL=1). =1: Leon's two owner passes go through a lean driver that calls the same
kernels with the same inputs in the same order, so the TA words are the same (same palettes, screen matrices, records,
strips, headers, run order). Anything the lean admission does not accept falls back to the existing path in the same
call, so a decline gives exactly today's decision. (No =2 check build was made: the knob takes 0 or 1; exactness was
proved with TA_HASH pairs instead, see "Result".)

1. Admission, pass 1 (replaces plan + bind x2 + palette scan + preflight x2 + skin lease):
   - bind-lite: owner_leon_bind's identity checks (role bindings, exact infos, binding revision, cached part list with
     the 0.01 lt_inv_mat test on a rebuild) and its finite test of all 119 parts' mat / lt_inv_mat as one integer
     exponent sweep (same decision, ~3 cycles a float instead of ~8). The Re4dcActorPlan is built once per binding.
   - actor_semantics minus the 29 immutable chunk proofs (compiled const arrays: proved once per binding); the live
     material certificate and every per-frame field test stay.
   - palettes: skin_bones + skin_groups unchanged; the per-float palette scan is replaced by a test of the 71 bone
     matrices T (finite and |x| < 2^120 / W, W = the largest sum of |weights| of an entry, computed once): a sufficient
     condition for finite palettes (an entry is a weighted sum of T). Failing it falls back to the full path, which
     decides as today.
   - textures: the same three leases (acquire, commit before the first header, release after pass 2); palettes in the
     same palette arena. No workspace lease (pass 1 completes in the call; pass 2 rebuilds its Frame), no skin registry
     lease (the driver hands each run its palette directly; Frames that borrowed it are invalidated at release).
2. Pass 1 submission: the 7 runs in one window as today, through one_chunk's body minus one_qualifies (the driver
   supplies the palette entry and source arrays).
3. Pass 2: the cheap per-pass re-checks (projection / viewport words, info list and flags, the 8 modelviews recomputed
   and compared, per-frame semantic fields, lifetime serial and binding revision unchanged since pass 1: the material
   certificate holds by ACTOR_PROOF_LEAN's audit, nothing else runs between the passes but render code), the PS2
   world barrier once, then the 14 hair runs in ONE store-queue window: a 32-byte header is sent at each material
   change (the material's header words and UV scale captured at its first window open; the TA receives the same
   header / vertex sequence as 14 windows send) and one Frame lookup for the shared role-7 palette.
4. Trans (LEON_FACE_LAZY, game/game30.mk, default 0, needs SKIN_PALETTE_LAZY=1; trans.cpp, model_bridge.cpp,
   shadow.cpp, mirror.cpp): ModelTrans's commonScreenMatSub for Leon's morphed face info allocates the arrays and runs
   the shape morph (ResetShape / CalculateShape_new: it holds a motion lease, so it stays where it was) as before, but
   defers calcWeightMat + MakeWeightPalette + CalcSk1_x / x2 (GQR6 is left in the eager path's end state). The first
   render read of those arrays (model_bridge.cpp re4dc_actor_model_buffers / re4dc_draw_model_part before the
   positions are taken, shadow.cpp and mirror.cpp before GXSetArray) runs them: same frame, same functions, same parts
   matrices (the SKIN_PALETTE_LAZY memo for calcWeightMat), g_gqr6 restored afterwards. When the owner path draws Leon
   nothing reads them. One pending face per frame, keyed on model id 0 (the player).

Expected saving by component, r100-h-fight (hw ms per drawn tick; from the Step-1 rows):

| component | now | lean | saving |
|---|---:|---:|---:|
| bind x2 + plan build | 0.508 | 0.07 | 0.44 |
| palette finite scan -> bone test | 0.356 | 0.015 | 0.34 |
| semantics pass 1 (chunk proofs once) | 0.150 | 0.10 | 0.05 |
| preflight x2 pass 1 + skin lease + run bookkeeping | 0.579 | 0.04 | 0.54 |
| pass-1 rest (identity, plan copies, record) | 0.195 | 0.05 | 0.15 |
| one_qualifies in the 21 one_chunk calls | 0.151 | 0 | 0.15 |
| semantics + preflight pass 2 | 0.448 | 0.02 | 0.43 |
| pass-2 windows (14 open/close -> 2 opens + 12 headers) | 0.242 | 0.04 | 0.20 |
| pass-2 rest (bookkeeping, mv re-proof, release) | 0.172 | 0.03 | 0.14 |
| face CPU morph + skin (Trans) | ~0.58 | ~0.01 | 0.57 |
| **expected total** | | | **~3.0-3.1 (39-40 %)** |
| pass-2 run loop (one Frame lookup, warm I-cache) and pass-1 per-run trims | ~0.52 | ~0.37 | 0.10-0.15 |
| **with the run loops** | | | **~3.1-3.2 (41-42 %)** |

Kernels, emit, palettes, screen matrices, the fog proof and the colour fill are unchanged (exactness); the PS2 world
flush stays where it is. On paper the threshold (>= 40 % = 3.08 ms, >= 1.5 ms) is reached with the run loops, by a
thin margin. Reserve if the measurement falls short: the weapon's four parts in one window (~0.1-0.2 of its 0.74),
and a kernel variant that stores the constant colour with the position (the separate colour fill misses the D-cache:
~0.1). Rejected: per-emitted-vertex transform straight to the TA (8,211 transforms instead of 3,660 plus a copy;
the near-clip decision needs the whole strip first), a reduced skeleton (not allowed here), linear inline vertex
streams (~66 KB more RAM for ~0.2-0.3 ms of kernel D-misses).

## Result (2026-10-05)

Commits (local on exp/ln-20261005, not pushed): 369c39d6 LEON_NATIVE_PIPE, 400c94b9 LEON_FACE_LAZY, and this document.
Both knobs default 0, neither is in the play recipe. Knobs off: base 3f4b599d and HEAD built with SOURCE_DATE_EPOCH
pinned (ln-e0 / ln-e1) are byte-identical (loadable image and sscrn.ovl); missing.txt empty in every build.

### Cost (hwmodel, r22 cost arm)

Arms: ln-a (base), ln-b1 (LEON_NATIVE_PIPE=1), ln-b2 (both knobs); evidence
D:\Flycast-Evidence\re4-dreamcast\ln-20261005\hwmodel-ln-{a,b1,b2}-{hf,hq,sq}. Same traced frames per preset (hf
0,1,3,4; hq 1,2,4,5; sq 1,3,4,5; B1 sq has 1,3,5, against A on 1,3,5 = 8.011). Leon's emTrans is found by its face path
(ResetShape stays in it with LEON_FACE_LAZY). hw ms per drawn tick:

| component | hf A | hf B1 | hf B2 | hq A | hq B1 | hq B2 | sq A | sq B1 | sq B2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P1 pass 1 | 3.813 | 2.661 | 2.659 | 3.751 | 2.732 | 2.739 | 4.051 | 3.044 | 2.881 |
| P2 pass 2 own | 2.330 | 1.768 | 1.828 | 2.612 | 1.973 | 1.986 | 2.315 | 1.814 | 1.830 |
| MR | 0.092 | 0.088 | 0.090 | 0.090 | 0.086 | 0.088 | 0.097 | 0.088 | 0.093 |
| TR Leon's emTrans | 0.699 | 0.700 | 0.125 | 0.684 | 0.693 | 0.111 | 0.735 | 0.743 | 0.157 |
| WEP weapon | 0.776 | 0.814 | 0.822 | 0.739 | 0.776 | 0.782 | 0.759 | 0.738 | 0.697 |
| **Leon total** | **7.711** | 6.030 | **5.525** | **7.876** | 6.260 | **5.706** | **7.958** | 6.427 | **5.658** |
| cut vs A | | -1.681 (21.8 %) | **-2.186 (28.3 %)** | | -1.616 (20.5 %) | -2.170 (27.6 %) | | -1.584 (19.8 %) | -2.300 (28.9 %) |

Whole drawn tick, work (total minus PACE/WAIT; includes the +-0.3-0.8 layout drift): hf 59.10 -> 57.33 -> 56.68, hq
43.61 -> 42.11 -> 41.45, sq 72.39 -> 70.68 -> 69.93 (B2: -2.42 / -2.16 / -2.46). Skipped ticks unchanged (hf 23.18 /
23.38 / 23.29).

Function level, hf A -> B2 (exclusive hw ms per drawn tick, frame total): one_chunk 0.636 -> one_chunk_core 0.556,
owner_leon_palettes -0.354, owner_leon_bind -0.279, one_qualifies -0.242, the face kernels re4dc_sk1_s16_loop -0.118
and re4dc_sk1_s8_loop -0.108, PSMTXConcat -0.120 (calcWeightMat), re4dc_actor_owned_source -0.107,
re4dc_actor_immutable_chunk_proof -0.102, re4dc_model_packet_reserve -0.091, re4dc_actor_preflight_owned_runs -0.089,
hash_bytes -0.082, image_key -0.082, re4dc_actor_role_bindings -0.067, re4dc_actor_texture_validate -0.061,
re4dc_model_packet_begin -0.059, actor_semantics -0.057; added: the lean pass-1 driver inlined in enc_transaction_draw
+0.132, re4dc_leon_pipe_submit +0.081, owned_run_load +0.072, (hq) re4dc_leon_direct_switch +0.050, (sq) find_skin
+0.091.

Why the paper estimate (-3.0..-3.2) missed by ~0.9 ms: pass 1 saved 1.15 of the 1.57 planned (the lean driver itself
costs ~0.5: the 2,856-word exponent sweep is 0.13 ms because the 119 cParts are scattered in memory, plus plan /
semantics / modelview / record and header-capture code); pass 2 saved 0.50 of 0.87 (one_chunk_core's per-run work
stays x14, owned_run_load, the header switch); Trans saved the planned 0.57 but the face morph (0.03, 0.10 when an
expression plays) stays. What remains of Leon's 5.53 ms on hf: the two submissions 3.29 (vertex kernel
re4dc_avk_pos_skin_u16 1.31 for 3,660 records, already a scheduled 37.5-cycle loop, 71 cycles a record measured with
palette switches and D-misses; emit Part::whole + strips 0.66 for 8,211 strip vertices; pass_positions 0.38 over 42
meshlets; one_chunk_core 0.33 over 21 runs; ~0.6 of per-run / per-material work), palettes 0.32, pass 1's own code
0.51 + preflight 0.09 + leases 0.05, pass 2's own 0.16, the weapon 0.82 (generic FRONT_NATIVE path: kernel 0.11, lights
0.17, emit 0.09, re4dc_actor_submit's own ~0.25), MR 0.09, TR 0.13. The listed reserves (weapon lean path
~0.2-0.3, per-run trims ~0.2, colour with position ~0.1, lt_inv_mat once per binding ~0.07) total ~0.6: still short of
-3.08 with the exact image; the rest is kernel and emit work the image needs, and a reduced render skeleton or a
non-exact emission is outside this prototype's rules. So the threshold is not reachable by this design.

### Exactness (TA_HASH pairs)

TA_HASH compares across builds need a polygon header's words 4-7 left out: KOS pvr_poly_compile leaves them as the
dirty-allocated cache line's padding, which is build-dependent (two runs of one build are identical; the unchanged
Ganado path differed between builds in exactly those words). With those words hashed as zero (temporary diagnostic, not
committed; /root/probe/lanes-20261005/ln/ta-hash-pad-mask.patch), every common frame is identical:
- LEON_NATIVE_PIPE=1 vs off: r100-h-fight 2,084 / 2,084 (dyn-dm1-hf / dyn-dm0-hf), perf-r101sq 2,241 / 2,241
  (dyn-dm1-sq / dyn-dm0-sq).
- both knobs vs off: r100-h-fight 2,084 / 2,084 (dyn-fh1-hf), perf-r101sq 2,241 / 2,241 (dyn-fh1-sq).
- the deferred face resolved by a source draw: r100-h-quiet with `late 0x10 1400 0x100` (Leon on the per-part source
  path from tick 1400), both knobs vs off: 2,376 / 2,376 frames, ~1,335 of them on the source path (dyn-fl1-hq /
  dyn-dl0-hq).

### Gates

- Look (frame-locked, CROWD_FREEZE_AT=1371 / AT2=2351, 40 s holds, r100-h-fight; dyn-fa-hf off / dyn-fb-hf both knobs):
  hold 1 identical (both framebuffers); hold 2 front buffer identical, the other buffer 3 pixels at 1 RGB565 step,
  which are exactly the two run-to-run states of one build (the same two hashes appear in the sk5 A/A pair
  dyn-sk5-lk-hf-a / -a2). Equal.
- MISALIGN: 0 (dyn-al2-hf: ln-b2, interpreter + HWTRACE_ALIGN=1, 900 s, past room frame 12,600).
- H2 (trace build + recipe, h2-v.json, 480 s, vs route-z-strict):
  - LEON_NATIVE_PIPE=1 alone (dyn-tp-h2) and LEON_FACE_LAZY=1 alone (dyn-tf-h2): STRICT (1450..1569, to 740, from 1218),
    whole room float drift only.
  - both knobs (dyn-t1-h2, rerun dyn-t1-h2b, identical to each other): FAIL. The radio-call sub screen closes at tick
    1218 instead of 1217, then everything is one tick late. The knobs-off control of the same base (dyn-t0-h2) is
    STRICT, and so is a knobs-off image with both knobs' heap start (dyn-tz-h2: 24,576 B of unread .bss, temporary), so
    neither the base nor the image size moves it. The call's end follows wall time (D367_THIRTY_FPS_ROUTE.md, r21v
    finding: a different-speed build shifts it by a tick). Both knobs make ticks 900..1200 19 vblanks faster (tp 15, tf
    5), enough to fit one more tick before the call ends.
  - timing-matched (the r21v procedure, with the delay on the faster arm): both knobs + LOGIC_TRACE_DELAY_US=1000
    (dyn-t1d-h2) and =1500 (dyn-t1e-h2) close the call at 1217 and are STRICT against route-z-strict on all four
    windows (whole room float drift only); against the knobs-off control dyn-t0-h2 every common tick (6,908 / 6,842)
    is identical apart from `om` in the 476 sub-screen swap ticks 741..1217. So the knobs change no logic; H2 across
    the call needs equal frame times. (dyn-t1d-h2 / dyn-t1e-h2 are kept on C:\Flycast-Evidence\re4-dreamcast\
    ln-20261005: D: was near its 10 GB floor.)

### Projection (console; not measured on hardware)

From the hf / hq / sq Leon cut and the r22 cost-arm pairs, with the brief's model (console = model x 1.107 fight /
0.937 house; VMU speed = 66.7 / (D+S) when above 66.7; fps = 15 x speed): r100-h-fight 82.28 -> 80.09 model ms, 91.1 ->
88.7 console ms, speed 0.732 -> 0.752, 10.98 -> 11.28 fps (+0.30); perf-r101sq (fight factor assumed) 98.54 -> 96.24,
109.1 -> 106.5, 9.17 -> 9.39 fps (+0.22); r100-h-quiet 66.85 -> 64.68 model ms, 62.6 -> 60.6 console ms: full speed
before and after, 2.0 console ms more margin.

### Notes for other lanes

- Matrix layout dependencies (lane fm): LEON_NATIVE_PIPE reads, each pass-1 call, the root m->pParts->mat (inverted for
  the palettes), every cParts' mat and lt_inv_mat as row-major 3x4 Mtx words (the exponent sweep; on a rebuild
  lt_inv_mat is checked against leon4k::bind within 0.01), bone_T = inverse(root) x parts[b]->mat x parts[b]->lt_inv_mat
  for the 71 skinned bones (re4dc_coarse_skin_bones' FTRV kernels assume that layout, translation in column 3),
  info->mat for the 8 modelviews and pG->Cam.v_mat. LEON_FACE_LAZY's resolve runs calcWeightMat at the draw: the root
  mat, every part's mat and bindMat, and the face's shape rates are read at Trans. Both assume the parts matrices are
  final at Trans and unchanged until the draw of the same frame.
- Ganado extension: not described (the verdict is FAIL). The per-actor proof / lease work this design removes for Leon
  (role bindings, identity, owned source, immutable chunk proofs, preflights, texture validation: ~0.9 ms per drawn hf
  tick in B2, now mostly the Ganados') is the same kind of work in the Ganado owner passes.


## 2026-10-07 bounded requalification on the accepted capacity stack

The original fixed 40% threshold and **FAIL** above remain unchanged. Current-stack testing found a modest
r101-square drawn/skipped model-pair gain of 1.738 ms (1.75%) for both knobs, with exact frozen images and
normalized TA/source-fallback output. It nevertheless fails required native-parts, ModelInit and createSat allocations
in both the untraced production-shaped run and H2; H2 first differs at tick 661 (43/42 enemies, 212/211 objects).
The later higher s30 free-heap reading does not establish safety after an actor failed allocation.

One face-only cabinet test adds 704 text bytes without moving the linked end, but yields only a derived
0.219 ms (0.60%) equal-mode tick gain with unmatched drawn subsets. It was not advanced to further qualification.
**Both Leon knobs stay off.** Accepted capacity-only runtime completes the 1971/2360/1175 New Game sequence
and reaches live r100 without required allocation failures. See [the requalification record](../D367_LEON_REQUALIFICATION_20261007.md)
for the rejected comparisons, corrected resource assessment, scopes, diagnostics and build identities.
