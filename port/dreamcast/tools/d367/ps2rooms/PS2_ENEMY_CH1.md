# PS2 room-code enemy rules, chapters 1-1 .. 2-1 (PS2_ENEMY_ROOMS)

Lane ps2enemy, 2026-10-14 (CH1 audit fix list 7, 11, 12). User decision: adopt the PS2 tables and room rules
fully; scale back only where a room is still too slow (no global ACT_CAP).

`PS2_ENEMY_ROOMS=<mask>` (Makefile; default 0 = no effect; needs `PS2_ENEMY_RULES=1`) ports the PS2 USA room code
(st1_0..2.rel, decoded and re-checked against the disassembly) one room per bit. Gameplay changes by design.
The knob-off play image is byte-identical to test 10 (out-t10stP: objcopy image 412198a093f8626b and all 6
overlays, from the committed tree).

| Bit | Room | PS2 rule (source) | Port |
|---|---|---|---|
| 0x01 | r100 | trap_set never sets trap 0x7A (st1_0 0x5b8c; 0x7A is id 0x2A, a trap); list rows 3/4 flags swapped | r100.cpp, stage.cpp |
| 0x02 | r101 | s21 destroys the dog 0x34 and entry 0x4F (cEmWrap setPtr+destroy) and sends 9 (no 0x3E/0x44) (st1_1 0x4ee0..0x4ff4) | r101.cpp |
| 0x04 | r104 | start 7 not 12 (F0 F1 F3 F4 F6 F7 FB); 6 patrols (em_patrol_data 0x173b0), after the dash-in mode 1 destroyed, mode 2 setFindPL; dash-in sends FC/FD only; waves (EmReset 0x9978/0x9b58, table 0x17330 + flagE 24..27) only after the dash, by area while fewer than 7, retired after two sends; area 0x15 once: EmFarDeleteNoWrap(7) (0x2de8) then F8/F9; areas 0x16/0x17 once while fewer than 8: F2/FE; area 3 retires wave 1; row 0xF1 PS2 flags/Character 1; merchant 0x5E drawn/moved only in PS2 area 0x18 after s20 (R104Main 0x8dd0) | r104.cpp, stage.cpp |
| 0x08 | r108 | bell reinforcements: fewer than 8 alive, up to 3 never-sent rows of the table for Leon's half (x > 13500: 1,2,0x2D,0x33,0x35,0x3B, else 0x47,0x4B,0x4D,0x67,0x6A) (st1_1 0xfc28) | r108.cpp |
| 0x10 | r11a | list-1 rows 0x16/0x18/0x1C/0x1D held back; 2 sent at entry by side, the rest one at a time from PS2 areas 03/04 (flags 64/65) while fewer than 9 (R11aInit st1_2 0xa458, task 0xa5d0) = the ROUTE_CH22 r11a code, now also in chapter 2-1 | r11a.cpp (guard), stage.cpp |
| 0x20 | r11b | after the shore ambush (flag 6) 0x3E/0x3F come one at a time in PS2 area 0x0B while fewer than 2 em22 (flags 3/4/5); the 8 fish (rows 0x53..0x5A) drawn/moved only in PS2 area 0x0A (R11bEmSet st1_2 0xb2b8) | r11b.cpp |

Notes
- PS2 IsGanado (SLUS 0x1bb630) also counts ids 0x40..0x4F: in the PS2 id map objects moved up by 0x10 (door 0x51,
  EmHit 0x5D), so here only 0x10..0x20 count. The first r104 run with the literal range deleted 20 objects (doors).
- With `ROUTE_CH22=1` the qualified CH22 full-record adapter writes the same list rows (list 0 rows 3/4/241,
  list 1 rows 22/24/28/29) and checks their baseline bytes, so the stage.cpp row patches stand aside; proven:
  `PS2_ENEMY_CH22: list=1 verified=58 replaced=30`, `list=0 verified=53 replaced=3`, no MISSING (arm pecW).
- r10f / r111 / r113 rules: implemented by Codex under ROUTE_CH22 / ROUTE_CH23 (chapters 2-2 / 2-3). r11c / r11d
  (Codex, default off) untouched.
- Not ported (non-enemy or not reachable on Normal): r104 door BGM table call (rsf23), the s20 BGM-task kill;
  r100 ambush row 3 gated on game_mode >= 4 (Normal = 5: no change).
- Logs (test arms): `ps2en: r10x ...` lines (OSReport) name every send, deletion, wave and fish/merchant state.

Fix list 12 (villager join): full-play segment `villager` (segments/villager-warp.txt): kills to fewer than 9 with
Leon in PS2 area 0x21; both villagers join (`ps2en: r101 villager 0x1b joins ... target 13`, `0x1a ... 14`).

Gates (twin base = test 10 release data + the knob-on test binary, evidence
C:\Flycast-Evidence\re4-dreamcast\ps2enemy-20261014): per-room warp runs (completion, no HALT / MISSING / fault,
TEX_CHECK, LEON-GC) and the full-play segments h2, villager, ch11, r107, r108, r109, lake, r11b, g3 (fp-oW2:
all PASS but h2, whose only failure is the known test 10 s30 UI texture staging line, known-issues.txt row 27).
Results and modelled cost: see the lane report (CODEX-COORDINATION / coordinator hand-off).

## Results (2026-10-14)

Twin-base warp runs (oW / oW2 = knob on 0x3f, bW = knob off), all no HALT / MISSING / fault / log overrun:

| Room | Knob on (PS2) | Knob off (GC) | Completion | TEX_CHECK / LEON-GC |
|---|---|---|---|---|
| r100 (h2) | `traps set without 0x7A`, s20, s30 340/340 | - | s30 movie | PASS / PASS |
| r101 | s21 sends 9 (alive 9); villagers 0x1B, 0x1A join (also knob off: PS2_ENEMY_RULES) | s21 11 | fight continues; bell | frag-latched 9fe00ef7 256x256 after s21 in both arms (pre-existing) / PASS |
| r104 | start 7, dash +2 (peak 9), far-delete 2 -> 7 + F8/F9, F2/FE, waves 2x max | start 12, peak 15 | r107 entered | 7506e95f fail at UI frame 191 and LEONGC f=190 (s00 QTE) in both arms (pre-existing) |
| r108 | bell: 3 + 3 east (x>13500), then 3 west | 3 once | - (full-play r108/r109 PASS) | PASS / PASS |
| r11a | 9 at entry, 0x1C/0x1D by area 03, 0x16/0x18 by area 04 | 11 at entry | r119 entered | PASS / PASS (knob off: missing 5ec91893 64x64 at UI 685) |
| r11b | fish hidden outside area 0x0A; 0x3E then 0x3F after em22 < 2 | all at the ambush | r11a entered | PASS / PASS |

r104 merchant gating (area 0x18) is compiled and matches R104Main but was not exercised: the s20 shop menu
did not close under the warp rig's scripted presses.

Modelled SH-4 cost (tools/hwmodel/hwproject.sh, MODELLED, not console; arms pehb/peho = test 10 recipe + DBG_WARP +
PC_SAMPLER_BYTES=8192, knob off/on; CD image of the test 10 release tree; windows in sampler frames; PACE fast
skip iterations alias with the trace step, so read the per-area rows, not only the total):

| View | Window:step | Off ms | On ms | Delta |
|---|---|---|---|---|
| r101 after s21 (11 vs 9 Ganados, dog gone) | 650:770:8 | 89.8 | 74.8 | -15.0 |
| r11b shore after the ambush (4 vs 2 em22) | 1000:1120:7 | 47.3 | 41.7 | -5.6 |
| r11b start pier (fish moving vs frozen) | 250:370:8 | 66.7 | 64.5 | -2.2 |
| r11a entry (11 vs 9) | 500:620:8 | 54.2 | 53.4 | -0.8 |
| r104 arrival point after s00 (12 vs 7, Leon standing) | 1800:1920:7 | 36.4 | 36.4 | 0 (logic -2.6, sampled render frames differ) |

r100 (one trap) and r108 (same 3 sends, other rows) not modelled.
