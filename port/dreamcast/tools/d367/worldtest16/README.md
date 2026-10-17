# worldtest16 (2026-10-16): in-game look test of the automatic world reduction

Test only, nothing lands. Arms share one ELF (t15-build.sh rT, LP=wt: t15/int 6153f987, WORLD_VERT=1 WORLD_VERT_LEVEL=5);
only the world files differ per fixture (mkfix.sh): A current world (r101: bake13, no variant 5), B world16 as built
(r101: world32 as landed), C per-room landmark protect bins (binstat.py rule: single placement 0.3..25 m wide and
>= 1.5 m tall) + gentler ladder (--px 96 --max-error-mm 2500, world32 L1 guards); r101 C = world32 recipe + stake/pyre
bins 0x10,0x65,0xa4 (room_c.sh). price2.py = MODELLED world ms (room-budget model). Runs: q.sh / t-run.sh (Flycast trace
arm, frozen tick 400, View Full), sheet.py. Private meshes: re4-assets-private/worldtest-20261016 (SHA256SUMS).
Results: C:\Game Dev\Emulators\worldtest-20261016\WORLDTEST-INDEX.md.
