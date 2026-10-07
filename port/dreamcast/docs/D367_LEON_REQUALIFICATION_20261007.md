# Leon requalification — 2026-10-07

## Outcome and scope

**Both `LEON_NATIVE_PIPE` and `LEON_FACE_LAZY` remain off.** The full pair has a modeled gain and passes its visual comparison, but fails required model/collision allocation and gameplay checks. The bounded face-only fallback has too small a derived net benefit to justify further qualification. No allocator, reserve, model, asset, or rendering architecture changes were made.

This freshly assesses the existing implementations on accepted capacity-512 source `96e0f20c3c13571fda90b96f8a0a91a452d04ebe`. It does not change lane ln's original **FAIL** against its fixed 40% attributable-Leon-cost threshold. The later assessment considered a useful whole-frame gain only if current uncapped gameplay, resources and visuals also passed. This documentation change activates neither knob.

## Cost and comparability

Performance arms use `ACT_CAP=0`, `GAME_ATLIST_512=1`, `GAME_ATLIST_OVERFLOW=1`, `PS2_INTERIOR_ACTORS=2`, `DBG_WARP=1`, `PC_SAMPLER=1`, trace/decision trace/delay off, and normal fast pacing (`PACE_FORCE=0`). `SOURCE_DATE_EPOCH=1791244800`. Current corrected title assets/audio are identical between arms. Fresh OFF BIN/overlay and every allocated ELF section/address/payload match accepted capacity ON; only three nonallocated debug sections differ in the fresh full ELF.

The initial r104 cabinet test executes the **pl08** owner and cannot establish a pl00 native-pipeline gain. The following r100 house-fight pair is **not comparable**: room-frame 900 occurs at global ticks 1563/1562, later player positions differ, and sampled actor transactions are five/six. Its raw costs are retained without a gain or regression claim.

The replacement `perf-r101sq` fixture enters r101 directly with its existing source-clock inputs and no house intro/radio boundary. Source 2300–2307 has four drawn/four skipped traces per arm, with a 2300–2331 instruction census. All seven logged positions/status/room flags, sampled modes, and nine actor transactions per drawn tick match. ON actually executes the pl00 native pipeline.

| SH-4 model, r101 square | OFF ms | Both ON ms | Change ms |
|---|---:|---:|---:|
| Drawn sample mean | 73.180 | 71.301 | −1.879 |
| Skipped sample mean | 26.261 | 26.402 | +0.141 |
| Drawn + skipped means | 99.441 | 97.703 | **−1.738 (−1.75%)** |
| Pair with explicit wait self time excluded | 99.4160 | 97.6791 | −1.7369 |

Each 32-count census has clearly separated 16/16 instruction bands. Only eight traces have direct draw-entry proof; the other 24 mode assignments are inferred. Sample means differ from band means by OFF −0.30%/−0.64%, ON −0.34%/−0.087% (drawn/skipped). Largest individual skipped-sample excursions are 6.52%/6.69%, retained rather than claimed below 5%. These bounded modeled costs are not physical-console timing, rendered FPS, or a 30 fps claim.

## Required memory and gameplay failure

The full pair adds **15,492 allocated bytes** (text 10,912, character data 4,576, constructors 4) and moves the linked end by **24,576 bytes**. The fitted source arena and untraced first/second movie entry heaps lose the same 24 KiB. Later s30 `heap_before` is 73,440 versus control 63,584, but this is **not** resource-acceptance evidence: a required actor had already failed allocation.

The first radio collector checked complete movies/backing restoration but omitted required-allocation scanning. Expanded review corrects that insufficient assessment. The **untraced** full-pair run logs native-parts backing failures, `ModelInit()  Parts allocate was failed.`, and `alloc[2a0]:free[760] atari.cpp(2621)` / `createSat() memory alloc failed.` The accepted capacity untraced reference has none of these failures. Source `ModelInit` releases model info and returns failure; the failed `createSat` allocation also returns failure. This is a production-shaped failure, not merely trace overhead.

H2 independently fails at the same transition. After the complete 571-frame r100s20 movie and exact tick 660, tick **661** first differs: reference/candidate RNG `b190`/`b98e`, enemies **43/42**, objects **212/211**, and required line-query decisions **318/304**. Immediately before it, source heap is 21,920/2,720 and candidate logs failed parts/model allocation plus `alloc[2a0]:free[6c0] atari.cpp(2621)` / `createSat() memory alloc failed.` Movie-terminal ordering, killed-enemy sequence and global/room mapping match, so a completion-clock shift is not evidenced at the first difference.

The complete comparison is **FAIL / MUST-DIFFER on 3237 common ticks, 0–3236**, without missing/duplicate records. Both radio closes are tick 1214 and backing restores. H2 uses the accepted reference's `LOGIC_TRACE_SWAPPED=1`, `LOGIC_TRACE_OWNERSHIP=0`, `LOGIC_TRACE_SPANS=6144`, `LOGIC_TRACE_DELAY_US=1000`, and existing canonical render masking. No new field/interval exclusion, delay retune, reserve or allocator change was attempted.

All 1465/571/340 movie frames uploaded/presented; untraced replay restored its full 3,026,944 saved bytes with matching hash. Those narrower passes do not override failed model/collision construction. Native movie staging retry messages present in accepted controls are retained separately.

## Visual success belongs to the rejected pair

A private `TA_HASH=1` diagnostic normalizes only words 4–7 of **one 32-byte normal packed-color polygon header**, with a valid opaque/translucent/punch-through list and no modifier bits. Float/intensity headers, sprites, vertices, bulk/unknown packets, other words and full word counts remain in the comparison. KOS header construction was checked and 42 predicate cases pass. Raw hashes/header counts are retained. This patch is absent from production/gameplay builds.

Both visual arms use `PACE_FORCE=2`, requested freezes 1371/2351 held 40 seconds, then `late 0x10 2400 0x101`. Actual next-drawn freezes are **1372/2352**, holding source **1371/2351**. Both framebuffers at both holds are pixel- and file-identical: **four comparisons, zero changed pixels**, without a noise allowance.

All **2,527 common normalized TA frames (1–2527)** match: 1,293 before/1,234 after source fallback. Raw hashes differ on 2,342 frames; that is retained alongside the narrow padding normalization, with no additional field/interval exclusions. The existing read-only PC sampler loses zero records. After source tick 2400, ON has 171/156/23 samples in s8/s16 skin/weight-palette kernels whose return addresses lie inside `re4dc_face_lazy_resolve`, proving active deferred face work on the source path. These are samples, not call counts/costs. This pass is not transferred to the face-only arm.

## Bounded face-only fallback

`LEON_NATIVE_PIPE=0 LEON_FACE_LAZY=1` adds **704 text bytes and zero linked-end bytes**. One r104 cabinet run covers source 1200–1207 plus the 1200–1231 census against retained capacity control. Nonprogram payloads/audio match; additional removal of already-absent `dc/dbgslot.txt` is metadata only. Raw entry checks verify every sampled mode and five actors/pl08 owner on drawn ticks. Neither cost arm logs allocation failures.

OFF has four drawn/four skipped samples; FACE has five/three. Drawn means are **50.376→49.344 ms**, skipped means **22.288→22.882 ms**. Derived equal-mode mean **36.332→36.113 ms (−0.219, −0.60%)** is not another measured window. The raw mean increase is composition-biased, not a regression claim. This small net benefit with unmatched drawn subsets is insufficient; no further face-only tests were made and it remains off.

## Final accepted-runtime startup

The final New Game run uses verified fresh **OFF** runtime/current title assets: both Leon knobs 0, capacity 512 on, `DBG_WARP=1`, `PC_SAMPLER=1`, normal pacing, no trace/delay/TA hash/freezes. It uploads/presents all **1971/2360/1175** intro frames, reaches live rendered r100, exits its owned emulator normally, and has **zero required model/atari/work-backing allocation failures**. Retained post-intro framebuffers were inspected. This automated startup twin is separate from a clean DBG=0 local-disc boot and physical-console acceptance. No Bell result for either rejected Leon candidate is claimed; accepted capacity Bell evidence remains in its separate record.

## Build identities

| Role | ELF SHA-256 |
|---|---|
| Fresh OFF / final New Game | `22a9c7efbc6e625f7116533e7246eae607b2c8b96e390fa97c731fbf84ad9d85` |
| Rejected full pair, untraced | `d5f0555a2f3e3e58e2fc264be287669e1f9f75fb6c735071fe2583d54617654e` |
| Face-only bounded cost | `8dd520e840eaf7a5203c13d9893f22a4d690d2f3b80f922e7b8eac5bf3c3e81e` |
| Private fixed-cadence TA OFF | `64e084d07b8d8113d39a3f4c8df50eade5140101b3622917d3e44c586d6fbde0` |
| Private fixed-cadence TA pair | `129e48a41569089e21e158656c9392267ccd289f767ef001710277ae4001e600` |
| Rejected full-pair H2 | `8622ac80c0af1947d4fe4bfb6b99dc61e00848af9e21f56d13026d71b644a2c5` |
| Accepted capacity H2 reference | `5b2f1eed348519925a3052e6e256e43eb5f8217fd4de776170dcdfcc4caf737d` |

Private evidence set `leon-next-20261007` retains raw traces, failures, fixtures/manifests, executables, frozen frames and corrected resource assessments outside Git. Only completed, hash-verified generated disc images were retired. This docs-only change contains no game payload, release or SD package.
