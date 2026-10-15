# Lane hwmodel-miss: console-fitted miss penalties in hwsim (2026-10-15)

Branch tools/hwmodel-miss, worktree /root/probe/hwmiss-20261015/tree. Tools only; no game code, no image change.
Evidence: C:\Flycast-Evidence\re4-dreamcast\hwmiss-20261015 (sim/, resim/, fit-*.txt, levers.txt, tools/).

## What changed
- `hwsim.c` (merged: HEAD + the hwcal `--phase` bench-part attribution + t2exact's `--dmap` / `--cmap`), new options:
  - `--dmiss-lat C`: CPU-side latency added to every D fill (first beat and line end; the bus is not held longer).
  - `--imiss-lat C`: the same for I fills.
  - `--wmiss-lat C`: extra stall on a store that misses (the nominal model only waits for the bus to accept the fill).
  - `--wb-extra C`: extra bus occupancy per dirty write-back (tried, not used by the fit).
  - `--console-fit`: the fitted set, **D 0, I 4, write miss 70** (2 parameters). Defaults are unchanged (nominal).
- `hwproject.sh`: a 5th job `console --console-fit`, reported as `--whatif console` next to low/high/nodma.
  Every existing cost arm keeps its nominal numbers; the console column is extra.
- `tools/hwmodel/miss/`: sim.sh / grid.sh / fit.py (re-sim the hwcal traces, fit error), reprice.py (re-price an
  A/B pair from proj/nominal.pcs.tsv without traces).

## Fit (hwcal traces of bench 76f40d95, CONSOLE = Part 1/2, ms per picture)
Grid: uniform D latency (d10..15) raised logic as much as render (logic fell to 0.91-0.96, render stayed 1.06-1.15);
the missing render cost is in **store misses** (skin/vertex output, OT writes), not in read misses. Weighted RMS of
log(console/model) over 4 scenes x 5 parts: nominal 0.153, d15/i6 0.076, d5/i8/w30 0.059, d3/i8/w50 0.044,
**d0/i4/w70 0.039** (chosen), d0/i5/w65 0.039, d0/i3/w80 0.042. Model stall per D miss 9-10 -> 18-22 (console 24-25),
per I miss 19 -> 21 (console 25-26).

| part | cross nom / fit | house | Del Lago | farm |
|---|---|---|---|---|
| LOGIC | 1.09 / **1.00** | 1.11 / 1.02 | 1.02 / 0.91 | 1.03 / 0.97 |
| ACTOR PREP | 1.10 / 0.96 | 1.10 / 0.93 | 1.10 / 0.94 | 1.11 / 1.00 |
| ACTOR DRAW | 1.28 / **1.04** | 1.23 / 1.01 | 1.28 / 1.04 | 1.20 / 0.98 |
| WORLD | 1.25 / **1.04** | 1.23 / 1.01 | 1.16 / 0.99 | 1.28 / 1.02 |
| OTHER | 1.25 / 1.05 | 1.11 / 0.94 | 1.13 / 0.96 | 1.14 / 0.98 |
| work per picture | 1.19 / **1.02** (99.2 vs 96.9) | 1.14 / 1.00 (76.8 vs 76.6) | 1.11 / 0.95 (59.9 vs 62.9) | 1.11 / 0.98 (141.5 vs 144.1) |

Residual per bench part (console/fit): LOGIC 0.91-1.02, APREP 0.93-1.00, ADRAW 0.98-1.04, WORLD 0.99-1.04,
OTHER 0.94-1.05. Del Lago logic (0.91) is the one outlier; it was the only scene already matched at nominal.
Not checked: the sweep deltas (sweep traces were dropped); close-Ganado x1.6 is unverified under the fit.

## Re-pricing without traces (reprice.py)
Extra = 0.79 x (4 x I misses + 70 x store misses). 0.79 = measured overlap (full re-sim / first-order: 0.78, 0.78,
0.83, 0.78). Checked against a full re-sim on uicoll u4/u5/u6 (traces kept): absolute within 0.1 ms, deltas within
~0.2 ms (u6-u4: estimate +0.87, re-sim +0.68; u5-u4: +0.07 vs -0.16). Treat deltas under 0.3 ms as noise.

## Levers, old (MODELLED nominal) vs new (MODELLED console-fit), ms per drawn tick
| lever | evidence pair | old | new |
|---|---|---|---|
| SH4ZAM memset/memcpy, cross | sh4zam-skin c0 -> msc | -0.50 | **-1.10** |
| SH4ZAM memset/memcpy, house | h0 -> msh | -0.86 | **-2.04** |
| logic waste lwx1, cross | logicwaste lwh0 -> lwx1 | -0.84 | -0.86 |
| logic waste lwh2 / lwhA / lwh1 / lwh8, cross | lwh0 -> | -0.30 / -0.21 / -0.08 / +0.05 | -0.31 / -0.22 / -0.09 / +0.05 |
| logic waste, house (all arms) | lwh0 -> | -0.02..+0.13 | +0.01..+0.14 |
| SG_SELECT_LEAN, cross | t2exact sgs0 -> sgs1 | -0.70 | -0.91 (I-cache part: still console A/B) |
| GC_CENSUS_TRIM, cross / farm | c0 -> a2 | -0.28 / -0.37 | -0.33 / -0.28 |
| B5 HOT_COLD_SPLIT, cross / farm | c0 -> b5c | -0.33 / -4.30 (farm runs not comparable) | -0.24 / -4.75 (same caveat); layout lever: console A/B only |
| Leon u70, cross | leonlod ll2-cross off -> on | -0.72 | **-0.97** |
| Leon u70, house | ll-house off -> on | -0.11 | -0.12 |
| Leon u70 cross (ll pair) / Ganado g70 (ll-off -> g2) | | 0.00 / -0.01..-0.05 | same: these pairs show no change (fixture did not engage the LOD); re-run needed |
| cross / house totals (bench 76f40d95, per picture) | hwcal | 83.1 / 67.6 | 96.9 / 76.6 (console 99.2 / 76.8) |

Pattern: store-heavy render work (memset/memcpy, skinning, Leon mesh) gains 1.3-2.4x under the fit; pure logic
levers barely move (their savings are compute, not misses).

## Trust policy under --console-fit (replaces the nominal factors when a run has the console column)
LOGIC x1.0, ACTOR PREP x1.0, ACTOR DRAW x1.0, WORLD x1.0, OTHER x1.0 (residual +-5%, Del Lago logic -9%).
Cache/layout levers stay console A/B only (the fit prices miss COUNT changes, not placement noise of +-2 ms).
Geometry deltas: expect the old x1.2 to shrink to ~x1.0; close-Ganado x1.6 not re-checked.

## Lanes that must re-run their pricing (add the console column: re-run hwproject, or reprice.py on kept proj/)
sh4zam (memset/memcpy, skin), leonlod (u70 cross, g70: fixture re-run), t2exact (SG_SELECT_LEAN, GC_CENSUS_TRIM, B5),
logicwaste (census tables: logic changes little), farhalf / worldlod / poc101 / g1parts / uicoll (render arms), the
backlog (PERF-BACKLOG-CH1-2 formulas use the old x1.25/x1.23 render factors) and ROOM-BUDGET-PROJECTION.

## Not reused
lane/ss-chain-check tools/d367/hwready/observer is a Flycast-side cost census (uncached, denormals, SQ, misses); it
counts events on the emulator and does not price them, so the fit stayed in hwsim.
