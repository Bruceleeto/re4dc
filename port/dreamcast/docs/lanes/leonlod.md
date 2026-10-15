# Lane leonlod (2026-10-15): LEON_LOD / GANADO_LOD

Knobs (default 0, render only): LEON_LOD (Leon mesh rungs, package dc/native/pl00/leon_lod.re4lp) and GANADO_LOD (PS2 cast
Ganado body/head levels, package dc/native/ganado/ganado_lod.re4gl). Cutscenes (Status_flg[1] 0x10000000) draw level 0.

User decisions 2026-10-15: GANADO_LOD=2 (g70) for gameplay. Leon stays at the full model (LEON_LOD=0; the level 4 / u70
choice was withdrawn; the code stays, default 0).

## Lean gates, GANADO_LOD=2 alone (Leon level 0), tree fa799f12

| Gate | Result |
| --- | --- |
| Pricing, r101 cross (hwproject, arm llDmW, run-time glod 0 vs 2, ticks 560..679, 30 traces) | nominal 64.48 -> 63.98 (-0.50); console-fit (37186a71 reprice, x1.0) 75.41 -> 74.75 (-0.65 ms) |
| Pricing, r100 house (ticks 1490..1609, 10 Ganados alive) | nominal 49.74 -> 49.63 (-0.11); console-fit 56.85 -> 56.75 (-0.10 ms) |
| Crowd stills + TEX / LEON-GC (g2-crowd) | halt 0, missing 0, fault 0, LEONGC 0, 8 stills; GANADOLOD level=2 loaded (3046 vs 4965 body/head tris) |
| Cutscene (g2-bell, trg 0 at room frame 60) | at the r101s30 event the level switches 2 -> 0 (GANADOLOD level=0 name=today) |
| KOS squeeze 48 KiB, fight (g2-kq, pair arm llDqrW) | held 49152, no OOM; min headroom 6736 vs control 9392 (= the pair's _end +2656 B) |
| _end, GANADO_LOD only (llGOqrW) | 8c4276dc vs knob-off 8c42733c: +928 B (inferred squeeze headroom ~8464 B) |
| Knob-off identity | llDsrP / llDprP objcopy -R .stack image c1ae83dd = the test 13 release image |

Trap: the poc101 bench image (llPT, DETAIL row) never ran the LOD code (no LEONLOD / GANADOLOD log lines), so the
earlier ll / ll2 / g2 / g3 bench pricing pairs are invalid. Price with a route arm whose disc carries the packs.

Evidence: C:\Flycast-Evidence\re4-dreamcast\leonlod-20261015 (hw\hwmodel-hw{c,h}-g{0,2}, g2-crowd, g2-bell, g2-kq).
