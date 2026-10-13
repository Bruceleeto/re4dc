# Contextual RE4 VMU implementation plan — 2026-10-12

Status: historical planning snapshot. Implementation is now in this isolated worktree; current mappings, tests and limitations are recorded in [VMU_IMPLEMENTATION_20261012.md](VMU_IMPLEMENTATION_20261012.md).

The statements below describe the pre-implementation planning checkpoint.

The first deliverable is the contextual docked LCD: Leon vitals, Ashley escort/playable status, and real Hunnigan calls. The detached specimen game is a separate executable and milestone. The existing preview supplies pixel references and behavioral fixtures, not live game inputs or a native VMU program.

## 1. Isolated checkout and input authority

- Worktree: `/root/probe/codex-vmu-plan-20261012/tree`.
- Windows access: `\\wsl.localhost\Ubuntu-24.04\root\probe\codex-vmu-plan-20261012\tree`.
- Pinned base: `d4bc5f45362c8de3ed2549328a0bc97d9f71a8c0`, observed test-8 HEAD when this worktree was created. Integrating later requires checking intervening source changes.
- Authoritative handoff: `C:\Game Dev\Emulators\re4-vmu-handoff\re4-vmu-handoff`. The second directory level contains the files; this supersedes the earlier empty-folder observation.
- Read `README.md`, `IMPLEMENTATION_SPEC.md`, `VALIDATION.md`, `assets/README.md`, the preview, generated assets and the supplied coding-session prompt. The current human request is to plan; the embedded prompt's implementation instructions describe a future implementation session.
- Handoff manifest SHA-256: `7305ad8a8f5c3ac81a5bca0d72940d7c2d7f0aaefa169b1246dda5bbfe7a5207`.
- Preview SHA-256: `4098ceb03e232c083401d4197a14811617f9f86dadf988ca705f33ce5857d50f`.
- Private host-check evidence and disposable handoff copy: `/root/probe/codex-vmu-plan-20261012/out/`; full result `handoff-validation.json` and rerun driver `validate_handoff.py`.

Keep authoritative source on the case-sensitive WSL filesystem (`src/Tools` and `src/tools` coexist). This planning change is one untracked document. No production source, build defaults, original handoff assets, saves or active checkout files were changed. No target build, emulator session, VMU write, commit or publication was performed.

## 2. Visible behavior and fixed boundaries

Preserve the handoff's exact binary artwork. Ashley and Hunnigan each have two complete 48×27 portraits. Leon has four 48×27 growth layers, confined to the specified right-side region. Compose them into a full 48×32, 192-byte frame; never submit a 162-byte portrait directly. Use the supplied custom font and restored ECG geometry instead of KOS's default text font for these screens.

The bottom five rows always identify and show the **active playable character's health**. Escort Ashley does not transfer health ownership; playable Ashley does. Resolve typed, subject-specific urgent conditions before an active Hunnigan call, then Ashley context, then Leon vitals. On clearing a call or alert, resolve the latest complete snapshot rather than restoring an old bitmap.

Health, infection and specimen progression are independent. Derive infection from verified saved story state; a timer, damage, healing or specimen interaction must not advance it. Commit a newly resolved story stage before its finite visual transition; canceled animations cannot undo it. Re-snapshot after load, reset, character change, room transition and reconnection.

Initial docked work introduces no filesystem writes or save-format changes. Existing save/configuration behavior remains owned by its current implementation. Do not add a persistent reduced-motion setting just for this feature; use one if the project already exposes it, otherwise ship a static initial renderer and an optional build-time animation control until an appropriate setting is defined.

## 3. Current source map and integration findings

All source paths in this table are relative to this pinned repository.

| Input or owner | Verified source | Implementation consequence |
|---|---|---|
| Active character and HP | `include/global.h:249`; `src/game/pl_sub.cpp:55` (`PlSelect`); `src/game/player.cpp:192` | `pG->pl_type` selects the player; read signed `pl_life` and `pl_life_max` for the active character. `PlSelect` exchanges the life maxima and resets the active life field on a switch. Do not read `ashley_life` merely because Ashley is controlled. |
| Health condition | `src/game/pl_class.cpp:1057` (`cPlayer::getLifeLevel`); `src/game/cockpit.cpp:262` | The original HUD uses this condition function. Its thresholds use base HP (1200 Leon, 600 Ashley), not the upgraded maximum or the preview's 51/26-percent boundaries. Use this meaning for FINE/CAUT/DNGR; HP <= 0 adds DEAD. The bar still uses actual current/max HP. Validate upgraded health and exact boundaries separately. |
| Loaded ammo and whether it is displayed | `src/game/item.cpp:2780`; `src/game/cockpit.cpp:552`, `:633`; `include/item.h:128` | `ItemMgr.bulletNum()` supplies the equipped count; the original HUD has a weapon/state visibility policy and supports three digits. Keep finite/hidden/infinite/unknown states distinct. Do not clamp a real count to 99 or display a hidden counter as zero. |
| Ashley presence/status | `src/game/cockpit.cpp:393`; `src/game/pl_npc.cpp:3951` (`SubCharGetCondition`); `src/game/read.cpp:671` | Follow/wait are bits 1/2; other bits describe special conditions. Respect actual Ashley identity, including costume handling, and distinguish Luis/other companions. HELP requires auditing the originating rescue/capture/assistance state, not treating every nonzero bit as urgency. |
| Death/failure | `src/game/game.cpp:1197` (`gameDiedemoCheck`) | Player and partner failure are distinct. Display observes their existing rules without triggering or changing them. Active-player critical/dead must not select Ashley by a generic urgent boolean. |
| Actual radio lifecycle | `src/game/sscrn.cpp:897`, `:1010`, `:1016`; `src/Sscrn/ss_term.cpp:856`, `:924`, `:969` | Use the real terminal/call enter, end, skip and cleanup paths. A stored last call number is not evidence that a call is currently active. Clear observation state on every abort/reset path. |
| Radio identity | `src/Sscrn/ss_term.cpp:680` (`partnerType`); `src/game/sscrn.cpp:878` (`OpeOwTypeSet`); `include/sscrn.h:121` | Real call numbers, partner types and `ope_ow_type` exist. The entire identity table has not been validated against displayed participants. Only verified Hunnigan calls may select her portrait; do not infer caller identity from a function named `hunniganModelInit`. |
| Story/infection | saved globals/scenario flags; no verified four-stage adapter located | Build an explicit, source-evidenced event/flag table for Clear/Stirring/Branching/Advanced, including suppression/removal and loading older saves. Unknown remains explicit in the adapter; never expose the preview's Branching fixture as live state. |
| Coherent update point | `src/game/main.cpp:241-321`, especially after `TaskScheduler()` | Publish one read-only snapshot on the game thread after simulation advances, including render-skipped ticks. Main/subscreen/movie loops need a lifecycle audit; a gameplay-only callback must not leave a call stuck or fail to paint while the terminal owns execution. No game-pointer dereferences from Maple callbacks. |
| Existing LCD writers | `port/dreamcast/game/pace.cpp:285`; `port/dreamcast/game/dbgslot_bridge.cpp:132` | Both currently choose the first LCD and submit directly. One shared submission owner is needed before enabling contextual pages alongside them. |
| Speed-page selection | `port/dreamcast/game/platform/quality.h:63`, `quality.cpp:99`; `pace.cpp:315` | The existing `RE4DC_SPEED_VMU` setting explicitly requests the performance page. Preserve it as a diagnostic override; turning it off reveals contextual output. Do not silently rewrite stored settings. |
| Controller/LCD routing | `port/dreamcast/game/platform/pad.cpp:449`; current `maple_enum_type` calls | Controller channels are enumerated; their ordinal must not simply be assumed to equal physical port. Select the LCD attached to the actual gameplay controller. Define deterministic slot selection and rescan on reconnect. Save-device selection is a separate concern. |
| Existing storage | `port/dreamcast/game/platform/card.cpp`, `vmu_store.cpp`, `lz_small.cpp`, `vmu_dialog_session.inc`; `game/vmusave.mk` | Reuse existing Maple contention handling and preserve worker-owned CARD operations, A/B replacement, capacity/error handling and the save container. Docked LCD needs none of these formats changed. |
| Capture helper | `port/dreamcast/tools/flycast-harness/read_vmu_lcd.py` | Existing helper decodes a 192-byte KOS buffer but hard-codes the PACE `v_lcd` symbol. Extend symbol selection for the new shared framebuffer when implementing. Reading main RAM proves composition only, not Maple delivery or physical orientation. |

The pinned KOS implementation at `/root/work/kos-re4dc-d367/kernel/arch/dreamcast/` was also inspected. `util/vmu_fb.c:166` uses row-major, MSB-first pixels, compatible with the handoff's logical packing. Its `vmufb_present` orientation rule chooses the ordinary or 180-degree-rotated LCD call from controller/VMU connector direction. `hardware/maple/vmu.c:333` uses a try-lock, copies 192 bytes into the Maple frame and queues it; busy returns `MAPLE_EAGAIN`. Reuse this behavior with the return code visible. Source inspection does not substitute for the asymmetric-pattern hardware test.

## 4. Proposed implementation shape

Keep the feature small and local. Proposed new paths under `port/dreamcast/game/` are `vmu_context.h/.cpp` for snapshot resolution and native scheduling, `vmu_render.h/.cpp` for pure logical rendering, and `platform/vmu_lcd.cpp` plus its header for shared submission. Names may follow existing conventions during implementation; no new framework or rendering engine is needed.

The snapshot contains validity, a lifecycle generation, active character, signed current/max HP, original condition, ammo kind/count, companion identity/condition, typed urgency and subject, real call identity/activity, and a story stage with an explicit validity flag. It owns values rather than pointers into room, player or subscreen allocations. The selector is pure and returns display mode, subject, health owner, status and committed stage.

The renderer accepts the resolved state and bounded visual phase, and writes exactly 192 logical bytes. It does not read gameplay globals, allocate memory, access files, call RNG or send Maple traffic. Use fixed-width data and static buffers; the original four portrait and four growth bitmaps total **1,296 bytes**, excluding font, metadata and code. Two full frames require **384 bytes**. A provisional **2 KiB mutable-state budget** is an implementation target, not a measured footprint; report map-file ROM/BSS/stack totals before integration. Leave the 3,564-byte specimen art out of the docked binary unless it is actually used.

Specific design choices:

- **Ammo:** preserve the supplied header for 0–99. For larger finite counts, replace the cartridge icon region with the full right-aligned number; five 3-pixel digits plus spacing can fit in a 19-pixel header span without touching the LEON label or growth region. Measure actual supplied glyph widths in a host test. Use an explicit `INF` only for verified infinite-ammo semantics; hidden counters remain hidden. Unknown is neither zero nor infinity. These additional production cases need their own golden fixtures.
- **Urgent screens:** use the existing subject-appropriate portrait/vitals and compact status; do not invent additional portrait assets. Player danger/death retains the active player as subject. HELP only represents verified Ashley assistance/rescue conditions. Unsupported playable characters need an honest neutral/disabled contextual page rather than a mislabeled LEON screen; later character artwork is outside this handoff.
- **Animations:** first reproduce static final states. Then add one finite scheduler for pulse, blink, speaking and growth reveal/retract. A new generation invalidates stale work. Resolve committed state first and render the final state after interruptions/reconnect. Speaking animation is illustrative unless a real speaking hook is proven; call presence is not a claim of audio synchronization.
- **Update rate:** event/change-driven output, with a proposed upper limit of 10 submissions/s during finite animations. Static frames send only on change or reconnect. Compare 192 bytes before submitting. This is a starting policy, not a physical-bus performance result.
- **Maple failure:** never wait for the LCD. On busy, keep only the newest pending frame and retry at a bounded interval. After repeated busy/error results, back off; no retry spin or queue of obsolete frames. Invalidate cached device references on removal and send a fresh snapshot on reconnect. Use suitably aligned buffers for the existing rotated path's 32-bit accesses.
- **One LCD owner:** debug-operation feedback has a short explicit lease; an explicitly selected performance page overrides normal contextual output; otherwise contextual output wins. Expiration recomputes the latest context. The diagnostic producers submit candidate frames through the same adapter instead of continuing independent direct writes. Preserve their old behavior exactly with the feature disabled. Normal save I/O retains Maple priority through the existing try-lock/contention behavior.
- **No new persistent state:** derive infection on load; do not write a second infection value into the save. Do not add docked state to `RE4DCCFG` for this first milestone.

Add a default-off `VMU_CONTEXT=0` build option (generated `RE4DC_VMU_CONTEXT`) and compile new units/assets only when enabled. Guard observation hooks so the off build preserves original program bytes and existing diagnostic writers. Shared PowerPC builds must preprocess out the port-only hooks and pass the repository's comparison checks if recovered files change.

## 5. Implementation sequence and exit evidence

| Stage | Concrete work | Required exit evidence |
|---|---|---|
| A. Preserve reference and native renderer | Copy the authorized custom bitmaps/font with provenance; pure 48×32 drawing; fixture adapters for the reference preview; static screens and packing. | Pixel-exact **25 docked golden frames** (15 Leon + 8 original portrait/call + 2 low-health portrait), source-array equality, clipping/strip bounds, every digit, positive-HP minimum pixel, zero/dead, invalid max HP and production ammo cases. The other 24 goldens belong to the separate specimen renderer. |
| B. Live state and priority | Read active HP/ammo and companion state; instrument genuine terminal lifecycle; build typed alerts and story mapping; add lifecycle generation and finite animations. | Snapshot/selector transition tests and runtime observations for actual inputs; loaded/suppressed/reversed story stages. Every mapping cites a producing source path. Unknown inputs stay explicit. Full docked acceptance waits for required story/caller/HELP mappings. |
| C. Shared LCD transport | Route contextual, PACE and debug pages through one output owner; select actual controller/slot; apply existing orientation rule; bounded retries and reconnect. | Fake-transport tests for busy/error/removal/latest-frame behavior; off-build byte identity; focused target build; correct coexistence with existing speed setting and debug-save feedback. |
| D. Integration acceptance | One isolated test build with exact knobs and asset hashes; extend capture helper; exercise ordinary play, call, escort/playable Ashley and lifecycle cases with disposable evidence. | STRICT game-state/logic comparison for display-only changes; host/emulator/physical results labeled separately; observed frame cost, submit rate and memory increase. No performance-benefit claim is expected for this feature; establish bounded overhead. |
| E. Standalone specimen | Separate native-VMU project, toolchain, executable/package, input and scheduling; preserve the 22-frame discovery/molt loop. | Native build/run and install evidence, all six action orders, payoff timing, cancellation and committed growth, input behavior and physical detached execution. Durable progression only after its separate format/install design. |

Proposed touched files are the new small units above; `game/Makefile` and a small VMU build fragment; `pace.cpp` and `dbgslot_bridge.cpp` for shared submission; narrowly guarded game-loop/reset and terminal lifecycle hooks; isolated native-render/state tests; and the existing LCD observation helper. Reuse `ItemMgr`, `getLifeLevel`, `SubCharGetCondition` and existing terminal events. Do not alter collision, AI, RNG, simulation cadence, caller audio timing or save logic to make the display easier to drive.

The first useful implementation checkpoint is a native host renderer matching the 25 docked fixtures plus the live-state adapter skeleton. The first hardware checkpoint is an asymmetric corner marker and one exact portrait through the shared adapter. Neither checkpoint alone completes the contextual feature.

## 6. Acceptance cases that matter

1. Leon alone → Ashley follow → wait → genuine help → resume; Leon's HP remains the strip owner throughout escort. Switching to playable Ashley uses active `pl_life`, correct max and original condition rules.
2. Hunnigan call starts and ends normally, is skipped, fails during open, or resets during playback. A non-Hunnigan call never inherits her portrait. Context changes during the call are reflected on exit.
3. Leon critical during an Ashley context selects a player alert; Ashley help during a call interrupts it; a call that ends under an alert does not reappear when the alert clears.
4. Upgraded HP tests demonstrate that condition labels follow original base thresholds while bar length follows actual maximum. Zero/negative HP is dead/empty; missing maximum never divides by zero or displays sample health as real.
5. Loaded ammo 0, 1, 9, 10, 99, 100 and every supported larger count; hidden weapon state; verified infinite mode; character with no conventional weapon counter. No silent clamping or unsupported-glyph omission.
6. Infection changes and decreases finish exactly at one of four supplied bitmaps; rapid changes, scene switch and reconnect cancel old visuals while preserving newly resolved state. An older loaded save wins over any pre-load visual state.
7. No device, two slots, removal during animation/call/save, reconnect on another physical port, device busy, and repeated errors cannot block gameplay or flood Maple. Reconnect receives current content. Test default and rotated device orientation with asymmetric pixels.
8. Existing speed page on/off and debug operation start/end release ownership correctly. Exercise save/load while contextual updates run using disposable VMU media; compare persistent save bytes and existing error paths as appropriate. Docked code issues no filesystem operations.
9. Quantify overhead on the same pinned program/recipe with no VMU, static VMU, animated VMU and busy transport. Name scene, tick window, devices and clock source. Model results remain modeled; Flycast proxy results remain proxy; physical Dreamcast/VMU acceptance is separate.

## 7. Standalone specimen boundary

A repository filename/source inventory found VMU filesystem/LCD support and host utilities, but no standalone VMU game source or build target. This does not prove a suitable toolchain is absent from the machine. Toolchain selection, reproducibility, VMU input mapping, packaging and installation are an explicit discovery stage before coding the detached executable.

Keep the existing loop: LIGHT, FEED and TAP set their respective observation bit at the authored payoff; repeats do not add progress; the third unique payoff commits mask and grown state together before the finite molt. New actions cancel stale visuals and unearned payoffs; they cannot undo earned growth. Grown reactions use grown frames. Reduced motion reaches the same outcome. No hunger, care failure, extra evolution stages, coupling to Leon's infection, or background timer simulation is implied.

The initial native milestone may keep this session's progress in RAM, as the preview does. Choose any durable-save record, game install name, available capacity behavior and recovery protocol separately, preserving RE4 save/config files and existing VMU content. No automatic upload/install should be added to the docked display milestone. Disconnecting the VMU stops Dreamcast LCD traffic; it does not create or install a standalone game.

## 8. Checks completed during planning

All checks below ran against a copied handoff outside the Git checkout on 2026-10-12 local time:

- All **79** entries in `MANIFEST.sha256` match the supplied source; the original handoff remains byte-identical.
- `export_assets.py`, `export_leon_assets.py`, `export_specimen_assets.py` pass source/packing/asset checks.
- `export_preview_frames.cjs` reproduces **49** complete 48×32, 192-byte reference frames. The generated golden JSON is byte-identical to the supplied one.
- `test_leon.cjs`: **12 groups**, 12 preview instances, **223 rendered frames** pass. The optional comparison against a separate earlier preview was not run.
- `test_specimen.cjs`: **10 groups**, 24 preview instances, **560 rendered frames** pass.
- Six regenerated JSON/header files differ only in newline bytes; normalized text is identical. All other 73 manifest files match byte-for-byte.

These checks validate the supplied host preview, deterministic behaviors and assets. No native renderer exists yet in this worktree. No Dreamcast build, strict replay, emulator LCD transport, physical VMU orientation or standalone execution has been validated. Existing VMU-save tests were located but not rerun because storage implementation was unchanged.

## 9. Remaining mapping work before full docked acceptance

These are concrete implementation investigations, not missing artwork:

- Verify story flags/events for the four infection stages, including loaded saves, suppression and removal. This plan does not invent a chapter-to-stage table.
- Finish the real caller-identity table and prove terminal enter/exit observation across every task loop. Existing `CODEC_READY_FIXTURE` instrumentation is test infrastructure, not a production call-state source.
- Trace the origins of Ashley assistance/capture/failure conditions and costume identities before assigning HELP/urgent severity.
- Resolve actual selected-controller-to-LCD routing rather than retaining the current first-LCD shortcut.
- Verify finite/infinite/hidden ammo policy and new header fixtures, and account for unsupported playable characters.

The rendering and transport stages can proceed while these source mappings are completed; full feature completion cannot be claimed with fixture or guessed values replacing them.

## 10. Separate conversion-hitch investigation

The earlier performance spike remains outside this VMU plan. Evidence and scripts are under `/root/probe/codex-visibility-spike-20261013/`.

The t8tW r100 house trace at source tick 1569 contains **17.728785 nominal SH-4 modeled ms** in six geometry-conversion function families: **16.043985 ms under deferred `relod()`** and **1.684800 ms under ordinary `convert()`**. Those families do not appear in the other 17 sampled ticks, every seventh tick from 1450 to 1562. A debug warp at tick 1562 and new model/texture preparation precede the spike. This supports a cold-preparation/stutter investigation; it does not establish a recurring per-frame saving, a particular missing prebuilt asset or physical console timing.
