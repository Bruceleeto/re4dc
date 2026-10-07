# D367 outdoor performance: 2026-10-07

## Scope and current baseline

User report: outdoor levels, especially the village fight and dense world, are too slow.
Accepted source is `fc39b433` in the isolated integration checkout. The clean local
capacity-512 play build is unchanged. Public r22j and SD folder154 are unchanged.
Inherited changes in `/root/work/re4-dreamcast` remain untouched.

The fresh OFF runtime has ELF SHA256
`22a9c7efbc6e625f7116533e7246eae607b2c8b96e390fa97c731fbf84ad9d85`.
Performance uses current title assets/audio, ACT_CAP=0, GAME_ATLIST_512=1,
GAME_ATLIST_OVERFLOW=1, PS2_INTERIOR_ACTORS=2, both Leon knobs off, normal pacing,
DBG_WARP=1, PC_SAMPLER=1, LOGIC_TRACE=0 and GAME_DECISION_TRACE=0.
Eight consecutive source ticks2300..2307 have four directly proven drawn and
four skipped ticks, with a 32-count census2300..2331. Baseline drawn73.180,
skipped26.261 and equal-mode mean49.7205 SH-4 modeled ms. The incremental draw
cost is46.919 ms; world exclusive9.6749 and whole world subtree10.68568 ms.
These are local hardware-model costs, not console timing, rendered FPS, a complete
fight route, or 30fps acceptance. No optimization here changes the locked budget.

## Rejected candidates

### Smaller opaque scenery groups

Lossless ordered triangle/corner/material/LOD/placement correspondence was
verified for opaque groups64->32; PT/TR groups remain unchanged. The retained
package grows61,824 bytes and the frozen view transforms16.7% fewer total vertices,
but performs39.2% more bounds tests. All680 ordered LOD streams match. Runtime
world exclusive9.6749->9.4777 (-0.1972 ms) and subtree10.68568->10.40471
(-0.28097 ms) are below the0.3ms usefulness gate. Reject; original assets remain
active. A draw-phase shift prevents an overall geometry speed claim.
Evidence: `D:/Flycast-Evidence/re4-dreamcast/outdoor-next-20261007/WORLD32_RESULT.md`
and `world32-attribution.json`.

### Transaction-local repeated enemy qualification certificate

The guarded private prototype retained mutable workspace/skin/texture/stream and
packet guards. Its804-byte stack certificate adds820 bytes to the owned caller
frame; target data/bss/linked span remain unchanged. Default-off allocated ELF
sections, BIN and overlay are byte-identical to baseline.

Initial ON3 is invalid performance evidence: a closed-window readiness validator
ran after opening the submission window, aborted later chunks and stalled
presentation. Preserve the failed run; do not quote its apparent gain. A narrow
read-only scene-pin validation fix leaves original readiness/commit checks
unchanged;51 host cases pass in both modes with ASan/UBSan.

Corrected ON4 ELF is
`955600c41892c3cdeffc59dcffd59d7466a8b3dfd3bb88791ac9843ebe746627`.
Text+2432 bytes, no data/bss/linked-span growth. Valid direct entry proof gives
four drawn/four skipped samples. Drawn75.015, skipped25.014, pair100.029
versus99.441 (+0.588 ms); equal-mode mean50.0145 versus49.7205 (+0.294 ms).
Commands/logged state match but draw parity flips. Presentation remains live;
this is no improvement and the certificate remains private/off. Attribution of
local guard savings and layout/preemption costs is recorded separately.
Evidence: `cert-on4-cost-evidence.json`, `square-cert-on-mode-proof.json`,
`certificate-build-on-fixed-verification.json` under the same evidence root.

## Architecture review

ASTRA/MAX ARCHITECTURE ESCALATION REQUIRED was dispatched under
R100_NATIVE_CUTOVER_GOAL because the measured outdoor draw budget materially
contradicts the old performance model. The reviewer examines existing mechanisms
and must record the decision here/that durable goal before a new contract is
implemented. World-only elimination cannot close the full-frame gap: even removing
the whole10.68568ms world subtree leaves a modeled62.49ms drawn tick.

Astra/Max resolves one bounded implementation: query the existing current
Trans-time cell eligibility before owner Ganado interior bounds are built. Keep
the final predicate and all source/owner/crowd/resource behavior unchanged. The
current owner self pool is 0.6274 ms per drawn sample; no saving is yet measured.
Required actual-source host/cache boundary checks precede fresh OFF identity and
one isolated cost arm. Continue only with at least 0.3 ms attributable net saving,
then require active-interior/checker, current STRICT Bell/H2 and all route/resource
gates. Optional cache warming and diagnostics may differ; they are not a broad
permission to mask submissions or ignore lifecycle differences.

The precise [architecture decision and acceptance contract](D367_OUTDOOR_ARCHITECTURE_20261007.md)
is copied from the review into this durable handoff before implementation.
The 30 fps gap remains open. Larger submission/visibility work needs disjoint
attribution and a source-valid occlusion certificate; no new renderer, format,
cache, ownership, gameplay, model-building or budget change is authorized.
