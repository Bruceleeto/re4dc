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
this is no improvement and the certificate remains private/off.

The mapped proof subtotal also fails: exclusive initial/pre-submit/within-core
qualification and transaction self/copy work rises 3.404356->3.656688 ms per
drawn sample (+0.252331). Removing 56 qualification calls saves 0.231356 ms
inside chunk cores, but submit-side validation/copy work grows 0.355564 ms,
initial proof scope 0.090403 ms and transaction self/direct copies 0.037721 ms.
Each exclusive context is assigned once; world flush and IRQ descendants are
excluded. Shared original proof/cache placement is included, so this is not a
descriptor-only causal charge. IRQ +0.068047 ms is recorded separately.
Both arms have nine transactions, 49 chunk cores and zero packet aborts per
drawn sample; ON validates 48 submitted texture leases. No guard/stall regression
is observed, but this is not full correctness acceptance. Stop without further
cost/STRICT arms. See `certificate-on4-attribution.json` and its text report.
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
initial owner self pool is 0.6274 ms per drawn sample. The isolated guard passed the bounded cost continuation bar, but did not pass
final exact TA/framebuffer qualification. It remains private and disabled.
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


## Current Trans eligibility guard qualification

**NOT ADOPTED: final TA/framebuffer qualification requires review.** Isolated source `d865794dac7e198315c4c6dd6d2f9f582be68ed2`
queries only the existing current Trans cell eligibility before optional owner
bounds preparation. It keeps the final predicate, all active-cell math and the
existing fixed caches. It does not enable Leon or the rejected certificate/world32.

Actual-source host tests pass: 89 positive ASan/UBSan cases, three expected poisoned
negative controls, plus the two existing lifetime suites. These include absent/stale
cell state, retirement/movie restoration, fifth info, replacement/wrap/failure and
an inactive call followed by an active-cell demand. Exact host logs are retained
under `outdoor-next-20261007/eligibility-analysis/sanitizers`.

OFF ELF `d340aa25c29d508d877a6e0f80ba0e5e5e71fc21cd700f0ae593fe732094e7b2`
has byte-identical allocated sections/addresses, BIN and overlay to baseline.
ON ELF `855579280027b6bbc92e55719274153cd692b89bb7d6791283947361f1dc3188`
adds 64 text bytes; every other allocated section and both linked end symbols
remain unchanged. The owner stack frame is unchanged; the query uses eight stack
bytes. No new persistent state, larger arena or allocator policy was introduced.

| Nominal 200 MHz SH-4 model; square source2300–2307 | OFF ms | ON ms |
|---|---:|---:|
| Owner self | 0.627393 | 0.005125 |
| Owner synchronous subtree including query | 0.706746 | 0.006980 |
| Drawn sample mean | 73.180 | 72.057 |
| Skipped sample mean | 26.261 | 26.464 |
| Drawn plus skipped means | 99.441 | 98.521 |
| Equal-mode mean | 49.7205 | 49.2605 |

The **0.699766 ms net synchronous owner saving** excludes the complete interrupt/
scheduler subtrees (baseline0.011879 ms). Owner self falls0.622268 ms. Across the four
drawn samples there are28 owner calls,32 decisions and28 marked queries; candidate
early guards reject28, read no first actor-part pointer, and skip the final hidden
query. Skipped samples execute none of these functions. Actual draw parity stays
the same; commands and logged source census match. A32-tick census supports the
mode distribution; only8 full samples have direct entry proof. Whole-tick movement
is not wholly attributed to the guard. This is a small bounded modeled gain,
not physical hardware timing, ordinary rendered FPS or an outdoor 30 fps solution.

Completed target checks: actual candidate stairs and walking, each1494 checked
render frames with zero magenta pixels; checked owner replays191/1599 with zero
mismatches; two full movie loans/restores per run. The shadow stair arm checked2400
owner invocations, rejected59 and found zero disagreement; it is separate from the
real candidate cold-cache runs. All three have zero required allocation failures.
The full Bell baseline6370 records (source0–6369) is STRICT / MUST-IDENTICAL,
also with zero required allocation failures. Assets/inputs match their current
control manifests exactly except executable/overlay; no comparison exclusions
were added. H2 also passes all3237 baseline records (source0–3236), STRICT /
MUST-IDENTICAL under the accepted swapped/timing-controlled diagnostic. All
three movies are full1465/571/340; s30heap_before57504 matches its control,
backing3144608bytes/hash02c0cf88 restores at source1214, no required allocation
fails, and borrowed spans restore exactly. This H2 method remains diagnostic;
ordinary radio and final New Game also complete, as detailed below.

Ordinary radio completes all 1465/571/340 movie frames with s30 heap_before
63584, matching the current control. Arena12361728, KOS left150440 and all
three movie heap_before values981856/799808/63584 match exactly. Replay
5518..6079 restores3027520 bytes/hash5f326502 and returns to live rendering.
Its radio timing is resource evidence, not a strict pose/gameplay comparison.
Final automated New Game completes1971/2360/1175 with live r100 through
source4870 and no required allocation failures. It uses debug1 automated
title inputs and is not an ordinary clean-disc manual playthrough.

Clean diagnostic-off OFF/ON builds also pass image/resource accounting. Clean
OFF ELF12a8d7e3 has identical allocated sections/addresses, BIN and overlay to
accepted clean play ELF5ad665ec. Clean ON ELFc06cd760 adds 64 text bytes only;
all other allocated sizes/addresses and linked ends are unchanged. This clean
ON build is retained privately; no play package was made or activated.

The final deterministic stairs TA pair is **REVIEW_REQUIRED**, not accepted.
Both runs complete420 seconds without required allocation failures. Both hold
source1371/presented1370 and source2351/presented2350, with matching capture
contexts and no release during capture. All 2,988 ordinary native-frame TA
records match, including their hashes and every list word count. Movies reuse
native UI frames216/426 for1465/571 additional presentations. Comparing every
occurrence retains493 normalized hash differences in those movie-only records;
the first is frame216 occurrence2, TR465ea436 vs a540e9f6, both41 words.
No frame, movie interval, word or field is excluded from the qualification.
The private observer normalizes only the already reviewed unused tail of an
entire qualified packed32-byte polygon header; bulk movie packets remain raw.
Unused stack header words inside the bulk movie packet are a plausible cause,
but actual differing packet words were not captured, so this is unproven.

Held framebuffer pixel differences are0/8 at1371 and 5/0 at2351, maximum
channel step8. Exact source context and matching gameplay TA do not prove why
these pixels differ. There is no noise threshold, new mask or waiver. The
initial comparator wrongly assumed the native UI frame was unique; the repaired
comparator keys repeated movie presentations by frame and occurrence and saves
the complete failed comparison. No mismatch was silently deduplicated.

**Disposition:** preserve the guard at private source d865794 and all evidence;
do not integrate or enable it. Its modeled 0.699766 ms owner saving remains a
candidate result, not an accepted improvement. Production source, recipe,
accepted local play discs, public r22j and SD folder154 are unchanged. The
observer is private and is not a production patch. The outdoor 30 fps problem
remains unresolved.

The separate remaining-stage prerequisite audit assigns each of 8,092 call-tree
nodes once and accounts for 73.17987 ms per drawn tick. It establishes no further
compatible removable pool of at least 0.3 ms. World flush nested in actor submission
is excluded from actor totals; the global world-transform non-base ceiling is
only 0.2925 ms. The separate Leon zero-budget donor audit also stops without an
approved donor or rewrite. Larger changes require the existing architecture
review and source/resource evidence; these reports do not authorize them.

Evidence under `D:/Flycast-Evidence/re4-dreamcast/outdoor-next-20261007`:
`eligibility-build-on-fixed-verification.json`, `eligibility-on-cost-evidence.json`,
`square-eligibility-on-mode-proof.json`, `eligibility-analysis/cost-attribution.json`,
`gate-input-identity.json`, all nine `gate-{name}.json` reports,
`gate-{bell,h2}-{all,decisions}.json`, `radio-resource-identity.json`,
`clean-build-{off,on}-verification.json`, `gate-ta-pixels.json`,
`REMAINING_DRAW_STAGES.md` and `LEON_ZERO_BUDGET_PREREQUISITE.md`.
