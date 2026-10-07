# Alive-list capacity 512 validation — 2026-10-07

Runtime source is `6c7cc182c565de553e94dd4e7843ac1ac239519b`, based on accepted runtime `d20ba6fca3164c3bbc2948a9276fd00d6fde9c65`. `GAME_ATLIST_512` remains default **0** in this change. This document records the bounded candidate evidence; integration activation is separate.

## Scope and host checks

The knob grows the existing two ordered alive-list arrays from 320 to 512 pointers. It preserves head/generation invalidation, existing dirty-note candidate reuse, ordering and full-list fallbacks. `ATCHK_MAX=96` is unchanged; there is no new cache or collision approximation.

The extracted-source capacity test passes all eight capacity/list-check/cache-check combinations. It covers the actual 470-object case, dirty flag/radius wrappers beyond index 320, reorder, retirement/reuse, head change, manager isolation, dirty-ring 64/65 boundary, sequence wrap, capacities 320/321/511/512/513/600, shrink/empty transitions, and 96/97 candidate overflow. Omitted-invalidation negative controls detect the expected failures. All eight existing overflow combinations also pass. Tests are in `port/dreamcast/tests/test_atlist_capacity.py` and `test_atlist_overflow.py`; retained output is in `host-capacity.log` and `host-overflow.log`.

## Cabinet cost and limits

Both fresh performance builds use the corrected combined title fixture with identical r104 cabinet commands, `ACT_CAP=0`, `PS2_INTERIOR_ACTORS=2`, `GAME_ATLIST_OVERFLOW=1`, and `SOURCE_DATE_EPOCH=1791244800`. Pacing is fast/catchup2/cap1/force0. Logic/decision trace and trace delay are **0** in both performance arms. OFF program and overlay are byte-identical to the accepted prior CPU-on baseline.

The aligned SH-4 model records an instruction census for source frames 1200–1231 and eight consecutive full traces, 1200–1207. Each sample has four drawn and four skipped ticks.

| Nominal modeled cost | OFF ms | ON ms | Change ms |
|---|---:|---:|---:|
| Balanced sampled tick | 39.832 | 36.338 | −3.494 (−8.77%) |
| Drawn sample mean | 53.062 | 50.376 | −2.686 |
| Skipped sample mean | 26.592 | 22.288 | −4.304 |
| atchkCandidates self | 3.9747 | 0.1158 | −3.8589 |
| ObjHitCheck self | 0.5243 | 0.3608 | −0.1635 |

Direct collision self cost falls 4.0224 ms; changes elsewhere offset part of that saving. Wait self cost is 0.0123/0.0129 ms, yielding a work delta of −3.4946 ms. Sound watcher instruction counts remain 5041+24 per sampled tick. Both arms have zero required MISSING, HALT and MISALIGN reports.

These are **eight-sample means, not 32-frame timing means**. The OFF census contains 16 drawn/16 skipped ticks; ON contains 17/15 because cadence changes after 1214 and near 1228. A clear instruction-count gap classifies the census and agrees with every traced draw mode; parity is not extrapolated. The largest within-mode sample instruction deviation from its census is **4.28549%** (ON skipped). This is a representativeness caveat, not a timing confidence interval. Mode means are not exact source-frame pairs. No rendered-FPS, r101-square or physical-console performance claim follows from this sample.

Machine traces retain 528 candidate calls per arm. Existing successful cache copies increase 264→528; 264 complete 470-body fallback walks (124,080 visits) disappear. ObjHitCheck retains 40 calls × 470 objects = 18,800 visits through its existing array path. Exact PCs and disassembly are retained in `traversal-evidence.json` and the function disassembly files. Sparse live framebuffers show the same cabinet scene, Leon and two adjacent Ganados, with different animation phases; this is not pixel identity.

Fixture, command and corrected sound-bank hashes match, as do bank-3 copy size and source cue sequence. Bank SHA256 is `6f3f35c0e21e41b5f5239d33c42098d4faa6108e584e95f1f453af9ae2e26408`.

## Memory and build identity

The complete allocated-section audit finds `.data` **+1,536 bytes**, `.text` **−32 bytes**, and every other allocated section unchanged, including `.re4dc_char_data`. Payload grows 1,504 bytes. Linked `_end` grows 1,536 bytes (`8c3e8e9c`→`8c3e949c`); `_etext` remains `8c256062`. Full section sizes, flags, alignment, addresses, resolved knobs and program/overlay hashes are in `build-evidence.json`. All unresolved-symbol reports are empty.

| Build | ELF SHA256 |
|---|---|
| off | `593664830615152cae03fd3216987589a5abdec0aa6b77c41dfd1b2917873799` |
| on | `62439285204f7f4ca91144f338582fb0d7a59ffda2c135f374281cf363b4bd0e` |
| trace | `377114f813a59d4fad1d23bf06b3495bc4e0ac1dc9519260cc5fe75a8eb2de58` |
| check | `0888566d8ac92f6c6a37aa1660f7131d547cdfd3d373fa9ccd8bc870bb39972c` |
| swap-off | `bd8d031abcf2387ceb81b9a3a826a3dfb8faa2e90680f5d2e5b79f02ac7a31ca` |
| swap-on | `3289fbf47dc8236beab7faf74ff587c2dd83b6d3042818e124af655846472a1d` |
| swap-delay1k | `5b2f1eed348519925a3052e6e256e43eb5f8217fd4de776170dcdfcc4caf737d` |

`on` is the untraced production-knob twin. `trace` has ordinary logic/decision tracing. `check` has `ATCHK_LIST=2` and `ATCHK_CACHE=2`. Both swapped builds use schema 4, `LOGIC_TRACE_SWAPPED=1`, ownership 0 and 6144 spans. `swap-delay1k` adds the existing trace-only 1000 μs delay on ON. No swapped-memory or delay knob is enabled in production/performance binaries.

The production-knob s30 heap headroom is 4,096 bytes lower, 67,680→63,584. This is a measured resource cost. `ARENA_FIT=1` in `port/dreamcast/game/platform/mem.cpp:59–74` rounds `(room - reserve)` down to 4 KiB. Boot logs show pre-fit room falling by exactly 1,536 bytes (12,513,704→12,512,168), crossing one rounding boundary: arena size 12,365,824→12,361,728. Room-entry heap already falls by 4,096 bytes before asset loading, with the same native pack sizes. The original collector assumption that heap loss would be at most 1,536 bytes failed and is retained in `heap-assumption-failure.log`. The coordinator accepted the explicit 4 KiB cost after s30 and radio restoration passed, under the current heap-4 gate requiring full 340/340 playback and reported headroom. `heap-resource-evidence.json` preserves source, boot lines, arithmetic and disposition. No allocator change was made.

## H2: all outcomes retained

1. **Ordinary direct-memory comparison:** 5,700 shared records; only `om` differs for 475 records, 741–1215 (first `8b282948`→`63fecb48`). Required decisions match for 5,699 records. Pre 0–740 and post 1218–5699 are STRICT. This is not a whole-run STRICT pass. The ordinary tracer hashes object-parts bytes while the radio owns the borrowed region. Each arm restores its own 3,144,608-byte window with hash confirmation; those hashes are per-arm restoration evidence, not cross-arm equality.
2. **Matched swapped-memory pair, delay 0:** snapshot/restoration succeeds, but full state and required decisions FAIL. OFF closes the radio at 1214 and ON at 1215. The first discrete difference is `st` at 1214 (`223e147f`→`25fa147f`); all frames 0–1213 match. Coarse pace logs do not establish a precise faster/slower relationship. This failure remains recorded.
3. **Single authorized timing hypothesis test:** ON with the existing 1000 μs trace delay is compared against the exact retained swapped OFF. Both close at 1214. All 3,237 shared records, 0–3236, are canonical **STRICT**, and all required gameplay decisions are **MUST-IDENTICAL**. No extra field or interval is excluded; the canonical pre-existing render-bit mask remains 1 in both arms. Informational audio `sq` differs on 2 ticks, first 1341. Player/enemy maximum position drift and every required field difference are zero. The delay is a diagnostic hypothesis test, not measured speed compensation or a production change.

The qualified pair captures 2,621 exact read ranges (148,162 bytes) plus 20,968 bytes of index in the existing 2 MiB backing store. Spare capacity is 98,812/98,944 bytes; both log `restored=1`. All three movies present 1465/1465, 571/571 and 340/340 frames. Diagnostic s30 `heap_before` is 57,504 in both arms. Ordinary traced ON separately plays s30 340/340 at 67,584, unchanged from its ordinary traced control. No allocator-cause inference is made from these observations.

## Other gates

**Actual cabinet checker:** the longer replay observes the 470-object list and later peaks at 479 objects. Every reported mismatch/overflow counter is zero. Final ATL reports 229,376 synchronizations, 58,543,108 checked visits and 37 rebuilds. Final ATC reports 196,573 hits, 35 misses and 53,908 processed notes, mismatch 0. The collector initially assumed the maximum would remain exactly 470; its evidence-only assertion was corrected to require observed 470 and peak ≤512. No runtime change followed. This check build is not performance evidence.

**Bell:** all 6,370 shared records, 0–6369, are canonical STRICT and all 6,370 required gameplay-decision records are MUST-IDENTICAL against the accepted CPU trace. Full optional audio buckets remain in the result JSON.

**Untraced production-knob radio/resource gate:** all movies present 1465/1465, 571/571 and s30 340/340. s30 `heap_before` is **63,584**, versus **67,680** in the accepted untraced control. Scripted radio replay spans source 5518–6079 and restores 3,027,520 backing bytes with hash confirmation:

    subscreen backing: close area=8c814f40 restored=3027520 restore_us=233251 hash=5f326502 ok pool_free=634368

The final framebuffer is visually reviewed; exact paths and findings are in `cpu-capacity-radio-gate.json`. This proves return to rendered world/event processing after the fixture's scripted replay, not manual control or ordinary event order. All seven bounded runtime/diagnostic captures exit normally with no capture errors, required MISSING, HALT or MISALIGN. Final combined New Game remains deferred to the subsequent Leon integration.

## Evidence and boundaries

Private evidence root: `D:/Flycast-Evidence/re4-dreamcast/cpu-capacity-20261007/`. It retains the raw cost traces/projections, runtime captures, all failed and successful comparisons, `cost-evidence.json`, `traversal-evidence.json`, `build-evidence.json`, `fixture-evidence.json`, `runtime-evidence.json`, host logs and gate JSONs. Original executables are retained in the scenario captures. Owned generated disc images were retired only after completion and hash verification; manifests and disc hashes remain. No private assets, user VMUs or unrelated worktrees were cleaned.

This is bounded emulator/model evidence. It does not establish physical Dreamcast acceptance. No release, SD-card write or push was performed by this validation lane.
