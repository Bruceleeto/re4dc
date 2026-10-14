# Codex work integrated into dreamcast-port (lane/cx-integrate, 2026-10-14)

Codex (the external agent) stopped on 10-14 at about 10:18 UTC after hitting its usage limit. Claude is the only
lander. This page records what was brought in from Codex's private trees, which settings turn each part on, how far
Codex got with each part, and what Codex was planning to do next.

Map: `C:\Game Dev\Emulators\CODEX-INTEGRATION-PLAN-20261014.md` (inventory, lineage, conflicts).

Where the original work is kept:
- Every Codex tip that existed only in a detached worktree has a ref, `refs/archive/codex/*` in
  `/root/work/re4-dreamcast`. There are 76 of these refs.
- All Codex branches and archive refs are also in a bundle:
  `C:\Game Dev\Emulators\re4-cx-ch23-20261013\codex-archive-20261014.bundle`.
- The D59 working-tree diff, which Codex never committed, is saved as `re4-cx-ch23-20261013\D59-uncommitted.patch`.

**Defaults.** Every setting below defaults to 0. With all of them off, the test 10 recipe
(`tools/d367/test10s/t10s-build.sh tP`) builds a play image that is byte-identical to test 10 (`out-t10stP`). That
covers the ELF image, all six overlays and `syms.txt`, and it was checked after every step of the integration.

**What Codex's runs mean.** Every Codex runtime result is a Flycast or component result. None is a console
measurement, and every ms figure is modelled. "Component PASS" means one bounded scenario passed its own gates.

## Chains

| Chain | Setting(s) (all default 0) | Status (Codex seals; Claude gates on this branch) | Known failures / open | Next step Codex planned |
|---|---|---|---|---|
| **CH22/CH23 route, stage-1 FX, haze** (P = `f9362b85` + AIC2 `e640631f`, merged as `766da968`) | ROUTE_CH22, ROUTE_CH23, PS2_ENEMY_CH22_DIR / _CH23_DIR, PS2_FX_STAGE1 / _POPULATION / _ADDITIONS, PS2_FX_COMMON_HAZE, TEX_PAL4_ALPHA, ACTOR_GANADO_APP0_GRIP, ACTOR_GANADO_PS2_STUMP(_DIR), TRUCK_DIAG, NATIVE_MODEL_REGISTRY_BONES (96 is used only with ROUTE_CH23=1) | **Codex:** identity offP4..offP23. r101 chapter trace pair: 2,890 ticks, STRICT and MUST-IDENTICAL. Merchant r10d D10, component PASS. Luis 1195/0 plus face fix, component PASS. D9 stage-1 core prep qualified. **Claude:** merge identity PASS; 20 host tests PASS. | No full CH22/CH23 playthrough. STRICT is still open for r10e, r10d, r11e, r11f and r10f. r11d halts on module 63. Merchant Trade has never been exercised: the r112 approach reboots, 7 times so far. CH23 dual BGM does not fit. | Room-by-room STRICT, then merchant Trade, then a full chapter run. |
| **AIC2 audio** (phase 1 `2ef1a89f`, phase 2 host `e640631f`) | none. No game Makefile references `aica_bank_v2*`. | Host-only. `test_aica_banks_v2.py` PASS. | Not linked into the game. | Design for the source, queue and lock integration. |
| **Leon lighting D36** (`c909234c`, `b643056c`) | LEON_SOURCE_LIGHT; ACTOR_SKIN_RESERVE (P's 64-slot version, rebased onto origin's 80-slot LEON_SKIN_SLOTS registry) | **Codex:** on `b689f048`: identity, H2 STRICT, s30 340/340, r103 and New Game GDI all PASS. Modelled cost +6.6 ms in the house, +2.2 ms at the r101 cross. **Claude, on this branch with the test 10 recipe and both settings at 1:** H2 trace pair `cx2ctT`/`cx2dtT` (padded to the same `_end` 8c409bdc, `RE4DC_LOG_STOP_TICK=4700`) is STRICT, with `af` included and no masking. Decisions MUST-IDENTICAL; s30 340/340 in both arms; boat loop LEON-GC PASS and TEXCHK PASS. Evidence: `C:\Flycast-Evidence\re4-dreamcast\cxint-20261014\d36*`. | Changes the look: user-approved Leon design 1. Cost was not measured on console. | Decide by measured fps whether to turn it on in a test recipe. |
| **G1 Ganado death fade** (D34/D37: `47b9b86e` `fea3b1ed` `426145df`) | ACTOR_GANADO_DEATH_FADE | **Codex:** D37 component PASS (7 fade lifecycles; off = D26). | D34 (kind 1) was never exercised. No H2, siege-completion or visual-equivalence gate. | H2 plus a siege run with the setting on. |
| **Movie world arena D38/D38a + D33a** (`f2ae50bf` `c9401e97` `90e3631b` `0be83b23` `26b33613`) | MOVIE_WORLD_ARENA | **Codex:** D38a component PASS: S10 265/265, S11 321/321, pickup and window exit, on a god/source-damage fixture. With the setting off, `main_mem.o` is identical. | D33a fails when used alone; it needs D38. Shared memory code: review before turning it on. | Combined r11f run with the owner. |
| **UI polygon order D43** (`58929361` `195b862b` `b0a76015` `37d8f2e5`) | UI_POLY_ORDER | **Codex:** host gate, glyph PASS, H2 STRICT, GDI. The "You got the False Eye" pickup text is readable. | The MCHECK square TEX 2 failure and the inventory TEX failure at 1016 also happen with the setting off. | Check whether route PS2-world rooms (r100/r101/r103) show blank pickup text. If they do, D43 becomes a route-fix candidate. |
| **Core FX texture prep D31** (`8936ed2f` `fd7f1be2`; D58's copy `c6e23490`/`b2dd1dc5` is identical and was skipped) | FX_CORE_TEX_PREP (needs EFFECT_ROOM 1..7) | **Codex:** first-demand prep component PASS. | None of its own. | Enable together with the cabin (D58). |
| **Actor texture prep D49 → D53 → D52** (`e010572f` `ffea90fa`, `59cafb03` `ec7c0d49`, `dcfc0305` `fed10229`) | ACTOR_TEX_PREP(_DIAG), ACTOR_TEX_PREP_LEON, ACTOR_SKIN_OWNER_POOL (needs ACTOR_TRANSACTION=1; it is a make error together with ACTOR_SKIN_RESERVE=1), ACTOR_TEX_PREP_DRAW | **Codex:** D49 H2 STRICT plus GDI PASS. D52: square 120 s plus H2 PASS. D53: farm, H2 STRICT and GDI PASS. | D57 (D52+D53): **square TEX FAIL 2 at native 892** (9fe00ef7). It reproduces on D52 alone. The farm PASS at 10:08 was never sealed. The H2 off/on pair for D57 (`cx-H2-D57-combined-off/on-01`) was started but has no result. | VRAM_CENSUS on the square failure, then the D57 H2 pair. |
| **Skin diagnostic D51** (`3b1798a7` `b943ad9e` `8027fcd7`) | ACTOR_SKIN_DIAG (a compile error together with MCHECK_LEONGC=1) | Diagnostic only. Rebased onto the 80-slot registry: it instruments the plain acquisition path, and origin's MCHECK_LEONGC copy is left unchanged. | none | Only needed while chasing skin-slot refusals. |
| **Cabin r11c D39 → D55 (+D31 = D58)** (`704d4e2e` `1829ce27` `c51f79fa` `b6604616` `24000082` `4e809c37` `b19f63e2` `47752217`; the duplicate ModuleMemFree `1b6c795f` was dropped) | CABIN_SOURCE, CABIN_HANDOFF_DIAG, CABIN_COMPLETE_HANDOFF, FX_CORE_TEX_PREP; MOVIE_WORLD_ARENA as a prerequisite | **Codex:** D55: movie 2296/2296, UI close unblocked, Luis 600/600 (component), but **TEX FAIL at 3636** (441a0cca). D54 diagnostic sealed. D58 links are sealed, with off = D55 on. **The checkpoint name says "D58runtimePASS", but no seal or log exists, so D58 counts as pending.** | TEX FAIL 3636. D39b presentation continuity. The missing Luis pair a333b301-0ad86c86. AICA block10. The cabin chain has no matched H2. Active-display capture is needed, because fb0 stills cannot prove continuous movie display. | Seal `cx-r11c-D58-combined-fx-01` (exact D55 fixture), then a matched H2. |
| **r200 world owner D30 → D41, D44, D46, D47** (`97c861f7` `539dee84` `8eb918f4` `60197572` `cbdd582f` `720910ac` `085b919e` `7c498dc8`, `9a899bcf` `5d1c0b9b`, `13e5736e` `e757ef03`, `56e34e47` `4bb6131e` `7b389fbb` `a9a2d5a3` `17de4936`; `215d27b8` = P's `f9362b85`) | PS2_WORLD_SOURCE_OWNER, PS2_WORLD_SOURCE_TEX_PREP, PS2_WORLD_PREFLIGHT_DIAG (D44), PS2_WORLD_TRANSITION_PIN (D46), PS2_WORLD_TRANSITION_OWNER (D47) | **Codex:** D41 (`720910ac`/`085b919e`/`7c498dc8`) component PASS: chapter ending plus save prompt, VMU save PASS, normal title Load PASS. D44 is diagnostic only (cause found). D47 links are sealed, and its off identity was repaired by `a9a2d5a3`/`17de4936`. | **D46 (PS2_WORLD_TRANSITION_PIN) was a REJECTED trial**: the pin moves the failure to 634fe733. It stays at 0 and is kept only because D47's sources reference the setting. **D47 is not accepted**: runtime v3 passes save and door09, but the owner DECLINEs with reason14 on frames 4733..4736 (members 0, callbacks 0). r202 assets are absent. | "D60" bounded diagnostics before the callback walk, to explain reason14. This was never written. Then the reload scenario `cx-r200-D47-reload-01`, following the plan sealed in `D47-normal-reload-plan-v1` (seal 1451b7cf). |
| **r11f owner D45 → D56 → D59** (`99a2be11` `0072501d` `d8e1e2e8` `5820aeaa` `9026754a` `8747691b`, plus the D59 patch as `558fa909`) | PS2_WORLD_R11F_OWNER, PS2_WORLD_R11F_CONTEXT_DIAG; MOTION_BOUNDED_R11F and NATIVE_MODEL_REGISTRY_IMMUTABLE_ALIAS (r11f motion and registry, in P) | **Codex:** D45 links are sealed, but the owner was **never entered** (0 R11FOWNER rows). D56 diagnostic: the predicate rejects the pre-swap window. D59 had a host review only (`D59-source-host-review-v1`) and was never linked. Codex built the r11f owner on its A-line copies of r200 D30–D41 and never together with D47 (see "Conflicts"). | The owner has never run. The outside view runs at about 2.7 Flycast fps. Ashley's native ownership and the r11f→r10f door are open. `test_movie_world_arena.py` fails on Codex's own D56 tree too, because the r11f guard comes before the arena guard in `re4dc_ps2_mesh_draw`. | Build fresh D56/D59 owner-off baselines, then the enabled D59 candidate. A true owner-off (OWNER0) identity check is a separate later gate: D56's off build was OWNER1/DIAG0. |
| **Vegetation / TA material diag** (`549f39a7` `f6e45f55` `df54ee7b` `a6e97116` `22b81a69` `78752eeb` `259d0aae` `40255557` `6f908e44` `a4ac7409`) | TA_MATERIAL_DIAG (tahash.mk; needs TA_HASH=1, TA_BIN_DIAG=1, and so RENDER_OPTION=0, because RES_MODES excludes TA_BIN_DIAG); PS2_PT_VARIANT_CRC=176921082 (r100 candidate package; a make error together with PS2_R100_SMX=1) | **Codex:** W6/W7/W8 and D5a cross pair qualified. Foliage TR→PT is about 10.7% in r101 and about 27% in r100 (modelled). MCHECK_PT parser v2 (`6f908e44` also changes `tools/d367/mcheck/pt_check.py`; `test_pt_audit.py` PASS). | Waits on the **user's approval of the stills**. W9 and PAL4D2/D3 were rejected and not brought in. | The user's decision. |
| **Luis fixture tools/docs** (`30dabe82` `ae47b026` `12a095ee` `2039775c` `f03b28df` `5e94b7ea`) | none: docs and offline tools | n/a | n/a | n/a |
| **Weapon-target overflow (Claude, not Codex)** `89f5b377` | WEP_TARGET_GUARD (1 = WepTarget[20] at emMineHitCk/obj1bHitCk, 2 = 1 plus WEPTGT log lines) | Knob off: identity PASS. With =1, only `emMineHitCk` and `obj1bHitCk` change. Route count: a full-play gate with a WEP_TARGET_GUARD=2 twin (`FP_TWIN_EXTRA`, fullplay-20261014\cxwep-092637, all 19 segments from New Game to the chapter 2-1 end, PASS) logged 0 `WEPTGT` lines. No overflow on the test 10 route. The gate does not count how often these callers run (mines, arrows, thrown spears), so this does not prove the later chapters are safe. | Luis's own caller is fixed only under ROUTE_CH22 (`402dd372`, in P). | Turn it on after the WEPTGT route count and gates. |

## Not brought in (rejected, obsolete, or held for Codex)

- **D35 as a stage.** The commit `cbdd582f` stays, because D41 (`720910ac`) is built on it. The D35 linked candidate
  and run were superseded by D41.
- **D25/D28/D30/D32** as separate stages. They are superseded, and their code is part of the D41 chain.
- **W9, PAL4D1/D2/D3** (rejected: the problem was fragmentation, not the palette).
- **LeonD4** (rejected).
- **The old lighting lane** `c7f45a3f`, `bc91eedb`, `12ac83b7`, `4ea89b75`, `7f3c142c` (frozen D5), superseded by D36.
- **Villager lighting D5 matrix** (`296a1bf8` GANADO_ONE_LIGHT): waits on the user's choice.
- **Duplicate ModuleMemFree** `80fcc8de` (D42) and `1b6c795f` (D39 prerequisite): origin already has `c9052efb`.
- **Duplicate actor-prep compile fix** `8ef4d985`/`4b4df79d`, the same change as P's `f060ba7f`.
- **A-line re-created copies:** `c5f13659`, `d7d6c25c` (context variants of P's commits) and `7bfac5fe…ca7c4375`
  (copies of r200). B's versions were used instead.
- **Old 10-06..10-12 Codex trees and the 10-12 dirty trees.** They are already on origin; their settings exist there.
- **PS2 world recipes and first-pass tools** (the `85e7da5d` lineage: `e417cb19` `3ff0928b` `90606dcf` `7ce8c218`,
  castle `6f53933e` `acc13b27` `c093f63f`, first-pass `8bf46efe` `e084c80a` `0ccd6986` `5a01a9a2`). Codex owns world
  builds, so these are held for Codex. They are tools only and are not part of any runtime chain. They are kept by
  branches and archive refs.

## Conflicts resolved in this integration

Each resolution is also written into its commit message.

- **D36 vs P's ACTOR_SKIN_RESERVE.**
  - Took D36's `native_actor_skin_reserve.inc`: a batch of at most 64 keys, inside either the 64-entry or the
    80-entry table.
  - Kept P's CH22 cabin-Luis exception in `sourceActorNativeOwner`.
  - `test_actor_skin_reserve.py` now runs D36's harnesses for slots 64/80 × MCHECK_LEONGC 0/1, plus P's nomination
    harness for LEON_SKIN_SLOTS 0/1: 72 PASS.
- **D53 pool vs D36 reserve.** `ACTOR_SKIN_OWNER_POOL=1` replaces the registry that the reserve indexes. Turning
  both on is now a make error: otherwise `trans.cpp` would link to a silent missing-symbol stub.
- **D51 vs origin's MCHECK_LEONGC SKINACQ copy.**
  - The D51 instrumentation applies only to the plain acquisition path.
  - The MCHECK copy is unchanged.
  - Turning both on is a compile error.
- **Movie arena (A line) vs r200 source owner (P/B)** in `native_static.cpp`, `native_ps2_world.cpp`, `native_ui.cpp`
  and `main_mem.cpp`. The arena refusals come first, which is Codex's own A-line order. A MemReplaceHeap refusal
  returns before the retained-OT publication.
- **Cabin vs D41** in `main_mem.cpp`. The cabin carrier refusals run before the retained-OT capture and free.
- **r11f owner vs r200 D47** in 7 files: `ps2_source_world.h`, `native_static.cpp`, `native_ui.cpp`, `main_mem.cpp`,
  `scroll.cpp`, `trans.cpp`, `trans_ot.cpp`. Codex never built these two together.
  - The owner checks are kept as parallel guards, r200 first.
  - The retained-OT guards are widened to `SOURCE_OWNER || R11F_OWNER`.
  - The dynamic-slot bypass tests both claims.
  - D47 already carried D45's generalized postlude guard, so the copy added again by `5820aeaa` was removed.
  - The second `SourceWorldModelScope` was removed (`2402df63`).
  - Compile/link checks with the settings on (cx6o1..o5) all link with an empty `missing.txt`. These cover:
    - r200 + D44 + D36 + G1;
    - actor prep + r11f + arena + D43;
    - cabin + D31 + D51;
    - both world owners;
    - r200 + cabin + the Ganado set.
- **Vegetation PS2_PT_VARIANT_CRC vs origin's PS2_R100_SMX.** VARIANT_CRC becomes an `#elif` after SMX, and turning
  both on is a make error.
- **`audio_aica.cpp` (cabin) vs origin's LEON_HAND_PACK.** The clash was only adjacent declarations. The cabin's
  stream-claim suppression does not touch the hand AICA cache.

## Host tests (WSL, this branch)

- **PASS (26):**
  - actor skin reserve, tex prep, tex prep draw, visibility diag;
  - aica banks v2, fx core source prep, leon source light;
  - Luis nomination, target capacity, TEV group;
  - native ui, pal4 alpha;
  - source world r200, retained, r11f context;
  - ps2 enemy ch22/ch23;
  - Luis coverage and mask runs, merchant robe;
  - the ps2 fx recipe/phase/prepare tests;
  - pt audit.
- **Need fixture arguments** (not run standalone): stump, cabin complete handoff, motion bounded r11f, source world
  r11f/native, r11f route movies, Luis generator/pack, fx common source records.
- **Need numpy** (not installed in WSL): ps2 cast sections, ps2 luis, ps2 vegetation candidate.
- **Fail the same way in Codex's own trees:**
  - `test_actor_skin_owner_pool.py` and `test_actor_tex_prep_leon.py`: no 32-bit multilib headers on this host
    (`-m32`: `bits/c++config.h`).
  - `test_movie_world_arena.py`: fails on Codex's D56 tree too.
  - `test_motion_residency.py`: fails on origin itself.
