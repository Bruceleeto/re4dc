# October 7 source bug qualification

## Missing weapon beam, issue 12

The reporter and user confirm that the target dot already appears; only the beam
is missing. The source weapon target, collision result and dot are unchanged.
The source Esp19 line had no native presentation route during the coarse effect
pass. `NATIVE_LASER=1` retains its original callback and carries the final source
endpoints, maximum-length clamp, colour fade, blend, depth and fog state into
the existing deferred effect queue. One untextured 160-byte strip packet draws
the one-pixel line in source OT order. There is no new renderer/frame owner,
texture, persistent cache, heap allocation or memory reservation. The general
make default is 0; the play recipe enables it.

Private qualification is rooted at
`D:/Flycast-Evidence/re4-dreamcast/bugs-20261007`. No release or SD was changed.

* Same wall, handgun aim commands and 1,195-payload fixture: beam absent in the
  control and present in the candidate. Both 180-second Flycast runs finish
  normally. Captures are visual checks, not an exact held-frame pixel gate.
* Full common source-frame window 0..2910: 2,911 STRICT logic records and
  MUST-IDENTICAL decision records, including both aiming periods. `ACT_CAP=0`.
* r22j and accepted 512-entry clean knob-off twins match their respective
  retained baselines in all allocated section addresses, sizes and bytes, and
  in the sub-screen overlay. Debug metadata differs.
* Both 320-entry and 512-entry clean laser-on builds add 1,664 text bytes. All
  allocated section addresses, every other section size, BSS and linked `_end`
  match their own off twins. Overlay import addresses are regenerated for the
  changed main functions; overlay bytes therefore differ.
* At sampled native frames 480/600/720, control and candidate match VRAM use
  1,895,808 bytes, peak 1,952,640, texture loads/frees 268/149, model resource
  rejection 294/414/534 and wrap rejection. Model capacity/state/invalid/overflow,
  stream discarded, pipeline failures/timeouts and UI/effect drops remain zero.
  Existing ambient effect missing/capped counters are 19/5 in both arms. Those
  pre-existing warnings are not described as zero or as a beam regression.
* SH4 nominal hardware model at 200 MHz, r101 wall aim, source frames 630..633:
  direct entry proof finds one beam on each drawn frame 630/632 and none on
  skipped frames 631/633. The 32-frame census is 630..661. The synchronous
  Esp19 callback subtree is 0.0228075 ms per drawn frame, with no IRQ cost in
  that subtree. The shared drain's extra 160-byte submission is outside this
  number. This is neither physical-console timing nor a whole-frame FPS delta.

* Laser-on no-item-action inventory regression: the source-pad-clock fixture
  runs 301.14 seconds, completes three closes, and restores matching hashes
  `fb7a2a22` / `b5f45eaf` / `79a53681` for 3,134,048 / 3,134,272 / 3,134,272
  bytes. World execution resumes between those visits; the script then leaves
  a fourth inventory open with its UI still advancing. No required allocation
  failure or exception occurs. The earlier six-pulse retrace fixture completed
  only two closes and is retained without calling it a three-cycle pass.

The reviewed runtime is commit `abd0853b`. A fresh clean rebuild from that
committed source, with no private inventory diagnostic patch, produces ELF
`33c0fd02cffc36aa3a63c48f7ac752f2ccd96a7b60c76bbd885dd1e9dd0dfd83`.
All allocated section addresses/sizes/bytes, the boot binary and the sub-screen
overlay match the qualified final clean candidate exactly. Private helper/debug
metadata explains the different full ELF hash. No missing symbols are reported.

The final combined play-stack resource gate below passes with the 512-entry
collision list, beam on and Ganado source lighting off. Console beam/depth/fog
quality and the reported console faults are not certified by these checks.

## Console inventory fault, issue 8

The clean diagnostic-off build has exact r22j allocated-byte/overlay identity.
Its automatic no-item-action r101 fixture and an observational cleanup twin
each complete three inventory opens and closes. All backing bytes restore with
matching hashes; every observed cleanup phase and subsequent world execution
finishes. The fault is not reproduced, and no speculative cleanup change is
adopted. The reporter subsequently confirms that starting New Game before
loading the save prevents the inventory crash. This is a reported workaround,
not an independently reproduced cause. The failing VMU and pacing remain
pending; a follow-up also asks whether the workaround prevents issue 9.

A further cold-boot test uses normal title Load, a preserved private FILE1 r103
typewriter save and no warp. The diagnostic r22j runtime runs 361.28 seconds,
completes three no-item-action inventory closes, reaches cleanup phase 30 on
each close and continues world execution after the third. Restored sizes and
hashes are 3,129,056 / `c3d0e545`, 3,128,864 / `495c5382` and 3,129,088 /
`4a87721b`. The final framebuffer shows native gameplay. ELF identity is
`1c9ab2e203bcd6551d21654c53d14ee433a731e9b29a164bc77b6fe1cceffc9d`;
the reviewed private report is
`C:/Flycast-Evidence/re4-dreamcast/coldload-20261007/cold-inventory-qualification.json`.
This save does not reproduce the cold-load failure. These Flycast checks do not
fix or certify the console report; no runtime change follows this investigation.

## Bridge door hang, issue 9

The reporter confirms the door at the end of the pictured bridge, loading the
next area. Archive door 1 points from r108 to r109 and starts with trigger 2;
the original `SceAtRoomSet` turns it into runtime action trigger 8. The live
source dump confirms that conversion. A walking-only fixture does not activate
this door and is not transition evidence.

The corrected fixture uses ordinary A presses and movement from a synthesized
bridge start. Source door loading enters r109 generation 2, completes its room
initialization and continues for the remainder of the 300-second run without
HALT, MISSING or a hang. This is a real source door transition in Flycast, not a
forced room jump or a reproduction of the reporter's hardware/save history.
The console cause remains unresolved; the requested VMU and pacing are pending.

## Ganados use Leon's prelit lighting path

On October 7 the user reconfirmed Leon's historical baked-lighting performance
choice and asked that Ganados use the same path. The play recipe now selects
`ACTOR_GANADO_SOURCE_LIGHT=0`. Native Ganado owners use the existing constant
`SourceLighting` record already used by Leon, including registered native
appearances. This turns off the existing live-light capture override. Meshes,
textures, source poses, simulation and existing fallback/proof rules remain.
No new lightmaps, format, renderer, frame owner or model conversion is introduced.
Unqualified source fallback still keeps its original semantic checks.
The separate private live-Leon lighting probe is not adopted; both rejected
Leon performance knobs stay off. The general lighting make default was already 0.

* Beam-on live-light versus beam-on prelit trace twins: all 2,911 common source
  frames 0..2910 are STRICT; required decisions are MUST-IDENTICAL. No exclusions
  or diagnostic delays are added. Both traced runs finish normally.
* SH4 nominal model at 200 MHz, r101 wall aim, source frames 630..633, `ACT_CAP=0`,
  320-entry list, `DBG_WARP=1`, `PC_SAMPLER=1`: live-light ELF `389c401a` versus
  prelit `979fafae`. Direct entries prove the same two drawn/two skipped frames,
  seven actor draws, one world draw and one beam on each drawn frame. All 32
  census frames 630..661 are retained. The sample instruction means differ
  from their census means by -0.335% / -0.381%; untraced modes are not invented.
  Drawn cost 70.259773 -> 69.478605 ms; skipped 26.441400 -> 26.093970 ms;
  balanced sample 48.350586 -> 47.786288 ms (-0.564299, 1.17%). This small local
  whole-model gain includes compiler/cache/interrupt effects; it is not a
  lighting-subtree saving, general crowd result, physical-console FPS or 30 fps
  acceptance. Raw attribution shows native actor work moving between paths.
* Clean final 512-entry ELF shrinks text by 544 bytes and character data by 32
  versus the laser-only carry build. Compared with the accepted capacity-only
  baseline, beam plus prelit adds 1,120 text bytes and removes 32 character-data
  bytes. All allocated addresses, BSS and linked `_end=0x8c3dfe7c` are unchanged;
  there is no arena/reserve growth. The existing per-owner live-light record is
  omitted by its already supported build switch.
* Final combined 512-entry diagnostic play build, `ACT_CAP=0`, completes a
  420.91-second synthesized r100 source-event run. s03/s20/s30 finish
  1,465/571/340 frames. s30 starts with 63,584 bytes, matching the accepted
  capacity baseline. Both radio visits restore all 3,144,448 / 3,027,520 bytes
  with matching `dea20b8a` / `a7924635` hashes. World execution continues through
  source tick 9,600. No required allocation, work-backing, pipeline failure,
  timeout, HALT or MISSING is reported. This is Flycast event/resource evidence,
  not continuous normal New Game or physical-console acceptance.

The lighting draw-only host run was stopped by the capacity guard at 129.56
seconds, after the sampled aim interval, and is retained as aborted. The final
trace/resource runs and separate hardware-model arm complete normally. Earlier
beam trace and laser-only radio attempts stopped by the same storage guard are
also retained. Completed owned test discs were compressed with before/after
SHA256 identity verification; none was deleted and no SD/release was changed.
Private exact reports include `ganado-cost-evidence.json`,
`ganado-linked-resources.json`, `gate-ganado-all.json`,
`gate-ganado-decisions.json` and `ganado-final-radio-resource.json`.

## Fog and older freeze

Issue 11: r108 source fog is type 4, start -2,733, end 246,702. The native table
uses the selected far limit 25,000 and reaches full opacity over its last 20%
to hide rejection at that same distance. PS2 haze is also enabled. The user's
issue comment confirms that the reduced drawing distance is partly intentional.
The range/fog decision is preserved; the unmatched comparison does not establish
a KOS defect. A less opaque table alone would expose that distance boundary.

Issue 2 remains a separate earlier hardware/save freeze, with no supplied failing
VMU or current r22j confirmation. None of the above checks closes it.
