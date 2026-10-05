# Lane ln: a simpler native rendering pipeline for Leon (2026-10-05)

Experiment lane (LANE-BRIEF 2026-10-05). Branch exp/ln-20261005, worktree /root/probe/lanes-20261005/ln/tree, base
3f4b599d (r22 source). Proof of concept with the pass/fail threshold fixed before coding. Render only: the logic trace
stays STRICT; the renderer reads the matrices the game already computes (no reduced render skeleton).

Threshold (fixed by the brief, before coding): PASS if the prototype cuts Leon's attributable drawn-tick cost by >= 40 %
AND >= 1.5 hw ms on r100-h-fight, the look is equal on frame-locked frozen frames (same mesh: identical or within the
known 1 RGB565 noise, otherwise an off/on sheet), logic STRICT on H2, 0 MISALIGN. Stop rules: Leon < 2.5 hw ms per drawn
fight tick, or the design cannot reach the threshold on paper.

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
strips, headers, run order). =2 (check build): the existing path draws and the lean path draws again; both passes' TA
words are folded and compared per pass ("LNCHK" lines; the image draws Leon twice). Anything the lean admission does
not accept falls back to the existing path in the same call, so a decline gives exactly today's decision.

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
4. Trans (LEON_FACE_LAZY, game/game30.mk, default 0, needs SKIN_PALETTE_LAZY=1; trans.cpp + model_bridge.cpp):
   ModelTrans's commonScreenMatSub for Leon's morphed face info allocates the arrays as before but defers calcWeightMat
   + MakeWeightPalette + shape + CalcSk1_x / x2 (GQR6 ends in the same state). The first render read of those arrays
   (model_bridge.cpp, before p->positions takes pPosBuf: a source draw of Leon) runs them, same frame, same functions,
   same parts matrices (the SKIN_PALETTE_LAZY memo for calcWeightMat). When the owner path draws Leon nothing reads
   them. =2: eager build + lazy rebuild compared on every resolve. Matrix dependency for lane fm: parts[b]->mat,
   lt_inv_mat, the root pParts->mat, info->mat, pG->Cam.v_mat; the face shape rates are read at resolve.

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
