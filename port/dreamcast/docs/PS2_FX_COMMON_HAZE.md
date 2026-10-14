# Chapter 1 common PS2 haze candidate

Status: default-off render-only candidate. Host qualification is complete; target compile, render-only STRICT, matched runtime stills and physical-hardware timing remain pending. `RE4DC_PS2_FX_COMMON_HAZE` defaults to zero in `esp_sub.cpp`; this patch intentionally does not wire or enable a Make knob. It requires `PS2_FX_POPULATION`, `ESP_SPRITE_FAST` and `COARSE_FX_SPRITES` (and their existing dependencies).

The shared profile table covers all 14 paired camera-haze emitters in r100–r107, r109, r10a and r10b, including the six earlier legacy rooms. r108 has no paired camera haze. The existing r118/r11c private additions and their exact legacy alpha arithmetic remain untouched. Every recipe uses its authored count, range, size/random size, velocity/random velocity, angular jitter, RGBA, alpha fade-in, indoor duration, near fade and texture. The private 19-lane LCG ordering matches the source scalar construction, but the chosen deterministic seeds do not claim real PS2 RNG identity. Current core texture pixels are not certified as PS2 pixel identity.

## Source proof and bounded state

One read-only walk over at most 2048 existing source slots identifies at most two authored groups. Room, source box/RGB, owner/kind, immutable world-particle fields, full call/core/flags identity, complete source count, uniform u16 age and uniform growth must qualify. The source objects, RNG, effects pool, scripts, EAR and status fields are never changed. Area emitters additionally require the source area state; the audited target EAR volumes are equal across platforms.

The two private states advance only by observed source age. Repeated renders and paused ages do not progress. Cold bootstrap and each catch-up are capped at 1025 source moves; an unseen source-tick gap over 63 is refused to prevent an ambiguous whole-u16-age cycle. A cold age must reproduce the exact GC growth witnesses from the certified initial increment. Changed room/pool generation, group identity or growth restart resets private state. Missing, partial, ambiguous, unsupported or unavailable input falls back to the previous source presentation.

Multi-step bootstrap/catch-up carries `MissingHistory`: the current camera and indoor state are replayed for unobserved steps. This cannot reconstruct exact PS2 trajectories through unseen camera/indoor changes. No source observation hook is added. Enabling the feature late on a mature group can intentionally fall back until a qualified restart because cold bootstrap is bounded.

The r101 indoor calculation substitutes only the certified PS2 geometry for EAR row10 after checking its live GC identity and geometry. It reads all other flagged room volumes with the existing area test, preserves the forced-indoor and Stop20 behavior and player+100 versus camera choice, and never edits the source area. Other rooms reuse the source indoor result, whose audited geometry is equivalent.

## Submission transaction

The private batch uses the same billboard, projection, source final-color multiplication, 640×480 coordinates and standard SRCALPHA/INVSRCALPHA packet path. The batch is bounded at 12 scratch quads. It validates all quads, computes visibility, checks the complete sprite cap and contiguous queue requirement, and resolves one already-resident texture. It borrows only the existing primary queue or an already-existing spill tail: no new allocation, texture upload or direct stream submission is introduced. Missing resources preserve the previous source draw; this can warm the texture for a later pass.

Only after all packets are built and atomically linked is the complete qualified source group suppressed. A successful empty batch intentionally suppresses an entirely clipped/faded private group. A failed batch submits no private packet and suppresses nothing. When source draws have already finished, the batch refuses rather than using a partial direct-stream path.

## Footprint

Compiled host layouts: one visual recipe 60 bytes; one guarded source+visual row 88 bytes (1232 bytes for 14); one state 448 bytes; one clock/binding 488 bytes (976 bytes for two). The r101 GC area certificate is 44 bytes, with a 44-byte local substitution. Small room/pool/diagnostic fields and render constants are additional. The bounded sprite scratch is 12×116 = 1392 bytes on the 32-bit target (1536 bytes on the 64-bit host); target stack/code-size measurements remain pending. This is storage accounting, not frame-time evidence.

## Host verification

Each test builds independently with `g++ -std=c++11 -O2 -ffp-contract=off -Wall -Wextra -Werror -pedantic`:

- `tools/test_ps2_fx_common_math.cpp` imports the actual runtime table/helper and compares 9,306,141 particles against expanded scalar EspSeqSet/CommonMove/Esp15 math over 66,000 changing-camera/indoor steps per profile. It covers u16 wrap, bootstrap, 1025-step catch-up, pause/repeat, reset, hard overflow, cold wrapped rejection, source tick gaps and existing legacy tuples.
- `tools/test_ps2_fx_common_haze.cpp` includes the actual adapter against synthetic source structs. It covers all 11 rooms/14 profiles, source-byte preservation, partial/mixed/ambiguous groups, group-local fallback, source age, missing batch/texture/residency, invalid camera/projection, target area exit/reentry, checked r101 shadow geometry and forced indoor/Stop20. These stubs do not verify the source ABI or runtime visuals.
- `tools/test_native_effect_haze_batch.cpp` includes the actual native batch body with bounded queue stubs. It checks full cap/storage/texture preflight, pre-existing spill, 12/10/0 accepted quads, last-quad corruption without partial emission, cull-only success, resolution scaling and source-finished rejection. Packet/GPU behavior remains a target gate.
- Existing `tools/test_ps2_fx_population.cpp` and the recipe-audit unit suite remain applicable.

Private frozen source evidence: `chapter1-weather-and-profile-proof-v2.json` and `chapter1-common-haze-offline-proof-v1.sha256` in the isolated lane evidence directory. No raw source assets or runtime captures are added by this commit.
